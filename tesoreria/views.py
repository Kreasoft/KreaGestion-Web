from utilidades.utils import clean_id
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import datetime, timedelta
from calendar import monthrange
from urllib.parse import urlencode
import json
import re
from decimal import Decimal
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from .models import CuentaCorrienteProveedor, MovimientoCuentaCorriente
from documentos.models import DocumentoCompra
from proveedores.models import Proveedor
from empresas.models import Empresa
from bodegas.models import Bodega
from core.decorators import requiere_empresa, empresa_id_desde_sesion, persistir_empresa_activa
from core.fechas import parse_fecha


def _empresa_de_request(request):
    """Empresa activa: la del request, o la de sesión (ambas claves)."""
    empresa = getattr(request, 'empresa', None)
    if empresa:
        return empresa
    if request.user.is_superuser:
        empresa_id = empresa_id_desde_sesion(request)
        if empresa_id:
            try:
                return Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                pass
        return Empresa.objects.first()
    try:
        return request.user.perfil.empresa
    except Exception:
        return None


def parse_monto_chileno(value):
    """Convierte montos con separadores CL o técnicos a Decimal sin cortar miles."""
    text = str(value or '').strip().replace('$', '').replace(' ', '')
    if not text:
        return Decimal('0')

    has_comma = ',' in text
    has_dot = '.' in text

    if has_comma and has_dot:
        if text.rfind(',') > text.rfind('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    elif has_dot:
        parts = text.split('.')
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            text = text.replace('.', '')
    elif has_comma:
        parts = text.split(',')
        text = text.replace(',', '.') if len(parts) == 2 and len(parts[1]) != 3 else text.replace(',', '')

    return Decimal(text)


def _href_filtro_cc(search='', estado_pago='', vencimiento_desde='', vencimiento_hasta='', orden='desc'):
    params = {}
    if search:
        params['search'] = search
    if estado_pago:
        params['estado_pago'] = estado_pago
    if vencimiento_desde:
        params['vencimiento_desde'] = vencimiento_desde
    if vencimiento_hasta:
        params['vencimiento_hasta'] = vencimiento_hasta
    if orden and orden != 'desc':
        params['orden'] = orden
    qs = urlencode(params)
    return f'?{qs}' if qs else '?'


def _filtros_cuenta_corriente(request):
    """Filtros comunes: búsqueda, estado y rango de vencimiento."""
    search = (request.GET.get('search') or '').strip()
    estado_pago = (request.GET.get('estado_pago') or request.GET.get('estado') or '').strip()
    if estado_pago in ('con_deuda', 'al_dia'):
        estado_pago = ''
    desde = parse_fecha(request.GET.get('vencimiento_desde'))
    hasta = parse_fecha(request.GET.get('vencimiento_hasta'))
    if desde and hasta and hasta < desde:
        desde, hasta = hasta, desde
    orden = (request.GET.get('orden') or 'desc').strip().lower()
    if orden not in ('asc', 'desc'):
        orden = 'desc'
    hoy = timezone.localdate()
    hoy_s = hoy.strftime('%Y-%m-%d')
    ayer_s = (hoy - timedelta(days=1)).strftime('%Y-%m-%d')
    mes_inicio = hoy.replace(day=1).strftime('%Y-%m-%d')
    mes_fin = hoy.replace(day=monthrange(hoy.year, hoy.month)[1]).strftime('%Y-%m-%d')
    desde_s = desde.strftime('%Y-%m-%d') if desde else ''
    hasta_s = hasta.strftime('%Y-%m-%d') if hasta else ''

    def _preset(ident, label, p_desde, p_hasta):
        return {
            'id': ident,
            'label': label,
            'href': _href_filtro_cc(search, estado_pago, p_desde, p_hasta, orden),
            'activo': desde_s == p_desde and hasta_s == p_hasta,
        }

    return {
        'search': search,
        'estado_pago': estado_pago,
        'vencimiento_desde': desde,
        'vencimiento_hasta': hasta,
        'vencimiento_desde_str': desde_s,
        'vencimiento_hasta_str': hasta_s,
        'orden': orden,
        'today': hoy,
        'presets_vencimiento': [
            _preset('hoy', 'Hoy', hoy_s, hoy_s),
            _preset('7d', '7 días', hoy_s, (hoy + timedelta(days=7)).strftime('%Y-%m-%d')),
            _preset('15d', '15 días', hoy_s, (hoy + timedelta(days=15)).strftime('%Y-%m-%d')),
            _preset('30d', '30 días', hoy_s, (hoy + timedelta(days=30)).strftime('%Y-%m-%d')),
            _preset('mes', 'Este mes', mes_inicio, mes_fin),
            _preset('vencidos', 'Vencidos', '', ayer_s),
        ],
        'querystring': request.GET.urlencode(),
    }


def _ctx_filtros_cc(filtros):
    return {
        'search': filtros['search'],
        'estado_pago': filtros['estado_pago'],
        'vencimiento_desde_str': filtros['vencimiento_desde_str'],
        'vencimiento_hasta_str': filtros['vencimiento_hasta_str'],
        'orden': filtros.get('orden', 'desc'),
        'today': filtros['today'],
        'presets_vencimiento': filtros['presets_vencimiento'],
        'querystring': filtros['querystring'],
    }


def _filtrar_por_vencimiento(qs, vencimiento_desde=None, vencimiento_hasta=None):
    if not vencimiento_desde and not vencimiento_hasta:
        return qs
    qs = qs.filter(fecha_vencimiento__isnull=False)
    if vencimiento_desde:
        qs = qs.filter(fecha_vencimiento__gte=vencimiento_desde)
    if vencimiento_hasta:
        qs = qs.filter(fecha_vencimiento__lte=vencimiento_hasta)
    return qs


def _en_rango_vencimiento(fecha_vencimiento, vencimiento_desde=None, vencimiento_hasta=None):
    if not vencimiento_desde and not vencimiento_hasta:
        return True
    if not fecha_vencimiento:
        return False
    if vencimiento_desde and fecha_vencimiento < vencimiento_desde:
        return False
    if vencimiento_hasta and fecha_vencimiento > vencimiento_hasta:
        return False
    return True


def _documentos_proveedor_filtrados(empresa, search='', estado_pago='', vencimiento_desde=None, vencimiento_hasta=None):
    hoy = timezone.localdate()
    documentos = DocumentoCompra.objects.filter(
        empresa=empresa,
        en_cuenta_corriente=True,
        estado_documento='activo',
    ).select_related('proveedor')

    if search:
        documentos = documentos.filter(
            Q(numero_documento__icontains=search) |
            Q(proveedor__nombre__icontains=search) |
            Q(proveedor__rut__icontains=search)
        )

    if estado_pago in ('pagado', 'pagada'):
        documentos = documentos.filter(Q(saldo_pendiente__lte=0) | Q(estado_pago='pagada'))
    elif estado_pago == 'vencida':
        documentos = documentos.filter(saldo_pendiente__gt=0, fecha_vencimiento__lt=hoy)
    elif estado_pago == 'parcial':
        documentos = documentos.filter(saldo_pendiente__gt=0, monto_pagado__gt=0)
    elif estado_pago in ('credito', 'pendiente'):
        documentos = documentos.filter(saldo_pendiente__gt=0).filter(
            Q(fecha_vencimiento__isnull=True) | Q(fecha_vencimiento__gte=hoy)
        ).filter(Q(monto_pagado__isnull=True) | Q(monto_pagado__lte=0))
    else:
        documentos = documentos.filter(saldo_pendiente__gt=0)

    documentos = _filtrar_por_vencimiento(documentos, vencimiento_desde, vencimiento_hasta)
    return documentos.order_by('fecha_vencimiento', 'fecha_emision', 'numero_documento')


def _stats_documentos_proveedor(documentos):
    return {
        'total_documentos': documentos.count(),
        'total_general': documentos.aggregate(Sum('total_documento'))['total_documento__sum'] or 0,
        'total_pagado': documentos.aggregate(Sum('monto_pagado'))['monto_pagado__sum'] or 0,
        'total_saldo': documentos.aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
        'total_pendiente': documentos.filter(estado_pago='credito').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
        'total_vencido': documentos.filter(estado_pago='vencida').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
        'total_parcial': documentos.filter(estado_pago='parcial').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
    }


def _pesos(valor):
    """Redondea a pesos enteros para mostrar y comparar saldos."""
    return int(round(Decimal(str(valor or 0))))


def _dte_de_venta_cc(venta):
    """DTE tributario de la venta (no el ticket de caja)."""
    if not venta:
        return None
    dte = getattr(venta, 'dte', None)
    if dte:
        return dte
    from facturacion_electronica.models import DocumentoTributarioElectronico
    dte = DocumentoTributarioElectronico.objects.filter(venta=venta).order_by('-id').first()
    if dte:
        return dte
    from caja.models import VentaProcesada
    vp = (
        VentaProcesada.objects.filter(venta_final=venta)
        .select_related('dte_generado')
        .order_by('-id')
        .first()
    )
    if vp and vp.dte_generado_id:
        return vp.dte_generado
    vp = (
        VentaProcesada.objects.filter(venta_preventa=venta)
        .select_related('dte_generado')
        .order_by('-id')
        .first()
    )
    if vp and vp.dte_generado_id:
        return vp.dte_generado
    return None


def _url_ver_documento_cc(venta):
    """Copia tributaria A4, sin usar la impresora térmica de la empresa."""
    if venta:
        return reverse('tesoreria:ver_documento_cc', args=[venta.id])
    return ''


def _anotar_saldos_movimiento_cliente(mov):
    """Saldo = total del documento (venta) − pagos HABER aplicados, en pesos."""
    from .models import MovimientoCuentaCorrienteCliente

    venta = getattr(mov, 'venta', None)
    if venta is not None:
        monto_factura = Decimal(str(venta.total or 0))
    else:
        monto_factura = Decimal(str(mov.monto or 0))

    total_pagado_result = MovimientoCuentaCorrienteCliente.objects.filter(
        cuenta_corriente=mov.cuenta_corriente,
        venta=mov.venta,
        tipo_movimiento='haber',
    ).aggregate(total=Sum('monto'))['total']
    total_pagado = Decimal(str(total_pagado_result or 0))

    if venta is not None:
        pagado_venta = Decimal(str(venta.monto_pagado or 0))
        if pagado_venta > total_pagado:
            total_pagado = pagado_venta

    saldo = monto_factura - total_pagado
    if saldo < 0:
        saldo = Decimal('0')

    if monto_factura > 0 and total_pagado >= monto_factura:
        mov.estado_pago = 'pagado'
    elif total_pagado > 0:
        mov.estado_pago = 'parcial'
    else:
        mov.estado_pago = 'pendiente'

    from core.fechas import calcular_fecha_vencimiento

    fecha_venc = getattr(venta, 'fecha_vencimiento', None) if venta is not None else None
    if not fecha_venc and venta is not None and getattr(venta, 'fecha', None):
        dias = getattr(venta.cliente, 'plazo_pago', 0) if getattr(venta, 'cliente_id', None) else 0
        fecha_venc = calcular_fecha_vencimiento(venta.fecha, dias)
    mov.fecha_vencimiento = fecha_venc
    hoy = timezone.localdate()
    if mov.estado_pago != 'pagado' and mov.fecha_vencimiento and mov.fecha_vencimiento < hoy:
        mov.estado_pago = 'vencido'
        mov.dias_vencido = (hoy - mov.fecha_vencimiento).days
    elif mov.fecha_vencimiento:
        mov.dias_vencido = (mov.fecha_vencimiento - hoy).days
    else:
        mov.dias_vencido = None

    mov.monto_display = _pesos(monto_factura)
    mov.total_pagado = _pesos(total_pagado)
    mov.saldo_pendiente_factura = _pesos(saldo)
    mov.url_documento = _url_ver_documento_cc(venta)
    return mov


def _folio_factura_movimiento(mov):
    """Extrae el número de factura/venta como entero para ordenamiento correlativo."""
    venta = getattr(mov, 'venta', None)
    folio = 0
    if venta:
        num_str = str(getattr(venta, 'numero_venta', '') or '').strip()
        digits = re.sub(r'\D', '', num_str)
        if digits:
            try:
                folio = int(digits)
            except (ValueError, TypeError):
                pass
        if folio == 0:
            dte = getattr(venta, 'dte', None)
            if dte and getattr(dte, 'folio', None):
                try:
                    folio = int(dte.folio)
                except (ValueError, TypeError):
                    pass
    return folio


def _movimientos_cliente_filtrados(empresa, search='', estado_pago='', vencimiento_desde=None, vencimiento_hasta=None, orden='desc'):
    from .models import MovimientoCuentaCorrienteCliente

    movimientos_base = MovimientoCuentaCorrienteCliente.objects.filter(
        cuenta_corriente__empresa=empresa,
        tipo_movimiento='debe'
    ).select_related(
        'cuenta_corriente', 'cuenta_corriente__cliente', 'venta', 'venta__cliente', 'venta__dte'
    ).order_by('-fecha_movimiento')

    movimientos = [_anotar_saldos_movimiento_cliente(mov) for mov in movimientos_base]

    if search:
        search_lower = search.lower()
        movimientos = [
            mov for mov in movimientos
            if (
                search_lower in mov.cuenta_corriente.cliente.nombre.lower() or
                search_lower in (mov.cuenta_corriente.cliente.rut or '').lower() or
                (mov.venta and search in mov.venta.numero_venta)
            )
        ]

    if estado_pago in ('pagado', 'pagada'):
        movimientos = [mov for mov in movimientos if mov.estado_pago == 'pagado']
    elif estado_pago == 'vencido':
        movimientos = [mov for mov in movimientos if mov.estado_pago == 'vencido']
    elif estado_pago == 'parcial':
        movimientos = [mov for mov in movimientos if mov.estado_pago == 'parcial']
    elif estado_pago in ('pendiente', 'credito'):
        movimientos = [mov for mov in movimientos if mov.estado_pago == 'pendiente']
    else:
        movimientos = [mov for mov in movimientos if mov.estado_pago != 'pagado' and mov.saldo_pendiente_factura > 0]

    if vencimiento_desde or vencimiento_hasta:
        movimientos = [
            mov for mov in movimientos
            if _en_rango_vencimiento(mov.fecha_vencimiento, vencimiento_desde, vencimiento_hasta)
        ]

    # Ordenar siempre por N° de factura (descendente por defecto, o ascendente si se solicita)
    if orden == 'asc':
        movimientos.sort(key=lambda m: (0 if _folio_factura_movimiento(m) > 0 else 1, _folio_factura_movimiento(m), m.id or 0))
    else:
        movimientos.sort(key=lambda m: (1 if _folio_factura_movimiento(m) > 0 else 0, _folio_factura_movimiento(m), m.id or 0), reverse=True)
    return movimientos


def _stats_movimientos_cliente(movimientos):
    return {
        'total_documentos': len(movimientos),
        'total_general': sum(m.monto_display for m in movimientos),
        'total_pagado': sum(m.total_pagado for m in movimientos),
        'total_saldo': sum(m.saldo_pendiente_factura for m in movimientos),
        'total_pendiente': sum(m.saldo_pendiente_factura for m in movimientos if m.estado_pago == 'pendiente'),
        'total_parcial': sum(m.saldo_pendiente_factura for m in movimientos if m.estado_pago == 'parcial'),
        'total_vencido': sum(m.saldo_pendiente_factura for m in movimientos if m.estado_pago == 'vencido'),
    }


@login_required
@requiere_empresa
def cuenta_corriente_proveedor_list(request):
    """Lista de cuentas corrientes de proveedores"""
    empresa = _empresa_de_request(request)
    if not empresa:
        messages.error(request, 'No hay empresas configuradas en el sistema.')
        return redirect('dashboard')
    persistir_empresa_activa(request, empresa)

    filtros = _filtros_cuenta_corriente(request)
    documentos_query = _documentos_proveedor_filtrados(
        empresa,
        search=filtros['search'],
        estado_pago=filtros['estado_pago'],
        vencimiento_desde=filtros['vencimiento_desde'],
        vencimiento_hasta=filtros['vencimiento_hasta'],
    )
    
    # Agregar información de pagos a cada documento
    for documento in documentos_query:
        documento.pagos = documento.historial_pagos.all().order_by('-fecha_pago')
    
    # Paginación
    paginator = Paginator(documentos_query, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Estadísticas
    stats = {
        'total_documentos': documentos_query.count(),
        'total_pendiente': documentos_query.filter(estado_pago='credito').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
        'total_vencido': documentos_query.filter(estado_pago='vencida').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
        'total_parcial': documentos_query.filter(estado_pago='parcial').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
    }
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'empresa': empresa,
        **_ctx_filtros_cc(filtros),
    }
    
    return render(request, 'tesoreria/cuenta_corriente_proveedor_list.html', context)


@login_required
@requiere_empresa
def cuenta_corriente_proveedor_print(request):
    """Reporte imprimible de cuenta corriente de proveedores."""
    empresa = request.empresa
    filtros = _filtros_cuenta_corriente(request)
    documentos = _documentos_proveedor_filtrados(
        empresa,
        search=filtros['search'],
        estado_pago=filtros['estado_pago'],
        vencimiento_desde=filtros['vencimiento_desde'],
        vencimiento_hasta=filtros['vencimiento_hasta'],
    )

    context = {
        'empresa': empresa,
        'documentos': documentos,
        'stats': _stats_documentos_proveedor(documentos),
        **_ctx_filtros_cc(filtros),
        'generated_at': timezone.now(),
        'titulo_reporte': 'Cuenta Corriente Proveedores',
        'subtitulo_reporte': 'Documentos de compra y saldos por pagar',
        'back_url': f"{request.path.rsplit('/imprimir/', 1)[0]}/" + (f"?{request.GET.urlencode()}" if request.GET else ""),
    }
    return render(request, 'tesoreria/cuenta_corriente_proveedor_print.html', context)


@login_required
@requiere_empresa
def exportar_cuenta_corriente_proveedor_excel(request):
    """Exportar cuentas corrientes de proveedores a Excel con formato profesional"""
    empresa = _empresa_de_request(request)
    if not empresa:
        return HttpResponse('No hay empresa configurada', status=400)

    filtros = _filtros_cuenta_corriente(request)
    documentos_query = _documentos_proveedor_filtrados(
        empresa,
        search=filtros['search'],
        estado_pago=filtros['estado_pago'],
        vencimiento_desde=filtros['vencimiento_desde'],
        vencimiento_hasta=filtros['vencimiento_hasta'],
    )
    documentos_list = list(documentos_query)
    
    # Crear workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Cuenta Corriente Proveedores"
    
    # Estilos profesionales
    title_font = Font(name='Poppins', size=18, bold=True, color="6F5B44")
    subtitle_font = Font(name='Poppins', size=11, color="6F5B44")
    header_font = Font(name='Poppins', size=11, bold=True, color="FFFFFF")
    data_font = Font(name='Poppins', size=10)
    
    header_fill = PatternFill(start_color="8B7355", end_color="6F5B44", fill_type="solid")
    title_fill = PatternFill(start_color="F5F1E8", end_color="E8DCC8", fill_type="solid")
    
    border = Border(
        left=Side(style='thin', color='D4C4A8'),
        right=Side(style='thin', color='D4C4A8'),
        top=Side(style='thin', color='D4C4A8'),
        bottom=Side(style='thin', color='D4C4A8')
    )
    
    # Título principal
    ws.merge_cells('A1:J1')
    cell_title = ws['A1']
    cell_title.value = f"CUENTA CORRIENTE PROVEEDORES - {empresa.nombre.upper()}"
    cell_title.font = title_font
    cell_title.alignment = Alignment(horizontal='center', vertical='center')
    cell_title.fill = title_fill
    ws.row_dimensions[1].height = 35
    
    # Información de la empresa y fecha
    ws.merge_cells('A2:J2')
    cell_info = ws['A2']
    cell_info.value = f"Fecha de exportación: {datetime.now().strftime('%d-%m-%Y %H:%M')}"
    cell_info.font = subtitle_font
    cell_info.alignment = Alignment(horizontal='center')
    ws.row_dimensions[2].height = 20
    
    # Espacio
    ws.row_dimensions[3].height = 10
    
    # Encabezados
    headers = [
        '#', 'N° Documento', 'Proveedor', 'RUT Proveedor', 'Fecha Emisión', 'Fecha Vencimiento',
        'Total Documento', 'Monto Pagado', 'Saldo Pendiente', 'Estado'
    ]
    
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    ws.row_dimensions[4].height = 25
    
    # Datos
    row_num = 5
    total_documento = 0
    total_pagado = 0
    total_pendiente = 0
    
    for idx, doc in enumerate(documentos_list, 1):
        # Número de fila
        ws.cell(row=row_num, column=1, value=idx).border = border
        ws.cell(row=row_num, column=1).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=1).font = data_font
        
        # N° Documento
        ws.cell(row=row_num, column=2, value=doc.numero_documento).border = border
        ws.cell(row=row_num, column=2).font = data_font
        
        # Proveedor
        proveedor_nombre = doc.proveedor.nombre if doc.proveedor else '-'
        ws.cell(row=row_num, column=3, value=proveedor_nombre).border = border
        ws.cell(row=row_num, column=3).font = data_font
        
        # RUT Proveedor
        proveedor_rut = doc.proveedor.rut if doc.proveedor and doc.proveedor.rut else '-'
        ws.cell(row=row_num, column=4, value=proveedor_rut).border = border
        ws.cell(row=row_num, column=4).font = data_font
        
        # Fecha Emisión
        fecha_str = doc.fecha_emision.strftime('%d-%m-%Y') if doc.fecha_emision else '-'
        ws.cell(row=row_num, column=5, value=fecha_str).border = border
        ws.cell(row=row_num, column=5).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=5).font = data_font

        venc_str = doc.fecha_vencimiento.strftime('%d-%m-%Y') if doc.fecha_vencimiento else '-'
        cell_venc = ws.cell(row=row_num, column=6, value=venc_str)
        cell_venc.border = border
        cell_venc.alignment = Alignment(horizontal='center')
        cell_venc.font = data_font
        
        # Total Documento
        monto_total = float(doc.total_documento or 0)
        cell_monto = ws.cell(row=row_num, column=7, value=monto_total)
        cell_monto.number_format = '$#,##0'
        cell_monto.border = border
        cell_monto.alignment = Alignment(horizontal='right')
        cell_monto.font = data_font
        total_documento += monto_total
        
        # Monto Pagado
        pagado = float(doc.monto_pagado or 0)
        cell_pagado = ws.cell(row=row_num, column=8, value=pagado)
        cell_pagado.number_format = '$#,##0'
        cell_pagado.border = border
        cell_pagado.alignment = Alignment(horizontal='right')
        cell_pagado.font = Font(name='Poppins', size=10, color='28a745')
        total_pagado += pagado
        
        # Saldo Pendiente
        pendiente = float(doc.saldo_pendiente or 0)
        cell_pendiente = ws.cell(row=row_num, column=9, value=pendiente)
        cell_pendiente.number_format = '$#,##0'
        cell_pendiente.border = border
        cell_pendiente.alignment = Alignment(horizontal='right')
        if pendiente > 0:
            cell_pendiente.font = Font(name='Poppins', size=10, color='dc3545', bold=True)
        else:
            cell_pendiente.font = Font(name='Poppins', size=10, color='28a745')
        total_pendiente += pendiente
        
        # Estado
        estado_texto = {
            'credito': 'Pendiente',
            'parcial': 'Pago Parcial',
            'vencida': 'Vencido',
            'pagado': 'Pagado'
        }.get(doc.estado_pago, doc.estado_pago.title() if doc.estado_pago else 'Sin estado')
        
        # Determinar estado visual si no está definido
        if not doc.estado_pago:
            if pendiente <= 0:
                estado_texto = 'Pagado'
            elif pagado > 0:
                estado_texto = 'Pago Parcial'
            else:
                estado_texto = 'Pendiente'
        
        cell_estado = ws.cell(row=row_num, column=10, value=estado_texto)
        cell_estado.border = border
        cell_estado.alignment = Alignment(horizontal='center')
        
        # Color según estado
        estado_actual = doc.estado_pago or ('pagado' if pendiente <= 0 else ('parcial' if pagado > 0 else 'credito'))
        
        if estado_actual == 'pagado' or pendiente <= 0:
            estado_fill = PatternFill(start_color="D4EDDA", end_color="C3E6CB", fill_type="solid")
            cell_estado.font = Font(name='Poppins', size=10, bold=True, color='155724')
        elif estado_actual == 'parcial' or (pagado > 0 and pendiente > 0):
            estado_fill = PatternFill(start_color="FFF3CD", end_color="FFE69C", fill_type="solid")
            cell_estado.font = Font(name='Poppins', size=10, bold=True, color='856404')
        elif estado_actual == 'vencida':
            estado_fill = PatternFill(start_color="F8D7DA", end_color="F5C6CB", fill_type="solid")
            cell_estado.font = Font(name='Poppins', size=10, bold=True, color='721C24')
        else:
            estado_fill = PatternFill(start_color="D1ECF1", end_color="BEE5EB", fill_type="solid")
            cell_estado.font = Font(name='Poppins', size=10, bold=True, color='0C5460')
        
        cell_estado.fill = estado_fill
        
        row_num += 1
    
    # Fila de totales
    ws.merge_cells(f'A{row_num}:F{row_num}')
    cell_total_label = ws[f'A{row_num}']
    cell_total_label.value = 'TOTALES'
    cell_total_label.font = Font(name='Poppins', size=11, bold=True, color="FFFFFF")
    cell_total_label.fill = header_fill
    cell_total_label.alignment = Alignment(horizontal='right', vertical='center')
    cell_total_label.border = border
    
    # Total Documento
    cell_total_doc = ws.cell(row=row_num, column=7, value=total_documento)
    cell_total_doc.number_format = '$#,##0'
    cell_total_doc.font = Font(name='Poppins', size=11, bold=True, color="FFFFFF")
    cell_total_doc.fill = header_fill
    cell_total_doc.alignment = Alignment(horizontal='right')
    cell_total_doc.border = border
    
    # Total Pagado
    cell_total_pagado = ws.cell(row=row_num, column=8, value=total_pagado)
    cell_total_pagado.number_format = '$#,##0'
    cell_total_pagado.font = Font(name='Poppins', size=11, bold=True, color="FFFFFF")
    cell_total_pagado.fill = header_fill
    cell_total_pagado.alignment = Alignment(horizontal='right')
    cell_total_pagado.border = border
    
    # Total Pendiente
    cell_total_pendiente = ws.cell(row=row_num, column=9, value=total_pendiente)
    cell_total_pendiente.number_format = '$#,##0'
    cell_total_pendiente.font = Font(name='Poppins', size=11, bold=True, color="FFFFFF")
    cell_total_pendiente.fill = header_fill
    cell_total_pendiente.alignment = Alignment(horizontal='right')
    cell_total_pendiente.border = border
    
    # Celda vacía para estado
    ws.cell(row=row_num, column=10).border = border
    ws.cell(row=row_num, column=10).fill = header_fill
    
    ws.row_dimensions[row_num].height = 25
    
    # Ajustar anchos de columna
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 35
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 15
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 18
    ws.column_dimensions['I'].width = 18
    ws.column_dimensions['J'].width = 15
    
    # Preparar respuesta
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    fecha_export = datetime.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename=cuenta_corriente_proveedores_{fecha_export}.xlsx'
    wb.save(response)
    return response


