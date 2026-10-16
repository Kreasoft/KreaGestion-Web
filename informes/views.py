from utilidades.utils import clean_id
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Avg, F, Q, DecimalField
from django.db.models.functions import TruncDate, TruncMonth, Cast
from datetime import datetime, timedelta
from decimal import Decimal
import json

from empresas.models import Empresa
from ventas.models import Venta, VentaDetalle
from inventario.models import Stock
from tesoreria.models import DocumentoCliente, PagoDocumentoCliente, MovimientoCuentaCorrienteCliente
from caja.models import AperturaCaja
from documentos.models import DocumentoCompra
from core.decorators import requiere_empresa
from core.excel_utils import (
    build_excel_response,
    finalize_excel_table,
    format_excel_date,
    set_column_widths,
    setup_corporate_sheet,
    style_data_row,
    write_table_headers,
)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO

# Importar funciones de exportación adicionales
from .exportaciones import (
    exportar_cuentas_cobrar_excel,
    exportar_cuentas_pagar_excel,
    exportar_pagos_recibidos_excel,
    exportar_stock_bajo_excel,
    exportar_cierres_caja_excel,
    exportar_compras_periodo_excel,
    exportar_utilidad_familias_excel,
    exportar_categorias_excel,
    exportar_utilidad_articulos_excel
)


