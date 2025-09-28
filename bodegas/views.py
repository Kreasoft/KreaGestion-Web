from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.template.loader import render_to_string
from usuarios.decorators import requiere_empresa
from .models import Bodega
from .forms import BodegaForm, BodegaFilterForm

@login_required
@requiere_empresa
def bodega_list(request):
    """
    Lista todas las bodegas de la empresa
    """
    bodegas_qs = Bodega.objects.filter(empresa=request.empresa).order_by('nombre')

    # Filtros
    filter_form = BodegaFilterForm(request.GET)
    if filter_form.is_valid():
        search_query = filter_form.cleaned_data.get('search')
        activa = filter_form.cleaned_data.get('activa')

        if search_query:
            bodegas_qs = bodegas_qs.filter(
                Q(nombre__icontains=search_query) |
                Q(codigo__icontains=search_query)
            )
        if activa:
            bodegas_qs = bodegas_qs.filter(activa=(activa == 'true'))

    # Paginación
    paginator = Paginator(bodegas_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'titulo': 'Gestión de Bodegas',
        'page_obj': page_obj,
        'filter_form': filter_form,
    }
    return render(request, 'bodegas/bodega_list.html', context)

@login_required
@requiere_empresa
def bodega_create_modal(request):
    """
    Vista para crear una bodega usando modal
    """
    if request.method == 'POST':
        print(f"POST data: {request.POST}")
        print(f"Empresa: {request.empresa}")
        
        form = BodegaForm(request.POST, request=request)
        print(f"Form is valid: {form.is_valid()}")
        if not form.is_valid():
            print(f"Form errors: {form.errors}")
        
        if form.is_valid():
            bodega = form.save(commit=False)
            bodega.empresa = request.empresa
            bodega.save()
            print(f"Bodega guardada: {bodega}")
            messages.success(request, f'Bodega "{bodega.nombre}" creada exitosamente.')
            return JsonResponse({'status': 'success', 'message': 'Bodega creada exitosamente.'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Error en el formulario.', 'errors': form.errors})
    else:
        form = BodegaForm(request=request)
    
    context = {
        'form': form,
        'modal_title': 'Crear Nueva Bodega',
        'is_create': True
    }
    return JsonResponse({
        'html_form': render_to_string('bodegas/includes/bodega_form_modal.html', context, request=request)
    })

@login_required
@requiere_empresa
def bodega_update_modal(request, pk):
    """
    Vista para editar una bodega usando modal
    """
    bodega = get_object_or_404(Bodega, pk=pk, empresa=request.empresa)
    if request.method == 'POST':
        form = BodegaForm(request.POST, instance=bodega, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, f'Bodega "{bodega.nombre}" actualizada exitosamente.')
            return JsonResponse({'status': 'success', 'message': 'Bodega actualizada exitosamente.'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Error en el formulario.', 'errors': form.errors})
    else:
        form = BodegaForm(instance=bodega, request=request)
    
    context = {
        'form': form,
        'bodega': bodega,
        'modal_title': f'Editar Bodega: {bodega.nombre}',
        'is_create': False
    }
    return JsonResponse({
        'html_form': render_to_string('bodegas/includes/bodega_form_modal.html', context, request=request)
    })

@login_required
@requiere_empresa
def bodega_delete_modal(request, pk):
    """
    Vista para eliminar una bodega usando modal
    """
    bodega = get_object_or_404(Bodega, pk=pk, empresa=request.empresa)
    if request.method == 'POST':
        nombre_bodega = bodega.nombre
        bodega.delete()
        messages.success(request, f'Bodega "{nombre_bodega}" eliminada exitosamente.')
        return JsonResponse({'status': 'success', 'message': 'Bodega eliminada exitosamente.'})
    
    context = {
        'bodega': bodega,
        'modal_title': f'Eliminar Bodega: {bodega.nombre}'
    }
    return JsonResponse({
        'html_form': render_to_string('bodegas/includes/bodega_delete_modal.html', context, request=request)
    })