@login_required
@requiere_empresa
def cuenta_corriente_proveedor_detail(request, proveedor_id):
    """Detalle de cuenta corriente de un proveedor específico"""
    empresa = request.empresa
    
    # Obtener documentos del proveedor de la empresa activa
    documentos = DocumentoCompra.objects.filter(
        empresa=empresa,
        proveedor_id=proveedor_id,
        en_cuenta_corriente=True
    ).select_related('proveedor').order_by('fecha_vencimiento')
    
    # Si no hay documentos, el proveedor no es válido para esta empresa
    if not documentos.exists():
        messages.error(request, 'No se encontraron documentos para este proveedor en la empresa actual.')
        return redirect('tesoreria:cuenta_corriente_proveedor_list')
    
    proveedor = documentos.first().proveedor
    
    # Estadísticas
    stats = {
        'total_documentos': documentos.count(),
        'total_pendiente': documentos.filter(estado_pago='credito').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
        'total_vencido': documentos.filter(estado_pago='vencida').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
        'total_parcial': documentos.filter(estado_pago='parcial').aggregate(Sum('saldo_pendiente'))['saldo_pendiente__sum'] or 0,
    }
    
    context = {
        'proveedor': proveedor,
        'documentos': documentos,
        'stats': stats,
        'empresa': empresa,
        'today': timezone.localdate(),
    }
    
    return render(request, 'tesoreria/cuenta_corriente_proveedor_detail.html', context)