@login_required
@requiere_empresa
def dashboard_informes(request):
    """Dashboard principal de informes con BI Gerencial"""
    hoy = datetime.now().date()
    inicio_mes = hoy.replace(day=1)
    
    # Ventas Mes Actual
    ventas_mes = Venta.objects.filter(
        empresa=request.empresa,
        fecha__gte=inicio_mes,
        fecha__lte=hoy,
        estado='confirmada'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    # Ventas Mes Anterior (mismo rango de días para comparación justa)
    inicio_mes_anterior = (inicio_mes - timedelta(days=1)).replace(day=1)
    fin_mes_anterior = inicio_mes - timedelta(days=1)
    # Ajustar fin mes anterior al mismo día relativo si es posible
    dia_relativo = hoy.day
    try:
        fin_mes_anterior_relativo = inicio_mes_anterior.replace(day=dia_relativo)
    except ValueError:
        # Si el mes anterior tiene menos días
        fin_mes_anterior_relativo = fin_mes_anterior
        
    ventas_mes_anterior = Venta.objects.filter(
        empresa=request.empresa,
        fecha__gte=inicio_mes_anterior,
        fecha__lte=fin_mes_anterior_relativo,
        estado='confirmada'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    # Variación
    if ventas_mes_anterior > 0:
        variacion = ((ventas_mes - ventas_mes_anterior) / ventas_mes_anterior) * 100
    else:
        variacion = 100 if ventas_mes > 0 else 0
        
    # Top 5 Productos (Cantidad)
    top_productos_raw = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__fecha__gte=inicio_mes,
        venta__estado='confirmada'
    ).values('articulo__nombre').annotate(
        total_qty=Sum('cantidad')
    ).order_by('-total_qty')[:5]
    
    top_productos_labels = [p['articulo__nombre'] for p in top_productos_raw]
    top_productos_values = [float(p['total_qty']) for p in top_productos_raw]
    
    # Ventas Diarias (Últimos 15 días)
    hace_15_dias = hoy - timedelta(days=14)
    ventas_diarias_raw = Venta.objects.filter(
        empresa=request.empresa,
        fecha__gte=hace_15_dias,
        estado='confirmada'
    ).values('fecha').annotate(
        total=Sum('total')
    ).order_by('fecha')
    
    # Llenar huecos de días sin ventas
    fechas = []
    totales_diarios = []
    curr = hace_15_dias
    ventas_dict = { v['fecha']: float(v['total']) for v in ventas_diarias_raw }
    while curr <= hoy:
        fechas.append(curr.strftime('%d-%m'))
        totales_diarios.append(ventas_dict.get(curr, 0))
        curr += timedelta(days=1)
        
    # Ventas por Vendedor
    ventas_vendedor_raw = Venta.objects.filter(
        empresa=request.empresa,
        fecha__gte=inicio_mes,
        estado='confirmada',
        vendedor__isnull=False
    ).values('vendedor__nombre').annotate(
        total=Sum('total')
    ).order_by('-total')[:5]
    
    vendedor_labels = [v['vendedor__nombre'] for v in ventas_vendedor_raw]
    vendedor_values = [float(v['total']) for v in ventas_vendedor_raw]

    # ---------------------------
    # DATOS PARA BI GERENCIAL
    # ---------------------------
    
    # 1. Ventas por Categoría (Mes Actual)
    ventas_categoria_raw = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__fecha__gte=inicio_mes,
        venta__estado='confirmada'
    ).values('articulo__categoria__nombre').annotate(
        total=Sum('precio_total')
    ).order_by('-total')
    
    cat_labels = [c['articulo__categoria__nombre'] or 'Sin Categoría' for c in ventas_categoria_raw]
    cat_values = [float(c['total']) for c in ventas_categoria_raw]

    # 2. Comparativa Mensual (Últimos 12 meses)
    hace_12_meses = (hoy - timedelta(days=365)).replace(day=1)
    ventas_mensuales_raw = Venta.objects.filter(
        empresa=request.empresa,
        fecha__gte=hace_12_meses,
        estado='confirmada'
    ).annotate(mes=TruncMonth('fecha')).values('mes').annotate(
        total=Sum('total')
    ).order_by('mes')
    
    mensual_labels = []
    mensual_values = []
    meses_nombres = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    
    # Asegurar que mostramos los 12 meses aunque no haya ventas
    mes_dict = { v['mes'].strftime('%Y-%m'): float(v['total']) for v in ventas_mensuales_raw }
    curr_mes = hace_12_meses
    while curr_mes <= hoy:
        key = curr_mes.strftime('%Y-%m')
        mensual_labels.append(f"{meses_nombres[curr_mes.month-1]} {curr_mes.year}")
        mensual_values.append(mes_dict.get(key, 0))
        # Incrementar un mes
        if curr_mes.month == 12:
            curr_mes = curr_mes.replace(year=curr_mes.year + 1, month=1)
        else:
            curr_mes = curr_mes.replace(month=curr_mes.month + 1)

    # 3. Comparativa Anual (Año Actual vs Año Anterior)
    anio_actual = hoy.year
    anio_anterior = anio_actual - 1
    
    ventas_anio_actual = Venta.objects.filter(
        empresa=request.empresa,
        fecha__year=anio_actual,
        estado='confirmada'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    ventas_anio_anterior = Venta.objects.filter(
        empresa=request.empresa,
        fecha__year=anio_anterior,
        estado='confirmada'
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')

    # Cumplimiento de meta (Año actual vs Año anterior)
    cumplimiento_meta = 0
    if ventas_anio_anterior > 0:
        cumplimiento_meta = (ventas_anio_actual / ventas_anio_anterior) * 100

    context = {
        'ventas_mes': float(ventas_mes),
        'ventas_mes_anterior': float(ventas_mes_anterior),
        'variacion': float(variacion),
        'top_productos_labels': json.dumps(top_productos_labels),
        'top_productos_values': json.dumps(top_productos_values),
        'ventas_diarias_labels': json.dumps(fechas),
        'ventas_diarias_values': json.dumps(totales_diarios),
        'vendedor_labels': json.dumps(vendedor_labels),
        'vendedor_values': json.dumps(vendedor_values),
        'cat_labels': json.dumps(cat_labels),
        'cat_values': json.dumps(cat_values),
        'mensual_labels': json.dumps(mensual_labels),
        'mensual_values': json.dumps(mensual_values),
        'ventas_anio_actual': float(ventas_anio_actual),
        'ventas_anio_anterior': float(ventas_anio_anterior),
        'cumplimiento_meta': float(cumplimiento_meta),
        'anio_actual': anio_actual,
        'anio_anterior': anio_anterior,
    }
    
    return render(request, 'informes/dashboard.html', context)


# ==================== INFORMES DE VENTAS ====================

@login_required
@requiere_empresa
def informe_ventas_periodo(request):
    """Informe de ventas por período"""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde or not fecha_hasta:
        # Por defecto: último mes
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    # Obtener ventas del período
    ventas_query = Venta.objects.filter(
        empresa=request.empresa,
        fecha__gte=fecha_desde,
        fecha__lte=fecha_hasta,
        estado='confirmada'
    ).order_by('fecha')
    
    # Agrupar por fecha manualmente
    ventas_por_fecha = {}
    for venta in ventas_query:
        fecha_key = venta.fecha
        if fecha_key not in ventas_por_fecha:
            ventas_por_fecha[fecha_key] = {
                'fecha_solo': fecha_key,
                'total_ventas': 0,
                'cantidad_ventas': 0
            }
        ventas_por_fecha[fecha_key]['total_ventas'] += float(venta.total)
        ventas_por_fecha[fecha_key]['cantidad_ventas'] += 1
    
    # Convertir a lista ordenada y calcular promedios
    ventas = sorted(ventas_por_fecha.values(), key=lambda x: x['fecha_solo'])
    
    # Calcular totales
    total_general = sum(v['total_ventas'] for v in ventas)
    cantidad_total = sum(v['cantidad_ventas'] for v in ventas)
    ticket_promedio = total_general / cantidad_total if cantidad_total > 0 else 0
    
    # Agregar ticket promedio a cada venta
    for venta in ventas:
        venta['ticket_promedio'] = venta['total_ventas'] / venta['cantidad_ventas'] if venta['cantidad_ventas'] > 0 else 0
    
    context = {
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'ventas': ventas,
        'total_general': total_general,
        'cantidad_total': cantidad_total,
        'ticket_promedio': ticket_promedio
    }
    
    return render(request, 'informes/ventas_periodo.html', context)


@login_required
@requiere_empresa
def informe_ventas_vendedor(request):
    """Informe de ventas por vendedor"""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    # Usar vendedor en lugar de usuario_creacion
    ventas_vendedor = Venta.objects.filter(
        empresa=request.empresa,
        fecha__range=[fecha_desde, fecha_hasta],
        estado='confirmada',
        vendedor__isnull=False
    ).values(
        'vendedor__codigo',
        'vendedor__nombre'
    ).annotate(
        total_ventas=Sum('total'),
        cantidad_ventas=Count('id'),
        ticket_promedio=Avg('total')
    ).order_by('-total_ventas')
    
    context = {
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'ventas_vendedor': ventas_vendedor
    }
    
    return render(request, 'informes/ventas_vendedor.html', context)


@login_required
@requiere_empresa
def informe_productos_vendidos(request):
    """Informe de productos más vendidos"""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    productos = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__fecha__range=[fecha_desde, fecha_hasta],
        venta__estado='confirmada'
    ).values(
        'articulo__nombre',
        'articulo__codigo'
    ).annotate(
        cantidad_vendida=Sum('cantidad'),
        total_vendido=Sum('precio_total')
    ).order_by('-cantidad_vendida')[:50]
    
    context = {
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'productos': productos
    }
    
    return render(request, 'informes/productos_vendidos.html', context)


# ==================== INFORMES DE INVENTARIO ====================

@login_required
@requiere_empresa
def informe_stock_actual(request):
    """Informe de stock actual por bodega"""
    from inventario.models import Stock
    from bodegas.models import Bodega
    from articulos.models import CategoriaArticulo
    from decimal import Decimal
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    bodega_id = clean_id(clean_id(request.GET.get('bodega'))) # Changed from bodega_id to match template standard usually or keep as is but clarify param
    categoria_id = clean_id(clean_id(request.GET.get('categoria')))
    search = request.GET.get('search', '')
    
    stocks = Stock.objects.filter(
        bodega__empresa=request.empresa
    ).select_related('articulo', 'bodega').order_by('bodega__nombre', 'articulo__nombre')
    
    if bodega_id:
        stocks = stocks.filter(bodega_id=bodega_id)
        
    if categoria_id:
        stocks = stocks.filter(articulo__categoria_id=categoria_id)
        
    if search:
        stocks = stocks.filter(
            Q(articulo__nombre__icontains=search) | 
            Q(articulo__codigo__icontains=search)
        )
    
    # Calcular valorización y agregar a cada stock
    stocks_list = []
    total_valorizacion = Decimal('0')
    articulos_unicos = set()  # Para contar artículos únicos
    
    # We need to iterate over all filtered stocks to calculate totals correctly BEFORE pagination if we want accurate totals for the whole set
    # OR we calculate totals on the queryset using aggregate if possible, but price_avg * qty calculation is row-based.
    # Given the previous implementation iterated, we'll iterate.
    
    for stock in stocks:
        # Obtener precio promedio (puede ser None o 0)
        precio_promedio = stock.precio_promedio or Decimal('0')
        cantidad = Decimal(str(stock.cantidad))
        
        # Calcular valorización
        valorizacion = cantidad * precio_promedio
        stock.valorizacion = valorizacion
        total_valorizacion += valorizacion
        
        # Contar artículos únicos (solo si tiene stock > 0)
        if cantidad > 0:
            articulos_unicos.add(stock.articulo.id)
        
        stocks_list.append(stock)
        
    # Paginación
    paginator = Paginator(stocks_list, 50) # Show 50 contacts per page.
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    total_articulos = len(articulos_unicos)
    
    # Get filters data
    bodegas = Bodega.objects.filter(empresa=request.empresa)
    categorias = CategoriaArticulo.objects.filter(empresa=request.empresa, activa=True)
    
    context = {
        'page_obj': page_obj, # Replaces 'stocks' with page_obj for the loop
        'total_valorizacion': total_valorizacion,
        'total_articulos': total_articulos,
        'bodegas': bodegas,
        'categorias': categorias,
        # Preserve filter values
        'bodega_id': bodega_id,
        'categoria_id': categoria_id,
        'search': search,
    }
    
    response = render(request, 'informes/stock_actual.html', context)
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    response['Pragma'] = 'no-cache'
    return response


@login_required
@requiere_empresa
def informe_stock_bajo(request):
    """Informe de productos con stock bajo"""
    # Convertir stock_minimo (CharField) a DecimalField para comparar con cantidad
    stocks_bajos = Stock.objects.filter(
        bodega__empresa=request.empresa
    ).annotate(
        stock_minimo_decimal=Cast('articulo__stock_minimo', DecimalField(max_digits=10, decimal_places=2))
    ).filter(
        cantidad__lte=F('stock_minimo_decimal')
    ).select_related('articulo', 'bodega').order_by('cantidad')
    
    context = {
        'stocks_bajos': stocks_bajos
    }
    
    return render(request, 'informes/stock_bajo.html', context)


# ==================== INFORMES DE TESORERÍA ====================

@login_required
@requiere_empresa
@login_required
@requiere_empresa
def informe_cuentas_por_cobrar(request):
    """Informe de cuentas y facturas por cobrar (clientes) con filtro de vencimiento / emisión"""
    fecha_desde_str = request.GET.get('fecha_desde', '').strip()
    fecha_hasta_str = request.GET.get('fecha_hasta', '').strip()
    tipo_fecha = request.GET.get('tipo_fecha', 'vencimiento')
    search = request.GET.get('search', '').strip()
    estado = request.GET.get('estado', 'todos')
    sin_filtro_fecha = request.GET.get('sin_filtro_fecha') == '1'
    hoy = datetime.now().date()

    if not fecha_desde_str or not fecha_hasta_str:
        if tipo_fecha == 'emision':
            fecha_hasta = hoy
            fecha_desde = hoy - timedelta(days=30)
        else:
            # Para vencimiento: ventana que incluye los últimos 30 días y los próximos 30 días
            fecha_desde = hoy - timedelta(days=30)
            fecha_hasta = hoy + timedelta(days=30)
    else:
        try:
            fecha_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
            fecha_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_desde = hoy - timedelta(days=30)
            fecha_hasta = hoy + timedelta(days=30)

    documentos = DocumentoCliente.objects.filter(
        empresa=request.empresa,
        saldo_pendiente__gt=0
    ).select_related('cliente')

    if not sin_filtro_fecha:
        if tipo_fecha == 'emision':
            documentos = documentos.filter(fecha_emision__range=[fecha_desde, fecha_hasta])
        else:
            documentos = documentos.filter(
                Q(fecha_vencimiento__range=[fecha_desde, fecha_hasta]) |
                Q(fecha_vencimiento__isnull=True, fecha_emision__range=[fecha_desde, fecha_hasta])
            )

    if search:
        documentos = documentos.filter(
            Q(numero_documento__icontains=search) |
            Q(cliente__nombre__icontains=search) |
            Q(cliente__rut__icontains=search)
        )

    if estado in ('vencido', 'vencidos'):
        documentos = documentos.filter(fecha_vencimiento__lt=hoy)
    elif estado in ('por_vencer', 'vigente'):
        documentos = documentos.filter(Q(fecha_vencimiento__gte=hoy) | Q(fecha_vencimiento__isnull=True))

    documentos = documentos.order_by('fecha_vencimiento', 'fecha_emision')

    # Estadísticas sobre los documentos filtrados
    vencidos = [d for d in documentos if d.fecha_vencimiento and d.fecha_vencimiento < hoy]
    por_vencer = [d for d in documentos if not d.fecha_vencimiento or d.fecha_vencimiento >= hoy]

    total_por_cobrar = sum(float(d.saldo_pendiente) for d in documentos)
    total_vencido = sum(float(d.saldo_pendiente) for d in vencidos)
    total_por_vencer = sum(float(d.saldo_pendiente) for d in por_vencer)
    total_monto_documentos = sum(float(d.total) for d in documentos)
    total_pagado = sum(float(d.monto_pagado) for d in documentos)

    context = {
        'documentos': documentos,
        'vencidos': vencidos,
        'por_vencer': por_vencer,
        'total_por_cobrar': total_por_cobrar,
        'total_vencido': total_vencido,
        'total_por_vencer': total_por_vencer,
        'total_monto_documentos': total_monto_documentos,
        'total_pagado': total_pagado,
        'cantidad_documentos': len(documentos),
        'cantidad_vencidos': len(vencidos),
        'cantidad_por_vencer': len(por_vencer),
        'fecha_desde': fecha_desde.strftime('%Y-%m-%d'),
        'fecha_hasta': fecha_hasta.strftime('%Y-%m-%d'),
        'tipo_fecha': tipo_fecha,
        'search': search,
        'estado': estado,
        'sin_filtro_fecha': sin_filtro_fecha,
        'today': hoy
    }
    
    return render(request, 'informes/cuentas_por_cobrar.html', context)


@login_required
@requiere_empresa
def informe_cuentas_por_pagar(request):
    """Informe de cuentas y facturas por pagar (proveedores) con filtro de vencimiento / emisión"""
    fecha_desde_str = request.GET.get('fecha_desde', '').strip()
    fecha_hasta_str = request.GET.get('fecha_hasta', '').strip()
    tipo_fecha = request.GET.get('tipo_fecha', 'vencimiento')
    search = request.GET.get('search', '').strip()
    estado = request.GET.get('estado', 'todos')
    sin_filtro_fecha = request.GET.get('sin_filtro_fecha') == '1'
    hoy = datetime.now().date()

    if not fecha_desde_str or not fecha_hasta_str:
        if tipo_fecha == 'emision':
            fecha_hasta = hoy
            fecha_desde = hoy - timedelta(days=180)
        else:
            fecha_desde = hoy - timedelta(days=180)
            fecha_hasta = hoy + timedelta(days=30)
    else:
        try:
            fecha_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
            fecha_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_desde = hoy - timedelta(days=180)
            fecha_hasta = hoy + timedelta(days=30)

    documentos = DocumentoCompra.objects.filter(
        empresa=request.empresa,
        estado_documento='activo',
        saldo_pendiente__gt=0
    ).select_related('proveedor')

    if not sin_filtro_fecha:
        if tipo_fecha == 'emision':
            documentos = documentos.filter(fecha_emision__range=[fecha_desde, fecha_hasta])
        else:
            documentos = documentos.filter(
                Q(fecha_vencimiento__range=[fecha_desde, fecha_hasta]) |
                Q(fecha_vencimiento__isnull=True, fecha_emision__range=[fecha_desde, fecha_hasta])
            )

    if search:
        documentos = documentos.filter(
            Q(numero_documento__icontains=search) |
            Q(proveedor__nombre__icontains=search) |
            Q(proveedor__rut__icontains=search)
        )

    if estado in ('vencida', 'vencidas', 'vencido'):
        documentos = documentos.filter(fecha_vencimiento__lt=hoy)
    elif estado in ('por_vencer', 'vigente'):
        documentos = documentos.filter(Q(fecha_vencimiento__gte=hoy) | Q(fecha_vencimiento__isnull=True))

    documentos = documentos.order_by('fecha_vencimiento', 'fecha_emision')

    # Estadísticas sobre los documentos filtrados
    vencidos = [d for d in documentos if d.fecha_vencimiento and d.fecha_vencimiento < hoy]
    por_vencer = [d for d in documentos if not d.fecha_vencimiento or d.fecha_vencimiento >= hoy]

    total_por_pagar = sum(float(d.saldo_pendiente) for d in documentos)
    total_vencido = sum(float(d.saldo_pendiente) for d in vencidos)
    total_por_vencer = sum(float(d.saldo_pendiente) for d in por_vencer)
    total_monto_documentos = sum(float(d.total_documento) for d in documentos)
    total_pagado = sum(float(d.monto_pagado) for d in documentos)

    context = {
        'documentos': documentos,
        'vencidos': vencidos,
        'por_vencer': por_vencer,
        'total_por_pagar': total_por_pagar,
        'total_vencido': total_vencido,
        'total_por_vencer': total_por_vencer,
        'total_monto_documentos': total_monto_documentos,
        'total_pagado': total_pagado,
        'cantidad_documentos': len(documentos),
        'cantidad_vencidos': len(vencidos),
        'cantidad_por_vencer': len(por_vencer),
        'fecha_desde': fecha_desde.strftime('%Y-%m-%d'),
        'fecha_hasta': fecha_hasta.strftime('%Y-%m-%d'),
        'tipo_fecha': tipo_fecha,
        'search': search,
        'estado': estado,
        'sin_filtro_fecha': sin_filtro_fecha,
        'today': hoy
    }
    
    return render(request, 'informes/cuentas_por_pagar.html', context)


@login_required
@requiere_empresa
def informe_pagos_recibidos(request):
    """Informe de pagos recibidos por período"""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    pagos = PagoDocumentoCliente.objects.filter(
        documento__empresa=request.empresa,
        fecha_pago__date__range=[fecha_desde, fecha_hasta]
    ).select_related('documento', 'documento__cliente').order_by('-fecha_pago')
    
    # Agrupar por forma de pago
    por_forma_pago = pagos.values('forma_pago').annotate(
        total=Sum('monto'),
        cantidad=Count('id')
    ).order_by('-total')
    
    total_recibido = sum(float(p.monto) for p in pagos)
    
    context = {
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'pagos': pagos,
        'por_forma_pago': por_forma_pago,
        'total_recibido': total_recibido
    }
    
    return render(request, 'informes/pagos_recibidos.html', context)


# ==================== INFORMES DE CAJA ====================

@login_required
@requiere_empresa
def informe_cierres_caja(request):
    """Informe de cierres de caja"""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    cierres = AperturaCaja.objects.filter(
        caja__empresa=request.empresa,
        estado='cerrada',
        fecha_cierre__gte=fecha_desde,
        fecha_cierre__lte=fecha_hasta
    ).select_related('usuario_cierre', 'caja').order_by('-fecha_cierre')
    
    # Calcular total de ventas
    total_ventas = sum(
        float(c.total_ventas_efectivo or 0) + 
        float(c.total_ventas_tarjeta or 0) + 
        float(c.total_ventas_transferencia or 0) + 
        float(c.total_ventas_cheque or 0) + 
        float(c.total_ventas_credito or 0)
        for c in cierres
    )
    
    context = {
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'cierres': cierres,
        'total_ventas': total_ventas
    }
    
    return render(request, 'informes/cierres_caja.html', context)


# ==================== INFORMES DE COMPRAS ====================

@login_required
@requiere_empresa
def informe_compras_periodo(request):
    """Informe de compras por período"""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    compras = DocumentoCompra.objects.filter(
        empresa=request.empresa,
        fecha_emision__range=[fecha_desde, fecha_hasta]
    ).select_related('proveedor').order_by('-fecha_emision')
    
    # Agrupar por proveedor
    por_proveedor = compras.values(
        'proveedor__nombre'
    ).annotate(
        total_compras=Sum('total_documento'),
        cantidad_compras=Count('id')
    ).order_by('-total_compras')
    
    context = {
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'compras': compras,
        'por_proveedor': por_proveedor,
        'total_compras': sum(float(c.total_documento) for c in compras)
    }
    
    return render(request, 'informes/compras_periodo.html', context)


# ==================== EXPORTACIONES ====================

@login_required
@requiere_empresa
def exportar_ventas_excel(request):
    """Exportar informe de ventas a Excel"""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    # Obtener datos
    ventas_query = Venta.objects.filter(
        empresa=request.empresa,
        fecha__gte=fecha_desde,
        fecha__lte=fecha_hasta,
        estado='confirmada'
    ).order_by('fecha')
    
    # Agrupar por fecha
    ventas_por_fecha = {}
    for venta in ventas_query:
        fecha_key = venta.fecha
        if fecha_key not in ventas_por_fecha:
            ventas_por_fecha[fecha_key] = {
                'fecha_solo': fecha_key,
                'total_ventas': 0,
                'cantidad_ventas': 0
            }
        ventas_por_fecha[fecha_key]['total_ventas'] += float(venta.total)
        ventas_por_fecha[fecha_key]['cantidad_ventas'] += 1
    
    ventas = sorted(ventas_por_fecha.values(), key=lambda x: x['fecha_solo'])
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Ventas por Período"
    headers = ['Fecha', 'Cantidad Ventas', 'Total Ventas', 'Ticket Promedio']
    branding = setup_corporate_sheet(
        ws,
        request.empresa,
        "INFORME DE VENTAS",
        f"Periodo: {format_excel_date(fecha_desde)} al {format_excel_date(fecha_hasta)}",
        len(headers),
    )
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for venta in ventas:
        ws.cell(row=row, column=1, value=format_excel_date(venta['fecha_solo'])).alignment = styles["center"]
        ws.cell(row=row, column=2, value=venta['cantidad_ventas']).alignment = styles["center"]
        ws.cell(row=row, column=3, value=venta['total_ventas']).alignment = styles["right"]
        ws.cell(row=row, column=3).number_format = '$#,##0'
        ticket_prom = venta['total_ventas'] / venta['cantidad_ventas'] if venta['cantidad_ventas'] > 0 else 0
        ws.cell(row=row, column=4, value=ticket_prom).alignment = styles["right"]
        ws.cell(row=row, column=4).number_format = '$#,##0'
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1
    
    # Totales
    total_general = sum(v['total_ventas'] for v in ventas)
    cantidad_total = sum(v['cantidad_ventas'] for v in ventas)
    ticket_promedio = total_general / cantidad_total if cantidad_total > 0 else 0
    
    ws.cell(row=row, column=1, value="TOTAL").font = Font(bold=True)
    ws.cell(row=row, column=2, value=cantidad_total).font = Font(bold=True)
    ws.cell(row=row, column=2).alignment = styles["center"]
    ws.cell(row=row, column=3, value=total_general).font = Font(bold=True)
    ws.cell(row=row, column=3).alignment = styles["right"]
    ws.cell(row=row, column=3).number_format = '$#,##0'
    ws.cell(row=row, column=4, value=ticket_promedio).font = Font(bold=True)
    ws.cell(row=row, column=4).alignment = styles["right"]
    ws.cell(row=row, column=4).number_format = '$#,##0'
    style_data_row(ws, row, len(headers), styles)

    set_column_widths(ws, [16, 18, 18, 18])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row, len(headers))
    return build_excel_response(wb, f"ventas_{fecha_desde}_{fecha_hasta}.xlsx")


