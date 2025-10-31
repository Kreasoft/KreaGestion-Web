from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from collections import defaultdict
from decimal import Decimal
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
@permission_required('inventario.view_movimientoinventario', raise_exception=True)
def inventario_list(request):
    """Lista todos los movimientos de inventario"""
    inventarios = Inventario.objects.filter(empresa=request.empresa).select_related(
        'bodega_destino', 'articulo', 'creado_por'
    ).order_by('-fecha_movimiento', '-fecha_creacion')
    
    # Filtros
    filter_form = InventarioFilterForm(request.GET, empresa=request.empresa)
    if filter_form.is_valid():
        bodega = filter_form.cleaned_data.get('bodega_destino')
        articulo = filter_form.cleaned_data.get('articulo')
        tipo_movimiento = filter_form.cleaned_data.get('tipo_movimiento')
        estado = filter_form.cleaned_data.get('estado')
        fecha_desde = filter_form.cleaned_data.get('fecha_desde')
        fecha_hasta = filter_form.cleaned_data.get('fecha_hasta')
        
        if bodega:
            inventarios = inventarios.filter(Q(bodega_origen=bodega) | Q(bodega_destino=bodega))
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
@permission_required('articulos.view_stockarticulo', raise_exception=True)
def stock_list(request):
    """Lista el stock actual de todos los artículos"""
    stocks = Stock.objects.filter(empresa=request.empresa).select_related(
        'bodega_destino', 'articulo', 'actualizado_por'
    ).order_by('articulo__nombre', 'bodega__nombre')
    
    # Filtros
    bodega_id = request.GET.get('bodega_destino')
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
    ).select_related('bodega_destino', 'articulo')[:10]
    
    # Artículos con stock bajo
    articulos_stock_bajo = Stock.objects.filter(
        empresa=request.empresa,
        cantidad__lte=F('stock_minimo')
    ).select_related('articulo', 'bodega_destino')[:10]
    
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
    """Actualiza el stock después de un movimiento de inventario, respetando origen/destino."""
    empresa = inventario.empresa
    articulo = inventario.articulo
    cantidad = inventario.cantidad
    precio = inventario.precio_unitario

    def get_stock(bodega):
        s, _ = Stock.objects.get_or_create(
            empresa=empresa,
            bodega=bodega,
            articulo=articulo,
            defaults={'cantidad': 0, 'precio_promedio': precio}
        )
        return s

    t = (inventario.tipo_movimiento or '').lower()
    if t == 'entrada':
        if inventario.bodega_destino:
            s = get_stock(inventario.bodega_destino)
            if s.cantidad > 0:
                total_actual = s.cantidad * s.precio_promedio
                total_nuevo = cantidad * precio
                s.precio_promedio = (total_actual + total_nuevo) / (s.cantidad + cantidad)
            else:
                s.precio_promedio = precio
            s.cantidad += cantidad
            s.save()
    elif t == 'salida':
        if inventario.bodega_origen:
            s = get_stock(inventario.bodega_origen)
            s.cantidad -= cantidad
            s.save()
    elif t == 'ajuste':
        # Se aplica como ajuste sobre la bodega seleccionada (preferir destino)
        b = inventario.bodega_destino or inventario.bodega_origen
        if b:
            s = get_stock(b)
            s.cantidad = cantidad
            s.precio_promedio = precio
            s.save()
    elif t == 'transferencia':
        # Restar del origen y sumar al destino
        if inventario.bodega_origen:
            so = get_stock(inventario.bodega_origen)
            so.cantidad -= cantidad
            so.save()
        if inventario.bodega_destino:
            sd = get_stock(inventario.bodega_destino)
            # Mantener precio promedio; si no hay, usar del origen o precio informado
            origen_pp = None
            try:
                origen_pp = Stock.objects.get(empresa=empresa, bodega=inventario.bodega_origen, articulo=articulo).precio_promedio
            except Stock.DoesNotExist:
                origen_pp = precio
            if sd.cantidad > 0:
                total_actual = sd.cantidad * sd.precio_promedio
                total_nuevo = cantidad * (origen_pp or precio)
                sd.precio_promedio = (total_actual + total_nuevo) / (sd.cantidad + cantidad)
            else:
                sd.precio_promedio = origen_pp or precio
            sd.cantidad += cantidad
            sd.save()