@login_required
@requiere_empresa
def cuenta_corriente_proveedor_detail_print(request, proveedor_id):
    """Reporte imprimible del detalle de cuenta corriente de un proveedor."""
    empresa = request.empresa
    documentos = DocumentoCompra.objects.filter(
        empresa=empresa,
        proveedor_id=proveedor_id,
        en_cuenta_corriente=True
    ).select_related('proveedor').order_by('fecha_vencimiento', 'fecha_emision', 'numero_documento')

    if not documentos.exists():
        messages.error(request, 'No se encontraron documentos para este proveedor en la empresa actual.')
        return redirect('tesoreria:cuenta_corriente_proveedor_list')

    proveedor = documentos.first().proveedor
    context = {
        'empresa': empresa,
        'proveedor': proveedor,
        'documentos': documentos,
        'stats': _stats_documentos_proveedor(documentos),
        'today': timezone.localdate(),
        'generated_at': timezone.now(),
        'titulo_reporte': f'Cuenta Corriente Proveedor',
        'subtitulo_reporte': proveedor.nombre,
        'back_url': request.path.rsplit('/imprimir/', 1)[0] + '/',
    }
    return render(request, 'tesoreria/cuenta_corriente_proveedor_detail_print.html', context)


@login_required
@requiere_empresa
def ver_documento_cc(request, venta_id):
    """Copia A4 del DTE. No usa la impresora térmica configurada en la empresa."""
    from ventas.models import Venta
    from facturacion_electronica.views_dte import ver_factura_electronica

    venta = get_object_or_404(Venta, pk=venta_id, empresa=request.empresa)
    dte = _dte_de_venta_cc(venta)
    if not dte:
        messages.error(request, 'Esta venta no tiene factura electrónica para mostrar.')
        return redirect('tesoreria:cuenta_corriente_cliente_list')
    return ver_factura_electronica(request, dte.pk, forzar_a4=True)