@login_required
@requiere_empresa
def exportar_productos_excel(request):
    """Exportar productos más vendidos a Excel"""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    productos = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__fecha__range=[fecha_desde, fecha_hasta],
        venta__estado='confirmada'
    ).values(
        'articulo__nombre',
        'articulo__codigo'
    ).annotate(
        cantidad_vendida=Sum('cantidad'),
        total_vendido=Sum('precio_total')
    ).order_by('-cantidad_vendida')[:50]
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Productos Más Vendidos"
    headers = ['#', 'Código', 'Producto', 'Cantidad', 'Total Vendido']
    branding = setup_corporate_sheet(
        ws,
        request.empresa,
        "PRODUCTOS MAS VENDIDOS",
        f"Periodo: {format_excel_date(fecha_desde)} al {format_excel_date(fecha_hasta)}",
        len(headers),
    )
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for idx, producto in enumerate(productos, start=1):
        ws.cell(row=row, column=1, value=idx).alignment = styles["center"]
        ws.cell(row=row, column=2, value=producto['articulo__codigo'])
        ws.cell(row=row, column=3, value=producto['articulo__nombre']).alignment = styles["wrap"]
        ws.cell(row=row, column=4, value=float(producto['cantidad_vendida'])).alignment = styles["right"]
        ws.cell(row=row, column=5, value=float(producto['total_vendido'])).alignment = styles["right"]
        ws.cell(row=row, column=5).number_format = '$#,##0'
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1

    set_column_widths(ws, [8, 15, 40, 15, 18])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row - 1, len(headers))
    return build_excel_response(wb, f"productos_vendidos_{fecha_desde}_{fecha_hasta}.xlsx")


