from django.urls import path
from . import views

app_name = 'informes'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_informes, name='dashboard'),
    
    # Informes de Ventas
    path('ventas/periodo/', views.informe_ventas_periodo, name='ventas_periodo'),
    path('ventas/vendedor/', views.informe_ventas_vendedor, name='ventas_vendedor'),
    path('ventas/productos/', views.informe_productos_vendidos, name='productos_vendidos'),
    
    # Informes de Inventario
    path('inventario/stock/', views.informe_stock_actual, name='stock_actual'),
    path('inventario/stock-bajo/', views.informe_stock_bajo, name='stock_bajo'),
    
    # Informes de Tesorería
    path('tesoreria/cuentas-por-cobrar/', views.informe_cuentas_por_cobrar, name='cuentas_por_cobrar'),
    path('tesoreria/pagos-recibidos/', views.informe_pagos_recibidos, name='pagos_recibidos'),
    
    # Informes de Caja
    path('caja/cierres/', views.informe_cierres_caja, name='cierres_caja'),
    
    # Informes de Compras
    path('compras/periodo/', views.informe_compras_periodo, name='compras_periodo'),
    
    # Informes de Utilidad
    path('utilidad/familias/', views.informe_utilidad_familias, name='utilidad_familias'),
    path('utilidad/familias/detalle/<int:familia_id>/', views.informe_utilidad_familias_detalle, name='utilidad_familias_detalle'),
    
    # Exportaciones
    path('exportar/ventas/excel/', views.exportar_ventas_excel, name='exportar_ventas_excel'),
    path('exportar/productos/excel/', views.exportar_productos_excel, name='exportar_productos_excel'),
    path('exportar/stock/excel/', views.exportar_stock_excel, name='exportar_stock_excel'),
    path('exportar/clientes/excel/', views.exportar_clientes_excel, name='exportar_clientes_excel'),
    path('exportar/proveedores/excel/', views.exportar_proveedores_excel, name='exportar_proveedores_excel'),
    path('exportar/articulos/excel/', views.exportar_articulos_excel, name='exportar_articulos_excel'),
    path('exportar/ventas-vendedor/excel/', views.exportar_ventas_vendedor_excel, name='exportar_ventas_vendedor_excel'),
    path('exportar/cuentas-cobrar/excel/', views.exportar_cuentas_cobrar_excel, name='exportar_cuentas_cobrar_excel'),
    path('exportar/pagos-recibidos/excel/', views.exportar_pagos_recibidos_excel, name='exportar_pagos_recibidos_excel'),
    path('exportar/stock-bajo/excel/', views.exportar_stock_bajo_excel, name='exportar_stock_bajo_excel'),
    path('exportar/cierres-caja/excel/', views.exportar_cierres_caja_excel, name='exportar_cierres_caja_excel'),
    path('exportar/compras/excel/', views.exportar_compras_periodo_excel, name='exportar_compras_periodo_excel'),
    path('exportar/utilidad-familias/excel/', views.exportar_utilidad_familias_excel, name='exportar_utilidad_familias_excel'),
    path('exportar/categorias/excel/', views.exportar_categorias_excel, name='exportar_categorias_excel'),
]