@login_required
@requiere_empresa
def cuenta_corriente_cliente_list(request):
    """Lista de cuentas corrientes de clientes"""
    # La empresa ya está configurada por el decorador @requiere_empresa
    empresa = request.empresa
    filtros = _filtros_cuenta_corriente(request)
    movimientos_list = _movimientos_cliente_filtrados(
        empresa,
        search=filtros['search'],
        estado_pago=filtros['estado_pago'],
        vencimiento_desde=filtros['vencimiento_desde'],
        vencimiento_hasta=filtros['vencimiento_hasta'],
        orden=filtros['orden'],
    )

    paginator = Paginator(movimientos_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    stats = _stats_movimientos_cliente(movimientos_list)
    
    context = {
        'empresa': empresa,
        'page_obj': page_obj,
        'stats': stats,
        **_ctx_filtros_cc(filtros),
    }
    
    return render(request, 'tesoreria/cuenta_corriente_cliente_list.html', context)


@login_required
@requiere_empresa
def cuenta_corriente_cliente_print(request):
    """Reporte imprimible de cuenta corriente de clientes."""
    empresa = request.empresa
    filtros = _filtros_cuenta_corriente(request)
    movimientos = _movimientos_cliente_filtrados(
        empresa,
        search=filtros['search'],
        estado_pago=filtros['estado_pago'],
        vencimiento_desde=filtros['vencimiento_desde'],
        vencimiento_hasta=filtros['vencimiento_hasta'],
        orden=filtros['orden'],
    )

    context = {
        'empresa': empresa,
        'movimientos': movimientos,
        'stats': _stats_movimientos_cliente(movimientos),
        **_ctx_filtros_cc(filtros),
        'generated_at': timezone.now(),
        'titulo_reporte': 'Cuenta Corriente Clientes',
        'subtitulo_reporte': 'Documentos de venta y saldos por cobrar',
        'back_url': f"{request.path.rsplit('/imprimir/', 1)[0]}/" + (f"?{request.GET.urlencode()}" if request.GET else ""),
    }
    return render(request, 'tesoreria/cuenta_corriente_cliente_print.html', context)


@login_required
@requiere_empresa
def exportar_cuenta_corriente_cliente_excel(request):
    """Exportar cuentas corrientes de clientes a Excel con formato profesional"""
    empresa = request.empresa
    filtros = _filtros_cuenta_corriente(request)
    movimientos_list = _movimientos_cliente_filtrados(
        empresa,
        search=filtros['search'],
        estado_pago=filtros['estado_pago'],
        vencimiento_desde=filtros['vencimiento_desde'],
        vencimiento_hasta=filtros['vencimiento_hasta'],
        orden=filtros['orden'],
    )
    
    # Crear workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Cuenta Corriente Clientes"
    
    # Estilos profesionales
    title_font = Font(name='Poppins', size=18, bold=True, color="6F5B44")
    subtitle_font = Font(name='Poppins', size=11, color="6F5B44")
    header_font = Font(name='Poppins', size=11, bold=True, color="FFFFFF")
    data_font = Font(name='Poppins', size=10)
    
    header_fill = PatternFill(start_color="8B7355", end_color="6F5B44", fill_type="solid")
    title_fill = PatternFill(start_color="F5F1E8", end_color="E8DCC8", fill_type="solid")
    
    border = Border(
        left=Side(style='thin', color='D4C4A8'),
        right=Side(style='thin', color='D4C4A8'),
        top=Side(style='thin', color='D4C4A8'),
        bottom=Side(style='thin', color='D4C4A8')
    )
    
    # Título principal
    ws.merge_cells('A1:J1')
    cell_title = ws['A1']
    cell_title.value = f"CUENTA CORRIENTE CLIENTES - {empresa.nombre.upper()}"
    cell_title.font = title_font
    cell_title.alignment = Alignment(horizontal='center', vertical='center')
    cell_title.fill = title_fill
    ws.row_dimensions[1].height = 35
    
    # Información de la empresa y fecha
    ws.merge_cells('A2:J2')
    cell_info = ws['A2']
    cell_info.value = f"Fecha de exportación: {datetime.now().strftime('%d-%m-%Y %H:%M')}"
    cell_info.font = subtitle_font
    cell_info.alignment = Alignment(horizontal='center')
    ws.row_dimensions[2].height = 20
    
    # Espacio
    ws.row_dimensions[3].height = 10
    
    # Encabezados
    headers = [
        '#', 'N° Factura', 'Cliente', 'RUT Cliente', 'Fecha Emisión', 'Fecha Vencimiento',
        'Monto Total', 'Total Pagado', 'Saldo Pendiente', 'Estado'
    ]
    
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_num)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    ws.row_dimensions[4].height = 25
    
    # Datos
    row_num = 5
    total_monto = 0
    total_pagado = 0
    total_pendiente = 0
    
    for idx, mov in enumerate(movimientos_list, 1):
        # Número de fila
        ws.cell(row=row_num, column=1, value=idx).border = border
        ws.cell(row=row_num, column=1).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=1).font = data_font
        
        # N° Factura
        numero_factura = mov.venta.numero_venta if mov.venta else '-'
        ws.cell(row=row_num, column=2, value=numero_factura).border = border
        ws.cell(row=row_num, column=2).font = data_font
        
        # Cliente
        cliente_nombre = mov.cuenta_corriente.cliente.nombre
        ws.cell(row=row_num, column=3, value=cliente_nombre).border = border
        ws.cell(row=row_num, column=3).font = data_font
        
        # RUT Cliente
        cliente_rut = mov.cuenta_corriente.cliente.rut or '-'
        ws.cell(row=row_num, column=4, value=cliente_rut).border = border
        ws.cell(row=row_num, column=4).font = data_font
        
        # Fecha
        fecha_str = mov.fecha_movimiento.strftime('%d-%m-%Y') if mov.fecha_movimiento else '-'
        ws.cell(row=row_num, column=5, value=fecha_str).border = border
        ws.cell(row=row_num, column=5).alignment = Alignment(horizontal='center')
        ws.cell(row=row_num, column=5).font = data_font

        venc_str = mov.fecha_vencimiento.strftime('%d-%m-%Y') if mov.fecha_vencimiento else '-'
        cell_venc = ws.cell(row=row_num, column=6, value=venc_str)
        cell_venc.border = border
        cell_venc.alignment = Alignment(horizontal='center')
        cell_venc.font = data_font
        
        # Monto Total
        monto_total = mov.monto_display
        cell_monto = ws.cell(row=row_num, column=7, value=monto_total)
        cell_monto.number_format = '$#,##0'
        cell_monto.border = border
        cell_monto.alignment = Alignment(horizontal='right')
        cell_monto.font = data_font
        total_monto += monto_total
        
        # Total Pagado
        pagado = mov.total_pagado
        cell_pagado = ws.cell(row=row_num, column=8, value=pagado)
        cell_pagado.number_format = '$#,##0'
        cell_pagado.border = border
        cell_pagado.alignment = Alignment(horizontal='right')
        cell_pagado.font = Font(name='Poppins', size=10, color='28a745')
        total_pagado += pagado
        
        # Saldo Pendiente
        pendiente = mov.saldo_pendiente_factura
        cell_pendiente = ws.cell(row=row_num, column=9, value=pendiente)
        cell_pendiente.number_format = '$#,##0'
        cell_pendiente.border = border
        cell_pendiente.alignment = Alignment(horizontal='right')
        if pendiente > 0:
            cell_pendiente.font = Font(name='Poppins', size=10, color='dc3545', bold=True)
        else:
            cell_pendiente.font = Font(name='Poppins', size=10, color='28a745')
        total_pendiente += pendiente
        
        # Estado
        estado_texto = {
            'pagado': 'Pagado',
            'parcial': 'Parcial',
            'pendiente': 'Pendiente',
            'vencido': 'Vencido',
        }.get(mov.estado_pago, mov.estado_pago.title())
        
        cell_estado = ws.cell(row=row_num, column=10, value=estado_texto)
        cell_estado.border = border
        cell_estado.alignment = Alignment(horizontal='center')
        
        # Color según estado
        if mov.estado_pago == 'pagado':
            estado_fill = PatternFill(start_color="D4EDDA", end_color="C3E6CB", fill_type="solid")
            cell_estado.font = Font(name='Poppins', size=10, bold=True, color='155724')
        elif mov.estado_pago == 'parcial':
            estado_fill = PatternFill(start_color="FFF3CD", end_color="FFE69C", fill_type="solid")
            cell_estado.font = Font(name='Poppins', size=10, bold=True, color='856404')
        else:
            estado_fill = PatternFill(start_color="F8D7DA", end_color="F5C6CB", fill_type="solid")
            cell_estado.font = Font(name='Poppins', size=10, bold=True, color='721C24')
        
        cell_estado.fill = estado_fill
        
        row_num += 1
    
    # Fila de totales
    ws.merge_cells(f'A{row_num}:F{row_num}')
    cell_total_label = ws[f'A{row_num}']
    cell_total_label.value = 'TOTALES'
    cell_total_label.font = Font(name='Poppins', size=11, bold=True, color="FFFFFF")
    cell_total_label.fill = header_fill
    cell_total_label.alignment = Alignment(horizontal='right', vertical='center')
    cell_total_label.border = border
    
    # Total Monto
    cell_total_monto = ws.cell(row=row_num, column=7, value=total_monto)
    cell_total_monto.number_format = '$#,##0'
    cell_total_monto.font = Font(name='Poppins', size=11, bold=True, color="FFFFFF")
    cell_total_monto.fill = header_fill
    cell_total_monto.alignment = Alignment(horizontal='right')
    cell_total_monto.border = border
    
    # Total Pagado
    cell_total_pagado = ws.cell(row=row_num, column=8, value=total_pagado)
    cell_total_pagado.number_format = '$#,##0'
    cell_total_pagado.font = Font(name='Poppins', size=11, bold=True, color="FFFFFF")
    cell_total_pagado.fill = header_fill
    cell_total_pagado.alignment = Alignment(horizontal='right')
    cell_total_pagado.border = border
    
    # Total Pendiente
    cell_total_pendiente = ws.cell(row=row_num, column=9, value=total_pendiente)
    cell_total_pendiente.number_format = '$#,##0'
    cell_total_pendiente.font = Font(name='Poppins', size=11, bold=True, color="FFFFFF")
    cell_total_pendiente.fill = header_fill
    cell_total_pendiente.alignment = Alignment(horizontal='right')
    cell_total_pendiente.border = border
    
    # Celda vacía para estado
    ws.cell(row=row_num, column=10).border = border
    ws.cell(row=row_num, column=10).fill = header_fill
    
    ws.row_dimensions[row_num].height = 25
    
    # Ajustar anchos de columna
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 15
    ws.column_dimensions['C'].width = 35
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 16
    ws.column_dimensions['G'].width = 15
    ws.column_dimensions['H'].width = 15
    ws.column_dimensions['I'].width = 18
    ws.column_dimensions['J'].width = 15
    
    # Preparar respuesta
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    fecha_export = datetime.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename=cuenta_corriente_clientes_{fecha_export}.xlsx'
    wb.save(response)
    return response


