from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import pandas as pd
import io
import json
from .models import Inventario, Stock
from .forms import InventarioForm, StockForm, InventarioFilterForm
from core.decorators import requiere_empresa
from articulos.models import Articulo
from empresas.models import Sucursal


@login_required
@requiere_empresa
def inventario_list(request):
    """Lista todos los movimientos de inventario"""
    inventarios = Inventario.objects.filter(empresa=request.empresa).select_related(
        'bodega', 'articulo', 'creado_por'
    ).order_by('-fecha_movimiento', '-fecha_creacion')
    
    # Filtros
    filter_form = InventarioFilterForm(request.GET, empresa=request.empresa)
    if filter_form.is_valid():
        bodega = filter_form.cleaned_data.get('bodega')
        articulo = filter_form.cleaned_data.get('articulo')
        tipo_movimiento = filter_form.cleaned_data.get('tipo_movimiento')
        estado = filter_form.cleaned_data.get('estado')
        fecha_desde = filter_form.cleaned_data.get('fecha_desde')
        fecha_hasta = filter_form.cleaned_data.get('fecha_hasta')
        
        if bodega:
            inventarios = inventarios.filter(bodega=bodega)
        if articulo:
            inventarios = inventarios.filter(articulo=articulo)
        if tipo_movimiento:
            inventarios = inventarios.filter(tipo_movimiento=tipo_movimiento)
        if estado:
            inventarios = inventarios.filter(estado=estado)
        if fecha_desde:
            inventarios = inventarios.filter(fecha_movimiento__date__gte=fecha_desde)
        if fecha_hasta:
            inventarios = inventarios.filter(fecha_movimiento__date__lte=fecha_hasta)
    
    # Paginación
    paginator = Paginator(inventarios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    total_entradas = inventarios.filter(tipo_movimiento='entrada').aggregate(
        total=Sum('cantidad')
    )['total'] or 0
    total_salidas = inventarios.filter(tipo_movimiento='salida').aggregate(
        total=Sum('cantidad')
    )['total'] or 0
    valor_total = inventarios.aggregate(total=Sum('total'))['total'] or 0
    
    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_entradas': total_entradas,
        'total_salidas': total_salidas,
        'valor_total': valor_total,
        'titulo': 'Movimientos de Inventario'
    }
    
    return render(request, 'inventario/inventario_list.html', context)


@login_required
@requiere_empresa
def inventario_create(request):
    """Crear nuevo movimiento de inventario"""
    if request.method == 'POST':
        form = InventarioForm(request.POST, empresa=request.empresa)
        if form.is_valid():
            inventario = form.save(commit=False)
            inventario.empresa = request.empresa
            inventario.creado_por = request.user
            inventario.save()
            
            # Actualizar stock
            actualizar_stock(inventario)
            
            messages.success(request, f'Movimiento de inventario creado exitosamente.')
            return redirect('inventario:inventario_list')
    else:
        form = InventarioForm(empresa=request.empresa)
        # Establecer fecha actual por defecto
        form.fields['fecha_movimiento'].initial = timezone.now()
    
    context = {
        'form': form,
        'titulo': 'Nuevo Movimiento de Inventario'
    }
    
    return render(request, 'inventario/inventario_form.html', context)


