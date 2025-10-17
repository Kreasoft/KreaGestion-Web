"""
URLs para el módulo de compras
"""
from django.urls import path
from . import views

app_name = 'compras'

urlpatterns = [
    # Dashboard de compras
    path('', views.orden_compra_list, name='orden_compra_list'),
    path('dashboard/', views.orden_compra_list, name='dashboard_compras'),
    
    # Órdenes de compra
    path('ordenes/', views.orden_compra_list, name='orden_compra_list'),
    path('ordenes/crear/', views.orden_compra_create, name='orden_compra_create'),
    path('ordenes/<int:pk>/', views.orden_compra_detail, name='orden_compra_detail'),
    path('ordenes/<int:pk>/editar/', views.orden_compra_update, name='orden_compra_update'),
    path('ordenes/<int:pk>/eliminar/', views.orden_compra_delete, name='orden_compra_delete'),
    path('ordenes/<int:pk>/aprobar/', views.orden_compra_aprobar, name='orden_compra_aprobar'),
    
    # Recepciones (DESHABILITADO - No se usa por el momento)
    # path('ordenes/<int:orden_id>/recepcion/crear/', views.recepcion_create, name='recepcion_create'),
    # path('recepciones/<int:pk>/', views.recepcion_detail, name='recepcion_detail'),
    
    # AJAX endpoints
    path('ajax/articulo-info/', views.get_articulo_info, name='get_articulo_info'),
    path('ajax/proveedor/crear/', views.proveedor_create_ajax, name='proveedor_create_ajax'),
]