@csrf_exempt
@login_required
def registrar_pago(request):
    """Registrar un pago con múltiples formas de pago mediante AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        documento_id = data.get('documento_id')
        formas_pago = data.get('formas_pago', [])
        observaciones = data.get('observaciones', '')
        
        documento = get_object_or_404(DocumentoCompra, pk=documento_id)
        
        # Validar que hay formas de pago
        if not formas_pago:
            return JsonResponse({'error': 'Debe especificar al menos una forma de pago'}, status=400)
        
        # Calcular monto total - manejar tanto números como strings con separadores
        monto_total = sum(parse_monto_chileno(forma['monto']) for forma in formas_pago)
        
        # Validar monto
        if monto_total <= 0:
            return JsonResponse({'error': 'El monto debe ser mayor a 0'}, status=400)
        
        if monto_total > documento.saldo_pendiente:
            return JsonResponse({'error': 'El monto excede el saldo pendiente'}, status=400)
        
        # Registrar el pago - asegurar que monto_pagado sea Decimal
        if documento.monto_pagado is None:
            documento.monto_pagado = Decimal('0')
        else:
            documento.monto_pagado = Decimal(str(documento.monto_pagado))
        
        documento.monto_pagado += monto_total
        documento.calcular_totales()
        documento.save()  # Guardar el documento actualizado
        
        # Crear registro de pago principal
        from documentos.models import HistorialPagoDocumento, FormaPagoPago
        from django.utils import timezone
        
        pago = HistorialPagoDocumento.objects.create(
            documento_compra=documento,
            fecha_pago=timezone.now(),
            monto_total_pagado=monto_total,
            observaciones=observaciones,
            registrado_por=request.user
        )
        
        # Crear las formas de pago específicas
        for forma_data in formas_pago:
            from ventas.models import FormaPago
            
            # Obtener la forma de pago del sistema
            try:
                forma_pago_obj = FormaPago.objects.get(
                    id=forma_data.get('forma_pago_id'),
                    empresa=documento.empresa,
                    activo=True
                )
            except FormaPago.DoesNotExist:
                return JsonResponse({'error': 'Forma de pago no válida'}, status=400)
            
            forma_pago = FormaPagoPago.objects.create(
                pago=pago,
                forma_pago=forma_pago_obj,
                monto=parse_monto_chileno(forma_data['monto']),
                numero_cheque=forma_data.get('numero_cheque', ''),
                banco_cheque=forma_data.get('banco_cheque', ''),
                numero_transferencia=forma_data.get('numero_transferencia', ''),
                banco_transferencia=forma_data.get('banco_transferencia', ''),
                numero_tarjeta=forma_data.get('numero_tarjeta', ''),
                codigo_autorizacion=forma_data.get('codigo_autorizacion', ''),
                observaciones=forma_data.get('observaciones', '')
            )
            
            # Si es cheque, manejar fecha de vencimiento
            if forma_pago_obj.requiere_cheque and forma_data.get('fecha_vencimiento_cheque'):
                from datetime import datetime
                try:
                    fecha_vencimiento = datetime.strptime(forma_data['fecha_vencimiento_cheque'], '%Y-%m-%d').date()
                    forma_pago.fecha_vencimiento_cheque = fecha_vencimiento
                    forma_pago.save()
                except ValueError:
                    pass  # Ignorar fecha inválida
        
        return JsonResponse({
            'success': True,
            'message': f'Pago registrado exitosamente por ${monto_total:,.0f}',
            'saldo_pendiente': str(documento.saldo_pendiente),
            'estado_pago': documento.get_estado_pago_display()
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error al procesar el pago: {str(e)}'}, status=500)


@login_required
def obtener_formas_pago(request):
    """Obtener formas de pago disponibles para la empresa"""
    try:
        empresa = _empresa_de_request(request)
        if not empresa:
            empresa = Empresa.objects.first()
        
        from ventas.models import FormaPago
        
        # Para Kreasoft, usar solo las formas de pago originales (excluyendo CREDITO y duplicados)
        if empresa and 'kreasoft' in empresa.nombre.lower():
            formas_pago = FormaPago.objects.filter(
                empresa=empresa,
                activo=True,
                id__in=[1, 2, 3, 4]  # Solo las formas de pago originales, excluyendo CREDITO (ID 5)
            ).order_by('id')
        else:
            # Para otras empresas, usar todas las formas de pago activas
            formas_pago = FormaPago.objects.filter(
                empresa=empresa,
                activo=True
            ).order_by('nombre')
        
        data = [{
            'id': fp.id,
            'codigo': fp.codigo,
            'nombre': fp.nombre,
            'requiere_cheque': fp.requiere_cheque,
            'es_cuenta_corriente': fp.es_cuenta_corriente
        } for fp in formas_pago]
        
        return JsonResponse({'formas_pago': data})
        
    except Exception as e:
        return JsonResponse({'error': f'Error al obtener formas de pago: {str(e)}'}, status=500)


@login_required
def cambiar_empresa_activa(request):
    """Cambiar la empresa activa para superusuarios"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'No autorizado'}, status=403)
    
    if request.method == 'POST':
        try:
            empresa_id = clean_id(request.POST.get('empresa_id'))
            if not empresa_id:
                return JsonResponse({'error': 'ID de empresa requerido'}, status=400)
            
            empresa = Empresa.objects.get(id=empresa_id)
            persistir_empresa_activa(request, empresa)
            response = JsonResponse({
                'success': True,
                'message': f'Empresa cambiada a: {empresa.nombre}',
                'empresa': {
                    'id': empresa.id,
                    'nombre': empresa.nombre
                }
            })
            response.set_cookie(
                'empresa_activa_id',
                empresa.id,
                max_age=30 * 24 * 60 * 60,
                httponly=True,
                samesite='Lax'
            )
            return response
            
        except Empresa.DoesNotExist:
            return JsonResponse({'error': 'Empresa no encontrada'}, status=404)
        except Exception as e:
            return JsonResponse({'error': f'Error al cambiar empresa: {str(e)}'}, status=500)
    
    # GET: Obtener lista de empresas disponibles
    empresas = Empresa.objects.all().order_by('nombre')
    empresas_data = [{
        'id': emp.id,
        'nombre': emp.nombre,
        'rut': emp.rut,
        'activa': empresa_id_desde_sesion(request) == emp.id
    } for emp in empresas]
    
    return JsonResponse({'empresas': empresas_data})