@login_required
@requiere_empresa
def exportar_stock_excel(request):
    """Exportar stock actual a Excel"""
    bodega_id = clean_id(clean_id(request.GET.get('bodega'))) or clean_id(clean_id(request.GET.get('bodega_id')))
    categoria_id = clean_id(clean_id(request.GET.get('categoria')))
    search = request.GET.get('search', '')
    
    stocks = Stock.objects.filter(
        bodega__empresa=request.empresa
    ).select_related('articulo', 'bodega')
    
    if bodega_id:
        stocks = stocks.filter(bodega_id=bodega_id)

    if categoria_id:
        stocks = stocks.filter(articulo__categoria_id=categoria_id)
        
    if search:
        stocks = stocks.filter(
            Q(articulo__nombre__icontains=search) | 
            Q(articulo__codigo__icontains=search)
        )
    
    stocks = stocks.order_by('bodega__nombre', 'articulo__nombre')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Stock Actual"
    headers = ['Bodega', 'Código', 'Artículo', 'Stock', 'Precio Promedio', 'Valorización']
    branding = setup_corporate_sheet(
        ws,
        request.empresa,
        "STOCK ACTUAL",
        "Inventario valorizado por bodega",
        len(headers),
    )
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    total_valorizacion = 0
    for stock in stocks:
        valorizacion = float(stock.cantidad) * float(stock.precio_promedio)
        total_valorizacion += valorizacion
        
        ws.cell(row=row, column=1, value=stock.bodega.nombre)
        ws.cell(row=row, column=2, value=stock.articulo.codigo)
        ws.cell(row=row, column=3, value=stock.articulo.nombre).alignment = styles["wrap"]
        ws.cell(row=row, column=4, value=float(stock.cantidad)).alignment = styles["right"]
        ws.cell(row=row, column=5, value=float(stock.precio_promedio)).alignment = styles["right"]
        ws.cell(row=row, column=5).number_format = '$#,##0'
        ws.cell(row=row, column=6, value=valorizacion).alignment = styles["right"]
        ws.cell(row=row, column=6).number_format = '$#,##0'
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1
    
    # Total
    ws.cell(row=row, column=5, value="TOTAL:").font = Font(bold=True)
    ws.cell(row=row, column=5).alignment = styles["right"]
    ws.cell(row=row, column=6, value=total_valorizacion).font = Font(bold=True)
    ws.cell(row=row, column=6).alignment = styles["right"]
    ws.cell(row=row, column=6).number_format = '$#,##0'
    style_data_row(ws, row, len(headers), styles)

    set_column_widths(ws, [20, 15, 40, 12, 18, 18])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row, len(headers))
    return build_excel_response(wb, "stock_actual.xlsx")


