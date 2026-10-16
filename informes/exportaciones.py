"""
Funciones de exportación para informes
"""
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Sum, Count, Avg, F, Q
from django.db.models.functions import Cast
from datetime import datetime, timedelta
from decimal import Decimal

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

from ventas.models import Venta
from inventario.models import Stock
from tesoreria.models import DocumentoCliente, PagoDocumentoCliente
from caja.models import AperturaCaja
from documentos.models import DocumentoCompra


@login_required
@requiere_empresa
def exportar_cuentas_cobrar_excel(request):
    """Exportar cuentas/facturas por cobrar a Excel con filtros de vencimiento"""
    fecha_desde_str = request.GET.get('fecha_desde')
    fecha_hasta_str = request.GET.get('fecha_hasta')
    search = request.GET.get('search', '').strip()
    estado = request.GET.get('estado', 'todos')
    sin_filtro_fecha = request.GET.get('sin_filtro_fecha') == '1'
    hoy = datetime.now().date()

    if not fecha_desde_str or not fecha_hasta_str:
        fecha_hasta = hoy
        fecha_desde = hoy - timedelta(days=30)
    else:
        try:
            fecha_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
            fecha_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_hasta = hoy
            fecha_desde = hoy - timedelta(days=30)

    documentos = DocumentoCliente.objects.filter(
        empresa=request.empresa,
        saldo_pendiente__gt=0
    ).select_related('cliente')

    if not sin_filtro_fecha:
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
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Facturas por Cobrar"
    headers = ['N° Documento', 'Tipo', 'Cliente', 'RUT', 'Fecha Emisión', 'Fecha Vencimiento', 'Total ($)', 'Pagado ($)', 'Saldo Pendiente ($)', 'Estado']
    subtitulo = f"Vencimiento: {format_excel_date(fecha_desde)} al {format_excel_date(fecha_hasta)}" if not sin_filtro_fecha else "Todos los vencimientos"
    branding = setup_corporate_sheet(ws, request.empresa, "FACTURAS Y CUENTAS POR COBRAR", subtitulo, len(headers))
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for doc in documentos:
        tipo_str = doc.get_tipo_documento_display() if hasattr(doc, 'get_tipo_documento_display') else doc.tipo_documento
        ws.cell(row=row, column=1, value=doc.numero_documento)
        ws.cell(row=row, column=2, value=tipo_str).alignment = styles["center"]
        ws.cell(row=row, column=3, value=doc.cliente.nombre if doc.cliente else 'Sin cliente')
        ws.cell(row=row, column=4, value=doc.cliente.rut if doc.cliente else '-').alignment = styles["center"]
        ws.cell(row=row, column=5, value=format_excel_date(doc.fecha_emision)).alignment = styles["center"]
        ws.cell(row=row, column=6, value=format_excel_date(doc.fecha_vencimiento)).alignment = styles["center"]
        ws.cell(row=row, column=7, value=float(doc.total)).alignment = styles["right"]
        ws.cell(row=row, column=7).number_format = '$#,##0'
        ws.cell(row=row, column=8, value=float(doc.monto_pagado)).alignment = styles["right"]
        ws.cell(row=row, column=8).number_format = '$#,##0'
        ws.cell(row=row, column=9, value=float(doc.saldo_pendiente)).alignment = styles["right"]
        ws.cell(row=row, column=9).number_format = '$#,##0'
        
        if doc.fecha_vencimiento and doc.fecha_vencimiento < hoy:
            estado_desc = "Vencido"
        else:
            estado_desc = "Por Vencer"
        ws.cell(row=row, column=10, value=estado_desc).alignment = styles["center"]
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1

    set_column_widths(ws, [18, 16, 32, 14, 15, 16, 15, 15, 18, 14])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row - 1, len(headers))
    return build_excel_response(wb, "facturas_por_cobrar.xlsx")