@login_required
def historial_pagos_documento(request, documento_id):
    """Obtener historial de pagos de un documento"""
    try:
        documento = get_object_or_404(DocumentoCompra, pk=documento_id)
        pagos = documento.historial_pagos.all().select_related('registrado_por').prefetch_related('formas_pago__forma_pago').order_by('-fecha_pago')

        pagos_data = []
        total_pagado = 0

        for pago in pagos:
            formas = []
            for fp in pago.formas_pago.all():
                refs = []
                if fp.numero_transferencia:
                    refs.append(f'N° transf. {fp.numero_transferencia}')
                if fp.banco_transferencia:
                    refs.append(fp.banco_transferencia)
                if fp.numero_cheque:
                    refs.append(f'Cheque {fp.numero_cheque}')
                if fp.banco_cheque:
                    refs.append(fp.banco_cheque)
                if fp.fecha_vencimiento_cheque:
                    refs.append(f'Vence {fp.fecha_vencimiento_cheque.strftime("%d-%m-%Y")}')
                if fp.numero_tarjeta:
                    refs.append(f'Tarjeta {fp.numero_tarjeta}')
                if fp.codigo_autorizacion:
                    refs.append(f'Aut. {fp.codigo_autorizacion}')
                if fp.observaciones:
                    refs.append(fp.observaciones)
                nombre = fp.forma_pago.nombre if fp.forma_pago else 'Sin forma'
                formas.append({
                    'nombre': nombre,
                    'monto': str(fp.monto),
                    'detalle': ' · '.join(refs) if refs else 'Sin número ni banco registrado',
                })

            usuario = ''
            if pago.registrado_por:
                usuario = pago.registrado_por.get_full_name() or pago.registrado_por.username

            pagos_data.append({
                'id': pago.id,
                'fecha': pago.fecha_pago.strftime('%d-%m-%Y %H:%M') if pago.fecha_pago else '',
                'monto': str(pago.monto_total_pagado),
                'forma_pago': ', '.join(f['nombre'] for f in formas) if formas else 'Sin forma de pago',
                'formas': formas,
                'observaciones': pago.observaciones or '',
                'registrado_por': usuario,
            })
            total_pagado += float(pago.monto_total_pagado or 0)

        return JsonResponse({
            'pagos': pagos_data,
            'total_pagado': total_pagado,
            'documento': {
                'numero': documento.numero_documento,
                'proveedor': documento.proveedor.nombre if documento.proveedor else '',
                'total': str(documento.total_documento or 0),
                'pagado': str(documento.monto_pagado or 0),
                'saldo': str(documento.saldo_pendiente or 0),
            },
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def detalle_pago(request, pago_id):
    """Ver detalle de un pago específico"""
    try:
        from documentos.models import HistorialPagoDocumento
        
        pago = get_object_or_404(HistorialPagoDocumento, pk=pago_id)
        
        # Verificar permisos
        if not request.user.is_superuser:
            try:
                if request.user.perfil.empresa != pago.documento_compra.empresa:
                    return JsonResponse({'error': 'No tienes permisos para ver este pago'}, status=403)
            except:
                return JsonResponse({'error': 'Usuario no tiene empresa asociada'}, status=403)
        
        # Obtener formas de pago del pago
        formas_pago = pago.formas_pago.all()
        
        data = {
            'pago': {
                'id': pago.id,
                'fecha_pago': pago.fecha_pago.strftime('%d-%m-%Y %H:%M'),
                'monto_total_pagado': str(pago.monto_total_pagado),
                'observaciones': pago.observaciones,
                'registrado_por': (pago.registrado_por.get_full_name() or pago.registrado_por.username) if pago.registrado_por else ''
            },
            'documento': {
                'numero_documento': pago.documento_compra.numero_documento,
                'proveedor': pago.documento_compra.proveedor.nombre,
                'total_documento': str(pago.documento_compra.total_documento),
                'saldo_pendiente': str(pago.documento_compra.saldo_pendiente)
            },
            'formas_pago': [{
                'id': fp.id,
                'forma_pago_id': fp.forma_pago_id,
                'forma_pago': fp.forma_pago.nombre if fp.forma_pago else '',
                'codigo': fp.forma_pago.codigo if fp.forma_pago else '',
                'monto': str(fp.monto),
                'numero_cheque': fp.numero_cheque or '',
                'banco_cheque': fp.banco_cheque or '',
                'fecha_vencimiento_cheque': fp.fecha_vencimiento_cheque.strftime('%Y-%m-%d') if fp.fecha_vencimiento_cheque else '',
                'numero_transferencia': fp.numero_transferencia or '',
                'banco_transferencia': fp.banco_transferencia or '',
                'numero_tarjeta': fp.numero_tarjeta or '',
                'codigo_autorizacion': fp.codigo_autorizacion or '',
                'observaciones': fp.observaciones or ''
            } for fp in formas_pago]
        }
        
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'error': f'Error al obtener detalle del pago: {str(e)}'}, status=500)


@login_required
def editar_pago(request, pago_id):
    """Editar un pago existente"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        from django.db import transaction
        from documentos.models import HistorialPagoDocumento, FormaPagoPago
        from ventas.models import FormaPago
        
        pago = get_object_or_404(HistorialPagoDocumento, pk=pago_id)
        
        # Verificar permisos
        if not request.user.is_superuser:
            try:
                if request.user.perfil.empresa != pago.documento_compra.empresa:
                    return JsonResponse({'error': 'No tienes permisos para editar este pago'}, status=403)
            except:
                return JsonResponse({'error': 'Usuario no tiene empresa asociada'}, status=403)
        
        data = json.loads(request.body)
        formas_pago = data.get('formas_pago', [])
        observaciones = data.get('observaciones', '')
        
        if not formas_pago:
            return JsonResponse({'error': 'Debe especificar al menos una forma de pago'}, status=400)
        
        # Calcular nuevo monto total
        nuevo_monto_total = sum(parse_monto_chileno(forma['monto']) for forma in formas_pago)
        
        if nuevo_monto_total <= 0:
            return JsonResponse({'error': 'El monto debe ser mayor a 0'}, status=400)

        documento = pago.documento_compra
        max_permitido = (documento.saldo_pendiente or Decimal('0')) + (pago.monto_total_pagado or Decimal('0'))
        if nuevo_monto_total > max_permitido:
            return JsonResponse({
                'error': f'El monto excede el total de este documento (${max_permitido:,.0f})'
            }, status=400)

        with transaction.atomic():
            documento.monto_pagado = (documento.monto_pagado or Decimal('0')) - (pago.monto_total_pagado or Decimal('0'))
            pago.formas_pago.all().delete()
            pago.monto_total_pagado = nuevo_monto_total
            pago.observaciones = observaciones
            pago.save()

            for forma_data in formas_pago:
                forma_pago_obj = FormaPago.objects.get(
                    id=forma_data.get('forma_pago_id'),
                    empresa=documento.empresa
                )

                forma_pago = FormaPagoPago.objects.create(
                    pago=pago,
                    forma_pago=forma_pago_obj,
                    monto=parse_monto_chileno(forma_data['monto']),
                    numero_cheque=forma_data.get('numero_cheque', ''),
                    banco_cheque=forma_data.get('banco_cheque', ''),
                    numero_transferencia=forma_data.get('numero_transferencia', ''),
                    banco_transferencia=forma_data.get('banco_transferencia', ''),
                    numero_tarjeta=forma_data.get('numero_tarjeta', ''),
                    codigo_autorizacion=forma_data.get('codigo_autorizacion', ''),
                    observaciones=forma_data.get('observaciones', '')
                )

                if forma_pago_obj.requiere_cheque and forma_data.get('fecha_vencimiento_cheque'):
                    try:
                        fecha_vencimiento = datetime.strptime(forma_data['fecha_vencimiento_cheque'], '%Y-%m-%d').date()
                        forma_pago.fecha_vencimiento_cheque = fecha_vencimiento
                        forma_pago.save()
                    except ValueError:
                        pass

            documento.monto_pagado += nuevo_monto_total
            documento.calcular_totales()
            documento.save()

        return JsonResponse({
            'success': True,
            'message': f'Pago actualizado exitosamente por ${nuevo_monto_total:,.0f}',
            'saldo_pendiente': str(documento.saldo_pendiente),
            'estado_pago': documento.get_estado_pago_display()
        })
        
    except Exception as e:
        return JsonResponse({'error': f'Error al actualizar el pago: {str(e)}'}, status=500)


# ==================== CRUD DOCUMENTOS PENDIENTES ====================

@login_required
@requiere_empresa
def documento_pendiente_proveedor_list(request):
    """Lista de documentos pendientes de proveedores"""
    empresa = request.empresa if hasattr(request, 'empresa') else request.user.perfil.empresa
    
    documentos = DocumentoCompra.objects.filter(
        empresa=empresa,
        en_cuenta_corriente=True
    ).select_related('proveedor').order_by('-fecha_emision')
    
    # Filtros
    search = request.GET.get('search', '')
    if search:
        documentos = documentos.filter(
            Q(numero_documento__icontains=search) |
            Q(proveedor__nombre__icontains=search)
        )
    
    paginator = Paginator(documentos, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    return render(request, 'tesoreria/documento_pendiente_proveedor_list.html', context)


@login_required
def documento_pendiente_proveedor_create(request):
    """Crear documento pendiente de proveedor (modal)"""
    empresa = request.empresa if hasattr(request, 'empresa') else request.user.perfil.empresa
    
    if request.method == 'POST':
        try:
            from core.fechas import calcular_fecha_vencimiento, parse_fecha
            proveedor_id = request.POST.get('proveedor')
            proveedor = get_object_or_404(Proveedor, pk=proveedor_id, empresa=empresa)
            total = int(parse_monto_chileno(request.POST.get('total', 0)))
            fecha_emision = parse_fecha(request.POST.get('fecha_emision'))
            fecha_vencimiento = parse_fecha(request.POST.get('fecha_vencimiento')) or calcular_fecha_vencimiento(
                fecha_emision, proveedor.plazo_pago
            )
            
            documento = DocumentoCompra.objects.create(
                empresa=empresa,
                proveedor=proveedor,
                bodega=Bodega.objects.filter(empresa=empresa).first(),
                tipo_documento=request.POST.get('tipo_documento'),
                numero_documento=request.POST.get('numero_documento'),
                fecha_emision=fecha_emision,
                fecha_vencimiento=fecha_vencimiento,
                total_documento=total,
                saldo_pendiente=Decimal(total),
                en_cuenta_corriente=True,
                estado_pago='credito',
                observaciones=request.POST.get('observaciones', ''),
                creado_por=request.user
            )
            
            return JsonResponse({'success': True, 'message': f'Documento {documento.numero_documento} creado exitosamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    proveedores = Proveedor.objects.filter(empresa=empresa, estado='activo')
    context = {'proveedores': proveedores}
    return HttpResponse(render_to_string('tesoreria/includes/documento_form_modal.html', context, request=request))


@login_required
def documento_pendiente_proveedor_edit(request, pk):
    """Editar documento pendiente de proveedor (modal)"""
    empresa = request.empresa if hasattr(request, 'empresa') else request.user.perfil.empresa
    documento = get_object_or_404(DocumentoCompra, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        try:
            from core.fechas import calcular_fecha_vencimiento, parse_fecha
            proveedor_id = request.POST.get('proveedor')
            proveedor = get_object_or_404(Proveedor, pk=proveedor_id, empresa=empresa)
            total = int(parse_monto_chileno(request.POST.get('total', 0)))
            fecha_emision = parse_fecha(request.POST.get('fecha_emision'))
            fecha_vencimiento = parse_fecha(request.POST.get('fecha_vencimiento')) or calcular_fecha_vencimiento(
                fecha_emision, proveedor.plazo_pago
            )
            
            documento.proveedor = proveedor
            documento.tipo_documento = request.POST.get('tipo_documento')
            documento.numero_documento = request.POST.get('numero_documento')
            documento.fecha_emision = fecha_emision
            documento.fecha_vencimiento = fecha_vencimiento
            documento.total_documento = total
            documento.saldo_pendiente = Decimal(total) - documento.monto_pagado
            documento.observaciones = request.POST.get('observaciones', '')
            documento.save()
            
            return JsonResponse({'success': True, 'message': f'Documento {documento.numero_documento} actualizado exitosamente.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})
    
    proveedores = Proveedor.objects.filter(empresa=empresa, estado='activo')
    context = {'documento': documento, 'proveedores': proveedores}
    return HttpResponse(render_to_string('tesoreria/includes/documento_form_modal.html', context, request=request))


@login_required
@requiere_empresa
def documento_pendiente_proveedor_delete(request, pk):
    """Eliminar documento pendiente de proveedor"""
    empresa = request.empresa if hasattr(request, 'empresa') else request.user.perfil.empresa
    documento = get_object_or_404(DocumentoCompra, pk=pk, empresa=empresa)
    
    if request.method == 'POST':
        numero = documento.numero_documento
        documento.delete()
        return JsonResponse({'success': True, 'message': f'Documento {numero} eliminado exitosamente.'})
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})


# ==================== CRUD DOCUMENTOS PENDIENTES CLIENTES ====================

@login_required
def obtener_clientes(request):
    """Obtener lista de clientes activos de la empresa"""
    try:
        # Obtener empresa del usuario
        empresa = _empresa_de_request(request)
        if not empresa:
            return JsonResponse({'error': 'No se encontró empresa'}, status=400)

        from clientes.models import Cliente
        clientes = Cliente.objects.filter(empresa=empresa).order_by('nombre')
        
        clientes_data = [{
            'id': cliente.id,
            'nombre': cliente.nombre,
            'rut': cliente.rut or '',
            'plazo_pago': int(cliente.plazo_pago or 0),
        } for cliente in clientes]
        
        return JsonResponse({'clientes': clientes_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def crear_documento_cliente(request):
    """Crear documento pendiente de cliente"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        # Obtener empresa del usuario
        empresa = _empresa_de_request(request)
        if not empresa:
            return JsonResponse({'success': False, 'message': 'No se encontró empresa'})
        
        from clientes.models import Cliente
        from .models import DocumentoCliente
        from core.fechas import calcular_fecha_vencimiento, parse_fecha
        
        data = json.loads(request.body)
        
        cliente_id = data.get('cliente')
        cliente = get_object_or_404(Cliente, pk=cliente_id, empresa=empresa)
        
        total = int(data.get('total', 0))
        fecha_emision = parse_fecha(data.get('fecha_emision'))
        fecha_vencimiento = parse_fecha(data.get('fecha_vencimiento')) or calcular_fecha_vencimiento(
            fecha_emision, cliente.plazo_pago
        )
        
        # Crear documento de cliente en cuenta corriente
        documento = DocumentoCliente.objects.create(
            empresa=empresa,
            cliente=cliente,
            tipo_documento=data.get('tipo_documento', 'factura'),
            numero_documento=data.get('numero_documento'),
            fecha_emision=fecha_emision,
            fecha_vencimiento=fecha_vencimiento,
            total=total,
            saldo_pendiente=Decimal(total),
            estado_pago='pendiente',
            observaciones=data.get('observaciones', ''),
            creado_por=request.user
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Documento {documento.numero_documento} creado exitosamente.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al crear documento: {str(e)}'
        })


