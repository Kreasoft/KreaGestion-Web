from django.urls import path
from . import views
from . import views_carga_inicial
from . import views_stock_modal
from . import views_stock_updated

app_name = 'inventario'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_inventario, name='dashboard'),
    
    # Movimientos de Inventario
    path('movimientos/', views.inventario_list, name='inventario_list'),
    path('movimientos/nuevo/', views.inventario_create, name='inventario_create'),
    path('movimientos/<int:pk>/', views.inventario_detail, name='inventario_detail'),
    path('movimientos/<int:pk>/editar/', views.inventario_update, name='inventario_update'),
    path('movimientos/<int:pk>/eliminar/', views.inventario_delete, name='inventario_delete'),
    
    # Control de Stock
    path('stock/', views_stock_updated.stock_list, name='stock_list'),
    path('stock/nuevo/', views.stock_create, name='stock_create'),
    path('stock/<int:pk>/editar/', views.stock_update, name='stock_update'),
    path('stock/<int:pk>/editar-modal/', views_stock_modal.stock_update_modal, name='stock_update_modal'),
    path('stock/<int:pk>/eliminar/', views.stock_delete, name='stock_delete'),
    
    # Carga Inicial de Inventario
    path('carga-inicial/', views_carga_inicial.carga_inicial_inventario, name='carga_inicial'),
    path('carga-inicial/exportar-plantilla/', views_carga_inicial.exportar_plantilla_excel, name='exportar_plantilla'),
    path('carga-inicial/importar/', views_carga_inicial.importar_inventario_excel, name='importar_excel'),
    path('carga-inicial/edicion-manual/', views_carga_inicial.edicion_manual_inventario, name='edicion_manual'),
    path('api/articulos-inventario/', views_carga_inicial.obtener_articulos_para_inventario, name='api_articulos'),
    path('api/guardar-inventario-manual/', views_carga_inicial.guardar_inventario_manual, name='api_guardar_manual'),
]


