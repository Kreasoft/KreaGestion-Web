from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.decorators import requiere_empresa
from articulos.models import Articulo
from clientes.models import Cliente
from inventario.models import Stock, Inventario
from ventas.models import Venta, VentaDetalle
from bodegas.models import Bodega
from empresas.models import Empresa, Sucursal
from django.db.models import Sum, Q, F, Count, DateField
from django.db.models.functions import Coalesce, TruncDate, ExtractMonth, ExtractYear
from django.utils import timezone
from datetime import datetime, timedelta

@login_required
@requiere_empresa
def dashboard(request):
    """Dashboard principal con estadísticas reales filtradas por sucursal"""

    # Cambios rápidos del tablero ejecutivo. La empresa continúa aislada por
    # sesión y la bodega seleccionada siempre se valida contra esa empresa.
    if request.method == 'POST' and request.POST.get('dashboard_selector'):
        from django.shortcuts import redirect
        if request.POST.get('dashboard_selector') == 'empresa' and request.user.is_superuser:
            try:
                nueva_empresa = Empresa.objects.get(pk=request.POST.get('empresa_id'))
                request.session['empresa_activa_id'] = nueva_empresa.id
                request.session['empresa_activa'] = nueva_empresa.id
                request.session.pop('dashboard_bodega_id', None)
                request.session.modified = True
                response = redirect('dashboard')
                response.set_cookie('empresa_activa_id', nueva_empresa.id, max_age=30*24*60*60, httponly=True, samesite='Lax')
                return response
            except (Empresa.DoesNotExist, ValueError, TypeError):
                pass
        elif request.POST.get('dashboard_selector') == 'bodega':
            bodega_id = request.POST.get('bodega_id', '')
            if bodega_id:
                bodega_valida = Bodega.objects.filter(pk=bodega_id, empresa=request.empresa, activa=True).first()
                if bodega_valida:
                    request.session['dashboard_bodega_id'] = bodega_valida.id
            else:
                request.session.pop('dashboard_bodega_id', None)
            request.session.modified = True
            return redirect('dashboard')
        elif request.POST.get('dashboard_selector') == 'fondo':
            fondo = request.POST.get('fondo', 'foto')
            request.session['dashboard_fondo'] = fondo if fondo in ('foto', 'suave') else 'foto'
            request.session.modified = True
            return redirect('dashboard')
        elif request.POST.get('dashboard_selector') == 'menu':
            layout = request.POST.get('menu_layout', 'lateral')
            if layout not in ('lateral', 'superior'):
                layout = 'lateral'
            request.session['menu_layout'] = layout
            request.session.modified = True
            response = redirect('dashboard')
            response.set_cookie('menu_layout', layout, max_age=30*24*60*60, samesite='Lax')
            return response
    
    # --- Ruteo por tipo de usuario ---
    try:
        tipo_usuario = request.user.perfil.tipo_usuario
    except:
        tipo_usuario = 'administrador'
        
    if tipo_usuario == 'vendedor':
        return dashboard_vendedor(request)
    elif tipo_usuario == 'cajero':
        return dashboard_cajero(request)
    
    # Obtener todas las sucursales de la empresa
    sucursales = Sucursal.objects.filter(empresa=request.empresa, estado='activa').order_by('nombre')
    
    # Manejar cambio de sucursal
    sucursal_id = request.GET.get('sucursal', '')
    if sucursal_id:
        if sucursal_id == 'todas':
            # Limpiar sucursal de la sesión
            if 'sucursal_filtro_id' in request.session:
                del request.session['sucursal_filtro_id']
            # Redirect para que el middleware actualice
            from django.shortcuts import redirect
            return redirect('dashboard')
        else:
            try:
                sucursal_seleccionada = Sucursal.objects.get(id=sucursal_id, empresa=request.empresa)
                # Guardar en sesión con el nombre correcto
                request.session['sucursal_filtro_id'] = sucursal_seleccionada.id
                # Redirect para que el middleware actualice
                from django.shortcuts import redirect
                return redirect('dashboard')
            except Sucursal.DoesNotExist:
                sucursal_seleccionada = None
    
    # Obtener sucursal del middleware (ya actualizada)
    sucursal_seleccionada = getattr(request, 'sucursal_activa', None)
    bodegas_dashboard = Bodega.objects.filter(empresa=request.empresa, activa=True).order_by('nombre')
    bodega_seleccionada = None
    bodega_sesion_id = request.session.get('dashboard_bodega_id')
    if bodega_sesion_id:
        bodega_seleccionada = bodegas_dashboard.filter(pk=bodega_sesion_id).first()
        if not bodega_seleccionada:
            request.session.pop('dashboard_bodega_id', None)
    
    # Calcular estadísticas reales
    total_articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).count()
    
    # Clientes activos
    total_clientes = Cliente.objects.filter(empresa=request.empresa, estado='activo').count()
    
    # --- Cálculo de Estado de Stock Basado en Movimientos (Lógica de Kardex) ---
    movimientos_query = Inventario.objects.filter(empresa=request.empresa, estado='confirmado')

    # Lógica de cálculo de stock: Suma directa de todos los movimientos (positivos y negativos).
    if bodega_seleccionada:
        movimientos_query = movimientos_query.filter(
            Q(bodega_origen=bodega_seleccionada) | Q(bodega_destino=bodega_seleccionada)
        )
    elif sucursal_seleccionada:
        bodegas_sucursal_ids = Bodega.objects.filter(empresa=request.empresa, sucursal=sucursal_seleccionada).values_list('id', flat=True)
        # Se consideran todos los movimientos que entran o salen de las bodegas de la sucursal.
        movimientos_query = movimientos_query.filter(
            Q(bodega_origen_id__in=bodegas_sucursal_ids) | Q(bodega_destino_id__in=bodegas_sucursal_ids)
        )

    # La suma de cantidades (positivas y negativas) da el stock neto.
    stock_calculado = movimientos_query.values('articulo_id').annotate(stock_neto=Sum('cantidad'))
    stock_map = {item['articulo_id']: item['stock_neto'] for item in stock_calculado}

    # Obtener todos los artículos activos con sus umbrales de stock
    articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).values('id', 'stock_minimo', 'stock_maximo')

    stock_normal = 0
    stock_bajo = 0
    stock_sin = 0
    stock_sobre = 0

    for art in articulos:
        cantidad_actual = float(stock_map.get(art['id'], 0) or 0)
        stock_min = float(art['stock_minimo'] or 0)
        stock_max = float(art['stock_maximo'] or 0)

        if cantidad_actual <= 0:
            stock_sin += 1
        elif stock_max > 0 and cantidad_actual >= stock_max:
            stock_sobre += 1
        elif cantidad_actual <= stock_min:
            stock_bajo += 1
        else:
            stock_normal += 1
    
    # Ventas de los últimos 30 días: por fecha de venta (DateField) O fecha de creación (DateTime)
    inicio_periodo = (timezone.now() - timedelta(days=30)).date()
    ventas_query = Venta.objects.filter(
        empresa=request.empresa,
        estado__in=['confirmada', 'borrador']
    ).filter(
        Q(fecha__gte=inicio_periodo) | Q(fecha_creacion__date__gte=inicio_periodo)
    )
    
    # Filtrar ventas por sucursal si está seleccionada
    if sucursal_seleccionada:
        ventas_query = ventas_query.filter(sucursal=sucursal_seleccionada)
    
    ventas_mes = ventas_query.aggregate(total=Sum('total'))['total'] or 0

    # Indicadores ejecutivos del dashboard alternativo. Se basan solo en
    # ventas confirmadas para no inflar resultados con borradores.
    hoy = timezone.localdate()
    ventas_confirmadas = Venta.objects.filter(
        empresa=request.empresa,
        estado='confirmada',
    )
    if sucursal_seleccionada:
        ventas_confirmadas = ventas_confirmadas.filter(sucursal=sucursal_seleccionada)
    ventas_30_confirmadas = ventas_confirmadas.filter(
        Q(fecha__gte=inicio_periodo) | Q(fecha_creacion__date__gte=inicio_periodo)
    )
    resumen_ventas = ventas_30_confirmadas.aggregate(total=Sum('total'), cantidad=Count('id'))
    ventas_30_total = resumen_ventas['total'] or 0
    ventas_30_cantidad = resumen_ventas['cantidad'] or 0
    ticket_promedio = ventas_30_total / ventas_30_cantidad if ventas_30_cantidad else 0
    ventas_hoy = ventas_confirmadas.filter(
        Q(fecha=hoy) | Q(fecha_creacion__date=hoy)
    ).aggregate(total=Sum('total'))['total'] or 0
    inicio_anterior = inicio_periodo - timedelta(days=30)
    fin_anterior = inicio_periodo - timedelta(days=1)
    ventas_anterior = ventas_confirmadas.filter(
        Q(fecha__range=(inicio_anterior, fin_anterior)) |
        Q(fecha_creacion__date__range=(inicio_anterior, fin_anterior))
    ).aggregate(total=Sum('total'))['total'] or 0
    variacion_ventas = float((ventas_30_total - ventas_anterior) * 100 / ventas_anterior) if ventas_anterior else (100.0 if ventas_30_total else 0.0)

    from pedidos.models import OrdenPedido
    from pedidos.views import total_saldo_por_despachar
    from tesoreria.models import DocumentoCliente
    OrdenPedido.sincronizar_estados_por_despacho(empresa=request.empresa)
    # Abiertos = con cantidad aún por despachar (incluye borrador si tiene saldo).
    pedidos_pendientes_qs = OrdenPedido.con_saldo_pendiente(empresa=request.empresa)
    if bodega_seleccionada:
        pedidos_pendientes_qs = pedidos_pendientes_qs.filter(bodega=bodega_seleccionada)
    pedidos_pendientes = pedidos_pendientes_qs.count()
    monto_pedidos_pendientes = total_saldo_por_despachar(pedidos_pendientes_qs)
    cuentas_cobrar_qs = DocumentoCliente.objects.filter(
        empresa=request.empresa,
        estado_pago__in=['pendiente', 'parcial', 'vencido'],
    )
    cuentas_por_cobrar = cuentas_cobrar_qs.aggregate(total=Sum('saldo_pendiente'))['total'] or 0
    documentos_vencidos = cuentas_cobrar_qs.filter(estado_pago='vencido').count()
    
    # Clientes nuevos este mes
    # CORRECCIÓN CRÍTICA: Se define inicio_mes aquí para la tarjeta de clientes nuevos.
    inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    try:
        clientes_nuevos_mes = Cliente.objects.filter(
            empresa=request.empresa,
            # CORRECCIÓN CRÍTICA: Usar inicio_periodo, no inicio_mes que ya no existe.
        fecha_creacion__gte=inicio_periodo
        ).count()
    except:
        clientes_nuevos_mes = 0
    
    # --- Top 5 productos más vendidos (Lógica Robusta de 2 Pasos) ---
    top_productos_query = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__estado__in=['confirmada', 'borrador']
    ).filter(
        Q(venta__fecha__gte=inicio_periodo) | Q(venta__fecha_creacion__date__gte=inicio_periodo)
    )
    if sucursal_seleccionada:
        top_productos_query = top_productos_query.filter(venta__sucursal=sucursal_seleccionada)

    # 1. Agrupar solo por ID y obtener el ranking
    top_ids_qs = (
        top_productos_query
        .values('articulo_id')
        .annotate(cantidad_total=Sum('cantidad'))
        .order_by('-cantidad_total')[:5]
    )

    # 2. Obtener los detalles de los artículos del Top 5
    top_ids = [item['articulo_id'] for item in top_ids_qs]
    cantidad_map = {item['articulo_id']: item['cantidad_total'] for item in top_ids_qs}

    articulos_top = Articulo.objects.filter(id__in=top_ids).values('id', 'codigo', 'nombre')
    
    # 3. Construir la lista final, ordenando según el ranking de ventas
    articulos_map = {art['id']: art for art in articulos_top}
    top_productos = []
    for articulo_id in top_ids:
        articulo_info = articulos_map.get(articulo_id)
        if articulo_info:
            top_productos.append({
                'codigo': articulo_info['codigo'],
                'nombre': articulo_info['nombre'],
                'cantidad': float(cantidad_map.get(articulo_id, 0))
            })


    # Serie de ventas mensuales del año seleccionado
    anio_actual = hoy.year
    try:
        anio_chart = int(request.GET.get('anio') or anio_actual)
    except (TypeError, ValueError):
        anio_chart = anio_actual
    if anio_chart < 2000 or anio_chart > anio_actual + 1:
        anio_chart = anio_actual

    fecha_venta_expr = Coalesce(
        F('fecha'),
        TruncDate('fecha_creacion'),
        output_field=DateField(),
    )
    anios_chart = set(range(anio_actual - 5, anio_actual + 1))
    anios_chart.add(anio_chart)
    anios_chart.update(
        ventas_confirmadas.annotate(anio=ExtractYear(fecha_venta_expr))
        .exclude(anio__isnull=True)
        .values_list('anio', flat=True)
        .distinct()
    )
    anios_chart = sorted((int(a) for a in anios_chart if a), reverse=True)

    ventas_mes_qs = (
        ventas_confirmadas
        .annotate(fecha_venta=fecha_venta_expr)
        .filter(fecha_venta__year=anio_chart)
        .annotate(mes=ExtractMonth('fecha_venta'))
        .values('mes')
        .annotate(total=Sum('total'))
    )
    montos_mes = {int(item['mes']): float(item['total'] or 0) for item in ventas_mes_qs if item['mes']}
    meses_es = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    labels = meses_es
    data = [montos_mes.get(mes, 0.0) for mes in range(1, 13)]

    # Ventas por categoría del mes
    ventas_categoria_query = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__estado__in=['confirmada', 'borrador']
    ).filter(
        Q(venta__fecha__gte=inicio_periodo) | Q(venta__fecha_creacion__date__gte=inicio_periodo)
    )
    
    # Filtrar por sucursal si está seleccionada
    if sucursal_seleccionada:
        ventas_categoria_query = ventas_categoria_query.filter(venta__sucursal=sucursal_seleccionada)
    
    ventas_por_categoria = (
        ventas_categoria_query
        .values('articulo__categoria__nombre')
        .annotate(total=Sum('precio_total'))
        .order_by('-total')[:5]
    )
    
    categorias_labels = []
    categorias_data = []
    for item in ventas_por_categoria:
        nombre_cat = item['articulo__categoria__nombre'] or 'Sin categoría'
        categorias_labels.append(nombre_cat)
        categorias_data.append(float(item['total']) if item['total'] else 0)
    
    
    import json
    
    # Verificar si el usuario puede cambiar de sucursal manualmente
    puede_filtrar_sucursal = getattr(request, 'puede_cambiar_sucursal', False)
    
    context = {
        'total_articulos': total_articulos,
        'total_clientes': total_clientes,
        'stock_bajo': stock_bajo, # Se mantiene para la tarjeta de resumen
        'stock_data': [stock_normal, stock_bajo, stock_sin, stock_sobre],
        'ventas_mes': ventas_mes,
        'ventas_hoy': ventas_hoy,
        'ventas_30_total': ventas_30_total,
        'ventas_30_cantidad': ventas_30_cantidad,
        'ticket_promedio': ticket_promedio,
        'variacion_ventas': variacion_ventas,
        'pedidos_pendientes': pedidos_pendientes,
        'monto_pedidos_pendientes': monto_pedidos_pendientes,
        'cuentas_por_cobrar': cuentas_por_cobrar,
        'documentos_vencidos': documentos_vencidos,
        'clientes_nuevos_mes': clientes_nuevos_mes,
        'top_productos': json.dumps(top_productos),  # Convertir a JSON
        'ventas_series_labels': labels,
        'ventas_series_data': data,
        'anio_chart': anio_chart,
        'anios_chart': anios_chart,
        'categorias_labels': categorias_labels,
        'categorias_data': categorias_data,
        # Filtro de sucursal
        'puede_filtrar_sucursal': puede_filtrar_sucursal,
        'sucursales': sucursales if puede_filtrar_sucursal else [],
        'sucursal_seleccionada': sucursal_seleccionada,
        'sucursal_id': str(sucursal_seleccionada.id) if sucursal_seleccionada else '',
        'empresas_dashboard': Empresa.objects.all().order_by('nombre') if request.user.is_superuser else [],
        'bodegas_dashboard': bodegas_dashboard,
        'bodega_seleccionada': bodega_seleccionada,
        'dashboard_fondo': request.session.get('dashboard_fondo', 'foto'),
        'ultimas_ventas': list(
            ventas_confirmadas.select_related('cliente').order_by('-fecha', '-id')[:5]
        ),
    }
    # Logs de diagnóstico (últimos 30 días + sucursal activa)
    try:
        ventas_count = ventas_query.count()
        ventas_total = float(ventas_query.aggregate(total=Sum('total'))['total'] or 0)
        productos_distintos = top_productos_query.values('articulo_id').distinct().count()
        categorias_distintas = ventas_categoria_query.values('articulo__categoria_id').distinct().count()
        sucs = list(Sucursal.objects.filter(empresa=request.empresa).values('id','nombre','estado'))
    except Exception as e:
        pass

    # Oficial: Centro Ejecutivo. El anterior queda en /dashboard-clasico/
    if request.resolver_match.url_name == 'dashboard_clasico':
        template_name = 'dashboard.html'
    else:
        template_name = 'dashboard_moderno.html'
    return render(request, template_name, context)

