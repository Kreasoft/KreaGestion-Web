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
from decimal import Decimal

from core.decorators import requiere_empresa, requiere_permiso
from ventas.models import Venta, VentaDetalle, FormaPago
from clientes.models import Cliente
from .models import Caja, AperturaCaja, VentaProcesada, MovimientoCaja
from .forms import ProcesarVentaForm, AperturaCajaForm
from facturacion_electronica.services import FolioService


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
    
    print("=" * 80)
    print(f"[CAJA] Procesando ticket ID: {ticket_id}")
    print(f"  Tipo planeado: {ticket.tipo_documento_planeado}")
    print(f"  Cliente: {ticket.cliente}")
    print(f"  Total: ${ticket.total}")
    print("=" * 80)
    
    # Validar que no sea Cotización o Vale no facturable
    if ticket.tipo_documento in ['cotizacion', 'vale_no_facturable']:
        messages.error(request, 'Los tickets de tipo Cotización y Vale no son facturables.')
        return redirect('caja:apertura_list')
    
    # Verificar que el ticket no esté ya procesado
    if VentaProcesada.objects.filter(venta_preventa=ticket).exists():
        messages.warning(request, 'Este ticket ya ha sido procesado.')
        return redirect('caja:apertura_list')
    
    if ticket.facturado:
        messages.warning(request, 'Este ticket ya ha sido facturado.')
        return redirect('caja:apertura_list')
    
    # Obtener apertura activa
    apertura_activa = None
    for caja in Caja.objects.filter(empresa=request.empresa, activo=True):
        apertura = caja.get_apertura_activa()
        if apertura:
            apertura_activa = apertura
            break
    
    # Si no hay caja abierta, preparar formulario de apertura
    mostrar_modal_apertura = False
    form_apertura = None
    if not apertura_activa:
        mostrar_modal_apertura = True
        form_apertura = AperturaCajaForm(empresa=request.empresa)
    
    # Determinar tipo de documento
    tipo_doc_planeado = ticket.tipo_documento_planeado or 'boleta'
    
    # Determinar si mostrar formas de pago
    # CAJA siempre muestra formas de pago, excepto para guías
    mostrar_formas_pago = (tipo_doc_planeado != 'guia')
    
    print(f"[CAJA] mostrar_formas_pago: {mostrar_formas_pago}")
    print(f"  - tipo_documento_planeado: {tipo_doc_planeado}")
    
    # GET: Mostrar formulario
    if request.method == 'GET':
        form = ProcesarVentaForm(empresa=request.empresa, ticket=ticket, initial={'ticket_id': ticket.id})
        
        # Obtener formas de pago disponibles
        formas_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
        
        context = {
            'ticket': ticket,
            'form': form,
            'formas_pago': formas_pago,
            'mostrar_formas_pago': mostrar_formas_pago,
            'mostrar_modal_apertura': mostrar_modal_apertura,
            'form_apertura': form_apertura,
            'origen': 'caja',  # Identificador explícito
        }
        
        return render(request, 'caja/procesar_venta.html', context)
    
    # POST: Procesar venta
    print("=" * 50)
    print("[CAJA] POST RECIBIDO - Procesar Venta")
    print(f"  Ticket ID: {ticket_id}")
    print("=" * 50)
    
    # Extraer formas de pago
    formas_pago_dict = {}
    total_pagado = 0
    
    contador = 1
    while f'forma_pago_{contador}' in request.POST:
        forma_pago_id = request.POST.get(f'forma_pago_{contador}')
        monto_pago = request.POST.get(f'monto_pago_{contador}')
        
        if forma_pago_id and monto_pago:
            try:
                monto = float(monto_pago)
                if monto > 0:
                    formas_pago_dict[contador] = {
                        'forma_pago_id': forma_pago_id,
                        'monto': monto,
                        'numero_cheque': request.POST.get(f'numero_cheque_{contador}', ''),
                        'banco': request.POST.get(f'banco_{contador}', ''),
                        'fecha_cheque': request.POST.get(f'fecha_cheque_{contador}', None),
                    }
                    total_pagado += monto
            except ValueError:
                pass
        contador += 1
    
    print(f"[CAJA] Formas de pago extraídas: {len(formas_pago_dict)}")
    print(f"[CAJA] Total pagado: ${total_pagado:,.0f}")
    print(f"[CAJA] Total ticket: ${float(ticket.total):,.0f}")
    
    # Validar formas de pago (solo si no es guía)
    if mostrar_formas_pago:
        if not formas_pago_dict:
            messages.error(request, 'Debe ingresar al menos una forma de pago.')
            form = ProcesarVentaForm(empresa=request.empresa, ticket=ticket, initial={'ticket_id': ticket.id})
            formas_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
            context = {
                'ticket': ticket,
                'form': form,
                'formas_pago': formas_pago,
                'mostrar_formas_pago': mostrar_formas_pago,
                'mostrar_modal_apertura': mostrar_modal_apertura,
                'form_apertura': form_apertura,
                'origen': 'caja',
            }
            return render(request, 'caja/procesar_venta.html', context)
        
        # Validar que el total pagado coincida con el total del ticket
        total_ticket = float(ticket.total)
        if abs(total_pagado - total_ticket) > 0.01:  # Tolerancia de 1 centavo
            messages.error(request, f'El total pagado (${total_pagado:,.0f}) no coincide con el total del ticket (${total_ticket:,.0f}).')
            form = ProcesarVentaForm(empresa=request.empresa, ticket=ticket, initial={'ticket_id': ticket.id})
            formas_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
            context = {
                'ticket': ticket,
                'form': form,
                'formas_pago': formas_pago,
                'mostrar_formas_pago': mostrar_formas_pago,
                'mostrar_modal_apertura': mostrar_modal_apertura,
                'form_apertura': form_apertura,
                'origen': 'caja',
            }
            return render(request, 'caja/procesar_venta.html', context)
    
    # Generar DTE y completar procesamiento
    try:
        from facturacion_electronica.dte_service import DTEService
        from inventario.models import Inventario
        from django.urls import reverse as django_reverse
        
        with transaction.atomic():
            # 1. Generar DTE si corresponde (factura, boleta, guía)
            dte = None
            numero_venta_final = ticket.numero_venta
            
            if ticket.tipo_documento_planeado in ['factura', 'boleta', 'guia']:
                tipo_dte_map = {
                    'factura': '33',  # Factura Electrónica
                    'boleta': '39',   # Boleta Electrónica
                    'guia': '52',     # Guía de Despacho Electrónica
                }
                tipo_dte_codigo = tipo_dte_map.get(ticket.tipo_documento_planeado, '39')
                
                print(f"[CAJA] Generando DTE tipo {tipo_dte_codigo} para ticket {ticket.id}...")
                print(f"[CAJA] Documento permanece como 'ticket', DTE se genera como '{ticket.tipo_documento_planeado}'")
                
                # NO modificar ticket.tipo_documento antes de generar DTE
                # El ticket debe permanecer como 'ticket' para evitar error de unicidad
                # El DTE se genera basándose en tipo_documento_planeado
                
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
                for fp_data in formas_pago_dict.values():
                    forma_pago_obj = FormaPago.objects.get(id=fp_data['forma_pago_id'], empresa=request.empresa)
                    
                    MovimientoCaja.objects.create(
                        apertura_caja=apertura_activa,
                        venta=ticket,
                        tipo='venta',
                        forma_pago=forma_pago_obj,
                        monto=Decimal(str(fp_data['monto'])),
                        descripcion=f"{ticket.tipo_documento_planeado.title()} #{numero_venta_final}",
                        usuario=request.user
                    )
                    print(f"[CAJA] Movimiento de caja creado: {forma_pago_obj.nombre} - ${fp_data['monto']}")
                
                # Recalcular totales de la apertura
                apertura_activa.calcular_totales()
            
            # 3. Descontar stock
            from inventario.models import Stock
            
            bodega_caja = apertura_activa.caja.bodega
            for detalle in ticket.ventadetalle_set.all():
                stock = Stock.objects.filter(
                    empresa=request.empresa,
                    bodega=bodega_caja,
                    articulo=detalle.articulo
                ).first()
                
                if stock:
                    stock.cantidad -= detalle.cantidad
                    stock.save()
                    print(f"[CAJA] Stock descontado: {detalle.articulo.nombre} - {detalle.cantidad}")
                else:
                    print(f"[CAJA] ADVERTENCIA: No se encontr stock para {detalle.articulo.nombre} en bodega {bodega_caja.nombre}")
            
            # 4. Marcar ticket como facturado
            ticket.facturado = True
            ticket.save()
            
            # 5. Crear registro de venta procesada
            VentaProcesada.objects.create(
                venta_preventa=ticket,
                venta_final=ticket,
                apertura_caja=apertura_activa,
                usuario_proceso=request.user,
                monto_recibido=ticket.total,
                monto_cambio=Decimal('0.00'),
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
            
            # 6. Redirigir a impresión del documento
            messages.success(request, f'{ticket.tipo_documento_planeado.title()} #{numero_venta_final} procesada exitosamente.')
            
            if dte:
                # Redirigir a vista del DTE con impresión automática y cierre automático
                from django.urls import reverse as django_reverse
                dte_url = django_reverse('facturacion_electronica:ver_factura_electronica', kwargs={'dte_id': dte.pk})
                
                # Determinar URL de retorno: si el ticket tiene estacion_trabajo, volver al POS
                if ticket.estacion_trabajo:
                    return_url = django_reverse('ventas:pos_view')
                else:
                    return_url = django_reverse('caja:procesar_venta_buscar')
                
                # auto=1: imprime automáticamente
                # autoclose=1: cierra y vuelve después de imprimir
                # autoclose_delay=1000: espera 1 segundo después de imprimir antes de volver
                from urllib.parse import quote
                return redirect(f"{dte_url}?auto=1&autoclose=1&autoclose_delay=1000&return_url={quote(return_url, safe='')}")
            else:
                # Si no hay DTE, imprimir como vale y volver a búsqueda
                messages.warning(request, 'Documento procesado pero no se generó DTE.')
                return redirect('caja:procesar_venta_buscar')
    
    except Exception as e:
        print(f"[CAJA] ERROR: {str(e)}")
        messages.error(request, f'Error al procesar el ticket: {str(e)}')
        form = ProcesarVentaForm(empresa=request.empresa, ticket=ticket, initial={'ticket_id': ticket.id})
        formas_pago = FormaPago.objects.filter(empresa=request.empresa, activo=True).order_by('nombre')
        context = {
            'ticket': ticket,
            'form': form,
            'formas_pago': formas_pago,
            'mostrar_formas_pago': mostrar_formas_pago,
            'mostrar_modal_apertura': mostrar_modal_apertura,
            'form_apertura': form_apertura,
            'origen': 'caja',
        }
        return render(request, 'caja/procesar_venta.html', context)


