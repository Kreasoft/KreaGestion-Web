from django.urls import path
from . import views
from . import views_despacho

app_name = 'pedidos'

urlpatterns = [
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
    path('despachos/<int:pk>/cambiar-estado/', views_despacho.orden_despacho_cambiar_estado, name='orden_despacho_cambiar_estado'),
    
    # AJAX
    path('ajax/items-pedido/', views_despacho.ajax_items_pedido, name='ajax_items_pedido'),
]