@login_required
@requiere_empresa
def exportar_clientes_excel(request):
    """Exportar clientes a Excel"""
    from clientes.models import Cliente
    
    clientes = Cliente.objects.filter(
        empresa=request.empresa
    ).order_by('nombre')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"
    headers = ['RUT', 'Nombre', 'Giro', 'Dirección', 'Comuna', 'Ciudad', 'Región', 'Teléfono', 'Email']
    branding = setup_corporate_sheet(ws, request.empresa, "LISTADO DE CLIENTES", "", len(headers))
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for cliente in clientes:
        ws.cell(row=row, column=1, value=cliente.rut)
        ws.cell(row=row, column=2, value=cliente.nombre)
        ws.cell(row=row, column=3, value=cliente.giro or '')
        ws.cell(row=row, column=4, value=cliente.direccion or '')
        ws.cell(row=row, column=5, value=cliente.comuna or '')
        ws.cell(row=row, column=6, value=cliente.ciudad or '')
        ws.cell(row=row, column=7, value=cliente.region or '')
        ws.cell(row=row, column=8, value=cliente.telefono or '')
        ws.cell(row=row, column=9, value=cliente.email or '')
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1

    set_column_widths(ws, [15, 35, 30, 35, 20, 20, 20, 15, 30])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row - 1, len(headers))
    return build_excel_response(wb, "clientes.xlsx")


