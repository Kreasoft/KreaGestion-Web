from django.urls import path
from . import views
from . import views_despacho
from . import views_transporte
from . import api_views

app_name = 'pedidos'

urlpatterns = [
    # API Endpoints
    path('api/vehiculos/', api_views.api_vehiculos, name='api_vehiculos'),
    path('api/choferes/', api_views.api_choferes, name='api_choferes'),
    
    # CRUD de órdenes de pedido
    path('', views.orden_pedido_list, name='orden_pedido_list'),
    path('crear/', views.orden_pedido_create, name='orden_pedido_create'),
    path('<int:pk>/', views.orden_pedido_detail, name='orden_pedido_detail'),
    path('<int:pk>/editar/', views.orden_pedido_update, name='orden_pedido_update'),
    path('<int:pk>/eliminar/', views.orden_pedido_delete, name='orden_pedido_delete'),
    path('<int:pk>/cambiar-estado/', views.orden_pedido_cambiar_estado, name='orden_pedido_cambiar_estado'),

    # Gestión de Órdenes de Despacho
    path('despachos/', views_despacho.orden_despacho_list, name='orden_despacho_list'),
    path('despachos/crear/', views_despacho.orden_despacho_create, name='orden_despacho_create'),
    path('despachos/<int:pk>/', views_despacho.orden_despacho_detail, name='orden_despacho_detail'),
    path('despachos/<int:pk>/editar/', views_despacho.orden_despacho_edit, name='orden_despacho_edit'),
    path('despachos/<int:pk>/eliminar/', views_despacho.orden_despacho_delete, name='orden_despacho_delete'),

    # Generación de documentos
    path('despachos/<int:pk>/generar-guia/', views_despacho.generar_guia_despacho, name='orden_despacho_generar_guia'),
    path('despachos/<int:pk>/generar-factura/', views_despacho.generar_factura_despacho, name='orden_despacho_generar_factura'),

    # API para el formulario de despacho
    # path('api/pedido/<int:pk>/', views.api_get_pedido_details, name='api_get_pedido_details'),  # Función no implementada
    path('despachos/<int:pk>/cambiar-estado/', views_despacho.orden_despacho_cambiar_estado, name='orden_despacho_cambiar_estado'),
    
    # Gestión de Vehículos
    path('vehiculos/', views_transporte.vehiculo_list, name='vehiculo_list'),
    path('vehiculos/crear/', views_transporte.vehiculo_create, name='vehiculo_create'),
    path('vehiculos/<int:pk>/', views_transporte.vehiculo_detail, name='vehiculo_detail'),
    path('vehiculos/<int:pk>/editar/', views_transporte.vehiculo_update, name='vehiculo_update'),
    path('vehiculos/<int:pk>/eliminar/', views_transporte.vehiculo_delete, name='vehiculo_delete'),
    
    # Gestión de Choferes
    path('choferes/', views_transporte.chofer_list, name='chofer_list'),
    path('choferes/crear/', views_transporte.chofer_create, name='chofer_create'),
    path('choferes/<int:pk>/', views_transporte.chofer_detail, name='chofer_detail'),
    path('choferes/<int:pk>/editar/', views_transporte.chofer_update, name='chofer_update'),
    path('choferes/<int:pk>/eliminar/', views_transporte.chofer_delete, name='chofer_delete'),
    
    # AJAX
    path('ajax/items-pedido/', views_despacho.ajax_items_pedido, name='ajax_items_pedido'),
]
