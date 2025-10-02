from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from usuarios.decorators import requiere_empresa
from articulos.models import Articulo
from clientes.models import Cliente
from inventario.models import Stock
# from ventas.models import Venta  # Temporalmente deshabilitado
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
    
    # Ventas del mes actual (temporalmente deshabilitado)
    ventas_mes = 0
    inicio_mes = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Clientes nuevos este mes
    try:
        clientes_nuevos_mes = Cliente.objects.filter(
            empresa=request.empresa,
            fecha_creacion__gte=inicio_mes
        ).count()
    except:
        clientes_nuevos_mes = 0
    
    context = {
        'total_articulos': total_articulos,
        'total_clientes': total_clientes,
        'stock_bajo': stock_bajo,
        'ventas_mes': ventas_mes,
        'clientes_nuevos_mes': clientes_nuevos_mes,
    }
    
    return render(request, 'dashboard.html', context)