@login_required
def historial_pagos_documento_cliente(request, documento_id):
    """Obtener historial de pagos de un documento de cliente"""
    try:
        from .models import DocumentoCliente, PagoDocumentoCliente
        
        documento = get_object_or_404(DocumentoCliente, pk=documento_id)
        pagos = documento.pagos.all().order_by('-fecha_pago')
        
        pagos_data = []
        for pago in pagos:
            pagos_data.append({
                'fecha': pago.fecha_pago.strftime('%d-%m-%Y %H:%M'),
                'monto': float(pago.monto),
                'forma_pago': pago.forma_pago,
                'observaciones': pago.observaciones
            })
        
        return JsonResponse({
            'pagos': pagos_data,
            'total_pagado': float(documento.monto_pagado)
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def registrar_pago_cliente(request):
    """Registrar un pago de cliente con múltiples formas de pago"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        from .models import DocumentoCliente
        
        data = json.loads(request.body)
        
        documento_id = data.get('documento_id')
        formas_pago = data.get('formas_pago', [])
        observaciones = data.get('observaciones', '')
        
        documento = get_object_or_404(DocumentoCliente, pk=documento_id)
        
        # Validar que hay formas de pago
        if not formas_pago:
            return JsonResponse({'success': False, 'message': 'Debe especificar al menos una forma de pago'})
        
        # Calcular monto total
        monto_total = sum(Decimal(str(forma['monto'])) for forma in formas_pago)
        
        # Validar monto
        if monto_total <= 0:
            return JsonResponse({'success': False, 'message': 'El monto debe ser mayor a 0'})
        
        if monto_total > documento.saldo_pendiente:
            return JsonResponse({'success': False, 'message': 'El monto excede el saldo pendiente'})
        
        # Registrar cada forma de pago
        from .models import PagoDocumentoCliente
        
        for forma in formas_pago:
            PagoDocumentoCliente.objects.create(
                documento=documento,
                monto=Decimal(str(forma['monto'])),
                forma_pago=forma['forma_pago'],
                observaciones=observaciones,
                registrado_por=request.user
            )
        
        # Actualizar documento
        documento.monto_pagado += monto_total
        documento.saldo_pendiente -= monto_total
        
        # Actualizar estado
        if documento.saldo_pendiente <= 0:
            documento.estado_pago = 'pagado'
        elif documento.monto_pagado > 0:
            documento.estado_pago = 'parcial'
        
        documento.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Pago registrado exitosamente por ${int(monto_total):,}'.replace(',', '.')
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al procesar el pago: {str(e)}'
        })


@login_required
def obtener_documento_cliente(request, pk):
    """Obtener datos de un documento de cliente"""
    try:
        from .models import DocumentoCliente
        
        # Obtener empresa
        empresa = _empresa_de_request(request)
        if not empresa:
            return JsonResponse({'success': False, 'message': 'No se encontró empresa'})
        
        documento = get_object_or_404(DocumentoCliente, pk=pk, empresa=empresa)
        
        return JsonResponse({
            'success': True,
            'documento': {
                'id': documento.id,
                'cliente_id': documento.cliente.id,
                'tipo_documento': documento.tipo_documento,
                'numero_documento': documento.numero_documento,
                'fecha_emision': documento.fecha_emision.strftime('%Y-%m-%d'),
                'fecha_vencimiento': documento.fecha_vencimiento.strftime('%Y-%m-%d') if documento.fecha_vencimiento else '',
                'total': int(documento.total),
                'observaciones': documento.observaciones
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al obtener documento: {str(e)}'
        })


@login_required
def editar_documento_cliente(request, pk):
    """Editar documento de cliente"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        from .models import DocumentoCliente
        from clientes.models import Cliente
        
        # Obtener empresa
        empresa = _empresa_de_request(request)
        if not empresa:
            return JsonResponse({'success': False, 'message': 'No se encontró empresa'})
        
        documento = get_object_or_404(DocumentoCliente, pk=pk, empresa=empresa)
        
        data = json.loads(request.body)
        
        cliente_id = data.get('cliente')
        cliente = get_object_or_404(Cliente, pk=cliente_id, empresa=empresa)
        
        total = int(data.get('total', 0))
        
        # Actualizar documento
        documento.cliente = cliente
        documento.tipo_documento = data.get('tipo_documento')
        documento.numero_documento = data.get('numero_documento')
        documento.fecha_emision = data.get('fecha_emision')
        documento.fecha_vencimiento = data.get('fecha_vencimiento') or None
        documento.total = total
        documento.saldo_pendiente = Decimal(total) - documento.monto_pagado
        documento.observaciones = data.get('observaciones', '')
        documento.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Documento {documento.numero_documento} actualizado exitosamente.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al actualizar documento: {str(e)}'
        })