@login_required
@requiere_empresa
def dashboard_vendedor(request):
    """Dashboard simplificado para vendedores"""
    from django.utils import timezone
    from django.db.models import Sum
    from ventas.models import Venta
    
    hoy = timezone.now().date()
    inicio_mes = hoy.replace(day=1)
    
    # Ventas del usuario actual
    ventas_usuario = Venta.objects.filter(
        empresa=request.empresa,
        usuario_creacion=request.user,
        estado__in=['confirmada', 'borrador']
    )
    
    # Ventas de hoy
    ventas_hoy = ventas_usuario.filter(fecha=hoy)
    total_ventas_hoy = ventas_hoy.aggregate(suma=Sum('total'))['suma'] or 0
    cantidad_ventas_hoy = ventas_hoy.count()
    
    # Ventas del mes
    ventas_mes_qs = ventas_usuario.filter(fecha__gte=inicio_mes)
    total_ventas_mes = ventas_mes_qs.aggregate(suma=Sum('total'))['suma'] or 0
    cantidad_ventas_mes = ventas_mes_qs.count()
    
    # Últimas 10 ventas para mostrar en tabla
    ultimas_ventas = ventas_usuario.order_by('-fecha_creacion')[:10]
    
    context = {
        'total_ventas_hoy': total_ventas_hoy,
        'cantidad_ventas_hoy': cantidad_ventas_hoy,
        'total_ventas_mes': total_ventas_mes,
        'cantidad_ventas_mes': cantidad_ventas_mes,
        'ultimas_ventas': ultimas_ventas,
    }
    return render(request, 'dashboard_vendedor.html', context)

