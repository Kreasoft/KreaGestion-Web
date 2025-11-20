"""
Vistas para gestionar Órdenes de Despacho
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.http import JsonResponse
from django.utils import timezone

from core.decorators import requiere_empresa
from .models_despacho import OrdenDespacho, DetalleOrdenDespacho
from .models import OrdenPedido, ItemOrdenPedido
from .forms_despacho import OrdenDespachoForm, DetalleOrdenDespachoFormSet
from facturacion_electronica.models import DocumentoTributarioElectronico


@login_required
@requiere_empresa
@permission_required('pedidos.view_ordendespacho', raise_exception=True)
def orden_despacho_list(request):
    """Lista de órdenes de despacho"""
    # Filtros
    estado = request.GET.get('estado', '')
    pedido_id = request.GET.get('pedido', '')
    search = request.GET.get('search', '')
    
    # Query base
    ordenes = OrdenDespacho.objects.filter(
        empresa=request.empresa
    ).select_related(
        'orden_pedido',
        'orden_pedido__cliente',
        'creado_por'
    ).prefetch_related('items')
    
    # Aplicar filtros
    if estado:
        ordenes = ordenes.filter(estado=estado)
    
    if pedido_id:
        ordenes = ordenes.filter(orden_pedido_id=pedido_id)
    
    if search:
        ordenes = ordenes.filter(
            Q(numero_despacho__icontains=search) |
            Q(orden_pedido__numero_pedido__icontains=search) |
            Q(orden_pedido__cliente__nombre__icontains=search) |
            Q(transportista__icontains=search)
        )
    
    # Estadísticas
    total_despachos = ordenes.count()
    pendientes = ordenes.filter(estado='pendiente').count()
    en_proceso = ordenes.filter(estado__in=['en_preparacion', 'despachado', 'en_transito']).count()
    entregados = ordenes.filter(estado='entregado').count()
    
    context = {
        'ordenes': ordenes,
        'total_despachos': total_despachos,
        'pendientes': pendientes,
        'en_proceso': en_proceso,
        'entregados': entregados,
        'estado_filter': estado,
        'pedido_filter': pedido_id,
        'search': search,
    }
    
    return render(request, 'pedidos/orden_despacho_list.html', context)


@login_required
@requiere_empresa
@permission_required('pedidos.add_ordendespacho', raise_exception=True)
def orden_despacho_create(request):
    """Crear nueva orden de despacho"""
    pedido_id = request.GET.get('pedido')
    pedido = None

    if pedido_id:
        pedido = get_object_or_404(OrdenPedido, pk=pedido_id, empresa=request.empresa)
        if pedido.estado in ['completada', 'cancelada']:
            messages.warning(request, f"El pedido {pedido.numero_pedido} ya está {pedido.get_estado_display()} y no se pueden crear nuevos despachos.")
            return redirect('pedidos:orden_pedido_detail', pk=pedido.pk)

    if request.method == 'POST':
        # Si el pedido no se obtuvo del POST, se busca de nuevo.
        if not pedido:
            pedido_id_post = request.POST.get('orden_pedido')
            if pedido_id_post:
                pedido = get_object_or_404(OrdenPedido, pk=pedido_id_post, empresa=request.empresa)
        
        form = OrdenDespachoForm(request.POST, empresa=request.empresa)
        formset = DetalleOrdenDespachoFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    orden = form.save(commit=False)
                    orden.empresa = request.empresa
                    orden.creado_por = request.user
                    orden.orden_pedido = pedido # Asignar el pedido
                    orden.estado = 'pendiente'
                    
                    if not orden.numero_despacho:
                        orden.generar_numero_despacho()
                    
                    orden.estado = 'despachado'
                    orden.save()

                    formset.instance = orden
                    formset.save()

                    tipo_documento = form.cleaned_data.get('tipo_documento')
                    if tipo_documento == 'guia':
                        from .utils_despacho import generar_guia_desde_orden_despacho
                        dte = generar_guia_desde_orden_despacho(orden, request.user)
                        messages.success(request, f'✓ Guía de Despacho N° {dte.folio} generada.')
                    elif tipo_documento == 'factura':
                        from .utils_despacho import generar_factura_desde_orden_despacho
                        dte = generar_factura_desde_orden_despacho(orden, request.user)
                        messages.success(request, f'✓ Factura N° {dte.folio} generada.')

                    messages.success(request, f'✓ Orden de Despacho {orden.numero_despacho} creada exitosamente.')
                    return redirect('pedidos:orden_despacho_detail', pk=orden.pk)
            
            except Exception as e:
                error_msg = str(e)
                messages.error(request, f'⚠ Error al crear orden: {error_msg}')
                if 'No hay folios CAF disponibles' in error_msg:
                    messages.warning(request, 'Debe cargar archivos CAF en Facturación Electrónica → Folios CAF')
        else:
            if form.errors:
                for field, error_list in form.errors.items():
                    messages.error(request, f'Error en {form.fields[field].label or field}: {error}')
            if formset.errors:
                for i, form_errors in enumerate(formset.errors):
                    if form_errors:
                        for field, error_list in form_errors.items():
                            for error_item in error_list:
                                messages.error(request, f'Error en Artículo {i+1} ({field}): {error_item}')
    
    else:
        initial_data = {'orden_pedido': pedido} if pedido else {}
        form = OrdenDespachoForm(initial=initial_data, empresa=request.empresa)
        formset = DetalleOrdenDespachoFormSet()
    
    context = {
        'form': form,
        'formset': formset,
        'pedido': pedido, # Pasar el objeto pedido a la plantilla
        'titulo': 'Nueva Orden de Despacho',
        'accion': 'Crear'
    }
    
    return render(request, 'pedidos/orden_despacho_form.html', context)


@login_required
@requiere_empresa
@permission_required('pedidos.view_ordendespacho', raise_exception=True)
def orden_despacho_detail(request, pk):
    """Detalle de orden de despacho"""
    orden = get_object_or_404(
        OrdenDespacho.objects.select_related(
            'orden_pedido',
            'orden_pedido__cliente',
            'creado_por'
        ).prefetch_related('items__item_pedido__articulo'),
        pk=pk,
        empresa=request.empresa
    )
    
    # Obtener documentos asociados
    documentos = orden.get_documentos_asociados()
    
    # Calcular totales
    total_items = orden.get_total_items()
    
    context = {
        'orden': orden,
        'documentos': documentos,
        'total_items': total_items,
    }
    
    return render(request, 'pedidos/orden_despacho_detail.html', context)


@login_required
@requiere_empresa
@permission_required('pedidos.change_ordendespacho', raise_exception=True)
def orden_despacho_edit(request, pk):
    """Editar orden de despacho"""
    orden = get_object_or_404(OrdenDespacho, pk=pk, empresa=request.empresa)
    
    # No permitir editar si ya está entregado o cancelado
    if orden.estado in ['entregado', 'cancelado']:
        messages.error(
            request,
            'No se puede editar una orden de despacho entregada o cancelada.'
        )
        return redirect('pedidos:orden_despacho_detail', pk=pk)
    
    if request.method == 'POST':
        form = OrdenDespachoForm(request.POST, instance=orden, empresa=request.empresa)
        formset = DetalleOrdenDespachoFormSet(request.POST, instance=orden)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    formset.save()
                    
                    messages.success(
                        request,
                        f'Orden de Despacho {orden.numero_despacho} actualizada exitosamente.'
                    )
                    return redirect('pedidos:orden_despacho_detail', pk=pk)
            
            except Exception as e:
                messages.error(request, f'Error al actualizar orden: {str(e)}')
    
    else:
        form = OrdenDespachoForm(instance=orden, empresa=request.empresa)
        formset = DetalleOrdenDespachoFormSet(instance=orden)
    
    context = {
        'form': form,
        'formset': formset,
        'orden': orden,
        'titulo': f'Editar Orden de Despacho {orden.numero_despacho}',
        'accion': 'Actualizar'
    }
    
    return render(request, 'pedidos/orden_despacho_form.html', context)


@login_required
@requiere_empresa
@permission_required('pedidos.delete_ordendespacho', raise_exception=True)
def orden_despacho_delete(request, pk):
    """Eliminar orden de despacho"""
    orden = get_object_or_404(OrdenDespacho, pk=pk, empresa=request.empresa)
    
    # Solo permitir eliminar si está pendiente
    if orden.estado != 'pendiente':
        messages.error(
            request,
            'Solo se pueden eliminar órdenes de despacho en estado pendiente.'
        )
        return redirect('pedidos:orden_despacho_detail', pk=pk)
    
    if request.method == 'POST':
        numero = orden.numero_despacho
        orden.delete()
        messages.success(request, f'Orden de Despacho {numero} eliminada exitosamente.')
        return redirect('pedidos:orden_despacho_list')
    
    context = {
        'orden': orden
    }
    
    return render(request, 'pedidos/orden_despacho_confirm_delete.html', context)


@login_required
@requiere_empresa
def orden_despacho_cambiar_estado(request, pk):
    """Cambiar estado de la orden de despacho"""
    if request.method == 'POST':
        orden = get_object_or_404(OrdenDespacho, pk=pk, empresa=request.empresa)
        nuevo_estado = request.POST.get('estado')
        
        if nuevo_estado in dict(OrdenDespacho.ESTADO_CHOICES):
            orden.estado = nuevo_estado
            
            # Si se marca como entregado, registrar fecha
            if nuevo_estado == 'entregado' and not orden.fecha_entrega_real:
                orden.fecha_entrega_real = timezone.now().date()
            
            orden.save()
            
            messages.success(
                request,
                f'Estado actualizado a: {orden.get_estado_display()}'
            )
        else:
            messages.error(request, 'Estado inválido.')
        
        return redirect('pedidos:orden_despacho_detail', pk=pk)
    
    return redirect('pedidos:orden_despacho_list')


@login_required
def ajax_items_pedido(request):
    """AJAX: Obtener items de un pedido para el formset"""
    import traceback
    
    pedido_id = request.GET.get('pedido_id')
    
    if not pedido_id:
        return JsonResponse({'error': 'ID de pedido requerido'}, status=400)
    
    try:
        # Obtener empresa de diferentes fuentes
        empresa = getattr(request, 'empresa', None)
        empresa_id = None
        
        if empresa:
            empresa_id = empresa.id
        else:
            # Intentar obtener de la sesión
            empresa_id = request.session.get('empresa_activa_id') or request.session.get('empresa_activa')
        
        if not empresa_id:
            return JsonResponse({
                'error': 'Debe seleccionar una empresa',
                'debug': {
                    'has_empresa_attr': hasattr(request, 'empresa'),
                    'empresa_value': str(empresa),
                    'session_keys': list(request.session.keys()),
                }
            }, status=400)
            
        pedido = OrdenPedido.objects.get(id=pedido_id, empresa_id=empresa_id)
        items = pedido.items.select_related('articulo').annotate(
            total_despachado=Sum('despachos__cantidad', filter=Q(despachos__orden_despacho__estado__in=['en_preparacion', 'despachado', 'en_transito', 'entregado']))
        ).all()

        items_data = []
        for item in items:
            total_despachado = item.total_despachado or 0
            cantidad_pendiente = item.cantidad - total_despachado
            
            if cantidad_pendiente > 0:
                items_data.append({
                    'id': item.id,
                    'articulo': item.articulo.nombre,
                    'codigo': item.articulo.codigo,
                    'cantidad_pedido': float(item.cantidad),
                    'cantidad_despachada': float(total_despachado),
                    'cantidad_pendiente': float(cantidad_pendiente),
                    'precio_neto': float(item.get_base_imponible()),
                    'iva': float(item.get_impuesto_monto()),
                    'impuesto_especifico': 0, # Modelo no tiene impuestos adicionales
                    'total': float(item.get_total()),
                    'item_pedido_id': item.id
                })

        # Información adicional sobre el cliente y el pedido
        cliente = pedido.cliente
        cliente_data = {
            'nombre': cliente.nombre,
            'rut': cliente.rut,
            'direccion': cliente.direccion or '',
            'comuna': cliente.comuna if isinstance(cliente.comuna, str) else (cliente.comuna.nombre if cliente.comuna else ''),
            'region': ''  # La región se puede obtener de otra manera si es necesario
        }
        
        # Si comuna es un objeto con región, obtenerla
        if hasattr(cliente, 'comuna') and cliente.comuna and hasattr(cliente.comuna, 'region'):
            if cliente.comuna.region:
                cliente_data['region'] = cliente.comuna.region.nombre if hasattr(cliente.comuna.region, 'nombre') else str(cliente.comuna.region)

        return JsonResponse({'success': True, 'items': items_data, 'cliente': cliente_data})
    
    except OrdenPedido.DoesNotExist:
        return JsonResponse({'error': 'Pedido no encontrado', 'pedido_id': pedido_id, 'empresa_id': empresa_id}, status=404)
    except Exception as e:
        # Log detallado del error
        error_trace = traceback.format_exc()
        print(f"ERROR en ajax_items_pedido: {error_trace}")
        return JsonResponse({
            'error': str(e),
            'type': type(e).__name__,
            'traceback': error_trace
        }, status=500)


@login_required
@requiere_empresa
@permission_required('facturacion_electronica.add_documentotributarioelectronico', raise_exception=True)
def generar_guia_despacho(request, pk):
    """Genera una Guía de Despacho para una orden de despacho específica."""
    orden = get_object_or_404(OrdenDespacho, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        try:
            from .utils_despacho import generar_guia_desde_orden_despacho
            dte = generar_guia_desde_orden_despacho(orden, request.user)
            messages.success(request, f'Guía de Despacho Electrónica {dte.folio} generada exitosamente.')
            orden.estado = 'despachado'
            orden.save()
        except Exception as e:
            messages.error(request, f'Error al generar Guía de Despacho: {str(e)}')
            
    return redirect('pedidos:orden_despacho_detail', pk=pk)


@login_required
@requiere_empresa
@permission_required('facturacion_electronica.add_documentotributarioelectronico', raise_exception=True)
def generar_factura_despacho(request, pk):
    """Genera una Factura para una orden de despacho específica."""
    orden = get_object_or_404(OrdenDespacho, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        try:
            from .utils_despacho import generar_factura_desde_orden_despacho
            dte = generar_factura_desde_orden_despacho(orden, request.user)
            messages.success(request, f'Factura Electrónica {dte.folio} generada exitosamente.')
            orden.estado = 'despachado'
            orden.save()
        except Exception as e:
            messages.error(request, f'Error al generar Factura: {str(e)}')
            
    return redirect('pedidos:orden_despacho_detail', pk=pk)




