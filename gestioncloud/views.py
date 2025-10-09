from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from usuarios.decorators import requiere_empresa
from articulos.models import Articulo
from clientes.models import Cliente
from inventario.models import Stock
from ventas.models import Venta, VentaDetalle
from django.db.models import Sum, Q, F
from django.utils import timezone
from datetime import datetime, timedelta

@login_required
@requiere_empresa
def dashboard(request):
    """Dashboard principal con estadísticas reales"""
    
    # Calcular estadísticas reales
    total_articulos = Articulo.objects.filter(empresa=request.empresa, activo=True).count()
    
    # Clientes activos
    total_clientes = Cliente.objects.filter(empresa=request.empresa, estado='activo').count()
    
    # Stock bajo (artículos con cantidad <= stock_minimo)
    stock_bajo = Stock.objects.filter(
        empresa=request.empresa,
        cantidad__lte=F('stock_minimo'),
        cantidad__gt=0
    ).count()
    
    # Ventas del mes actual (total confirmadas)
    inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    ventas_mes = (
        Venta.objects.filter(
            empresa=request.empresa,
            fecha__gte=inicio_mes,
            estado='confirmada'
        ).aggregate(total=Sum('total'))['total']
        or 0
    )
    
    # Clientes nuevos este mes
    try:
        clientes_nuevos_mes = Cliente.objects.filter(
            empresa=request.empresa,
            fecha_creacion__gte=inicio_mes
        ).count()
    except:
        clientes_nuevos_mes = 0
    
    # Top productos más vendidos del mes (por cantidad)
    top_productos_qs = (
        VentaDetalle.objects.filter(
            venta__empresa=request.empresa,
            venta__fecha__gte=inicio_mes,
            venta__estado='confirmada'
        )
        .values('articulo__codigo', 'articulo__nombre')
        .annotate(cantidad_total=Sum('cantidad'))
        .order_by('-cantidad_total')[:4]
    )

    top_productos = [
        {
            'codigo': it['articulo__codigo'],
            'nombre': it['articulo__nombre'],
            'cantidad': it['cantidad_total'],
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
        monto = (
            Venta.objects.filter(
                empresa=request.empresa,
                fecha__gte=month_start,
                fecha__lt=month_end,
                estado='confirmada'
            ).aggregate(total=Sum('total'))['total']
            or 0
        )
        labels.append(month_start.strftime('%b %Y'))
        data.append(float(monto))

    context = {
        'total_articulos': total_articulos,
        'total_clientes': total_clientes,
        'stock_bajo': stock_bajo,
        'ventas_mes': ventas_mes,
        'clientes_nuevos_mes': clientes_nuevos_mes,
        'top_productos': top_productos,
        'ventas_series_labels': labels,
        'ventas_series_data': data,
    }
    
    return render(request, 'dashboard.html', context)