@login_required
@requiere_empresa
def inventario_update(request, pk):
    """Editar movimiento de inventario"""
    inventario = get_object_or_404(Inventario, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = InventarioForm(request.POST, instance=inventario, empresa=request.empresa)
        if form.is_valid():
            # Revertir stock anterior
            revertir_stock(inventario)
            
            inventario = form.save(commit=False)
            inventario.actualizado_por = request.user
            inventario.save()
            
            # Actualizar stock con nuevos valores
            actualizar_stock(inventario)
            
            messages.success(request, f'Movimiento de inventario actualizado exitosamente.')
            return redirect('inventario:inventario_list')
    else:
        form = InventarioForm(instance=inventario, empresa=request.empresa)
    
    context = {
        'form': form,
        'inventario': inventario,
        'titulo': f'Editar Movimiento: {inventario.articulo.nombre}'
    }
    
    return render(request, 'inventario/inventario_form.html', context)


@login_required
@requiere_empresa
def inventario_delete(request, pk):
    """Eliminar movimiento de inventario"""
    inventario = get_object_or_404(Inventario, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        # Revertir stock
        revertir_stock(inventario)
        inventario.delete()
        messages.success(request, f'Movimiento de inventario eliminado exitosamente.')
        return redirect('inventario:inventario_list')
    
    context = {
        'inventario': inventario,
        'titulo': f'Eliminar Movimiento: {inventario.articulo.nombre}'
    }
    
    return render(request, 'inventario/inventario_confirm_delete.html', context)


@login_required
@requiere_empresa
def inventario_detail(request, pk):
    """Detalle de movimiento de inventario"""
    inventario = get_object_or_404(Inventario, pk=pk, empresa=request.empresa)
    
    context = {
        'inventario': inventario,
        'titulo': f'Detalle: {inventario.articulo.nombre}'
    }
    
    return render(request, 'inventario/inventario_detail.html', context)


@login_required
@requiere_empresa
def stock_list(request):
    """Lista el stock actual de todos los artículos"""
    stocks = Stock.objects.filter(empresa=request.empresa).select_related(
        'bodega', 'articulo', 'actualizado_por'
    ).order_by('articulo__nombre', 'bodega__nombre')
    
    # Filtros
    bodega_id = request.GET.get('bodega')
    if bodega_id:
        stocks = stocks.filter(bodega_id=bodega_id)
    
    # Paginación
    paginator = Paginator(stocks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    total_articulos = stocks.count()
    sin_stock = stocks.filter(cantidad__lte=0).count()
    stock_bajo = stocks.filter(
        cantidad__gt=0, 
        cantidad__lte=F('stock_minimo')
    ).count()
    
    context = {
        'page_obj': page_obj,
        'total_articulos': total_articulos,
        'sin_stock': sin_stock,
        'stock_bajo': stock_bajo,
        'titulo': 'Control de Stock'
    }
    
    return render(request, 'inventario/stock_list.html', context)


@login_required
@requiere_empresa
def stock_create(request):
    """Crear nuevo registro de stock"""
    if request.method == 'POST':
        form = StockForm(request.POST, empresa=request.empresa)
        if form.is_valid():
            stock = form.save(commit=False)
            stock.empresa = request.empresa
            stock.actualizado_por = request.user
            stock.save()
            
            messages.success(request, f'Stock creado exitosamente.')
            return redirect('inventario:stock_list')
    else:
        form = StockForm(empresa=request.empresa)
    
    context = {
        'form': form,
        'titulo': 'Nuevo Registro de Stock'
    }
    
    return render(request, 'inventario/stock_form.html', context)


@login_required
@requiere_empresa
def stock_update(request, pk):
    """Editar registro de stock"""
    stock = get_object_or_404(Stock, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = StockForm(request.POST, instance=stock, empresa=request.empresa)
        if form.is_valid():
            stock = form.save(commit=False)
            stock.actualizado_por = request.user
            stock.save()
            
            messages.success(request, f'Stock actualizado exitosamente.')
            return redirect('inventario:stock_list')
    else:
        form = StockForm(instance=stock, empresa=request.empresa)
    
    context = {
        'form': form,
        'stock': stock,
        'titulo': f'Editar Stock: {stock.articulo.nombre}'
    }
    
    return render(request, 'inventario/stock_form.html', context)


@login_required
@requiere_empresa
def stock_delete(request, pk):
    """Eliminar registro de stock"""
    stock = get_object_or_404(Stock, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        stock.delete()
        messages.success(request, f'Stock eliminado exitosamente.')
        return redirect('inventario:stock_list')
    
    context = {
        'stock': stock,
        'titulo': f'Eliminar Stock: {stock.articulo.nombre}'
    }
    
    return render(request, 'inventario/stock_confirm_delete.html', context)


@login_required
@requiere_empresa
def dashboard_inventario(request):
    """Dashboard principal del módulo de inventario"""
    # Estadísticas generales
    total_movimientos = Inventario.objects.filter(empresa=request.empresa).count()
    movimientos_hoy = Inventario.objects.filter(
        empresa=request.empresa,
        fecha_movimiento__date=timezone.now().date()
    ).count()
    
    # Stock bajo
    stock_bajo = Stock.objects.filter(
        empresa=request.empresa,
        cantidad__lte=F('stock_minimo'),
        cantidad__gt=0
    ).count()
    
    sin_stock = Stock.objects.filter(
        empresa=request.empresa,
        cantidad__lte=0
    ).count()
    
    # Movimientos recientes
    movimientos_recientes = Inventario.objects.filter(
        empresa=request.empresa
    ).select_related('bodega', 'articulo')[:10]
    
    # Artículos con stock bajo
    articulos_stock_bajo = Stock.objects.filter(
        empresa=request.empresa,
        cantidad__lte=F('stock_minimo')
    ).select_related('articulo', 'bodega')[:10]
    
    context = {
        'total_movimientos': total_movimientos,
        'movimientos_hoy': movimientos_hoy,
        'stock_bajo': stock_bajo,
        'sin_stock': sin_stock,
        'movimientos_recientes': movimientos_recientes,
        'articulos_stock_bajo': articulos_stock_bajo,
        'titulo': 'Dashboard de Inventario'
    }
    
    return render(request, 'inventario/dashboard.html', context)


def actualizar_stock(inventario):
    """Actualiza el stock después de un movimiento de inventario"""
    stock, created = Stock.objects.get_or_create(
        empresa=inventario.empresa,
        bodega=inventario.bodega,
        articulo=inventario.articulo,
        defaults={
            'cantidad': 0,
            'precio_promedio': inventario.precio_unitario
        }
    )
    
    if inventario.tipo_movimiento == 'entrada':
        # Calcular nuevo precio promedio
        if stock.cantidad > 0:
            total_actual = stock.cantidad * stock.precio_promedio
            total_nuevo = inventario.cantidad * inventario.precio_unitario
            stock.precio_promedio = (total_actual + total_nuevo) / (stock.cantidad + inventario.cantidad)
        else:
            stock.precio_promedio = inventario.precio_unitario
        
        stock.cantidad += inventario.cantidad
    elif inventario.tipo_movimiento == 'salida':
        stock.cantidad -= inventario.cantidad
    elif inventario.tipo_movimiento == 'ajuste':
        stock.cantidad = inventario.cantidad
        stock.precio_promedio = inventario.precio_unitario
    
    stock.save()


def revertir_stock(inventario):
    """Revierte el stock después de eliminar o modificar un movimiento"""
    try:
        stock = Stock.objects.get(
            empresa=inventario.empresa,
            bodega=inventario.bodega,
            articulo=inventario.articulo
        )
        
        if inventario.tipo_movimiento == 'entrada':
            stock.cantidad -= inventario.cantidad
        elif inventario.tipo_movimiento == 'salida':
            stock.cantidad += inventario.cantidad
        elif inventario.tipo_movimiento == 'ajuste':
            # Para ajustes, no revertimos automáticamente
            pass
        
        stock.save()
    except Stock.DoesNotExist:
        pass
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from django.utils import timezone
from .models import Inventario, Stock
from .forms import InventarioForm, StockForm, InventarioFilterForm
from core.decorators import requiere_empresa


@login_required
@requiere_empresa
def inventario_list(request):
    """Lista todos los movimientos de inventario"""
    inventarios = Inventario.objects.filter(empresa=request.empresa).select_related(
        'bodega', 'articulo', 'creado_por'
    ).order_by('-fecha_movimiento', '-fecha_creacion')
    
    # Filtros
    filter_form = InventarioFilterForm(request.GET, empresa=request.empresa)
    if filter_form.is_valid():
        bodega = filter_form.cleaned_data.get('bodega')
        articulo = filter_form.cleaned_data.get('articulo')
        tipo_movimiento = filter_form.cleaned_data.get('tipo_movimiento')
        estado = filter_form.cleaned_data.get('estado')
        fecha_desde = filter_form.cleaned_data.get('fecha_desde')
        fecha_hasta = filter_form.cleaned_data.get('fecha_hasta')
        
        if bodega:
            inventarios = inventarios.filter(bodega=bodega)
        if articulo:
            inventarios = inventarios.filter(articulo=articulo)
        if tipo_movimiento:
            inventarios = inventarios.filter(tipo_movimiento=tipo_movimiento)
        if estado:
            inventarios = inventarios.filter(estado=estado)
        if fecha_desde:
            inventarios = inventarios.filter(fecha_movimiento__date__gte=fecha_desde)
        if fecha_hasta:
            inventarios = inventarios.filter(fecha_movimiento__date__lte=fecha_hasta)
    
    # Paginación
    paginator = Paginator(inventarios, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    total_entradas = inventarios.filter(tipo_movimiento='entrada').aggregate(
        total=Sum('cantidad')
    )['total'] or 0
    total_salidas = inventarios.filter(tipo_movimiento='salida').aggregate(
        total=Sum('cantidad')
    )['total'] or 0
    valor_total = inventarios.aggregate(total=Sum('total'))['total'] or 0
    
    context = {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_entradas': total_entradas,
        'total_salidas': total_salidas,
        'valor_total': valor_total,
        'titulo': 'Movimientos de Inventario'
    }
    
    return render(request, 'inventario/inventario_list.html', context)


@login_required
@requiere_empresa
def inventario_create(request):
    """Crear nuevo movimiento de inventario"""
    if request.method == 'POST':
        form = InventarioForm(request.POST, empresa=request.empresa)
        if form.is_valid():
            inventario = form.save(commit=False)
            inventario.empresa = request.empresa
            inventario.creado_por = request.user
            inventario.save()
            
            # Actualizar stock
            actualizar_stock(inventario)
            
            messages.success(request, f'Movimiento de inventario creado exitosamente.')
            return redirect('inventario:inventario_list')
    else:
        form = InventarioForm(empresa=request.empresa)
        # Establecer fecha actual por defecto
        form.fields['fecha_movimiento'].initial = timezone.now()
    
    context = {
        'form': form,
        'titulo': 'Nuevo Movimiento de Inventario'
    }
    
    return render(request, 'inventario/inventario_form.html', context)


@login_required
@requiere_empresa
def inventario_update(request, pk):
    """Editar movimiento de inventario"""
    inventario = get_object_or_404(Inventario, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = InventarioForm(request.POST, instance=inventario, empresa=request.empresa)
        if form.is_valid():
            # Revertir stock anterior
            revertir_stock(inventario)
            
            inventario = form.save(commit=False)
            inventario.actualizado_por = request.user
            inventario.save()
            
            # Actualizar stock con nuevos valores
            actualizar_stock(inventario)
            
            messages.success(request, f'Movimiento de inventario actualizado exitosamente.')
            return redirect('inventario:inventario_list')
    else:
        form = InventarioForm(instance=inventario, empresa=request.empresa)
    
    context = {
        'form': form,
        'inventario': inventario,
        'titulo': f'Editar Movimiento: {inventario.articulo.nombre}'
    }
    
    return render(request, 'inventario/inventario_form.html', context)


@login_required
@requiere_empresa
def inventario_delete(request, pk):
    """Eliminar movimiento de inventario"""
    inventario = get_object_or_404(Inventario, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        # Revertir stock
        revertir_stock(inventario)
        inventario.delete()
        messages.success(request, f'Movimiento de inventario eliminado exitosamente.')
        return redirect('inventario:inventario_list')
    
    context = {
        'inventario': inventario,
        'titulo': f'Eliminar Movimiento: {inventario.articulo.nombre}'
    }
    
    return render(request, 'inventario/inventario_confirm_delete.html', context)


@login_required
@requiere_empresa
def inventario_detail(request, pk):
    """Detalle de movimiento de inventario"""
    inventario = get_object_or_404(Inventario, pk=pk, empresa=request.empresa)
    
    context = {
        'inventario': inventario,
        'titulo': f'Detalle: {inventario.articulo.nombre}'
    }
    
    return render(request, 'inventario/inventario_detail.html', context)


@login_required
@requiere_empresa
def stock_list(request):
    """Lista el stock actual de todos los artículos"""
    stocks = Stock.objects.filter(empresa=request.empresa).select_related(
        'bodega', 'articulo', 'actualizado_por'
    ).order_by('articulo__nombre', 'bodega__nombre')
    
    # Filtros
    bodega_id = request.GET.get('bodega')
    if bodega_id:
        stocks = stocks.filter(bodega_id=bodega_id)
    
    # Paginación
    paginator = Paginator(stocks, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    total_articulos = stocks.count()
    sin_stock = stocks.filter(cantidad__lte=0).count()
    stock_bajo = stocks.filter(
        cantidad__gt=0, 
        cantidad__lte=F('stock_minimo')
    ).count()
    
    context = {
        'page_obj': page_obj,
        'total_articulos': total_articulos,
        'sin_stock': sin_stock,
        'stock_bajo': stock_bajo,
        'titulo': 'Control de Stock'
    }
    
    return render(request, 'inventario/stock_list.html', context)


@login_required
@requiere_empresa
def stock_create(request):
    """Crear nuevo registro de stock"""
    if request.method == 'POST':
        form = StockForm(request.POST, empresa=request.empresa)
        if form.is_valid():
            stock = form.save(commit=False)
            stock.empresa = request.empresa
            stock.actualizado_por = request.user
            stock.save()
            
            messages.success(request, f'Stock creado exitosamente.')
            return redirect('inventario:stock_list')
    else:
        form = StockForm(empresa=request.empresa)
    
    context = {
        'form': form,
        'titulo': 'Nuevo Registro de Stock'
    }
    
    return render(request, 'inventario/stock_form.html', context)


@login_required
@requiere_empresa
def stock_update(request, pk):
    """Editar registro de stock"""
    stock = get_object_or_404(Stock, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        form = StockForm(request.POST, instance=stock, empresa=request.empresa)
        if form.is_valid():
            stock = form.save(commit=False)
            stock.actualizado_por = request.user
            stock.save()
            
            messages.success(request, f'Stock actualizado exitosamente.')
            return redirect('inventario:stock_list')
    else:
        form = StockForm(instance=stock, empresa=request.empresa)
    
    context = {
        'form': form,
        'stock': stock,
        'titulo': f'Editar Stock: {stock.articulo.nombre}'
    }
    
    return render(request, 'inventario/stock_form.html', context)


@login_required
@requiere_empresa
def stock_delete(request, pk):
    """Eliminar registro de stock"""
    stock = get_object_or_404(Stock, pk=pk, empresa=request.empresa)
    
    if request.method == 'POST':
        stock.delete()
        messages.success(request, f'Stock eliminado exitosamente.')
        return redirect('inventario:stock_list')
    
    context = {
        'stock': stock,
        'titulo': f'Eliminar Stock: {stock.articulo.nombre}'
    }
    
    return render(request, 'inventario/stock_confirm_delete.html', context)


@login_required
@requiere_empresa
def dashboard_inventario(request):
    """Dashboard principal del módulo de inventario"""
    # Estadísticas generales
    total_movimientos = Inventario.objects.filter(empresa=request.empresa).count()
    movimientos_hoy = Inventario.objects.filter(
        empresa=request.empresa,
        fecha_movimiento__date=timezone.now().date()
    ).count()
    
    # Stock bajo
    stock_bajo = Stock.objects.filter(
        empresa=request.empresa,
        cantidad__lte=F('stock_minimo'),
        cantidad__gt=0
    ).count()
    
    sin_stock = Stock.objects.filter(
        empresa=request.empresa,
        cantidad__lte=0
    ).count()
    
    # Movimientos recientes
    movimientos_recientes = Inventario.objects.filter(
        empresa=request.empresa
    ).select_related('bodega', 'articulo')[:10]
    
    # Artículos con stock bajo
    articulos_stock_bajo = Stock.objects.filter(
        empresa=request.empresa,
        cantidad__lte=F('stock_minimo')
    ).select_related('articulo', 'bodega')[:10]
    
    context = {
        'total_movimientos': total_movimientos,
        'movimientos_hoy': movimientos_hoy,
        'stock_bajo': stock_bajo,
        'sin_stock': sin_stock,
        'movimientos_recientes': movimientos_recientes,
        'articulos_stock_bajo': articulos_stock_bajo,
        'titulo': 'Dashboard de Inventario'
    }
    
    return render(request, 'inventario/dashboard.html', context)


def actualizar_stock(inventario):
    """Actualiza el stock después de un movimiento de inventario"""
    stock, created = Stock.objects.get_or_create(
        empresa=inventario.empresa,
        bodega=inventario.bodega,
        articulo=inventario.articulo,
        defaults={
            'cantidad': 0,
            'precio_promedio': inventario.precio_unitario
        }
    )
    
    if inventario.tipo_movimiento == 'entrada':
        # Calcular nuevo precio promedio
        if stock.cantidad > 0:
            total_actual = stock.cantidad * stock.precio_promedio
            total_nuevo = inventario.cantidad * inventario.precio_unitario
            stock.precio_promedio = (total_actual + total_nuevo) / (stock.cantidad + inventario.cantidad)
        else:
            stock.precio_promedio = inventario.precio_unitario
        
        stock.cantidad += inventario.cantidad
    elif inventario.tipo_movimiento == 'salida':
        stock.cantidad -= inventario.cantidad
    elif inventario.tipo_movimiento == 'ajuste':
        stock.cantidad = inventario.cantidad
        stock.precio_promedio = inventario.precio_unitario
    
    stock.save()


def revertir_stock(inventario):
    """Revierte el stock después de eliminar o modificar un movimiento"""
    try:
        stock = Stock.objects.get(
            empresa=inventario.empresa,
            bodega=inventario.bodega,
            articulo=inventario.articulo
        )
        
        if inventario.tipo_movimiento == 'entrada':
            stock.cantidad -= inventario.cantidad
        elif inventario.tipo_movimiento == 'salida':
            stock.cantidad += inventario.cantidad
        elif inventario.tipo_movimiento == 'ajuste':
            # Para ajustes, no revertimos automáticamente
            pass
        
        stock.save()
    except Stock.DoesNotExist:
        pass