def revertir_stock(inventario):
    """Revierte el impacto del movimiento en el stock."""
    empresa = inventario.empresa
    articulo = inventario.articulo
    cantidad = inventario.cantidad
    t = (inventario.tipo_movimiento or '').lower()
    try:
        if t == 'entrada' and inventario.bodega_destino:
            s = Stock.objects.get(empresa=empresa, bodega=inventario.bodega_destino, articulo=articulo)
            s.cantidad -= cantidad
            s.save()
        elif t == 'salida' and inventario.bodega_origen:
            s = Stock.objects.get(empresa=empresa, bodega=inventario.bodega_origen, articulo=articulo)
            s.cantidad += cantidad
            s.save()
        elif t == 'transferencia':
            if inventario.bodega_origen:
                so = Stock.objects.get(empresa=empresa, bodega=inventario.bodega_origen, articulo=articulo)
                so.cantidad += cantidad
                so.save()
            if inventario.bodega_destino:
                sd = Stock.objects.get(empresa=empresa, bodega=inventario.bodega_destino, articulo=articulo)
                sd.cantidad -= cantidad
                sd.save()
        elif t == 'ajuste':
            # No revertimos ajustes automáticamente
            pass
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
        'bodega_destino', 'articulo', 'creado_por'
    ).order_by('-fecha_movimiento', '-fecha_creacion')
    
    # Filtros
    filter_form = InventarioFilterForm(request.GET, empresa=request.empresa)
    if filter_form.is_valid():
        bodega = filter_form.cleaned_data.get('bodega_destino')
        articulo = filter_form.cleaned_data.get('articulo')
        tipo_movimiento = filter_form.cleaned_data.get('tipo_movimiento')
        estado = filter_form.cleaned_data.get('estado')
        fecha_desde = filter_form.cleaned_data.get('fecha_desde')
        fecha_hasta = filter_form.cleaned_data.get('fecha_hasta')
        
        if bodega:
            inventarios = inventarios.filter(Q(bodega_origen=bodega) | Q(bodega_destino=bodega))
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
def inventario_detail_modal(request, pk):
    """Retorna el detalle del movimiento para modal via AJAX."""
    inventario = get_object_or_404(Inventario, pk=pk, empresa=request.empresa)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        html = render_to_string(
            'inventario/partials/inventario_detail_content.html',
            {'inventario': inventario},
            request=request
        )
        return JsonResponse({'html': html})

    return redirect('inventario:inventario_detail', pk=pk)


@login_required
@requiere_empresa
def inventario_form_modal(request, pk=None):
    """Renderizar o procesar formulario de inventario para modal via AJAX."""
    inventario = None
    if pk:
        inventario = get_object_or_404(Inventario, pk=pk, empresa=request.empresa)

    if request.method == 'POST':
        form = InventarioForm(request.POST, instance=inventario, empresa=request.empresa)
        if form.is_valid():
            with transaction.atomic():
                if inventario:
                    revertir_stock(inventario)

                movimiento = form.save(commit=False)
                movimiento.empresa = request.empresa
                if inventario:
                    movimiento.actualizado_por = request.user
                else:
                    movimiento.creado_por = request.user
                movimiento.save()

                actualizar_stock(movimiento)

            return JsonResponse({'success': True})
        html = render_to_string(
            'inventario/partials/inventario_form_modal.html',
            {
                'form': form,
                'submit_text': 'Actualizar Movimiento' if pk else 'Guardar Movimiento',
                'action_url': request.path
            },
            request=request
        )
        return JsonResponse({'success': False, 'html': html}, status=400)

    form = InventarioForm(instance=inventario, empresa=request.empresa)
    html = render_to_string(
        'inventario/partials/inventario_form_modal.html',
        {
            'form': form,
            'submit_text': 'Actualizar Movimiento' if pk else 'Guardar Movimiento',
            'action_url': request.path
        },
        request=request
    )
    return JsonResponse({'html': html})


