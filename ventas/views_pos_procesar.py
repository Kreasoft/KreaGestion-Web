"""
Vista dedicada para procesar ventas desde el POS
Separada del módulo de caja para mayor claridad y mantenibilidad

ARQUITECTURA:
- procesar_venta_pos(): Modo VALE (cierre_directo=False) - Solo genera vale
- procesar_venta_pos_directo(): Modo FACTURA DIRECTA (cierre_directo=True) - Emite DTE
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from core.decorators import requiere_empresa
from .models import Venta, VentaDetalle, EstacionTrabajo, FormaPago
from caja.models import VentaProcesada


@login_required
@requiere_empresa
def procesar_venta_pos(request, ticket_id):
    """
    Procesa una venta desde el POS - MODO VALE (cierre_directo=False)
    
    FLUJO:
    1. Genera vale SIN pedir forma de pago
    2. Marca ticket como facturado (para evitar duplicados)
    3. Redirige a impresión de vale
    4. Vuelve al POS
    
    Este vale luego se factura en caja con formas de pago
    """
    empresa = request.empresa
    ticket = get_object_or_404(Venta, pk=ticket_id, empresa=empresa)
    
    print("=" * 80)
    print(f"[POS VALE] Ticket ID: {ticket_id}")
    print(f"  Tipo: {ticket.tipo_documento}")
    print(f"  Tipo planeado: {ticket.tipo_documento_planeado}")
    print("=" * 80)
    
    # POS SIN CIERRE DIRECTO: Solo generar vale
    print("[POS VALE] Generando vale facturable...")
    
    # Validar que sea un ticket
    if ticket.tipo_documento != 'ticket':
        print(f"[POS VALE] ADVERTENCIA: ticket tipo '{ticket.tipo_documento}' procesado como ticket/vale")
    
    # NO marcar como facturado - el vale debe procesarse en caja
    # El campo facturado se marca en True cuando se procesa en caja y se genera el DTE
    print("[POS VALE] Vale listo para facturar en caja (facturado=False)")
    
    # Redirigir a impresión de vale
    from urllib.parse import quote
    pos_url = reverse('ventas:pos_view')
    vale_url = reverse('ventas:vale_html', args=[ticket.pk])
    # Codificar return_url para que se pase correctamente
    vale_url += f"?auto=1&autoclose=1&autoclose_delay=2000&return_url={quote(pos_url, safe='')}"
    
    print(f"[POS VALE] Vale generado - Redirigiendo a impresión: {vale_url}")
    return redirect(vale_url)


@login_required
@requiere_empresa
def procesar_venta_pos_directo(request, ticket_id):
    """
    Procesa una venta desde el POS - MODO FACTURA DIRECTA (cierre_directo=True)
    """
    empresa = request.empresa
    ticket = get_object_or_404(Venta, pk=ticket_id, empresa=empresa)
    
    print("=" * 80)
    print(f"[POS DIRECTO] Ticket ID: {ticket_id}")
    print(f"  Tipo: {ticket.tipo_documento}")
    print(f"  Tipo planeado: {ticket.tipo_documento_planeado}")
    print(f"  Tipo despacho (DB): {ticket.tipo_despacho}")
    print("=" * 80)
    
    # GET: Mostrar formulario con formas de pago
    if request.method == 'GET':
        print("[POS DIRECTO] GET - Mostrando formulario con formas de pago")
        
        # Obtener formas de pago disponibles
        formas_pago = FormaPago.objects.filter(empresa=empresa, activo=True).order_by('nombre')
        
        context = {
            'ticket': ticket,
            'formas_pago': formas_pago,
            'origen': 'pos_directo',
        }
        
        return render(request, 'ventas/pos_procesar_directo.html', context)
    
    # POST: Procesar venta con formas de pago
    print("=" * 50)
    print("[POS DIRECTO] POST - Procesando venta directa")
    print(f"  Ticket ID: {ticket_id}")
    print("=" * 50)
    
    # Extraer formas de pago (solo si NO es guía)
    formas_pago_dict = {}
    total_pagado = 0
    
    if ticket.tipo_documento_planeado != 'guia':
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
                        }
                        total_pagado += monto
                except ValueError:
                    pass
            contador += 1
        
        print(f"[POS DIRECTO] Formas de pago extraídas: {len(formas_pago_dict)}")
        print(f"[POS DIRECTO] Total pagado: ${total_pagado:,.0f}")
        print(f"[POS DIRECTO] Total ticket: ${float(ticket.total):,.0f}")
        
        # Validar formas de pago
        if not formas_pago_dict:
            messages.error(request, 'Debe ingresar al menos una forma de pago.')
            return redirect('ventas:procesar_venta_pos_directo', ticket_id=ticket_id)
        
        # Validar que el total pagado coincida con el total del ticket
        total_ticket = float(ticket.total)
        if abs(total_pagado - total_ticket) > 0.01:  # Tolerancia de 1 centavo
            messages.error(request, f'El total pagado (${total_pagado:,.0f}) no coincide con el total del ticket (${total_ticket:,.0f}).')
            return redirect('ventas:procesar_venta_pos_directo', ticket_id=ticket_id)
    
    # Validar y actualizar tipo_despacho si es guía
    if ticket.tipo_documento_planeado == 'guia':
        tipo_despacho = request.POST.get('tipo_despacho')
        print(f"DEBUG: [POS DIRECTO] Procesando Guía. ID: {ticket.id}")
        print(f"DEBUG: [POS DIRECTO] POST tipo_despacho: '{tipo_despacho}'")
        print(f"DEBUG: [POS DIRECTO] DB tipo_despacho PREVIO: '{ticket.tipo_despacho}'")
        
        if tipo_despacho:
            # FORZAR ACTUALIZACIÓN DIRECTA A BASE DE DATOS
            rows = Venta.objects.filter(pk=ticket.id).update(tipo_despacho=tipo_despacho)
            ticket.refresh_from_db() # Recargar objeto
            print(f"DEBUG: [POS DIRECTO] Update ejecutado. Filas afectadas: {rows}")
            print(f"DEBUG: [POS DIRECTO] DB tipo_despacho ACTUAL: '{ticket.tipo_despacho}'")
        
        # Validar que exista un tipo de despacho asignado
        if not ticket.tipo_despacho:
            print("DEBUG: [POS DIRECTO] ERROR: No hay tipo de despacho seleccionado")
            messages.error(request, 'Debe seleccionar un Motivo de Traslado para la Guía de Despacho.')
            return redirect('ventas:procesar_venta_pos_directo', ticket_id=ticket_id)

    # Generar DTE y completar procesamiento
    try:
        from caja.models import Caja, AperturaCaja, MovimientoCaja
        from facturacion_electronica.dte_service import DTEService
        from inventario.models import Inventario
        
        with transaction.atomic():
            # Recargar ticket dentro de la transacción para asegurar frescura
            ticket.refresh_from_db()
            print(f"DEBUG: [POS DIRECTO] Ticket dentro de transacción. Tipo Despacho: '{ticket.tipo_despacho}'")
            
            # 1. Buscar apertura activa de caja
            apertura_activa = None
            for caja in Caja.objects.filter(empresa=empresa, activo=True):
                apertura = caja.get_apertura_activa()
                if apertura:
                    apertura_activa = apertura
                    break
            
            if not apertura_activa:
                messages.error(request, 'No hay caja abierta. Debe abrir una caja antes de procesar ventas.')
                return redirect('ventas:procesar_venta_pos_directo', ticket_id=ticket_id)
            
            print(f"[POS DIRECTO] Apertura de caja encontrada: {apertura_activa.id}")
            
            # 2. Generar DTE si corresponde (factura, boleta, guía)
            dte = None
            numero_venta_final = ticket.numero_venta
            
            if ticket.tipo_documento_planeado in ['factura', 'boleta', 'guia']:
                tipo_dte_map = {
                    'factura': '33',  # Factura Electrónica
                    'boleta': '39',   # Boleta Electrónica
                    'guia': '52',     # Guía de Despacho Electrónica
                }
                tipo_dte_codigo = tipo_dte_map.get(ticket.tipo_documento_planeado, '39')
                
                print(f"[POS DIRECTO] Generando DTE tipo {tipo_dte_codigo} para ticket {ticket.id}...")
                print(f"[POS DIRECTO] El documento original es un 'ticket', DTE se genera como '{ticket.tipo_documento_planeado}'")
                
                # El ticket debe permanecer como 'ticket' (o el tipo que tenga como preventa)
                # El DTE se genera basándose en tipo_documento_planeado
                
                # Generar DTE
                dte_service = DTEService(empresa)
                dte = dte_service.generar_dte_desde_venta(ticket, tipo_dte_codigo)
                
                if dte:
                    # El folio del DTE es el número final del documento
                    numero_venta_final = f"{dte.folio:06d}"
                    # NO modificar ticket.numero_venta para evitar error de unicidad
                    # El ticket mantiene su número original, el DTE tiene su propio folio
                    print(f"[POS DIRECTO] DTE generado - Folio {dte.folio}")
                else:
                    print(f"[POS DIRECTO] ADVERTENCIA: No se pudo generar DTE")
            
            # 3. Crear movimientos de caja (solo si NO es guía)
            if ticket.tipo_documento_planeado != 'guia' and formas_pago_dict:
                for fp_data in formas_pago_dict.values():
                    forma_pago = FormaPago.objects.get(id=fp_data['forma_pago_id'], empresa=empresa)
                    
                    MovimientoCaja.objects.create(
                        apertura_caja=apertura_activa,
                        venta=ticket,
                        tipo='venta',
                        forma_pago=forma_pago,
                        monto=Decimal(str(fp_data['monto'])),
                        descripcion=f"{ticket.tipo_documento_planeado.title()} #{numero_venta_final}",
                        usuario=request.user
                    )
                    
                    # Guardar la primera forma de pago en el ticket (para trazabilidad y DTE)
                    if not ticket.forma_pago:
                        ticket.forma_pago = forma_pago
                        ticket.save()
                        print(f"[POS DIRECTO] Forma de pago principal asignada al ticket: {forma_pago.nombre}")
                    
                    print(f"[POS DIRECTO] Movimiento de caja creado: {forma_pago.nombre} - ${fp_data['monto']}")
                
                # Recalcular totales de la apertura
                apertura_activa.calcular_totales()
            
            # 4. Crear venta procesada
            VentaProcesada.objects.create(
                venta_preventa=ticket,
                venta_final=ticket,  # En modo directo, el ticket ES la venta final
                apertura_caja=apertura_activa,
                usuario_proceso=request.user,
                monto_recibido=ticket.total,
                monto_cambio=Decimal('0.00'),
                stock_descontado=True,
                dte_generado=dte
            )
            
            # 5. Descontar stock
            from inventario.models import Stock
            
            bodega_caja = apertura_activa.caja.bodega
            for detalle in ticket.ventadetalle_set.all():
                stock = Stock.objects.filter(
                    empresa=empresa,
                    bodega=bodega_caja,
                    articulo=detalle.articulo
                ).first()
                
                if stock:
                    stock.cantidad -= detalle.cantidad
                    stock.save()
                    print(f"[POS DIRECTO] Stock descontado: {detalle.articulo.nombre} - {detalle.cantidad}")
                else:
                    print(f"[POS DIRECTO] ADVERTENCIA: No se encontró stock para {detalle.articulo.nombre} en bodega {bodega_caja.nombre}")
            
            # 6. Marcar ticket como facturado
            ticket.facturado = True
            ticket.save()
            
            # 7. Enviar al SII si está configurado
            estacion_id = request.session.get('pos_estacion_id')
            if dte and estacion_id:
                try:
                    estacion = EstacionTrabajo.objects.get(id=estacion_id, empresa=empresa)
                    if estacion.enviar_sii_directo:
                        from facturacion_electronica.background_sender import get_background_sender
                        sender = get_background_sender()
                        if sender.enviar_dte(dte.id, empresa.id):
                            print("[POS DIRECTO] DTE agregado a cola de envío")
                except Exception as e_envio:
                    print(f"[POS DIRECTO] Error al enviar DTE: {e_envio}")
            
            print("=" * 80)
            print("[POS DIRECTO] VENTA PROCESADA EXITOSAMENTE")
            print(f"   Número: {numero_venta_final}")
            print(f"   Tipo: {ticket.tipo_documento_planeado}")
            print(f"   Total: ${ticket.total}")
            print(f"   DTE: {dte.id if dte else 'No generado'}")
            print("=" * 80)
            
            # 8. Redirigir a impresión del documento
            messages.success(request, f'{ticket.tipo_documento_planeado.title()} #{numero_venta_final} procesada exitosamente.')
            
            if dte:
                # Redirigir a vista del DTE con impresión y cierre automático
                from urllib.parse import quote
                doc_url = reverse('facturacion_electronica:ver_factura_electronica', kwargs={'dte_id': dte.pk})
                pos_url = reverse('ventas:pos_view')
                # auto=1: imprime automáticamente
                # autoclose=1: cierra y vuelve después de imprimir
                # autoclose_delay=2000: espera 2 segundos (menos que caja porque POS es más rápido)
                # IMPORTANTE: codificar return_url para que se pase correctamente
                return redirect(f"{doc_url}?auto=1&autoclose=1&autoclose_delay=2000&return_url={quote(pos_url, safe='')}")
            else:
                # Si no hay DTE, imprimir como vale
                from urllib.parse import quote
                pos_url = reverse('ventas:pos_view')
                vale_url = reverse('ventas:vale_html', args=[ticket.pk])
                return redirect(f"{vale_url}?auto=1&autoclose=1&autoclose_delay=2000&return_url={quote(pos_url, safe='')}")
    
    except Exception as e:
        print(f"[POS DIRECTO] ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, f'Error al procesar la venta: {str(e)}')
        return redirect('ventas:procesar_venta_pos_directo', ticket_id=ticket_id)