@login_required
@requiere_empresa
def exportar_proveedores_excel(request):
    """Exportar proveedores a Excel"""
    from proveedores.models import Proveedor
    
    proveedores = Proveedor.objects.filter(
        empresa=request.empresa
    ).order_by('nombre')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Proveedores"
    headers = ['RUT', 'Nombre', 'Giro', 'Dirección', 'Comuna', 'Ciudad', 'Teléfono', 'Email']
    branding = setup_corporate_sheet(ws, request.empresa, "LISTADO DE PROVEEDORES", "", len(headers))
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for proveedor in proveedores:
        ws.cell(row=row, column=1, value=proveedor.rut)
        ws.cell(row=row, column=2, value=proveedor.nombre)
        ws.cell(row=row, column=3, value=proveedor.giro or '')
        ws.cell(row=row, column=4, value=proveedor.direccion or '')
        ws.cell(row=row, column=5, value=proveedor.comuna or '')
        ws.cell(row=row, column=6, value=proveedor.ciudad or '')
        ws.cell(row=row, column=7, value=proveedor.telefono or '')
        ws.cell(row=row, column=8, value=proveedor.email or '')
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1

    set_column_widths(ws, [15, 35, 30, 35, 20, 20, 15, 30])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row - 1, len(headers))
    return build_excel_response(wb, "proveedores.xlsx")