@login_required
def eliminar_documento_cliente(request, pk):
    """Eliminar documento de cliente"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'})
    
    try:
        from .models import DocumentoCliente
        
        # Obtener empresa
        empresa = _empresa_de_request(request)
        if not empresa:
            return JsonResponse({'success': False, 'message': 'No se encontró empresa'})
        
        documento = get_object_or_404(DocumentoCliente, pk=pk, empresa=empresa)
        numero = documento.numero_documento
        documento.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Documento {numero} eliminado exitosamente.'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al eliminar documento: {str(e)}'
        })


@csrf_exempt
@login_required
@requiere_empresa
def registrar_pago_movimiento(request):
    """Registrar pago de un movimiento de cuenta corriente (factura a crédito)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)
    
    try:
        from decimal import Decimal
        import json
        from .models import MovimientoCuentaCorrienteCliente
        from ventas.models import FormaPago
        from django.db import models, transaction
        
        data = json.loads(request.body)
        movimiento_id = data.get('movimiento_id')
        formas_pago = data.get('formas_pago', [])
        observaciones = data.get('observaciones', '')
        
        # Validaciones
        if not movimiento_id:
            return JsonResponse({'success': False, 'message': 'ID de movimiento requerido'}, status=400)
        
        if not formas_pago:
            return JsonResponse({'success': False, 'message': 'Debe especificar al menos una forma de pago'}, status=400)
        
        # Obtener el movimiento
        movimiento = get_object_or_404(
            MovimientoCuentaCorrienteCliente,
            pk=movimiento_id,
            cuenta_corriente__empresa=request.empresa
        )
        
        _anotar_saldos_movimiento_cliente(movimiento)
        saldo_pendiente = Decimal(movimiento.saldo_pendiente_factura)
        monto_total_pago = Decimal(_pesos(sum(
            parse_monto_chileno(fp.get('monto')) for fp in formas_pago
        )))

        if monto_total_pago <= 0:
            return JsonResponse({'success': False, 'message': 'El monto debe ser mayor a 0'}, status=400)

        if monto_total_pago > saldo_pendiente:
            return JsonResponse({
                'success': False,
                'message': 'El monto excede el saldo pendiente'
            }, status=400)
        
        # Registrar el pago como un movimiento HABER (abono)
        with transaction.atomic():
            cuenta = movimiento.cuenta_corriente
            saldo_anterior = cuenta.saldo_pendiente
            
            # Crear movimiento de pago (HABER)
            movimiento_pago = MovimientoCuentaCorrienteCliente.objects.create(
                cuenta_corriente=cuenta,
                venta=movimiento.venta,  # Relacionar con la misma venta
                tipo_movimiento='haber',  # Pago recibido
                monto=monto_total_pago,
                saldo_anterior=saldo_anterior,
                saldo_nuevo=saldo_anterior - monto_total_pago,
                estado='confirmado',
                observaciones=f"Pago de factura #{movimiento.venta.numero_venta if movimiento.venta else 'N/A'}. {observaciones}",
                registrado_por=request.user
            )
            
            # Registrar en DocumentoCliente y PagoDocumentoCliente
            if movimiento.venta:
                from .models import DocumentoCliente, PagoDocumentoCliente
                
                print(f"DEBUG PAGO: Buscando documento para factura {movimiento.venta.numero_venta}")
                print(f"DEBUG PAGO: Empresa: {request.empresa.nombre}")
                
                try:
                    documento = DocumentoCliente.objects.get(
                        empresa=request.empresa,
                        numero_documento=movimiento.venta.numero_venta
                    )
                    
                    print(f"✓ Documento encontrado: ID={documento.id}, Número={documento.numero_documento}")
                    
                    # Registrar cada forma de pago
                    for forma in formas_pago:
                        # Obtener el nombre de la forma de pago
                        forma_pago_nombre = forma.get('forma_pago', None)
                        if not forma_pago_nombre and 'forma_pago_id' in forma:
                            # Si viene el ID, obtener el nombre
                            try:
                                forma_pago_obj = FormaPago.objects.get(id=forma['forma_pago_id'])
                                forma_pago_nombre = forma_pago_obj.nombre
                            except FormaPago.DoesNotExist:
                                forma_pago_nombre = 'No especificado'
                        
                        pago_creado = PagoDocumentoCliente.objects.create(
                            documento=documento,
                            monto=Decimal(_pesos(parse_monto_chileno(forma.get('monto')))),
                            forma_pago=forma_pago_nombre or 'No especificado',
                            observaciones=observaciones,
                            registrado_por=request.user
                        )
                        print(f"✓ Pago creado: ID={pago_creado.id}, Monto=${pago_creado.monto}, Forma={pago_creado.forma_pago}")
                    
                    # Actualizar documento
                    documento.monto_pagado += monto_total_pago
                    documento.saldo_pendiente -= monto_total_pago
                    
                    if documento.saldo_pendiente <= 0:
                        documento.estado_pago = 'pagado'
                    elif documento.monto_pagado > 0:
                        documento.estado_pago = 'parcial'
                    
                    documento.save()
                    print(f"✓ Documento actualizado: Pagado=${documento.monto_pagado}, Saldo=${documento.saldo_pendiente}")
                    
                except DocumentoCliente.DoesNotExist:
                    print(f"⚠ ERROR: No se encontró documento para factura {movimiento.venta.numero_venta}")
                    print(f"⚠ Buscando con: empresa={request.empresa.id}, numero_documento={movimiento.venta.numero_venta}")
                    # Listar documentos existentes para debug
                    docs = DocumentoCliente.objects.filter(empresa=request.empresa).values_list('numero_documento', flat=True)
                    print(f"⚠ Documentos existentes: {list(docs)[:10]}")
            
            if movimiento.venta:
                venta = movimiento.venta
                venta.monto_pagado = Decimal(str(venta.monto_pagado or 0)) + monto_total_pago
                total_venta = Decimal(str(venta.total or 0))
                if venta.monto_pagado > total_venta:
                    venta.monto_pagado = total_venta
                venta.saldo_pendiente = max(total_venta - venta.monto_pagado, Decimal('0'))
                venta.save(update_fields=['monto_pagado', 'saldo_pendiente'])

            # Actualizar saldo de la cuenta corriente
            cuenta.saldo_pendiente -= monto_total_pago
            if cuenta.saldo_pendiente < 0:
                cuenta.saldo_pendiente = Decimal('0')
            cuenta.save()
            
            # Si el movimiento original está completamente pagado, marcarlo como anulado
            # (porque ya fue pagado)
            total_pagado = MovimientoCuentaCorrienteCliente.objects.filter(
                cuenta_corriente=cuenta,
                venta=movimiento.venta,
                tipo_movimiento='haber'
            ).aggregate(total=models.Sum('monto'))['total'] or Decimal('0')
            
            if _pesos(total_pagado) >= movimiento.monto_display:
                movimiento.observaciones = (movimiento.observaciones or '') + f"\n[PAGADO] Total pagado: ${total_pagado}"
                movimiento.save()
        
        return JsonResponse({
            'success': True,
            'message': f'Pago de ${monto_total_pago:,.0f} registrado exitosamente'
        })
        
    except Exception as e:
        import traceback
        print(f"Error al registrar pago: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'message': f'Error al registrar pago: {str(e)}'
        }, status=500)


@login_required
@requiere_empresa
def historial_pagos_movimiento(request, movimiento_id):
    """Obtener historial de pagos de un movimiento de cuenta corriente"""
    try:
        from .models import MovimientoCuentaCorrienteCliente
        from django.db.models import Sum
        
        # Obtener el movimiento original (debe)
        movimiento = get_object_or_404(
            MovimientoCuentaCorrienteCliente,
            pk=movimiento_id,
            cuenta_corriente__empresa=request.empresa,
            tipo_movimiento='debe'
        )
        
        # Buscar si existe un documento asociado a esta venta
        from .models import DocumentoCliente, PagoDocumentoCliente
        
        try:
            # Buscar documento por número de factura
            if movimiento.venta:
                print(f"DEBUG: Buscando documento para factura {movimiento.venta.numero_venta}")
                documento = DocumentoCliente.objects.filter(
                    empresa=request.empresa,
                    numero_documento=movimiento.venta.numero_venta
                ).first()
                
                if documento:
                    print(f"DEBUG: Documento encontrado: {documento.id}")
                    # Usar pagos del nuevo sistema
                    pagos_nuevos = documento.pagos.all().order_by('-fecha_pago')
                    print(f"DEBUG: Pagos encontrados en nuevo sistema: {pagos_nuevos.count()}")
                    
                    pagos_data = []
                    for pago in pagos_nuevos:
                        print(f"DEBUG: Pago - Monto: {pago.monto}, Forma: {pago.forma_pago}")
                        pagos_data.append({
                            'id': pago.pk,
                            'fecha': pago.fecha_pago.strftime('%d-%m-%Y %H:%M'),
                            'monto': float(pago.monto),
                            'forma_pago': pago.forma_pago,
                            'observaciones': pago.observaciones,
                            'registrado_por': pago.registrado_por.get_full_name() or pago.registrado_por.username
                        })
                    total_pagado = sum(float(p.monto) for p in pagos_nuevos)
                else:
                    print(f"DEBUG: No se encontró documento para factura {movimiento.venta.numero_venta}")
                    # Usar movimientos antiguos
                    pagos = MovimientoCuentaCorrienteCliente.objects.filter(
                        cuenta_corriente=movimiento.cuenta_corriente,
                        venta=movimiento.venta,
                        tipo_movimiento='haber'
                    ).order_by('-fecha_movimiento')
                    
                    pagos_data = []
                    for pago in pagos:
                        pagos_data.append({
                            'id': pago.pk,
                            'fecha': pago.fecha_movimiento.strftime('%d-%m-%Y %H:%M'),
                            'monto': float(pago.monto),
                            'forma_pago': 'No especificado',
                            'observaciones': pago.observaciones,
                            'registrado_por': pago.registrado_por.get_full_name() or pago.registrado_por.username
                        })
                    
                    from django.db.models import Sum
                    total_pagado = float(pagos.aggregate(total=Sum('monto'))['total'] or 0)
            else:
                pagos_data = []
                total_pagado = 0
        except Exception as e:
            print(f"Error buscando pagos: {e}")
            pagos_data = []
            total_pagado = 0
        
        return JsonResponse({
            'success': True,
            'pagos': pagos_data,
            'total_pagado': float(total_pagado),
            'monto_factura': float(movimiento.monto),
            'saldo_pendiente': float(Decimal(str(movimiento.monto)) - Decimal(str(total_pagado)))
        })
        
    except Exception as e:
        import traceback
        print(f"Error al obtener historial: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'message': f'Error al obtener historial: {str(e)}'
        }, status=500)
