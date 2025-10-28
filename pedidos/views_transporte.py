"""
Vistas para gestionar Vehículos y Choferes
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template.loader import render_to_string

from .models_transporte import Vehiculo, Chofer
from .forms_transporte import VehiculoForm, ChoferForm
from empresas.models import Empresa


# ========================================
# CRUD DE VEHÍCULOS
# ========================================

@login_required
def vehiculo_list(request):
    """
    Lista todos los vehículos de la empresa activa
    """
    empresa = request.session.get('empresa_activa')
    if not empresa:
        messages.error(request, 'Debe seleccionar una empresa para continuar.')
        return redirect('empresas:seleccionar_empresa')
    
    # Obtener vehículos de la empresa
    vehiculos = Vehiculo.objects.filter(empresa_id=empresa)
    
    # Búsqueda
    query = request.GET.get('q', '')
    if query:
        vehiculos = vehiculos.filter(
            Q(patente__icontains=query) |
            Q(descripcion__icontains=query)
        )
    
    # Filtro por estado
    estado = request.GET.get('estado', '')
    if estado == 'activo':
        vehiculos = vehiculos.filter(activo=True)
    elif estado == 'inactivo':
        vehiculos = vehiculos.filter(activo=False)
    
    # Ordenamiento
    vehiculos = vehiculos.order_by('patente')
    
    # Paginación
    paginator = Paginator(vehiculos, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'query': query,
        'estado': estado,
        'total': vehiculos.count(),
    }
    
    return render(request, 'pedidos/vehiculo_list.html', context)


@login_required
def vehiculo_detail(request, pk):
    """
    Muestra el detalle de un vehículo
    """
    empresa = request.session.get('empresa_activa')
    if not empresa:
        messages.error(request, 'Debe seleccionar una empresa para continuar.')
        return redirect('empresas:seleccionar_empresa')
    
    vehiculo = get_object_or_404(Vehiculo, pk=pk, empresa_id=empresa)
    
    context = {
        'vehiculo': vehiculo,
    }
    
    return render(request, 'pedidos/vehiculo_detail.html', context)


@login_required
def vehiculo_create(request):
    """
    Crea un nuevo vehículo
    """
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Debe seleccionar una empresa'}, status=400)
        messages.error(request, 'Debe seleccionar una empresa para continuar.')
        return redirect('empresas:seleccionar_empresa')
    
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    
    if request.method == 'POST':
        form = VehiculoForm(request.POST, empresa=empresa)
        if form.is_valid():
            vehiculo = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Vehículo {vehiculo.patente} creado exitosamente.',
                    'vehiculo': {
                        'id': vehiculo.pk,
                        'patente': vehiculo.patente,
                        'descripcion': vehiculo.descripcion,
                        'capacidad': str(vehiculo.capacidad) if vehiculo.capacidad else '-',
                        'activo': vehiculo.activo
                    }
                })
            messages.success(request, f'Vehículo {vehiculo.patente} creado exitosamente.')
            return redirect('pedidos:vehiculo_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
    else:
        form = VehiculoForm(empresa=empresa)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('pedidos/vehiculo_form_modal.html', {
            'form': form,
            'action': 'Crear',
        }, request=request)
        return JsonResponse({'html': html})
    
    context = {
        'form': form,
        'action': 'Crear',
    }
    
    return render(request, 'pedidos/vehiculo_form.html', context)


@login_required
def vehiculo_update(request, pk):
    """
    Actualiza un vehículo existente
    """
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Debe seleccionar una empresa'}, status=400)
        messages.error(request, 'Debe seleccionar una empresa para continuar.')
        return redirect('empresas:seleccionar_empresa')
    
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    vehiculo = get_object_or_404(Vehiculo, pk=pk, empresa_id=empresa_id)
    
    if request.method == 'POST':
        form = VehiculoForm(request.POST, instance=vehiculo, empresa=empresa)
        if form.is_valid():
            vehiculo = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Vehículo {vehiculo.patente} actualizado exitosamente.',
                    'vehiculo': {
                        'id': vehiculo.pk,
                        'patente': vehiculo.patente,
                        'descripcion': vehiculo.descripcion,
                        'capacidad': str(vehiculo.capacidad) if vehiculo.capacidad else '-',
                        'activo': vehiculo.activo
                    }
                })
            messages.success(request, f'Vehículo {vehiculo.patente} actualizado exitosamente.')
            return redirect('pedidos:vehiculo_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
    else:
        form = VehiculoForm(instance=vehiculo, empresa=empresa)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('pedidos/vehiculo_form_modal.html', {
            'form': form,
            'vehiculo': vehiculo,
            'action': 'Editar',
        }, request=request)
        return JsonResponse({'html': html})
    
    context = {
        'form': form,
        'vehiculo': vehiculo,
        'action': 'Editar',
    }
    
    return render(request, 'pedidos/vehiculo_form.html', context)


@login_required
def vehiculo_delete(request, pk):
    """
    Elimina un vehículo
    """
    empresa = request.session.get('empresa_activa')
    if not empresa:
        messages.error(request, 'Debe seleccionar una empresa para continuar.')
        return redirect('empresas:seleccionar_empresa')
    
    vehiculo = get_object_or_404(Vehiculo, pk=pk, empresa_id=empresa)
    
    if request.method == 'POST':
        patente = vehiculo.patente
        try:
            vehiculo.delete()
            messages.success(request, f'Vehículo {patente} eliminado exitosamente.')
            return redirect('pedidos:vehiculo_list')
        except Exception as e:
            messages.error(request, f'Error al eliminar el vehículo: {str(e)}')
            return redirect('pedidos:vehiculo_detail', pk=pk)
    
    context = {
        'vehiculo': vehiculo,
    }
    
    return render(request, 'pedidos/vehiculo_confirm_delete.html', context)


# ========================================
# CRUD DE CHOFERES
# ========================================

@login_required
def chofer_list(request):
    """
    Lista todos los choferes de la empresa activa
    """
    empresa = request.session.get('empresa_activa')
    if not empresa:
        messages.error(request, 'Debe seleccionar una empresa para continuar.')
        return redirect('empresas:seleccionar_empresa')
    
    # Obtener choferes de la empresa
    choferes = Chofer.objects.filter(empresa_id=empresa)
    
    # Búsqueda
    query = request.GET.get('q', '')
    if query:
        choferes = choferes.filter(
            Q(codigo__icontains=query) |
            Q(nombre__icontains=query) |
            Q(rut__icontains=query)
        )
    
    # Filtro por estado
    estado = request.GET.get('estado', '')
    if estado == 'activo':
        choferes = choferes.filter(activo=True)
    elif estado == 'inactivo':
        choferes = choferes.filter(activo=False)
    
    # Ordenamiento
    choferes = choferes.order_by('nombre')
    
    # Paginación
    paginator = Paginator(choferes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'query': query,
        'estado': estado,
        'total': choferes.count(),
    }
    
    return render(request, 'pedidos/chofer_list.html', context)


@login_required
def chofer_detail(request, pk):
    """
    Muestra el detalle de un chofer
    """
    empresa = request.session.get('empresa_activa')
    if not empresa:
        messages.error(request, 'Debe seleccionar una empresa para continuar.')
        return redirect('empresas:seleccionar_empresa')
    
    chofer = get_object_or_404(Chofer, pk=pk, empresa_id=empresa)
    
    context = {
        'chofer': chofer,
    }
    
    return render(request, 'pedidos/chofer_detail.html', context)


@login_required
def chofer_create(request):
    """
    Crea un nuevo chofer
    """
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Debe seleccionar una empresa'}, status=400)
        messages.error(request, 'Debe seleccionar una empresa para continuar.')
        return redirect('empresas:seleccionar_empresa')
    
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    
    if request.method == 'POST':
        form = ChoferForm(request.POST, empresa=empresa)
        if form.is_valid():
            chofer = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Chofer {chofer.nombre} creado exitosamente.',
                    'chofer': {
                        'id': chofer.pk,
                        'codigo': chofer.codigo,
                        'nombre': chofer.nombre,
                        'rut': chofer.rut,
                        'activo': chofer.activo
                    }
                })
            messages.success(request, f'Chofer {chofer.nombre} creado exitosamente.')
            return redirect('pedidos:chofer_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
    else:
        form = ChoferForm(empresa=empresa)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('pedidos/chofer_form_modal.html', {
            'form': form,
            'action': 'Crear',
        }, request=request)
        return JsonResponse({'html': html})
    
    context = {
        'form': form,
        'action': 'Crear',
    }
    
    return render(request, 'pedidos/chofer_form.html', context)


@login_required
def chofer_update(request, pk):
    """
    Actualiza un chofer existente
    """
    empresa_id = request.session.get('empresa_activa')
    if not empresa_id:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Debe seleccionar una empresa'}, status=400)
        messages.error(request, 'Debe seleccionar una empresa para continuar.')
        return redirect('empresas:seleccionar_empresa')
    
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    chofer = get_object_or_404(Chofer, pk=pk, empresa_id=empresa_id)
    
    if request.method == 'POST':
        form = ChoferForm(request.POST, instance=chofer, empresa=empresa)
        if form.is_valid():
            chofer = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'Chofer {chofer.nombre} actualizado exitosamente.',
                    'chofer': {
                        'id': chofer.pk,
                        'codigo': chofer.codigo,
                        'nombre': chofer.nombre,
                        'rut': chofer.rut,
                        'activo': chofer.activo
                    }
                })
            messages.success(request, f'Chofer {chofer.nombre} actualizado exitosamente.')
            return redirect('pedidos:chofer_list')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                }, status=400)
    else:
        form = ChoferForm(instance=chofer, empresa=empresa)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string('pedidos/chofer_form_modal.html', {
            'form': form,
            'chofer': chofer,
            'action': 'Editar',
        }, request=request)
        return JsonResponse({'html': html})
    
    context = {
        'form': form,
        'chofer': chofer,
        'action': 'Editar',
    }
    
    return render(request, 'pedidos/chofer_form.html', context)


@login_required
def chofer_delete(request, pk):
    """
    Elimina un chofer
    """
    empresa = request.session.get('empresa_activa')
    if not empresa:
        messages.error(request, 'Debe seleccionar una empresa para continuar.')
        return redirect('empresas:seleccionar_empresa')
    
    chofer = get_object_or_404(Chofer, pk=pk, empresa_id=empresa)
    
    if request.method == 'POST':
        nombre = chofer.nombre
        try:
            chofer.delete()
            messages.success(request, f'Chofer {nombre} eliminado exitosamente.')
            return redirect('pedidos:chofer_list')
        except Exception as e:
            messages.error(request, f'Error al eliminar el chofer: {str(e)}')
            return redirect('pedidos:chofer_detail', pk=pk)
    
    context = {
        'chofer': chofer,
    }
    
    return render(request, 'pedidos/chofer_confirm_delete.html', context)

