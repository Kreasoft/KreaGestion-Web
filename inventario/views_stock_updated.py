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
from usuarios.decorators import requiere_empresa
from articulos.models import Articulo
from bodegas.models import Bodega


@login_required
@requiere_empresa
def stock_list(request):
    """Lista el stock actual de todos los artículos"""
    stocks = Stock.objects.filter(empresa=request.empresa).select_related(
        'bodega', 'articulo', 'actualizado_por'
    ).order_by('articulo__nombre', 'bodega__nombre')
    
    # Filtros
    bodega_id = request.GET.get('bodega')
    estado = request.GET.get('estado')
    search = request.GET.get('search')
    
    if bodega_id:
        stocks = stocks.filter(bodega_id=bodega_id)
    
    if estado == 'sin_stock':
        stocks = stocks.filter(cantidad__lte=0)
    elif estado == 'bajo':
        stocks = stocks.filter(cantidad__gt=0, cantidad__lte=F('stock_minimo'))
    elif estado == 'normal':
        stocks = stocks.filter(cantidad__gt=F('stock_minimo'))
    
    if search:
        stocks = stocks.filter(
            Q(articulo__nombre__icontains=search) |
            Q(articulo__codigo__icontains=search) |
            Q(bodega__nombre__icontains=search)
        )
    
    # Paginación
    paginator = Paginator(stocks, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas (usar el queryset original sin filtros para estadísticas globales)
    all_stocks = Stock.objects.filter(empresa=request.empresa)
    total_articulos = all_stocks.count()
    sin_stock = all_stocks.filter(cantidad__lte=0).count()
    stock_bajo = all_stocks.filter(
        cantidad__gt=0, 
        cantidad__lte=F('stock_minimo')
    ).count()
    stock_normal = all_stocks.filter(cantidad__gt=F('stock_minimo')).count()
    
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