@login_required
@requiere_empresa
def stock_list(request):
    """Lista el stock actual de todos los artículos, mostrando también los que no tienen registro (0)."""
    from bodegas.models import Bodega
    
    # Base: artículos activos y bodegas activas para construir vista completa artículo×bodega
    articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).select_related('categoria').order_by('nombre')
    bodegas = Bodega.objects.filter(empresa=request.empresa)
    
    # Calcular cantidades desde movimientos de Inventario (estado confirmado), por artículo×bodega
    mov_rows = (
        Inventario.objects
        .filter(empresa=request.empresa, estado='confirmado')
        .values('articulo_id', 'tipo_movimiento', 'cantidad', 'bodega_origen_id', 'bodega_destino_id')
    )
    cantidad_map = defaultdict(Decimal)
    for r in mov_rows:
        art_id = r['articulo_id']
        t = (r['tipo_movimiento'] or '').lower()
        qty = Decimal(r['cantidad'] or 0)
        if t == 'entrada':
            bid = r['bodega_destino_id']
            if bid:
                cantidad_map[(art_id, bid)] += qty
        elif t == 'salida':
            bid = r['bodega_origen_id']
            if bid:
                cantidad_map[(art_id, bid)] -= qty
        elif t == 'ajuste':
            bid = r['bodega_destino_id']
            if bid:
                # Puede ser negativo o positivo; se suma directo al destino
                cantidad_map[(art_id, bid)] += qty
        elif t == 'transferencia':
            bid_o = r['bodega_origen_id']
            bid_d = r['bodega_destino_id']
            if bid_o:
                cantidad_map[(art_id, bid_o)] -= qty
            if bid_d:
                cantidad_map[(art_id, bid_d)] += qty
        else:
            # Tipos desconocidos: ignorar
            pass

    # Construir lista de stocks incluyendo ceros cuando no existe registro
    stocks_data = []
    existing_qs = Stock.objects.filter(empresa=request.empresa).select_related('bodega', 'articulo')
    # Índice rápido articulo-bodega -> Stock
    existing_map = {(s.articulo_id, s.bodega_id): s for s in existing_qs}
    for articulo in articulos:
        for bodega in bodegas:
            s = existing_map.get((articulo.id, bodega.id))
            if s:
                # Sobrescribir cantidad mostrada con cálculo por movimientos
                s.cantidad = cantidad_map.get((articulo.id, bodega.id), Decimal(0))
                stocks_data.append(s)
            else:
                # Crear objeto Stock en memoria (no persistente) con cantidad=0
                s0 = Stock(
                    empresa=request.empresa,
                    bodega=bodega,
                    articulo=articulo,
                    cantidad=cantidad_map.get((articulo.id, bodega.id), Decimal(0)),
                    stock_minimo=0,
                    stock_maximo=0,
                )
                stocks_data.append(s0)
    
    # Filtros GET
    bodega_id = request.GET.get('bodega')
    estado = request.GET.get('estado')
    search = request.GET.get('search', '')
    tipo_articulo = request.GET.get('tipo_articulo', '')
    
    if bodega_id:
        try:
            bodega_id_int = int(bodega_id)
            stocks_data = [s for s in stocks_data if s.bodega and s.bodega.id == bodega_id_int]
        except ValueError:
            pass
    
    if estado == 'sin_stock':
        stocks_data = [s for s in stocks_data if (s.cantidad or 0) <= 0]
    elif estado == 'bajo':
        stocks_data = [s for s in stocks_data if (s.cantidad or 0) > 0 and (s.cantidad or 0) <= (s.stock_minimo or 0)]
    elif estado == 'normal':
        stocks_data = [s for s in stocks_data if (s.cantidad or 0) > (s.stock_minimo or 0)]
    
    if tipo_articulo:
        stocks_data = [s for s in stocks_data if getattr(s.articulo, 'tipo_articulo', '') == tipo_articulo]
    
    if search:
        q = search.lower()
        stocks_data = [
            s for s in stocks_data
            if q in (s.articulo.codigo or '').lower() or q in (s.articulo.nombre or '').lower()
        ]
    
    # Estadísticas básicas sobre el conjunto filtrado
    total_articulos = len(stocks_data)
    sin_stock = sum(1 for s in stocks_data if (s.cantidad or 0) <= 0)
    stock_bajo = sum(1 for s in stocks_data if (s.cantidad or 0) > 0 and (s.cantidad or 0) <= (s.stock_minimo or 0))
    stock_normal = sum(1 for s in stocks_data if (s.cantidad or 0) > (s.stock_minimo or 0))
    
    # Paginación
    paginator = Paginator(stocks_data, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'bodegas': bodegas,
        'total_articulos': total_articulos,
        'sin_stock': sin_stock,
        'stock_bajo': stock_bajo,
        'stock_normal': stock_normal,
        'titulo': 'Control de Stock',
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
    ).select_related('bodega_destino', 'articulo')[:10]
    
    # Artículos con stock bajo
    articulos_stock_bajo = Stock.objects.filter(
        empresa=request.empresa,
        cantidad__lte=F('stock_minimo')
    ).select_related('articulo', 'bodega_destino')[:10]
    
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

