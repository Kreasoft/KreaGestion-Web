from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import datetime
from decimal import Decimal

from .models import OrdenPedido, ItemOrdenPedido
from .forms import OrdenPedidoForm, ItemOrdenPedidoFormSet, BusquedaPedidoForm
from empresas.models import Empresa
from articulos.models import Articulo
from usuarios.decorators import requiere_empresa


@login_required
@requiere_empresa
def orden_pedido_list(request):
    """Lista de órdenes de pedido"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id:
            try:
                empresa = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        else:
            empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    # Obtener pedidos
    pedidos = OrdenPedido.objects.filter(empresa=empresa).select_related(
        'cliente', 'bodega', 'creado_por'
    ).order_by('-fecha_pedido', '-numero_pedido')
    
    # Aplicar filtros
    search_form = BusquedaPedidoForm(request.GET)
    if search_form.is_valid():
        search = search_form.cleaned_data.get('search')
        estado = search_form.cleaned_data.get('estado')
        cliente = search_form.cleaned_data.get('cliente')
        fecha_desde = search_form.cleaned_data.get('fecha_desde')
        fecha_hasta = search_form.cleaned_data.get('fecha_hasta')
        
        if search:
            pedidos = pedidos.filter(
                Q(numero_pedido__icontains=search) |
                Q(cliente__nombre__icontains=search) |
                Q(numero_oc_cliente__icontains=search)
            )
        if estado:
            pedidos = pedidos.filter(estado=estado)
        if cliente:
            pedidos = pedidos.filter(cliente=cliente)
        if fecha_desde:
            pedidos = pedidos.filter(fecha_pedido__gte=fecha_desde)
        if fecha_hasta:
            pedidos = pedidos.filter(fecha_pedido__lte=fecha_hasta)
    
    # Estadísticas
    stats = {
        'total_pedidos': pedidos.count(),
        'pedidos_borrador': pedidos.filter(estado='borrador').count(),
        'pedidos_confirmados': pedidos.filter(estado='confirmada').count(),
        'pedidos_en_proceso': pedidos.filter(estado='en_proceso').count(),
        'pedidos_completados': pedidos.filter(estado='completada').count(),
        'monto_total': pedidos.aggregate(total=Sum('total_pedido'))['total'] or 0,
    }
    
    # Paginación
    paginator = Paginator(pedidos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_form': search_form,
        'stats': stats,
        'empresa': empresa,
    }
    
    return render(request, 'pedidos/orden_pedido_list.html', context)


@login_required
@requiere_empresa
def orden_pedido_create(request):
    """Crear nueva orden de pedido"""
    # Obtener la empresa del usuario
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id:
            try:
                empresa = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
        else:
            empresa = Empresa.objects.filter(nombre__icontains='Kreasoft').first()
    else:
        try:
            empresa = request.user.perfil.empresa
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    if request.method == 'POST':
        form = OrdenPedidoForm(request.POST)
        formset = ItemOrdenPedidoFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            try:
                pedido = form.save(commit=False)
                pedido.empresa = empresa
                pedido.creado_por = request.user
                
                # Generar número de pedido
                pedido.generar_numero_pedido()
                pedido.save()
                
                # Guardar items
                formset.instance = pedido
                formset.save()
                
                # Calcular totales
                pedido.calcular_totales()
                
                messages.success(request, f'Orden de pedido {pedido.numero_pedido} creada exitosamente.')
                return redirect('pedidos:orden_pedido_detail', pk=pedido.pk)
            except Exception as e:
                messages.error(request, f'Error al guardar el pedido: {str(e)}')
        else:
            # Mostrar errores del formulario
            if form.errors:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f'{field}: {error}')
            if formset.errors:
                for i, form_errors in enumerate(formset.errors):
                    if form_errors:
                        for field, errors in form_errors.items():
                            for error in errors:
                                messages.error(request, f'Item {i+1} - {field}: {error}')
    else:
        form = OrdenPedidoForm()
        formset = ItemOrdenPedidoFormSet()
    
    # Obtener artículos de la empresa
    articulos_empresa = Articulo.objects.filter(empresa=empresa).order_by('nombre')
    
    context = {
        'form': form,
        'formset': formset,
        'articulos_empresa': articulos_empresa,
        'empresa': empresa,
    }
    
    return render(request, 'pedidos/orden_pedido_form.html', context)


@login_required
@requiere_empresa
def orden_pedido_detail(request, pk):
    """Ver detalle de orden de pedido"""
    pedido = get_object_or_404(OrdenPedido, pk=pk)
    
    # Verificar que el pedido pertenece a la empresa del usuario
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id and pedido.empresa_id != int(empresa_id):
            messages.error(request, 'No tiene permisos para ver este pedido.')
            return redirect('pedidos:orden_pedido_list')
    else:
        try:
            if pedido.empresa != request.user.perfil.empresa:
                messages.error(request, 'No tiene permisos para ver este pedido.')
                return redirect('pedidos:orden_pedido_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    items = pedido.items.select_related('articulo').all()
    
    context = {
        'pedido': pedido,
        'items': items,
    }
    
    return render(request, 'pedidos/orden_pedido_detail.html', context)


@login_required
@requiere_empresa
def orden_pedido_update(request, pk):
    """Editar orden de pedido"""
    pedido = get_object_or_404(OrdenPedido, pk=pk)
    
    # Verificar permisos
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id and pedido.empresa_id != int(empresa_id):
            messages.error(request, 'No tiene permisos para editar este pedido.')
            return redirect('pedidos:orden_pedido_list')
    else:
        try:
            if pedido.empresa != request.user.perfil.empresa:
                messages.error(request, 'No tiene permisos para editar este pedido.')
                return redirect('pedidos:orden_pedido_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    if request.method == 'POST':
        form = OrdenPedidoForm(request.POST, instance=pedido)
        formset = ItemOrdenPedidoFormSet(request.POST, instance=pedido)
        
        if form.is_valid() and formset.is_valid():
            pedido = form.save()
            formset.save()
            
            # Recalcular totales
            pedido.calcular_totales()
            
            messages.success(request, f'Orden de pedido {pedido.numero_pedido} actualizada exitosamente.')
            return redirect('pedidos:orden_pedido_detail', pk=pedido.pk)
    else:
        form = OrdenPedidoForm(instance=pedido)
        formset = ItemOrdenPedidoFormSet(instance=pedido)
    
    # Obtener artículos de la empresa
    articulos_empresa = Articulo.objects.filter(empresa=pedido.empresa).order_by('nombre')
    
    context = {
        'form': form,
        'formset': formset,
        'pedido': pedido,
        'articulos_empresa': articulos_empresa,
        'empresa': pedido.empresa,
    }
    
    return render(request, 'pedidos/orden_pedido_form.html', context)


@login_required
@requiere_empresa
def orden_pedido_delete(request, pk):
    """Eliminar orden de pedido"""
    pedido = get_object_or_404(OrdenPedido, pk=pk)
    
    # Verificar permisos
    if request.user.is_superuser:
        empresa_id = request.session.get('empresa_activa')
        if empresa_id and pedido.empresa_id != int(empresa_id):
            messages.error(request, 'No tiene permisos para eliminar este pedido.')
            return redirect('pedidos:orden_pedido_list')
    else:
        try:
            if pedido.empresa != request.user.perfil.empresa:
                messages.error(request, 'No tiene permisos para eliminar este pedido.')
                return redirect('pedidos:orden_pedido_list')
        except:
            messages.error(request, 'Usuario no tiene empresa asociada.')
            return redirect('dashboard')
    
    if request.method == 'POST':
        numero_pedido = pedido.numero_pedido
        pedido.delete()
        messages.success(request, f'Orden de pedido {numero_pedido} eliminada exitosamente.')
        return redirect('pedidos:orden_pedido_list')
    
    context = {
        'pedido': pedido,
    }
    
    return render(request, 'pedidos/orden_pedido_confirm_delete.html', context)


@login_required
@requiere_empresa
def orden_pedido_cambiar_estado(request, pk):
    """Cambiar estado de orden de pedido"""
    pedido = get_object_or_404(OrdenPedido, pk=pk)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        if nuevo_estado in dict(OrdenPedido.ESTADO_CHOICES):
            pedido.estado = nuevo_estado
            pedido.save()
            messages.success(request, f'Estado del pedido {pedido.numero_pedido} actualizado a {pedido.get_estado_display()}.')
        else:
            messages.error(request, 'Estado inválido.')
    
    return redirect('pedidos:orden_pedido_detail', pk=pk)
