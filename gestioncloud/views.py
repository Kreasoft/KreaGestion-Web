from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from usuarios.decorators import requiere_empresa
from articulos.models import Articulo
from clientes.models import Cliente
from inventario.models import Stock, Inventario
from ventas.models import Venta, VentaDetalle
from bodegas.models import Bodega
from empresas.models import Sucursal
from django.db.models import Sum, Q, F, Count
from django.utils import timezone
from datetime import datetime, timedelta

@login_required
@requiere_empresa
def dashboard(request):
    """Dashboard principal con estadísticas reales filtradas por sucursal"""
    
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
    
    # Calcular estadísticas reales
    total_articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).count()
    
    # Clientes activos
    total_clientes = Cliente.objects.filter(empresa=request.empresa, estado='activo').count()
    
    # --- Cálculo de Estado de Stock Basado en Movimientos (Lógica de Kardex) ---
    movimientos_query = Inventario.objects.filter(empresa=request.empresa, estado='confirmado')

    # Lógica de cálculo de stock: Suma directa de todos los movimientos (positivos y negativos).
    if sucursal_seleccionada:
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


    # Serie de ventas de los últimos 30 días (sumatoria por día)
    labels = []
    data = []
    now = timezone.now()
    for i in range(29, -1, -1):
        day_date = (now - timedelta(days=i)).date()
        ventas_dia_query = Venta.objects.filter(
            empresa=request.empresa,
            estado__in=['confirmada', 'borrador']
        ).filter(
            Q(fecha=day_date) | Q(fecha_creacion__date=day_date)
        )
        if sucursal_seleccionada:
            ventas_dia_query = ventas_dia_query.filter(sucursal=sucursal_seleccionada)
        monto = ventas_dia_query.aggregate(total=Sum('total'))['total'] or 0
        labels.append(day_date.strftime('%d %b'))
        data.append(float(monto))

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
        'clientes_nuevos_mes': clientes_nuevos_mes,
        'top_productos': json.dumps(top_productos),  # Convertir a JSON
        'ventas_series_labels': labels,
        'ventas_series_data': data,
        'categorias_labels': categorias_labels,
        'categorias_data': categorias_data,
        # Filtro de sucursal
        'puede_filtrar_sucursal': puede_filtrar_sucursal,
        'sucursales': sucursales if puede_filtrar_sucursal else [],
        'sucursal_seleccionada': sucursal_seleccionada,
        'sucursal_id': str(sucursal_seleccionada.id) if sucursal_seleccionada else '',
    }
    # Logs de diagnóstico (últimos 30 días + sucursal activa)
    try:
        ventas_count = ventas_query.count()
        ventas_total = float(ventas_query.aggregate(total=Sum('total'))['total'] or 0)
        productos_distintos = top_productos_query.values('articulo_id').distinct().count()
        categorias_distintas = ventas_categoria_query.values('articulo__categoria_id').distinct().count()
        print("DBG30 Sucursal activa:", getattr(sucursal_seleccionada, 'id', None), getattr(sucursal_seleccionada, 'nombre', None))
        sucs = list(Sucursal.objects.filter(empresa=request.empresa).values('id','nombre','estado'))
        print("DBG30 Sucursales empresa:", sucs)
        print("DBG30 Ventas count:", ventas_count, " total:", ventas_total, " sucursal:", getattr(sucursal_seleccionada, 'id', None))
        print("DBG30 Productos distintos:", productos_distintos)
        print("DBG30 Categorías distintas:", categorias_distintas)
        print("DBG30 Top productos preview:", top_productos[:5])
        print("DBG30 Categorías preview:", list(zip(categorias_labels, categorias_data)))
    except Exception as e:
        print("DBG30 ERROR:", e)

    return render(request, 'dashboard.html', context)