@login_required
@requiere_empresa
def exportar_articulos_excel(request):
    """Exportar artículos a Excel"""
    from articulos.models import Articulo
    
    articulos = Articulo.objects.filter(
        empresa=request.empresa
    ).select_related('categoria', 'unidad_medida').order_by('codigo')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Artículos"
    headers = ['Código', 'Nombre', 'Descripción', 'Categoría', 'Unidad', 'Precio Costo', 'Precio Venta', 'Precio Final', 'Margen %', 'Código Barras']
    branding = setup_corporate_sheet(ws, request.empresa, "LISTADO DE ARTICULOS", "", len(headers))
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for articulo in articulos:
        ws.cell(row=row, column=1, value=articulo.codigo)
        ws.cell(row=row, column=2, value=articulo.nombre)
        ws.cell(row=row, column=3, value=articulo.descripcion or '')
        ws.cell(row=row, column=4, value=articulo.categoria.nombre if articulo.categoria else '')
        ws.cell(row=row, column=5, value=articulo.unidad_medida.nombre if articulo.unidad_medida else '')
        ws.cell(row=row, column=6, value=float(articulo.precio_costo)).alignment = styles["right"]
        ws.cell(row=row, column=6).number_format = '$#,##0'
        ws.cell(row=row, column=7, value=float(articulo.precio_venta)).alignment = styles["right"]
        ws.cell(row=row, column=7).number_format = '$#,##0'
        ws.cell(row=row, column=8, value=float(articulo.precio_final)).alignment = styles["right"]
        ws.cell(row=row, column=8).number_format = '$#,##0'
        ws.cell(row=row, column=9, value=float(articulo.margen_porcentaje)).alignment = styles["right"]
        ws.cell(row=row, column=9).number_format = '0.00"%"'
        ws.cell(row=row, column=10, value=articulo.codigo_barras or '')
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1

    set_column_widths(ws, [15, 35, 40, 20, 12, 15, 15, 15, 12, 18])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row - 1, len(headers))
    return build_excel_response(wb, "articulos.xlsx")


@login_required
@requiere_empresa
def informe_utilidad_familias(request):
    """Informe de costos, ventas y utilidad por familia"""
    from articulos.models import CategoriaArticulo
    
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    familia_id = request.GET.get('familia')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    # Query base de ventas por familia
    ventas_query = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__fecha__range=[fecha_desde, fecha_hasta],
        venta__estado='confirmada',
        articulo__categoria__isnull=False
    ).values(
        'articulo__categoria__id',
        'articulo__categoria__nombre'
    ).annotate(
        total_ventas=Sum(F('cantidad') * F('precio_unitario'), output_field=DecimalField(max_digits=20, decimal_places=2)),
        total_costo=Sum(F('cantidad') * Cast(F('articulo__precio_costo'), DecimalField(max_digits=20, decimal_places=2)), output_field=DecimalField(max_digits=20, decimal_places=2)),
        cantidad_vendida=Sum('cantidad'),
        num_ventas=Count('venta', distinct=True)
    )
    
    # Filtrar por familia si se especifica
    if familia_id:
        ventas_query = ventas_query.filter(articulo__categoria__id=familia_id)
    
    ventas_query = ventas_query.order_by('-total_ventas')
    
    # Calcular utilidad para cada familia
    resultados = []
    total_ventas_general = 0
    total_costo_general = 0
    
    for item in ventas_query:
        ventas = float(item['total_ventas'] or 0)
        costo = float(item['total_costo'] or 0)
        utilidad = ventas - costo
        margen = (utilidad / ventas * 100) if ventas > 0 else 0
        
        resultados.append({
            'familia_id': item['articulo__categoria__id'],
            'familia_nombre': item['articulo__categoria__nombre'],
            'total_ventas': ventas,
            'total_costo': costo,
            'utilidad': utilidad,
            'margen_porcentaje': margen,
            'cantidad_vendida': float(item['cantidad_vendida']),
            'num_ventas': item['num_ventas']
        })
        
        total_ventas_general += ventas
        total_costo_general += costo
    
    utilidad_general = total_ventas_general - total_costo_general
    margen_general = (utilidad_general / total_ventas_general * 100) if total_ventas_general > 0 else 0
    
    # Obtener todas las familias para el filtro
    familias = CategoriaArticulo.objects.filter(empresa=request.empresa).order_by('nombre')
    
    context = {
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'familia_id': familia_id,
        'familias': familias,
        'resultados': resultados,
        'total_ventas_general': total_ventas_general,
        'total_costo_general': total_costo_general,
        'utilidad_general': utilidad_general,
        'margen_general': margen_general
    }
    
    return render(request, 'informes/utilidad_familias.html', context)