@login_required
@requiere_empresa
def exportar_cuentas_pagar_excel(request):
    """Exportar facturas/cuentas por pagar a proveedores a Excel"""
    fecha_desde_str = request.GET.get('fecha_desde')
    fecha_hasta_str = request.GET.get('fecha_hasta')
    search = request.GET.get('search', '').strip()
    estado = request.GET.get('estado', 'todos')
    sin_filtro_fecha = request.GET.get('sin_filtro_fecha') == '1'
    hoy = datetime.now().date()

    if not fecha_desde_str or not fecha_hasta_str:
        fecha_hasta = hoy
        fecha_desde = hoy - timedelta(days=30)
    else:
        try:
            fecha_desde = datetime.strptime(fecha_desde_str, '%Y-%m-%d').date()
            fecha_hasta = datetime.strptime(fecha_hasta_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_hasta = hoy
            fecha_desde = hoy - timedelta(days=30)

    documentos = DocumentoCompra.objects.filter(
        empresa=request.empresa,
        estado_documento='activo',
        saldo_pendiente__gt=0
    ).select_related('proveedor')

    if not sin_filtro_fecha:
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

    wb = Workbook()
    ws = wb.active
    ws.title = "Facturas por Pagar"
    headers = ['N° Documento', 'Tipo', 'Proveedor', 'RUT', 'Fecha Emisión', 'Fecha Vencimiento', 'Total ($)', 'Pagado ($)', 'Saldo Pendiente ($)', 'Estado']
    subtitulo = f"Vencimiento: {format_excel_date(fecha_desde)} al {format_excel_date(fecha_hasta)}" if not sin_filtro_fecha else "Todos los vencimientos"
    branding = setup_corporate_sheet(ws, request.empresa, "FACTURAS Y CUENTAS POR PAGAR", subtitulo, len(headers))
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for doc in documentos:
        tipo_str = doc.get_tipo_documento_display() if hasattr(doc, 'get_tipo_documento_display') else doc.tipo_documento
        ws.cell(row=row, column=1, value=doc.numero_documento)
        ws.cell(row=row, column=2, value=tipo_str).alignment = styles["center"]
        ws.cell(row=row, column=3, value=doc.proveedor.nombre if doc.proveedor else 'Sin proveedor')
        ws.cell(row=row, column=4, value=doc.proveedor.rut if doc.proveedor else '-').alignment = styles["center"]
        ws.cell(row=row, column=5, value=format_excel_date(doc.fecha_emision)).alignment = styles["center"]
        ws.cell(row=row, column=6, value=format_excel_date(doc.fecha_vencimiento)).alignment = styles["center"]
        ws.cell(row=row, column=7, value=float(doc.total_documento)).alignment = styles["right"]
        ws.cell(row=row, column=7).number_format = '$#,##0'
        ws.cell(row=row, column=8, value=float(doc.monto_pagado)).alignment = styles["right"]
        ws.cell(row=row, column=8).number_format = '$#,##0'
        ws.cell(row=row, column=9, value=float(doc.saldo_pendiente)).alignment = styles["right"]
        ws.cell(row=row, column=9).number_format = '$#,##0'

        if doc.fecha_vencimiento and doc.fecha_vencimiento < hoy:
            estado_desc = "Vencida"
        else:
            estado_desc = "Por Vencer"
        ws.cell(row=row, column=10, value=estado_desc).alignment = styles["center"]
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1

    set_column_widths(ws, [18, 16, 32, 14, 15, 16, 15, 15, 18, 14])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row - 1, len(headers))
    return build_excel_response(wb, "facturas_por_pagar.xlsx")


@login_required
@requiere_empresa
def exportar_pagos_recibidos_excel(request):
    """Exportar pagos recibidos a Excel"""
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    pagos = PagoDocumentoCliente.objects.filter(
        empresa=request.empresa,
        fecha_pago__range=[fecha_desde, fecha_hasta]
    ).select_related('documento__cliente', 'forma_pago').order_by('-fecha_pago')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Pagos Recibidos"
    headers = ['Fecha', 'N° Documento', 'Cliente', 'Monto', 'Forma de Pago']
    branding = setup_corporate_sheet(
        ws,
        request.empresa,
        "PAGOS RECIBIDOS",
        f"Periodo: {format_excel_date(fecha_desde)} al {format_excel_date(fecha_hasta)}",
        len(headers),
    )
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for pago in pagos:
        ws.cell(row=row, column=1, value=format_excel_date(pago.fecha_pago)).alignment = styles["center"]
        ws.cell(row=row, column=2, value=pago.documento.numero_documento)
        ws.cell(row=row, column=3, value=pago.documento.cliente.nombre if pago.documento.cliente else 'Sin cliente')
        ws.cell(row=row, column=4, value=float(pago.monto)).alignment = styles["right"]
        ws.cell(row=row, column=4).number_format = '$#,##0'
        ws.cell(row=row, column=5, value=pago.forma_pago.nombre if pago.forma_pago else 'Sin especificar')
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1

    set_column_widths(ws, [12, 18, 35, 15, 20])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row - 1, len(headers))
    return build_excel_response(wb, f"pagos_recibidos_{fecha_desde}_{fecha_hasta}.xlsx")


