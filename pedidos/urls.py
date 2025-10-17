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
]
