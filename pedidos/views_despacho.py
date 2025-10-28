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

from empresas.decorators import requiere_empresa
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
    if request.method == 'POST':
        form = OrdenDespachoForm(request.POST, empresa=request.empresa)
        formset = DetalleOrdenDespachoFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    # Crear orden de despacho
                    orden = form.save(commit=False)
                    orden.empresa = request.empresa
                    orden.creado_por = request.user
                    orden.estado = 'pendiente'  # Forzar estado inicial
                    
                    # Generar número de despacho
                    if not orden.numero_despacho:
                        orden.generar_numero_despacho()
                    
                    orden.estado = 'despachado' # Se genera el documento, se marca como despachado
                    orden.save()

                    # Guardar items
                    formset.instance = orden
                    formset.save()

                    # Generar el documento seleccionado
                    tipo_documento = form.cleaned_data.get('tipo_documento')
                    try:
                        if tipo_documento == 'guia':
                            from .utils_despacho import generar_guia_desde_orden_despacho
                            dte = generar_guia_desde_orden_despacho(orden, request.user)
                            messages.info(request, f'Guía de Despacho {dte.folio} generada.')
                        elif tipo_documento == 'factura':
                            from .utils_despacho import generar_factura_desde_orden_despacho
                            dte = generar_factura_desde_orden_despacho(orden, request.user)
                            messages.info(request, f'Factura {dte.folio} generada.')
                        
                        # Vincular el DTE a los items del despacho
                        orden.items.update(guia_despacho=dte if tipo_documento == 'guia' else None, factura=dte if tipo_documento == 'factura' else None)

                    except Exception as e:
                        messages.error(request, f'Error al generar documento: {str(e)}')
                        # La transacción se revertirá, no es necesario eliminar la orden manualmente
                        raise # Levantar la excepción para que transaction.atomic() haga rollback

                    messages.success(
                        request,
                        f'Orden de Despacho {orden.numero_despacho} creada y documento generado exitosamente.'
                    )
                    return redirect('pedidos:orden_despacho_detail', pk=orden.pk)
            
            except Exception as e:
                messages.error(request, f'Error al crear orden de despacho: {str(e)}')
        else:
            # Si la validación falla, mostrar errores específicos
            if form.errors:
                for field, error_list in form.errors.items():
                    for error in error_list:
                        messages.error(request, f'Error en {form.fields[field].label or field}: {error}')
            
            if formset.errors:
                for i, form_errors in enumerate(formset.errors):
                    if form_errors:
                        for field, error_list in form_errors.items():
                            for error in error_list:
                                messages.error(request, f'Error en Artículo {i+1} ({field}): {error}')
    
    else:
        form = OrdenDespachoForm(empresa=request.empresa)
        formset = DetalleOrdenDespachoFormSet()
    
    context = {
        'form': form,
        'formset': formset,
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
@requiere_empresa
def ajax_items_pedido(request):
    """AJAX: Obtener items de un pedido para el formset"""
    pedido_id = request.GET.get('pedido_id')
    
    if not pedido_id:
        return JsonResponse({'error': 'ID de pedido requerido'}, status=400)
    
    try:
        pedido = OrdenPedido.objects.get(id=pedido_id, empresa=request.empresa)
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
        cliente_data = {
            'nombre': pedido.cliente.nombre,
            'rut': pedido.cliente.rut,
            'direccion': pedido.cliente.direccion,
            'comuna': pedido.cliente.comuna.nombre if pedido.cliente.comuna else '',
            'region': pedido.cliente.comuna.region.nombre if pedido.cliente.comuna and pedido.cliente.comuna.region else ''
        }

        return JsonResponse({'success': True, 'items': items_data, 'cliente': cliente_data})
    
    except OrdenPedido.DoesNotExist:
        return JsonResponse({'error': 'Pedido no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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