@login_required
@requiere_empresa
def dashboard_cajero(request):
    """Dashboard simplificado para cajeros"""
    from caja.models import AperturaCaja, MovimientoCaja
    from decimal import Decimal
    
    # Buscar si tiene una caja abierta
    apertura_activa = AperturaCaja.objects.filter(
        caja__empresa=request.empresa, 
        usuario_apertura=request.user, 
        estado='abierta'
    ).first()
    
    ultimos_movimientos = []
    total_recaudado = Decimal('0.00')
    
    if apertura_activa:
        # Recalcular para asegurar tener la información fresca
        apertura_activa.calcular_totales()
        
        # Sumamos los valores recibidos físicamente o digitalmente (ignoramos crédito)
        total_recaudado = (
            apertura_activa.total_ventas_efectivo + 
            apertura_activa.total_ventas_tarjeta + 
            apertura_activa.total_ventas_transferencia + 
            apertura_activa.total_ventas_cheque
        )
        
        ultimos_movimientos = MovimientoCaja.objects.filter(
            apertura_caja=apertura_activa
        ).order_by('-fecha')[:10]
        
    context = {
        'apertura_activa': apertura_activa,
        'total_recaudado': total_recaudado,
        'ultimos_movimientos': ultimos_movimientos,
    }
    return render(request, 'dashboard_cajero.html', context)
