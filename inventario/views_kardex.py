"""
Vistas para el Kardex (Cartola) de Artículos
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q, Sum, F
from django.utils import timezone
from datetime import datetime, timedelta
from usuarios.decorators import requiere_empresa
from articulos.models import Articulo
from bodegas.models import Bodega
from .models import Inventario, Stock
from ventas.models import Venta, VentaDetalle
from inventario.models import TransferenciaInventario


@login_required
@requiere_empresa
@permission_required('inventario.view_movimientoinventario', raise_exception=True)
def kardex_articulo(request):
    """
    Kardex (Cartola) de movimientos de un artículo
    Muestra todas las entradas, salidas, transferencias y ajustes
    """
    # Obtener parámetros
    articulo_id = request.GET.get('articulo', '').strip()
    bodega_id = request.GET.get('bodega', '').strip()
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    
    # Limpiar IDs (remover espacios no rompibles y otros caracteres)
    if articulo_id:
        articulo_id = articulo_id.replace('\xa0', '').replace(' ', '').replace(',', '').replace('.', '')
    if bodega_id:
        bodega_id = bodega_id.replace('\xa0', '').replace(' ', '').replace(',', '').replace('.', '')
    
    # Valores por defecto de fechas (último mes)
    if not fecha_desde:
        fecha_desde = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not fecha_hasta:
        fecha_hasta = timezone.now().strftime('%Y-%m-%d')
    
    # Obtener artículo seleccionado
    articulo = None
    if articulo_id:
        try:
            articulo = Articulo.objects.get(id=int(articulo_id), empresa=request.empresa)
        except (Articulo.DoesNotExist, ValueError):
            pass
    
    # Obtener bodega seleccionada - MOSTRAR TODAS LAS BODEGAS DE LA EMPRESA
    bodega = None
    bodegas = Bodega.objects.filter(empresa=request.empresa, activa=True).select_related('sucursal')
    
    # NO filtrar por sucursal - el kardex debe mostrar TODAS las bodegas de la empresa
    # para permitir consultas completas de movimientos entre sucursales
    
    if bodega_id:
        try:
            bodega = bodegas.get(id=int(bodega_id))
        except (Bodega.DoesNotExist, ValueError):
            pass
    
    # Lista de movimientos
    movimientos = []
    saldo_actual = 0
    
    if articulo:
        # Convertir fechas
        try:
            fecha_desde_obj = datetime.strptime(fecha_desde, '%Y-%m-%d').date()
            fecha_hasta_obj = datetime.strptime(fecha_hasta, '%Y-%m-%d').date()
        except:
            fecha_desde_obj = (timezone.now() - timedelta(days=30)).date()
            fecha_hasta_obj = timezone.now().date()
        
        # Calcular saldo inicial (antes de la fecha desde)
        saldo_inicial = 0
        inventarios_iniciales = Inventario.objects.filter(
            empresa=request.empresa,
            articulo=articulo,
            fecha_movimiento__date__lt=fecha_desde_obj,
            estado='confirmado'
        )
        
        if bodega:
            inventarios_iniciales = inventarios_iniciales.filter(
                Q(bodega_origen=bodega) | Q(bodega_destino=bodega)
            )
        
        for inv in inventarios_iniciales:
            tipo_mov = inv.tipo_movimiento.lower()
            if tipo_mov == 'entrada':
                if not bodega or inv.bodega_destino == bodega:
                    saldo_inicial += inv.cantidad
            elif tipo_mov == 'salida':
                if not bodega or inv.bodega_origen == bodega:
                    saldo_inicial -= inv.cantidad
            elif tipo_mov == 'ajuste':
                if not bodega or inv.bodega_destino == bodega:
                    saldo_inicial += inv.cantidad
            elif tipo_mov == 'transferencia':
                # En saldo inicial también considerar transferencias
                if bodega:
                    if inv.bodega_origen == bodega:
                        saldo_inicial -= inv.cantidad
                    elif inv.bodega_destino == bodega:
                        saldo_inicial += inv.cantidad
                # Sin bodega: las transferencias no afectan el saldo global
        
        # Obtener movimientos del período
        inventarios = Inventario.objects.filter(
            empresa=request.empresa,
            articulo=articulo,
            fecha_movimiento__date__gte=fecha_desde_obj,
            fecha_movimiento__date__lte=fecha_hasta_obj,
            estado='confirmado'
        ).select_related('bodega_origen', 'bodega_destino', 'creado_por')
        
        if bodega:
            inventarios = inventarios.filter(
                Q(bodega_origen=bodega) | Q(bodega_destino=bodega)
            )
        
        inventarios = inventarios.order_by('fecha_movimiento', 'id')
        
        # Procesar movimientos
        saldo = saldo_inicial
        for inv in inventarios:
            entrada = 0
            salida = 0
            
            tipo_mov = inv.tipo_movimiento.lower()
            
            if tipo_mov == 'entrada':
                if not bodega or inv.bodega_destino == bodega:
                    entrada = inv.cantidad
                    saldo += entrada
            elif tipo_mov == 'salida':
                if not bodega or inv.bodega_origen == bodega:
                    salida = inv.cantidad
                    saldo -= salida
            elif tipo_mov == 'ajuste':
                if not bodega or inv.bodega_destino == bodega:
                    if inv.cantidad >= 0:
                        entrada = inv.cantidad
                        saldo += entrada
                    else:
                        salida = abs(inv.cantidad)
                        saldo -= salida
            elif tipo_mov == 'transferencia':
                # Transferencia: salida de origen, entrada en destino
                if bodega:
                    if inv.bodega_origen == bodega:
                        salida = inv.cantidad
                        saldo -= salida
                    elif inv.bodega_destino == bodega:
                        entrada = inv.cantidad
                        saldo += entrada
                else:
                    # Sin bodega específica: mostrar transferencia sin afectar saldo global
                    # (es movimiento interno, no cambia stock total de la empresa)
                    entrada = inv.cantidad  # Mostrar la cantidad transferida
                    salida = inv.cantidad   # En ambas columnas para indicar movimiento
            
            if entrada > 0 or salida > 0:
                movimientos.append({
                    'fecha': inv.fecha_movimiento,
                    'tipo': inv.get_tipo_movimiento_display(),
                    'tipo_codigo': inv.tipo_movimiento,
                    'documento': inv.numero_documento or inv.numero_folio or '-',
                    'detalle': inv.descripcion or inv.motivo or '-',
                    'bodega_origen': inv.bodega_origen.nombre if inv.bodega_origen else '-',
                    'bodega_destino': inv.bodega_destino.nombre if inv.bodega_destino else '-',
                    'entrada': entrada,
                    'salida': salida,
                    'saldo': saldo,
                    'usuario': inv.creado_por.username if inv.creado_por else '-'
                })
        
        saldo_actual = saldo
    
    # Obtener artículos para el selector (todos para búsqueda con Select2)
    articulos = Articulo.objects.filter(
        empresa=request.empresa,
        activo=True
    ).order_by('nombre')
    
    # Stock en sistema basado en movimientos de Inventario (coherente con la cartola)
    stock_sistema = None
    if articulo:
        stock_sistema_calc = 0
        inv_qs = Inventario.objects.filter(
            empresa=request.empresa,
            articulo=articulo,
            estado='confirmado'
        ).select_related('bodega_origen', 'bodega_destino')
        # Considerar movimientos hasta la fecha_hasta seleccionada
        try:
            fecha_hasta_obj  # ya calculada arriba
        except NameError:
            from datetime import datetime as _dt
            from django.utils import timezone as _tz
            fecha_hasta_obj = _tz.now().date()
        inv_qs = inv_qs.filter(fecha_movimiento__date__lte=fecha_hasta_obj)
        if bodega:
            inv_qs = inv_qs.filter(Q(bodega_origen=bodega) | Q(bodega_destino=bodega))
        for inv in inv_qs:
            t = (inv.tipo_movimiento or '').lower()
            if t == 'entrada':
                if not bodega or inv.bodega_destino == bodega:
                    stock_sistema_calc += inv.cantidad
            elif t == 'salida':
                if not bodega or inv.bodega_origen == bodega:
                    stock_sistema_calc -= inv.cantidad
            elif t == 'ajuste':
                # En ajustes, la cantidad puede ser negativa; usar bodega_destino como referencia
                if not bodega or inv.bodega_destino == bodega:
                    stock_sistema_calc += inv.cantidad
            elif t == 'transferencia':
                if bodega:
                    if inv.bodega_origen == bodega:
                        stock_sistema_calc -= inv.cantidad
                    elif inv.bodega_destino == bodega:
                        stock_sistema_calc += inv.cantidad
                else:
                    # Sin bodega, transferencias netean en 0 a nivel global
                    pass
        stock_sistema = stock_sistema_calc
    
    context = {
        'articulo': articulo,
        'bodega': bodega,
        'bodegas': bodegas,
        'articulos': articulos,
        'movimientos': movimientos,
        'saldo_actual': saldo_actual,
        'stock_sistema': stock_sistema,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'tiene_sucursal': hasattr(request, 'sucursal_activa') and request.sucursal_activa,
        'sucursal_nombre': request.sucursal_activa.nombre if hasattr(request, 'sucursal_activa') and request.sucursal_activa else None,
    }
    
    return render(request, 'inventario/kardex_articulo.html', context)