@login_required
@requiere_empresa
def exportar_stock_bajo_excel(request):
    """Exportar stock bajo a Excel"""
    stocks_bajo = Stock.objects.filter(
        empresa=request.empresa,
        cantidad__lte=F('stock_minimo')
    ).select_related('articulo', 'bodega').order_by('cantidad')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Stock Bajo"
    headers = ['Código', 'Artículo', 'Bodega', 'Stock Actual', 'Stock Mínimo', 'Diferencia']
    branding = setup_corporate_sheet(ws, request.empresa, "PRODUCTOS CON STOCK BAJO", "", len(headers))
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for stock in stocks_bajo:
        diferencia = float(stock.stock_minimo - stock.cantidad)
        ws.cell(row=row, column=1, value=stock.articulo.codigo)
        ws.cell(row=row, column=2, value=stock.articulo.nombre)
        ws.cell(row=row, column=3, value=stock.bodega.nombre)
        ws.cell(row=row, column=4, value=float(stock.cantidad)).alignment = styles["right"]
        ws.cell(row=row, column=5, value=float(stock.stock_minimo)).alignment = styles["right"]
        ws.cell(row=row, column=6, value=diferencia).alignment = styles["right"]
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1

    set_column_widths(ws, [15, 40, 25, 15, 15, 15])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row - 1, len(headers))
    return build_excel_response(wb, "stock_bajo.xlsx")


@login_required
@requiere_empresa
def exportar_cierres_caja_excel(request):
    """Exportar cierres de caja a Excel"""
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
        fecha_apertura__range=[fecha_desde, fecha_hasta],
        estado='cerrada'
    ).select_related('caja', 'usuario_apertura', 'usuario_cierre').order_by('-fecha_apertura')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Cierres de Caja"
    headers = ['Caja', 'Fecha Apertura', 'Fecha Cierre', 'Monto Inicial', 'Total Ventas', 'Monto Final', 'Diferencia']
    branding = setup_corporate_sheet(
        ws,
        request.empresa,
        "CIERRES DE CAJA",
        f"Periodo: {format_excel_date(fecha_desde)} al {format_excel_date(fecha_hasta)}",
        len(headers),
    )
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for cierre in cierres:
        ws.cell(row=row, column=1, value=cierre.caja.nombre)
        ws.cell(row=row, column=2, value=cierre.fecha_apertura.strftime('%d-%m-%Y %H:%M')).alignment = styles["center"]
        ws.cell(row=row, column=3, value=cierre.fecha_cierre.strftime('%d-%m-%Y %H:%M') if cierre.fecha_cierre else '').alignment = styles["center"]
        ws.cell(row=row, column=4, value=float(cierre.monto_inicial)).alignment = styles["right"]
        ws.cell(row=row, column=4).number_format = '$#,##0'
        ws.cell(row=row, column=5, value=float(cierre.total_ventas)).alignment = styles["right"]
        ws.cell(row=row, column=5).number_format = '$#,##0'
        ws.cell(row=row, column=6, value=float(cierre.monto_cierre)).alignment = styles["right"]
        ws.cell(row=row, column=6).number_format = '$#,##0'
        ws.cell(row=row, column=7, value=float(cierre.diferencia)).alignment = styles["right"]
        ws.cell(row=row, column=7).number_format = '$#,##0'
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1

    set_column_widths(ws, [20, 18, 18, 15, 15, 15, 15])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row - 1, len(headers))
    return build_excel_response(wb, f"cierres_caja_{fecha_desde}_{fecha_hasta}.xlsx")


