from django.urls import path
from . import views

app_name = 'pedidos'

urlpatterns = [
    # CRUD de órdenes de pedido
    path('', views.orden_pedido_list, name='orden_pedido_list'),
    path('crear/', views.orden_pedido_create, name='orden_pedido_create'),
    path('<int:pk>/', views.orden_pedido_detail, name='orden_pedido_detail'),
    path('<int:pk>/editar/', views.orden_pedido_update, name='orden_pedido_update'),
    path('<int:pk>/eliminar/', views.orden_pedido_delete, name='orden_pedido_delete'),
    path('<int:pk>/cambiar-estado/', views.orden_pedido_cambiar_estado, name='orden_pedido_cambiar_estado'),

    # Gestión de despachos (Comentado temporalmente)
    # path('despachos/', views.despacho_list, name='despacho_list'),
    # path('despachos/crear/', views.despacho_create, name='despacho_create'),
    # path('despachos/<int:pk>/', views.despacho_detail, name='despacho_detail'),
    # path('despachos/<int:pk>/editar/', views.despacho_update, name='despacho_update'),
    # path('despachos/<int:pk>/cambiar-estado/', views.despacho_cambiar_estado, name='despacho_cambiar_estado'),
    # path('despachos/<int:pk>/eliminar/', views.despacho_delete, name='despacho_delete'),
    # path('despachos/<int:pk>/imprimir-guia/', views.despacho_imprimir_guia, name='despacho_imprimir_guia'),
]
