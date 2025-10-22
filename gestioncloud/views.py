from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from usuarios.decorators import requiere_empresa
from articulos.models import Articulo
from clientes.models import Cliente
from inventario.models import Stock
from ventas.models import Venta, VentaDetalle
from bodegas.models import Bodega
from empresas.models import Sucursal
from django.db.models import Sum, Q, F
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
    
    # Filtrar stock por sucursal si está seleccionada
    stock_query = Stock.objects.filter(empresa=request.empresa)
    if sucursal_seleccionada:
        # Filtrar por bodegas de la sucursal
        bodegas_sucursal = Bodega.objects.filter(
            empresa=request.empresa,
            sucursal=sucursal_seleccionada
        ).values_list('id', flat=True)
        stock_query = stock_query.filter(bodega_id__in=bodegas_sucursal)
    
    # Estado del stock (por artículo, sumado en todas las bodegas; incluir artículos sin registro=0)
    # Construir totales por artículo
    stock_totales = (
        stock_query
        .values('articulo_id')
        .annotate(
            total_cantidad=Sum('cantidad'),
            total_min=Sum('stock_minimo'),
            total_max=Sum('stock_maximo'),
        )
    )
    totales_map = {row['articulo_id']: row for row in stock_totales}
    
    articulos_activos = Articulo.objects.filter(empresa=request.empresa, activo=True).values_list('id', flat=True)
    stock_normal = 0
    stock_bajo = 0
    stock_sin = 0
    stock_sobre = 0
    
    for art_id in articulos_activos:
        row = totales_map.get(art_id, None)
        total = float(row['total_cantidad']) if row and row['total_cantidad'] is not None else 0.0
        min_total = float(row['total_min']) if row and row['total_min'] is not None else 0.0
        max_total = float(row['total_max']) if row and row['total_max'] is not None else 0.0
        if total <= 0:
            stock_sin += 1
        elif max_total > 0 and total >= max_total:
            stock_sobre += 1
        elif total <= min_total:
            stock_bajo += 1
        else:
            stock_normal += 1
    
    # Ventas del mes actual (total confirmadas)
    inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ventas_query = Venta.objects.filter(
        empresa=request.empresa,
        fecha__gte=inicio_mes,
        estado='confirmada'
    )
    
    # Filtrar ventas por sucursal si está seleccionada
    if sucursal_seleccionada:
        ventas_query = ventas_query.filter(sucursal=sucursal_seleccionada)
    
    ventas_mes = ventas_query.aggregate(total=Sum('total'))['total'] or 0
    
    # Clientes nuevos este mes
    try:
        clientes_nuevos_mes = Cliente.objects.filter(
            empresa=request.empresa,
            fecha_creacion__gte=inicio_mes
        ).count()
    except:
        clientes_nuevos_mes = 0
    
    # Top productos más vendidos del mes (por cantidad)
    top_productos_query = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__fecha__gte=inicio_mes,
        venta__estado='confirmada'
    )
    
    # Filtrar por sucursal si está seleccionada
    if sucursal_seleccionada:
        top_productos_query = top_productos_query.filter(venta__sucursal=sucursal_seleccionada)
    
    top_productos_qs = (
        top_productos_query
        .values('articulo__codigo', 'articulo__nombre')
        .annotate(cantidad_total=Sum('cantidad'))
        .order_by('-cantidad_total')[:4]
    )

    top_productos = [
        {
            'codigo': it['articulo__codigo'],
            'nombre': it['articulo__nombre'],
            'cantidad': float(it['cantidad_total']) if it['cantidad_total'] else 0,
        }
        for it in top_productos_qs
    ]

    # Serie de ventas de los últimos 6 meses (sumatoria por mes)
    labels = []
    data = []
    now = timezone.now()
    for i in range(5, -1, -1):
        first_day = (now.replace(day=1) - timedelta(days=now.day - 1))  # inicio del mes actual
        # retroceder i meses
        month_ref = (first_day - timedelta(days=first_day.day)) if i == 6 else first_day
        # Calcular mes objetivo restando i meses
        ref = (now - timedelta(days=i * 30))
        month_start = ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # fin de mes: inicio del siguiente mes
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1)
        ventas_mes_query = Venta.objects.filter(
            empresa=request.empresa,
            fecha__gte=month_start,
            fecha__lt=month_end,
            estado='confirmada'
        )
        
        # Filtrar por sucursal si está seleccionada
        if sucursal_seleccionada:
            ventas_mes_query = ventas_mes_query.filter(sucursal=sucursal_seleccionada)
        
        monto = ventas_mes_query.aggregate(total=Sum('total'))['total'] or 0
        labels.append(month_start.strftime('%b %Y'))
        data.append(float(monto))

    # Ventas por categoría del mes
    ventas_categoria_query = VentaDetalle.objects.filter(
        venta__empresa=request.empresa,
        venta__fecha__gte=inicio_mes,
        venta__estado='confirmada'
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
    
    # Si no hay datos, mostrar mensaje
    if not categorias_labels:
        categorias_labels = ['Sin datos']
        categorias_data = [1]
    
    import json
    
    # Verificar si el usuario puede cambiar de sucursal manualmente
    puede_filtrar_sucursal = getattr(request, 'puede_cambiar_sucursal', False)
    
    context = {
        'total_articulos': total_articulos,
        'total_clientes': total_clientes,
        'stock_bajo': stock_bajo,
        'stock_normal': stock_normal,
        'stock_sin': stock_sin,
        'stock_sobre': stock_sobre,
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
    
    return render(request, 'dashboard.html', context)