@login_required
@requiere_empresa
def exportar_utilidad_familias_excel(request):
    """Exportar utilidad por familias a Excel"""
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
    
    # Query de ventas por familia
    from ventas.models import VentaDetalle
    from django.db.models import F
    
    from django.db.models import DecimalField as DField
    
    ventas_query = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__fecha__range=[fecha_desde, fecha_hasta],
        venta__estado='confirmada',
        articulo__categoria__isnull=False
    ).values(
        'articulo__categoria__nombre'
    ).annotate(
        total_ventas=Sum(F('cantidad') * F('precio_unitario'), output_field=DField(max_digits=20, decimal_places=2)),
        total_costo=Sum(F('cantidad') * Cast(F('articulo__precio_costo'), DField(max_digits=20, decimal_places=2)), output_field=DField(max_digits=20, decimal_places=2)),
        cantidad_vendida=Sum('cantidad'),
        num_ventas=Count('venta', distinct=True)
    )
    
    if familia_id:
        ventas_query = ventas_query.filter(articulo__categoria__id=familia_id)
    
    ventas_query = ventas_query.order_by('-total_ventas')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Utilidad por Familias"
    headers = ['Familia', 'Cant. Vendida', 'N° Ventas', 'Total Ventas', 'Total Costos', 'Utilidad', 'Margen %']
    branding = setup_corporate_sheet(
        ws,
        request.empresa,
        "UTILIDAD POR FAMILIAS",
        f"Periodo: {format_excel_date(fecha_desde)} al {format_excel_date(fecha_hasta)}",
        len(headers),
    )
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    total_ventas = 0
    total_costos = 0
    
    for item in ventas_query:
        ventas = float(item['total_ventas'] or 0)
        costo = float(item['total_costo'] or 0)
        utilidad = ventas - costo
        margen = (utilidad / ventas * 100) if ventas > 0 else 0
        
        ws.cell(row=row, column=1, value=item['articulo__categoria__nombre'])
        ws.cell(row=row, column=2, value=float(item['cantidad_vendida'])).alignment = styles["right"]
        ws.cell(row=row, column=3, value=item['num_ventas']).alignment = styles["center"]
        ws.cell(row=row, column=4, value=ventas).alignment = styles["right"]
        ws.cell(row=row, column=4).number_format = '$#,##0'
        ws.cell(row=row, column=5, value=costo).alignment = styles["right"]
        ws.cell(row=row, column=5).number_format = '$#,##0'
        ws.cell(row=row, column=6, value=utilidad).alignment = styles["right"]
        ws.cell(row=row, column=6).number_format = '$#,##0'
        ws.cell(row=row, column=7, value=margen).alignment = styles["right"]
        ws.cell(row=row, column=7).number_format = '0.0"%"'
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        total_ventas += ventas
        total_costos += costo
        row += 1
    
    # Totales
    if row > 5:
        ws.cell(row=row, column=1, value='TOTALES')
        ws.cell(row=row, column=1).font = Font(bold=True)
        ws.cell(row=row, column=4, value=total_ventas).alignment = styles["right"]
        ws.cell(row=row, column=4).number_format = '$#,##0'
        ws.cell(row=row, column=4).font = Font(bold=True)
        ws.cell(row=row, column=5, value=total_costos).alignment = styles["right"]
        ws.cell(row=row, column=5).number_format = '$#,##0'
        ws.cell(row=row, column=5).font = Font(bold=True)
        ws.cell(row=row, column=6, value=total_ventas - total_costos).alignment = styles["right"]
        ws.cell(row=row, column=6).number_format = '$#,##0'
        ws.cell(row=row, column=6).font = Font(bold=True)
        margen_total = ((total_ventas - total_costos) / total_ventas * 100) if total_ventas > 0 else 0
        ws.cell(row=row, column=7, value=margen_total).alignment = styles["right"]
        ws.cell(row=row, column=7).number_format = '0.0"%"'
        ws.cell(row=row, column=7).font = Font(bold=True)
        style_data_row(ws, row, len(headers), styles)

    set_column_widths(ws, [35, 15, 12, 18, 18, 18, 12])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row, len(headers))
    return build_excel_response(wb, f"utilidad_familias_{fecha_desde}_{fecha_hasta}.xlsx")