@login_required
@requiere_empresa
def informe_utilidad_familias_detalle(request, familia_id):
    """API para obtener detalle de artículos por familia"""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    # Query de artículos de la familia
    articulos_query = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__fecha__range=[fecha_desde, fecha_hasta],
        venta__estado='confirmada',
        articulo__categoria__id=familia_id
    ).values(
        'articulo__id',
        'articulo__codigo',
        'articulo__nombre'
    ).annotate(
        total_ventas=Sum(F('cantidad') * F('precio_unitario'), output_field=DecimalField(max_digits=20, decimal_places=2)),
        total_costo=Sum(F('cantidad') * Cast(F('articulo__precio_costo'), DecimalField(max_digits=20, decimal_places=2)), output_field=DecimalField(max_digits=20, decimal_places=2)),
        cantidad_vendida=Sum('cantidad')
    ).order_by('-total_ventas')
    
    # Preparar datos para JSON
    articulos = []
    for item in articulos_query:
        ventas = float(item['total_ventas'] or 0)
        costo = float(item['total_costo'] or 0)
        utilidad = ventas - costo
        margen = (utilidad / ventas * 100) if ventas > 0 else 0
        
        articulos.append({
            'codigo': item['articulo__codigo'],
            'nombre': item['articulo__nombre'],
            'cantidad': float(item['cantidad_vendida']),
            'ventas': ventas,
            'costos': costo,
            'utilidad': utilidad,
            'margen': margen
        })
    
    return JsonResponse({
        'success': True,
        'articulos': articulos
    })


@login_required
@requiere_empresa
def exportar_ventas_vendedor_excel(request):
    """Exportar ventas por vendedor a Excel"""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    ventas_vendedor = Venta.objects.filter(
        empresa=request.empresa,
        fecha__range=[fecha_desde, fecha_hasta],
        estado='confirmada',
        vendedor__isnull=False
    ).values(
        'vendedor__codigo',
        'vendedor__nombre'
    ).annotate(
        total_ventas=Sum('total'),
        cantidad_ventas=Count('id'),
        ticket_promedio=Avg('total')
    ).order_by('-total_ventas')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Ventas por Vendedor"
    headers = ['Código', 'Vendedor', 'Cant. Ventas', 'Total Vendido', 'Ticket Promedio']
    branding = setup_corporate_sheet(
        ws,
        request.empresa,
        "VENTAS POR VENDEDOR",
        f"Periodo: {format_excel_date(fecha_desde)} al {format_excel_date(fecha_hasta)}",
        len(headers),
    )
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for vendedor in ventas_vendedor:
        ws.cell(row=row, column=1, value=vendedor['vendedor__codigo']).alignment = styles["center"]
        ws.cell(row=row, column=2, value=vendedor['vendedor__nombre'])
        ws.cell(row=row, column=3, value=vendedor['cantidad_ventas']).alignment = styles["center"]
        ws.cell(row=row, column=4, value=float(vendedor['total_ventas'])).alignment = styles["right"]
        ws.cell(row=row, column=4).number_format = '$#,##0'
        ws.cell(row=row, column=5, value=float(vendedor['ticket_promedio'])).alignment = styles["right"]
        ws.cell(row=row, column=5).number_format = '$#,##0'
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1

    set_column_widths(ws, [12, 35, 15, 18, 18])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row - 1, len(headers))
    return build_excel_response(wb, f"ventas_vendedor_{fecha_desde}_{fecha_hasta}.xlsx")


@login_required
@requiere_empresa
def informe_utilidad_articulos(request):
    """Informe de utilidad y margen por artículo"""
    from articulos.models import CategoriaArticulo
    
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    familia_id = request.GET.get('familia')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    # Query base de ventas por artículo
    ventas_query = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__fecha__range=[fecha_desde, fecha_hasta],
        venta__estado='confirmada'
    ).values(
        'articulo__id',
        'articulo__nombre',
        'articulo__codigo',
        'articulo__categoria__nombre'
    ).annotate(
        total_ventas=Sum(F('cantidad') * F('precio_unitario'), output_field=DecimalField(max_digits=20, decimal_places=2)),
        total_costo=Sum(F('cantidad') * Cast(F('articulo__precio_costo'), DecimalField(max_digits=20, decimal_places=2)), output_field=DecimalField(max_digits=20, decimal_places=2)),
        cantidad_vendida=Sum('cantidad')
    )
    
    if familia_id:
        ventas_query = ventas_query.filter(articulo__categoria__id=familia_id)
    
    # Ordenar por ventas (descendente)
    ventas_query = ventas_query.order_by('-total_ventas')
    
    resultados = []
    total_ventas_general = 0
    total_costo_general = 0
    utilidad_general = 0
    
    for item in ventas_query:
        ventas = float(item['total_ventas'] or 0)
        costo = float(item['total_costo'] or 0)
        utilidad = ventas - costo
        margen = (utilidad / ventas * 100) if ventas > 0 else 0
        
        resultados.append({
            'nombre': item['articulo__nombre'],
            'codigo': item['articulo__codigo'],
            'familia': item['articulo__categoria__nombre'] or 'Sin Familia',
            'cantidad': float(item['cantidad_vendida']),
            'total_ventas': ventas,
            'total_costo': costo,
            'utilidad': utilidad,
            'margen': margen
        })
        
        total_ventas_general += ventas
        total_costo_general += costo
        
    utilidad_general = total_ventas_general - total_costo_general
    margen_general = (utilidad_general / total_ventas_general * 100) if total_ventas_general > 0 else 0
    
    # Obtener todas las familias para el filtro
    familias = CategoriaArticulo.objects.filter(
        empresa=request.empresa,
        activa=True
    ).order_by('nombre')
    
    context = {
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'familia_id': familia_id,
        'familias': familias,
        'resultados': resultados,
        'total_ventas_general': total_ventas_general,
        'total_costo_general': total_costo_general,
        'utilidad_general': utilidad_general,
        'margen_general': margen_general
    }
    
    return render(request, 'informes/utilidad_articulos.html', context)
