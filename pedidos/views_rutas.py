"""
Vistas para gestionar Rutas y Hojas de Ruta
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.http import JsonResponse
from django.utils import timezone

from core.decorators import requiere_empresa
from .models_rutas import Ruta, HojaRuta
from facturacion_electronica.models import DocumentoTributarioElectronico


@login_required
@requiere_empresa
@permission_required('pedidos.view_ruta', raise_exception=True)
def ruta_list(request):
    """Lista de rutas maestras"""
    rutas = Ruta.objects.filter(empresa=request.empresa).annotate(
        clientes_count=Count('clientes')
    ).order_by('orden_visita', 'codigo')
    
    context = {
        'rutas': rutas,
        'titulo': 'Rutas de Despacho'
    }
    return render(request, 'pedidos/ruta_list.html', context)


@login_required
@requiere_empresa
@permission_required('pedidos.add_ruta', raise_exception=True)
def ruta_create(request):
    """Crear nueva ruta"""
    if request.method == 'POST':
        # TODO: Crear formulario
        messages.success(request, 'Ruta creada exitosamente.')
        return redirect('pedidos:ruta_list')
    
    context = {
        'titulo': 'Crear Ruta'
    }
    return render(request, 'pedidos/ruta_form.html', context)


@login_required
@requiere_empresa
@permission_required('pedidos.view_ruta', raise_exception=True)
def ruta_detail(request, pk):
    """Detalle de ruta"""
    ruta = get_object_or_404(Ruta, pk=pk, empresa=request.empresa)
    
    context = {
        'ruta': ruta,
        'titulo': f'Ruta: {ruta.nombre}'
    }
    return render(request, 'pedidos/ruta_detail.html', context)


@login_required
@requiere_empresa
@permission_required('pedidos.change_ruta', raise_exception=True)
def ruta_edit(request, pk):
    """Editar ruta"""
    ruta = get_object_or_404(Ruta, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        # TODO: Procesar formulario
        messages.success(request, 'Ruta actualizada exitosamente.')
        return redirect('pedidos:ruta_detail', pk=ruta.pk)
    
    context = {
        'ruta': ruta,
        'titulo': f'Editar Ruta: {ruta.nombre}'
    }
    return render(request, 'pedidos/ruta_form.html', context)


@login_required
@requiere_empresa
@permission_required('pedidos.delete_ruta', raise_exception=True)
def ruta_delete(request, pk):
    """Eliminar ruta"""
    ruta = get_object_or_404(Ruta, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        ruta.delete()
        messages.success(request, 'Ruta eliminada exitosamente.')
        return redirect('pedidos:ruta_list')
    
    context = {
        'ruta': ruta,
        'titulo': 'Eliminar Ruta'
    }
    return render(request, 'pedidos/ruta_confirm_delete.html', context)


@login_required
@requiere_empresa
@permission_required('pedidos.view_hojaruta', raise_exception=True)
def hoja_ruta_list(request):
    """Lista de hojas de ruta"""
    # Filtros
    estado = request.GET.get('estado', '')
    fecha = request.GET.get('fecha', '')
    ruta_id = request.GET.get('ruta', '')
    search = request.GET.get('search', '')
    
    # Query base
    hojas_ruta = HojaRuta.objects.filter(
        empresa=request.empresa
    ).select_related(
        'ruta', 'vehiculo', 'chofer', 'creado_por'
    ).prefetch_related('facturas')
    
    # Aplicar filtros
    if estado:
        hojas_ruta = hojas_ruta.filter(estado=estado)
    
    if fecha:
        hojas_ruta = hojas_ruta.filter(fecha=fecha)
    
    if ruta_id:
        hojas_ruta = hojas_ruta.filter(ruta_id=ruta_id)
    
    if search:
        hojas_ruta = hojas_ruta.filter(
            Q(numero_ruta__icontains=search) |
            Q(ruta__nombre__icontains=search) |
            Q(chofer__nombre__icontains=search) |
            Q(vehiculo__patente__icontains=search)
        )
    
    # Estadísticas
    total_hojas = hojas_ruta.count()
    pendientes = hojas_ruta.filter(estado='pendiente').count()
    en_ruta = hojas_ruta.filter(estado='en_ruta').count()
    completadas = hojas_ruta.filter(estado='completada').count()
    
    context = {
        'hojas_ruta': hojas_ruta.order_by('-fecha', '-numero_ruta'),
        'rutas': Ruta.objects.filter(empresa=request.empresa, activo=True),
        'estado': estado,
        'fecha': fecha,
        'ruta_id': ruta_id,
        'search': search,
        'total_hojas': total_hojas,
        'pendientes': pendientes,
        'en_ruta': en_ruta,
        'completadas': completadas,
        'titulo': 'Hojas de Ruta'
    }
    return render(request, 'pedidos/hoja_ruta_list.html', context)


@login_required
@requiere_empresa
@permission_required('pedidos.view_hojaruta', raise_exception=True)
def hoja_ruta_detail(request, pk):
    """Detalle de hoja de ruta"""
    hoja_ruta = get_object_or_404(
        HojaRuta.objects.select_related('ruta', 'vehiculo', 'chofer', 'creado_por')
        .prefetch_related('facturas'),
        pk=pk,
        empresa=request.empresa
    )
    
    # Obtener facturas con detalles
    facturas = hoja_ruta.facturas.all().select_related('venta').order_by('folio')
    
    context = {
        'hoja_ruta': hoja_ruta,
        'facturas': facturas,
        'titulo': f'Hoja de Ruta: {hoja_ruta.numero_ruta}'
    }
    return render(request, 'pedidos/hoja_ruta_detail.html', context)


@login_required
@requiere_empresa
@permission_required('pedidos.change_hojaruta', raise_exception=True)
def hoja_ruta_edit(request, pk):
    """Editar hoja de ruta"""
    hoja_ruta = get_object_or_404(HojaRuta, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        # TODO: Procesar formulario
        estado = request.POST.get('estado')
        if estado:
            hoja_ruta.estado = estado
            hoja_ruta.save()
            messages.success(request, 'Hoja de ruta actualizada exitosamente.')
        return redirect('pedidos:hoja_ruta_detail', pk=hoja_ruta.pk)
    
    context = {
        'hoja_ruta': hoja_ruta,
        'titulo': f'Editar Hoja de Ruta: {hoja_ruta.numero_ruta}'
    }
    return render(request, 'pedidos/hoja_ruta_form.html', context)


@login_required
@requiere_empresa
@permission_required('pedidos.view_hojaruta', raise_exception=True)
def hoja_ruta_imprimir(request, pk):
    """Imprimir hoja de ruta"""
    hoja_ruta = get_object_or_404(
        HojaRuta.objects.select_related('ruta', 'vehiculo', 'chofer')
        .prefetch_related('facturas'),
        pk=pk,
        empresa=request.empresa
    )
    
    facturas = hoja_ruta.facturas.all().select_related('venta').order_by('folio')
    
    context = {
        'hoja_ruta': hoja_ruta,
        'facturas': facturas,
        'titulo': f'Hoja de Ruta: {hoja_ruta.numero_ruta}'
    }
    return render(request, 'pedidos/hoja_ruta_imprimir.html', context)

