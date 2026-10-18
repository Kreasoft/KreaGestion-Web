"""
Vista dedicada para procesar ventas desde el MÓDULO DE CAJA
Separada del POS para mayor claridad y mantenibilidad
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django.utils import timezone
from decimal import Decimal, InvalidOperation

from core.decorators import requiere_empresa, requiere_permiso
from core.fechas import (
    caja_es_del_dia_actual,
    fecha_apertura_caja,
    fecha_documento_caja,
    mensaje_caja_desfasada,
    resolver_fecha_vencimiento,
)
from ventas.models import Venta, VentaDetalle, FormaPago
from clientes.models import Cliente
from .models import Caja, AperturaCaja, VentaProcesada, MovimientoCaja
from .forms import ProcesarVentaForm, AperturaCajaForm
from facturacion_electronica.services import FolioService


def print(*args, **kwargs):
    """Evita que mensajes de depuracion rompan vistas si stdout falla en Windows."""
    return None


def _es_efectivo(forma_pago):
    codigo = (getattr(forma_pago, 'codigo', '') or '').upper()
    nombre = (getattr(forma_pago, 'nombre', '') or '').lower()
    return codigo in ('EF', 'EFE', 'EFECTIVO') or 'efectivo' in nombre


def _monto_decimal(raw):
    try:
        texto = str(raw or '').replace(',', '.').strip()
        if not texto:
            return Decimal('0')
        return Decimal(texto)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def _listas_despacho_caja(empresa):
    """Vendedores, móviles y choferes activos para el formulario de cobro."""
    from ventas.models import Vendedor

    vendedores = Vendedor.objects.filter(empresa=empresa, activo=True).order_by('nombre')
    vehiculos = []
    choferes = []
    if getattr(empresa, 'usa_sistema_despacho', False):
        try:
            from pedidos.models_transporte import Vehiculo, Chofer
            vehiculos = Vehiculo.objects.filter(empresa=empresa, activo=True).order_by('patente')
            choferes = Chofer.objects.filter(empresa=empresa, activo=True).order_by('nombre')
        except Exception:
            vehiculos = []
            choferes = []
    return vendedores, vehiculos, choferes


def _aplicar_despacho_caja(ticket, empresa, post_data):
    """Asigna vendedor, móvil y chofer del formulario al ticket antes de generar el DTE."""
    campos = []
    vendedor_id = (post_data.get('vendedor_id') or '').strip()
    if vendedor_id:
        from ventas.models import Vendedor
        vendedor = Vendedor.objects.filter(pk=vendedor_id, empresa=empresa, activo=True).first()
        if vendedor:
            ticket.vendedor = vendedor
            campos.append('vendedor')

    if getattr(empresa, 'usa_sistema_despacho', False):
        from pedidos.models_transporte import Vehiculo, Chofer
        vehiculo_id = (post_data.get('vehiculo_id') or '').strip()
        chofer_id = (post_data.get('chofer_id') or '').strip()
        if vehiculo_id:
            vehiculo = Vehiculo.objects.filter(pk=vehiculo_id, empresa=empresa, activo=True).first()
            if vehiculo:
                ticket.vehiculo = vehiculo
                campos.append('vehiculo')
        if chofer_id:
            chofer = Chofer.objects.filter(pk=chofer_id, empresa=empresa, activo=True).first()
            if chofer:
                ticket.chofer = chofer
                campos.append('chofer')
    return campos


@login_required
@requiere_empresa
@requiere_permiso('caja.add_ventaprocesada', mensaje='No tienes permisos para procesar ventas. Contacta al administrador.', redirect_url='caja:apertura_list')
def procesar_venta_caja(request, ticket_id):
    """
    Procesar un ticket desde el MÓDULO DE CAJA
    
    IMPORTANTE: Esta vista es EXCLUSIVA para el módulo de CAJA.
    El POS usa su propia vista: ventas.views_pos_procesar.procesar_venta_pos
    
    FLUJO:
    1. Cajero busca ticket pendiente
    2. Muestra formulario con formas de pago (SIEMPRE, excepto guías)
    3. Genera DTE (Factura/Boleta según tipo_documento_planeado)
    4. Imprime documento
    5. Vuelve a lista de tickets en caja
    """
    empresa = request.empresa
    ticket = get_object_or_404(Venta, pk=ticket_id, empresa=empresa, tipo_documento='ticket')
    
    # Determinar URL de retorno (de donde vino el usuario)
    next_url = request.GET.get('next') or request.POST.get('next') or request.session.get('caja_retorno_listado') or reverse('caja:procesar_venta_buscar')
    # Seguridad: solo permitir URLs relativas (que comiencen con /)
    if not next_url.startswith('/') or next_url.startswith('//'):
        next_url = reverse('caja:procesar_venta_buscar')
    request.session['caja_retorno_listado'] = next_url
    
    print("=" * 80)
    print(f"[CAJA] Procesando ticket ID: {ticket_id}")
    print(f"  Tipo planeado: {ticket.tipo_documento_planeado}")
    print(f"  Cliente: {ticket.cliente}")
    print(f"  Total: ${ticket.total}")
    print(f"  next_url: {next_url}")
    print("=" * 80)
    
    # Validar que no sea Cotización o Vale no facturable
    if ticket.tipo_documento in ['cotizacion', 'vale_no_facturable']:
        messages.error(request, 'Los tickets de tipo Cotización y Vale no son facturables.')
        return redirect(next_url)
    
    # Verificar que el ticket no esté ya procesado
    if VentaProcesada.objects.filter(venta_preventa=ticket).exists():
        messages.warning(request, 'Este ticket ya ha sido procesado.')
        return redirect(next_url)
    
    if ticket.facturado:
        messages.warning(request, 'Este ticket ya ha sido facturado.')
        return redirect(next_url)
    
    from empresas.middleware import resolver_sucursal_operativa
    from .views import _apertura_activa_empresa
    sucursal_caja = resolver_sucursal_operativa(request)
    apertura_activa = _apertura_activa_empresa(request, sucursal_caja)
    
    # Si no hay caja abierta, preparar formulario de apertura
    mostrar_modal_apertura = False
    form_apertura = None
    if not apertura_activa:
        mostrar_modal_apertura = True
        form_apertura = AperturaCajaForm(empresa=request.empresa, sucursal=sucursal_caja)

    caja_desfasada = bool(apertura_activa and not caja_es_del_dia_actual(apertura_activa))
    fecha_caja_abierta = fecha_apertura_caja(apertura_activa) if apertura_activa else None
    hoy_fecha = timezone.localdate()
    
    # Determinar tipo de documento
    tipo_doc_planeado = ticket.tipo_documento_planeado or 'boleta'
    
    # Determinar si mostrar formas de pago
    # CAJA siempre muestra formas de pago, excepto para guías
    mostrar_formas_pago = (tipo_doc_planeado != 'guia')
    
    print(f"[CAJA] mostrar_formas_pago: {mostrar_formas_pago}")
    print(f"  - tipo_documento_planeado: {tipo_doc_planeado}")

    fecha_documento = fecha_documento_caja(apertura_activa)
    plazo_pago_cliente = int(getattr(ticket.cliente, 'plazo_pago', 0) or 0) if ticket.cliente_id else 0
    fecha_vencimiento_default = resolver_fecha_vencimiento(fecha_documento, plazo_pago_cliente)

    def _contexto_formulario(form=None, fecha_vencimiento=None, **extra):
        from gestioncloud.views import bodegas_para_rebaja
        vendedores, vehiculos, choferes = _listas_despacho_caja(request.empresa)
        bodegas_rebaja, bodega_rebaja = bodegas_para_rebaja(
            request,
            sucursal=sucursal_caja,
            caja=getattr(apertura_activa, 'caja', None),
            bodega_id=request.POST.get('bodega_id') if request.method == 'POST' else None,
        )
        ctx = {
            'ticket': ticket,
            'empresa': request.empresa,
            'apertura_activa': apertura_activa,
            'caja_desfasada': caja_desfasada,
            'fecha_caja_abierta': fecha_caja_abierta,
            'hoy_fecha': hoy_fecha,
            'mensaje_caja_desfasada_texto': mensaje_caja_desfasada(apertura_activa) if caja_desfasada else '',
            'form': form or ProcesarVentaForm(empresa=request.empresa, ticket=ticket, initial={'ticket_id': ticket.id}),
            'formas_pago': FormaPago.objects.filter(empresa=request.empresa, activo=True).order_by('nombre'),
            'mostrar_formas_pago': mostrar_formas_pago,
            'mostrar_modal_apertura': mostrar_modal_apertura,
            'form_apertura': form_apertura,
            'origen': 'caja',
            'next_url': next_url,
            'fecha_documento': fecha_documento,
            'plazo_pago_cliente': plazo_pago_cliente,
            'fecha_vencimiento': fecha_vencimiento or fecha_vencimiento_default,
            'vendedores': vendedores,
            'vehiculos': vehiculos,
            'choferes': choferes,
            'bodegas': bodegas_rebaja,
            'bodega_rebaja': bodega_rebaja,
        }
        ctx.update(extra)
        return ctx
    
    # GET: Mostrar formulario
    if request.method == 'GET':
        if caja_desfasada:
            messages.warning(request, mensaje_caja_desfasada(apertura_activa))
        return render(request, 'caja/procesar_venta.html', _contexto_formulario(es_pos_vale=False))
    
    # POST: Procesar venta
    print("=" * 50)
    print("[CAJA] POST RECIBIDO - Procesar Venta")
    print(f"  Ticket ID: {ticket_id}")
    print("=" * 50)

    if not apertura_activa:
        messages.error(request, 'No hay una caja abierta en esta sucursal. Debe abrir una caja con fecha de hoy antes de procesar o imprimir.')
        return render(request, 'caja/procesar_venta.html', _contexto_formulario(
            fecha_vencimiento=resolver_fecha_vencimiento(
                fecha_documento, plazo_pago_cliente, request.POST.get('fecha_vencimiento')
            )
        ))

    if caja_desfasada:
        messages.error(request, mensaje_caja_desfasada(apertura_activa))
        return render(request, 'caja/procesar_venta.html', _contexto_formulario(
            fecha_vencimiento=resolver_fecha_vencimiento(
                fecha_documento, plazo_pago_cliente, request.POST.get('fecha_vencimiento')
            )
        ))
    
    # Extraer formas de pago
    formas_pago_dict = {}
    total_pagado = Decimal('0')
    
    contador = 1
    while f'forma_pago_{contador}' in request.POST:
        forma_pago_id = request.POST.get(f'forma_pago_{contador}')
        monto_pago = request.POST.get(f'monto_pago_{contador}')
        
        if forma_pago_id and monto_pago:
            monto = _monto_decimal(monto_pago)
            if monto > 0:
                formas_pago_dict[contador] = {
                    'forma_pago_id': forma_pago_id,
                    'monto': monto,
                    'numero_cheque': request.POST.get(f'numero_cheque_{contador}', ''),
                    'banco': request.POST.get(f'banco_{contador}', ''),
                    'fecha_cheque': request.POST.get(f'fecha_cheque_{contador}', None),
                }
                total_pagado += monto
        contador += 1
    
    print(f"[CAJA] Formas de pago extraídas: {len(formas_pago_dict)}")
    print(f"[CAJA] Total pagado: ${total_pagado:,.0f}")
    print(f"[CAJA] Total ticket: ${float(ticket.total):,.0f}")
    
    # Validar formas de pago (solo si no es guía)
    if mostrar_formas_pago:
        if not formas_pago_dict:
            messages.error(request, 'Debe ingresar al menos una forma de pago.')
            return render(request, 'caja/procesar_venta.html', _contexto_formulario(
                fecha_vencimiento=resolver_fecha_vencimiento(
                    fecha_documento, plazo_pago_cliente, request.POST.get('fecha_vencimiento')
                )
            ))
        
        total_ticket = Decimal(str(ticket.total or 0))
        if total_pagado + Decimal('0.01') < total_ticket:
            falta = total_ticket - total_pagado
            messages.error(
                request,
                f'El monto pagado (${total_pagado:,.0f}) es menor al total del ticket (${total_ticket:,.0f}). Faltan ${falta:,.0f}.'
            )
            return render(request, 'caja/procesar_venta.html', _contexto_formulario(
                fecha_vencimiento=resolver_fecha_vencimiento(
                    fecha_documento, plazo_pago_cliente, request.POST.get('fecha_vencimiento')
                )
            ))

        no_efectivo = Decimal('0')
        for fp_data in formas_pago_dict.values():
            forma_chk = FormaPago.objects.filter(pk=fp_data['forma_pago_id'], empresa=request.empresa).first()
            if not forma_chk:
                continue
            if ticket.tipo_documento_planeado != 'factura' and forma_chk.es_cuenta_corriente:
                messages.error(request, 'El crédito / cuenta corriente solo se permite en facturas. La boleta se cobra al contado.')
                return render(request, 'caja/procesar_venta.html', _contexto_formulario(
                    fecha_vencimiento=resolver_fecha_vencimiento(
                        fecha_documento, plazo_pago_cliente, request.POST.get('fecha_vencimiento')
                    )
                ))
            if not _es_efectivo(forma_chk):
                no_efectivo += fp_data['monto']

        if no_efectivo > total_ticket + Decimal('0.01'):
            messages.error(request, 'Los pagos que no son efectivo no pueden superar el total del ticket.')
            return render(request, 'caja/procesar_venta.html', _contexto_formulario(
                fecha_vencimiento=resolver_fecha_vencimiento(
                    fecha_documento, plazo_pago_cliente, request.POST.get('fecha_vencimiento')
                )
            ))

        monto_cambio = max(Decimal('0.00'), total_pagado - total_ticket)
    else:
        monto_cambio = Decimal('0.00')
    
    # Generar DTE y completar procesamiento
    try:
        from facturacion_electronica.dte_service import DTEService
        from inventario.models import Inventario
        from django.urls import reverse as django_reverse
        
        with transaction.atomic():
            # 1. Generar DTE si corresponde (factura, boleta, guía)
            dte = None
            numero_venta_final = ticket.numero_venta

            ticket.fecha = fecha_documento
            if ticket.tipo_documento_planeado in ['factura', 'guia']:
                ticket.fecha_vencimiento = resolver_fecha_vencimiento(
                    fecha_documento, plazo_pago_cliente, request.POST.get('fecha_vencimiento')
                )
            else:
                ticket.fecha_vencimiento = None
            campos_ticket = ['fecha', 'fecha_vencimiento']
            campos_ticket.extend(_aplicar_despacho_caja(ticket, request.empresa, request.POST))
            ticket.save(update_fields=campos_ticket)
            
            if ticket.tipo_documento_planeado in ['factura', 'boleta', 'guia']:
                tipo_dte_map = {
                    'factura': '33',  # Factura Electrónica
                    'boleta': '39',   # Boleta Electrónica
                    'guia': '52',     # Guía de Despacho Electrónica
                }
                tipo_dte_codigo = tipo_dte_map.get(ticket.tipo_documento_planeado, '39')
                
                print(f"[CAJA] Generando DTE tipo {tipo_dte_codigo} para ticket {ticket.id}...")
                print(f"[CAJA] Documento permanece como 'ticket', DTE se genera como '{ticket.tipo_documento_planeado}'")
                
                # Generar DTE
                dte_service = DTEService(request.empresa)
                dte = dte_service.generar_dte_desde_venta(ticket, tipo_dte_codigo)
                
                if dte:
                    # El folio del DTE es el número final del documento
                    # NO modificar ticket.numero_venta para evitar error de unicidad
                    # El ticket mantiene su número original, el DTE tiene su propio folio
                    print(f"[CAJA] DTE generado - Folio {dte.folio}")
                else:
                    print(f"[CAJA] ADVERTENCIA: No se pudo generar DTE")
            
            # 2. Crear movimientos de caja (solo si NO es guía)
            if ticket.tipo_documento_planeado != 'guia' and formas_pago_dict:
                if not apertura_activa:
                    raise ValueError('No hay caja abierta para registrar el cobro.')
                monto_credito = Decimal('0.00')
                forma_pago_credito = None
                for fp_data in formas_pago_dict.values():
                    forma_pago_obj = FormaPago.objects.get(id=fp_data['forma_pago_id'], empresa=request.empresa)
                    monto_fp = Decimal(str(fp_data['monto']))
                    
                    # USAR FECHA DE APERTURA PARA EL MOVIMIENTO (ESTRICTO)
                    MovimientoCaja.objects.create(
                        apertura_caja=apertura_activa,
                        venta=ticket,
                        tipo='venta',
                        forma_pago=forma_pago_obj,
                        monto=monto_fp,
                        descripcion=f"{ticket.tipo_documento_planeado.title()} #{numero_venta_final}",
                        usuario=request.user,
                        fecha=timezone.now()
                    )

                    # Guardar la primera forma de pago en el ticket (para trazabilidad y DTE)
                    if not ticket.forma_pago:
                        ticket.forma_pago = forma_pago_obj
                        ticket.save()
                        print(f"[CAJA] Forma de pago principal asignada al ticket: {forma_pago_obj.nombre}")

                    if forma_pago_obj.es_cuenta_corriente:
                        monto_credito += monto_fp
                        if forma_pago_credito is None:
                            forma_pago_credito = forma_pago_obj

                    print(f"[CAJA] Movimiento de caja creado: {forma_pago_obj.nombre} - ${fp_data['monto']}")
                
                if forma_pago_credito and monto_credito > 0:
                    from tesoreria.services import sincronizar_venta_credito_en_tesoreria

                    ticket.forma_pago = forma_pago_credito
                    ticket.monto_pagado = ticket.total - monto_credito
                    ticket.saldo_pendiente = monto_credito
                    ticket.save(update_fields=['forma_pago', 'monto_pagado', 'saldo_pendiente'])

                    sincronizar_venta_credito_en_tesoreria(
                        ticket,
                        dte=dte,
                        usuario=request.user,
                        descripcion=f"Documento a crédito {ticket.tipo_documento_planeado} {numero_venta_final}",
                    )

                # Recalcular totales de la apertura
                apertura_activa.calcular_totales()
            
            # 3. Rebajar stock solo al facturar el documento
            from django.db.models.signals import post_save
            from gestioncloud.views import bodegas_para_rebaja
            from ventas.signals import actualizar_stock_venta
            from .views import descontar_stock_venta_completo

            _bodegas, bodega_caja = bodegas_para_rebaja(
                request,
                sucursal=sucursal_caja,
                caja=getattr(apertura_activa, 'caja', None),
                bodega_id=request.POST.get('bodega_id'),
            )
            if bodega_caja:
                request.session['dashboard_bodega_id'] = bodega_caja.id
                request.session.modified = True
                descontar_stock_venta_completo(ticket, bodega_caja)

            # 4. Marcar ticket como facturado (sin volver a rebajar por el signal)
            post_save.disconnect(actualizar_stock_venta, sender=Venta)
            try:
                ticket.facturado = True
                ticket.save()
            finally:
                post_save.connect(actualizar_stock_venta, sender=Venta)
            
            # 5. Crear registro de venta procesada
            VentaProcesada.objects.create(
                venta_preventa=ticket,
                venta_final=ticket,
                apertura_caja=apertura_activa,
                usuario_proceso=request.user,
                monto_recibido=total_pagado if mostrar_formas_pago else ticket.total,
                monto_cambio=monto_cambio,
                stock_descontado=True,
                dte_generado=dte
            )
            
            print("=" * 80)
            print("[CAJA] VENTA PROCESADA EXITOSAMENTE")
            print(f"   Número: {numero_venta_final}")
            print(f"   Tipo: {ticket.tipo_documento_planeado}")
            print(f"   Total: ${ticket.total}")
            print(f"   DTE: {dte.id if dte else 'No generado'}")
            print("=" * 80)

        encolado = False
        try:
            from caja.impresion_utils import encolar_impresion_agente
            encolado = bool(encolar_impresion_agente(
                request.empresa,
                ticket,
                estacion=ticket.estacion_trabajo,
                dte=dte,
                tipo_documento='dte' if dte else 'vale',
            ))
        except Exception:
            import traceback
            traceback.print_exc()
            encolado = False

        if encolado:
            messages.success(
                request,
                f'{ticket.tipo_documento_planeado.title()} #{numero_venta_final} procesada e impresa.'
            )
        else:
            messages.warning(
                request,
                f'{ticket.tipo_documento_planeado.title()} #{numero_venta_final} procesada, pero no se pudo encolar la impresión.'
            )
        request.session.pop('caja_retorno_listado', None)
        return redirect(next_url)
    
    except Exception as e:
        print(f"[CAJA] ERROR: {str(e)}")
        messages.error(request, f'Error al procesar el ticket: {str(e)}')
        return render(request, 'caja/procesar_venta.html', _contexto_formulario(
            fecha_vencimiento=resolver_fecha_vencimiento(
                fecha_documento, plazo_pago_cliente, request.POST.get('fecha_vencimiento')
            )
        ))


