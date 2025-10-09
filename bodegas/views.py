from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from usuarios.decorators import requiere_empresa
from .models import Bodega
from .forms import BodegaForm, BodegaFilterForm

@login_required
@requiere_empresa
@permission_required('bodegas.view_bodega', raise_exception=True)
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

    # Estadísticas
    total_bodegas = Bodega.objects.filter(empresa=request.empresa).count()
    bodegas_activas = Bodega.objects.filter(empresa=request.empresa, activa=True).count()
    bodegas_inactivas = Bodega.objects.filter(empresa=request.empresa, activa=False).count()

    context = {
        'titulo': 'Gestión de Bodegas',
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_bodegas': total_bodegas,
        'bodegas_activas': bodegas_activas,
        'bodegas_inactivas': bodegas_inactivas,
        'bodegas': Bodega.objects.filter(empresa=request.empresa),
    }
    return render(request, 'bodegas/bodega_list.html', context)

@login_required
def bodega_create_modal(request):
    """Vista para crear una bodega usando modal"""
    empresa = request.empresa if hasattr(request, 'empresa') else request.user.perfil.empresa
    
    if request.method == 'POST':
        form = BodegaForm(request.POST, request=request)
        if form.is_valid():
            bodega = form.save(commit=False)
            bodega.empresa = empresa
            bodega.save()
            return JsonResponse({'success': True, 'message': 'Bodega creada exitosamente.'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = BodegaForm(request=request)
    
    context = {'form': form}
    return HttpResponse(render_to_string('bodegas/includes/bodega_form_modal.html', context, request=request))

@login_required
def bodega_update_modal(request, pk):
    """Vista para editar una bodega usando modal"""
    empresa = request.empresa if hasattr(request, 'empresa') else request.user.perfil.empresa
    bodega = get_object_or_404(Bodega, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        form = BodegaForm(request.POST, instance=bodega, request=request)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True, 'message': 'Bodega actualizada exitosamente.'})
        else:
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = BodegaForm(instance=bodega, request=request)
    
    context = {'form': form, 'bodega': bodega}
    return HttpResponse(render_to_string('bodegas/includes/bodega_form_modal.html', context, request=request))

@login_required
def bodega_delete_modal(request, pk):
    """Vista para eliminar una bodega usando modal"""
    empresa = request.empresa if hasattr(request, 'empresa') else request.user.perfil.empresa
    bodega = get_object_or_404(Bodega, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        nombre_bodega = bodega.nombre
        bodega.delete()
        return JsonResponse({'success': True, 'message': f'Bodega "{nombre_bodega}" eliminada exitosamente.'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})