@login_required
@requiere_empresa
def exportar_compras_periodo_excel(request):
    """Exportar compras por período a Excel"""
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
        fecha__range=[fecha_desde, fecha_hasta]
    ).select_related('proveedor').order_by('-fecha')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Compras"
    headers = ['Fecha', 'N° Documento', 'Proveedor', 'Tipo', 'Neto', 'IVA', 'Total']
    branding = setup_corporate_sheet(
        ws,
        request.empresa,
        "COMPRAS POR PERIODO",
        f"Periodo: {format_excel_date(fecha_desde)} al {format_excel_date(fecha_hasta)}",
        len(headers),
    )
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for compra in compras:
        ws.cell(row=row, column=1, value=format_excel_date(compra.fecha)).alignment = styles["center"]
        ws.cell(row=row, column=2, value=compra.numero_documento)
        ws.cell(row=row, column=3, value=compra.proveedor.nombre if compra.proveedor else 'Sin proveedor')
        ws.cell(row=row, column=4, value=compra.get_tipo_documento_display()).alignment = styles["center"]
        ws.cell(row=row, column=5, value=float(compra.neto)).alignment = styles["right"]
        ws.cell(row=row, column=5).number_format = '$#,##0'
        ws.cell(row=row, column=6, value=float(compra.iva)).alignment = styles["right"]
        ws.cell(row=row, column=6).number_format = '$#,##0'
        ws.cell(row=row, column=7, value=float(compra.total_documento)).alignment = styles["right"]
        ws.cell(row=row, column=7).number_format = '$#,##0'
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1

    set_column_widths(ws, [12, 18, 35, 15, 15, 15, 15])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row - 1, len(headers))
    return build_excel_response(wb, f"compras_{fecha_desde}_{fecha_hasta}.xlsx")


@login_required
@requiere_empresa
def exportar_categorias_excel(request):
    """Exportar categorías a Excel"""
    from articulos.models import Categoria
    
    categorias = Categoria.objects.filter(
        empresa=request.empresa
    ).annotate(
        total_articulos=Count('articulos')
    ).order_by('nombre')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Categorías"
    headers = ['Código', 'Nombre', 'Descripción', 'Total Artículos', 'Estado']
    branding = setup_corporate_sheet(ws, request.empresa, "CATEGORIAS", "", len(headers))
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    for categoria in categorias:
        ws.cell(row=row, column=1, value=categoria.codigo)
        ws.cell(row=row, column=2, value=categoria.nombre)
        ws.cell(row=row, column=3, value=categoria.descripcion or '')
        ws.cell(row=row, column=4, value=categoria.total_articulos).alignment = styles["center"]
        ws.cell(row=row, column=5, value='Activa' if categoria.activo else 'Inactiva').alignment = styles["center"]
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        row += 1
    
    # Totales
    row += 1
    ws.cell(row=row, column=1, value='TOTAL CATEGORÍAS:').font = Font(bold=True)
    ws.cell(row=row, column=2, value=categorias.count()).font = Font(bold=True)
    style_data_row(ws, row, len(headers), styles)

    set_column_widths(ws, [12, 30, 40, 18, 12])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row, len(headers))
    return build_excel_response(wb, f"categorias_{datetime.now().strftime('%Y%m%d')}.xlsx")


