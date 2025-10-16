from django.urls import path
from . import views
from . import views_carga_inicial
from . import views_stock_modal
from . import views_stock_updated
from . import views_ajustes_simple
from . import views_transferencias
from . import views_kardex

app_name = 'inventario'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_inventario, name='dashboard'),
    
    # Kardex de Artículo
    path('kardex/', views_kardex.kardex_articulo, name='kardex_articulo'),
    
    # Movimientos de Inventario
    path('movimientos/', views.inventario_list, name='inventario_list'),
    path('movimientos/nuevo/', views.inventario_create, name='inventario_create'),
    path('movimientos/<int:pk>/', views.inventario_detail, name='inventario_detail'),
    path('movimientos/<int:pk>/editar/', views.inventario_update, name='inventario_update'),
    path('movimientos/<int:pk>/eliminar/', views.inventario_delete, name='inventario_delete'),
    
    # Control de Stock
    path('stock/', views.stock_list, name='stock_list'),
    path('stock/nuevo/', views.stock_create, name='stock_create'),
    path('stock/<int:pk>/editar/', views.stock_update, name='stock_update'),
    path('stock/<int:pk>/editar-modal/', views_stock_modal.stock_update_modal, name='stock_update_modal'),
    path('stock/<int:pk>/eliminar/', views.stock_delete, name='stock_delete'),
    
    # Transferencias de Inventario
    path('transferencias/', views_transferencias.transferencia_list, name='transferencia_list'),
    path('transferencias/nueva/', views_transferencias.transferencia_create, name='transferencia_create'),
    path('transferencias/<int:pk>/', views_transferencias.transferencia_detail, name='transferencia_detail'),
    path('transferencias/<int:pk>/cancelar/', views_transferencias.transferencia_cancelar, name='transferencia_cancelar'),
    path('transferencias/<int:pk>/generar-guia/', views_transferencias.transferencia_generar_guia, name='transferencia_generar_guia'),
    path('transferencias/<int:pk>/imprimir-guia/', views_transferencias.transferencia_imprimir_guia, name='transferencia_imprimir_guia'),
    path('api/stock-disponible/', views_transferencias.api_stock_disponible, name='api_stock_disponible'),
    
    # Carga Inicial de Inventario
    path('carga-inicial/', views_carga_inicial.carga_inicial_inventario, name='carga_inicial'),
    path('carga-inicial/exportar-plantilla/', views_carga_inicial.exportar_plantilla_excel, name='exportar_plantilla'),
    path('carga-inicial/importar/', views_carga_inicial.importar_inventario_excel, name='importar_excel'),
    path('carga-inicial/edicion-manual/', views_carga_inicial.edicion_manual_inventario, name='edicion_manual'),
    path('api/articulos-inventario/', views_carga_inicial.obtener_articulos_para_inventario, name='api_articulos'),
    path('api/guardar-inventario-manual/', views_carga_inicial.guardar_inventario_manual, name='api_guardar_manual'),
    
    # Ajustes de Stock (Simple)
    path('ajustes/', views_ajustes_simple.ajustes_list_simple, name='ajustes_list'),
    path('ajustes/nuevo/', views_ajustes_simple.ajuste_create_simple, name='ajuste_create_simple'),
    path('ajustes/<int:pk>/', views_ajustes_simple.ajuste_detail_simple, name='ajuste_detail_simple'),
    path('ajustes/<int:pk>/editar/', views_ajustes_simple.ajuste_edit_simple, name='ajuste_edit_simple'),
    path('ajustes/<int:pk>/eliminar/', views_ajustes_simple.ajuste_delete_simple, name='ajuste_delete_simple'),
    path('api/articulos-ajuste/', views_ajustes_simple.api_articulos_ajuste_simple, name='api_articulos_ajuste'),
]


