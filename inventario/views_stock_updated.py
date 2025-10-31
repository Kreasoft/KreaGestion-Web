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
from bodegas.models import Bodega


@login_required
@requiere_empresa
def stock_list(request):
    """Lista el stock actual de todos los artículos activos"""
    # Obtener todos los artículos activos de la empresa
    articulos_activos = Articulo.objects.filter(
        empresa=request.empresa, 
        activo=True
    ).order_by('nombre')
    
    # Obtener todas las bodegas activas
    bodegas_activas = Bodega.objects.filter(
        empresa=request.empresa,
        activa=True
    )
    
    # Crear una lista de todos los artículos con su stock por bodega
    stocks_data = []
    
    for articulo in articulos_activos:
        for bodega in bodegas_activas:
            # Buscar si existe stock para este artículo en esta bodega
            stock_existente = Stock.objects.filter(
                empresa=request.empresa,
                articulo=articulo,
                bodega=bodega
            ).first()
            
            if stock_existente:
                # Usar el stock existente
                stocks_data.append(stock_existente)
            else:
                # Crear un registro de stock con cantidad 0 para artículos sin stock
                stock_vacio = Stock(
                    empresa=request.empresa,
                    articulo=articulo,
                    bodega=bodega,
                    cantidad=0,
                    stock_minimo=0,
                    stock_maximo=0
                )
                stocks_data.append(stock_vacio)
    
    # Convertir a queryset para mantener compatibilidad con filtros
    from django.db.models import QuerySet
    stocks = QuerySet(model=Stock)
    stocks._result_cache = stocks_data
    
    # Aplicar filtros a la lista de datos
    bodega_id = request.GET.get('bodega')
    estado = request.GET.get('estado')
    search = request.GET.get('search')
    
    # Filtrar por bodega
    if bodega_id:
        stocks_data = [s for s in stocks_data if s.bodega.id == int(bodega_id)]
    
    # Filtrar por estado
    if estado == 'sin_stock':
        stocks_data = [s for s in stocks_data if s.cantidad <= 0]
    elif estado == 'bajo':
        stocks_data = [s for s in stocks_data if s.cantidad > 0 and s.cantidad <= s.stock_minimo]
    elif estado == 'normal':
        stocks_data = [s for s in stocks_data if s.cantidad > s.stock_minimo]
    
    # Filtrar por búsqueda
    if search:
        search_lower = search.lower()
        stocks_data = [s for s in stocks_data if 
                      search_lower in s.articulo.nombre.lower() or
                      search_lower in s.articulo.codigo.lower() or
                      search_lower in s.bodega.nombre.lower()]
    
    # Actualizar el queryset con los datos filtrados
    stocks._result_cache = stocks_data
    
    # Paginación
    paginator = Paginator(stocks, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas basadas en todos los artículos activos
    total_articulos = len(articulos_activos)
    
    # Contar artículos por estado de stock
    sin_stock = 0
    stock_bajo = 0
    stock_normal = 0
    
    for articulo in articulos_activos:
        # Obtener stock total del artículo
        stock_total = Stock.objects.filter(
            empresa=request.empresa,
            articulo=articulo
        ).aggregate(total=Sum('cantidad'))['total'] or 0
        
        if stock_total <= 0:
            sin_stock += 1
        else:
            # Obtener stock mínimo del artículo (el más bajo de todas las bodegas)
            stock_minimo = Stock.objects.filter(
                empresa=request.empresa,
                articulo=articulo
            ).aggregate(minimo=Sum('stock_minimo'))['minimo'] or 0
            
            if stock_total <= stock_minimo:
                stock_bajo += 1
            else:
                stock_normal += 1
    
    # Obtener bodegas para el filtro
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True)
    
    context = {
        'page_obj': page_obj,
        'total_articulos': total_articulos,
        'sin_stock': sin_stock,
        'stock_bajo': stock_bajo,
        'stock_normal': stock_normal,
        'bodegas': bodegas,
        'titulo': 'Control de Stock'
    }
    
    return render(request, 'inventario/stock_list.html', context)