@login_required
@requiere_empresa
def exportar_utilidad_articulos_excel(request):
    """Exportar utilidad por artículos a Excel"""
    from articulos.models import CategoriaArticulo
    from ventas.models import VentaDetalle
    from django.db.models import DecimalField as DField
    from django.db.models.functions import Cast
    
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    familia_id = request.GET.get('familia')
    
    if not fecha_desde or not fecha_hasta:
        fecha_hasta = datetime.now().date()
        fecha_desde = fecha_hasta - timedelta(days=30)
    else:
        fecha_desde = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
        fecha_hasta = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
    
    # Query de ventas por artículo
    ventas_query = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__fecha__range=[fecha_desde, fecha_hasta],
        venta__estado='confirmada'
    ).values(
        'articulo__codigo',
        'articulo__nombre',
        'articulo__categoria__nombre'
    ).annotate(
        total_ventas=Sum(F('cantidad') * F('precio_unitario'), output_field=DField(max_digits=20, decimal_places=2)),
        total_costo=Sum(F('cantidad') * Cast(F('articulo__precio_costo'), DField(max_digits=20, decimal_places=2)), output_field=DField(max_digits=20, decimal_places=2)),
        cantidad_vendida=Sum('cantidad')
    )
    
    if familia_id:
        ventas_query = ventas_query.filter(articulo__categoria__id=familia_id)
    
    ventas_query = ventas_query.order_by('-total_ventas')
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Utilidad por Artículos"
    headers = ['Código', 'Artículo', 'Familia', 'Cant. Vendida', 'Total Ventas', 'Total Costos', 'Utilidad', 'Margen %']
    branding = setup_corporate_sheet(
        ws,
        request.empresa,
        "UTILIDAD POR ARTICULOS",
        f"Periodo: {format_excel_date(fecha_desde)} al {format_excel_date(fecha_hasta)}",
        len(headers),
    )
    styles = branding["styles"]
    write_table_headers(ws, branding["header_row"], headers, styles)

    row = branding["data_row"]
    total_ventas = 0
    total_costos = 0
    
    for item in ventas_query:
        ventas = float(item['total_ventas'] or 0)
        costo = float(item['total_costo'] or 0)
        utilidad = ventas - costo
        margen = (utilidad / ventas * 100) if ventas > 0 else 0
        
        ws.cell(row=row, column=1, value=item['articulo__codigo'])
        ws.cell(row=row, column=2, value=item['articulo__nombre'])
        ws.cell(row=row, column=3, value=item['articulo__categoria__nombre'] or 'Sin Familia')
        ws.cell(row=row, column=4, value=float(item['cantidad_vendida'])).alignment = styles["right"]
        ws.cell(row=row, column=5, value=ventas).alignment = styles["right"]
        ws.cell(row=row, column=5).number_format = '$#,##0'
        ws.cell(row=row, column=6, value=costo).alignment = styles["right"]
        ws.cell(row=row, column=6).number_format = '$#,##0'
        ws.cell(row=row, column=7, value=utilidad).alignment = styles["right"]
        ws.cell(row=row, column=7).number_format = '$#,##0'
        ws.cell(row=row, column=8, value=margen).alignment = styles["right"]
        ws.cell(row=row, column=8).number_format = '0.0"%"'
        style_data_row(ws, row, len(headers), styles, zebra=((row - branding["data_row"]) % 2 == 1))
        total_ventas += ventas
        total_costos += costo
        row += 1
    
    # Totales
    if row > 5:
        ws.cell(row=row, column=1, value='TOTALES')
        ws.cell(row=row, column=1).font = Font(bold=True)
        ws.cell(row=row, column=5, value=total_ventas).alignment = styles["right"]
        ws.cell(row=row, column=5).number_format = '$#,##0'
        ws.cell(row=row, column=5).font = Font(bold=True)
        ws.cell(row=row, column=6, value=total_costos).alignment = styles["right"]
        ws.cell(row=row, column=6).number_format = '$#,##0'
        ws.cell(row=row, column=6).font = Font(bold=True)
        ws.cell(row=row, column=7, value=total_ventas - total_costos).alignment = styles["right"]
        ws.cell(row=row, column=7).number_format = '$#,##0'
        ws.cell(row=row, column=7).font = Font(bold=True)
        margen_total = ((total_ventas - total_costos) / total_ventas * 100) if total_ventas > 0 else 0
        ws.cell(row=row, column=8, value=margen_total).alignment = styles["right"]
        ws.cell(row=row, column=8).number_format = '0.0"%"'
        ws.cell(row=row, column=8).font = Font(bold=True)
        style_data_row(ws, row, len(headers), styles)

    set_column_widths(ws, [15, 40, 25, 12, 18, 18, 18, 12])
    finalize_excel_table(ws, branding["header_row"], branding["data_row"], row, len(headers))
    return build_excel_response(wb, f"utilidad_articulos_{fecha_desde}_{fecha_hasta}.xlsx")
