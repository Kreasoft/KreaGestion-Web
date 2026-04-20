from django.urls import path
from . import views

app_name = 'clientes'

urlpatterns = [
    path('', views.cliente_list, name='cliente_list'),
    path('crear/', views.cliente_create, name='cliente_create'),
    path('<int:pk>/', views.cliente_detail, name='cliente_detail'),
    path('<int:pk>/editar/', views.cliente_update, name='cliente_update'),
    path('<int:pk>/eliminar/', views.cliente_delete, name='cliente_delete'),
    path('<int:pk>/toggle-estado/', views.cliente_toggle_estado, name='cliente_toggle_estado'),
    path('ajax/crear/', views.ajax_cliente_create, name='ajax_cliente_create'),
    path('ajax/vendedores/', views.ajax_vendedores, name='ajax_vendedores'),
    path('ajax/<int:pk>/contactos/', views.ajax_cliente_contactos, name='ajax_cliente_contactos'),
    path('ajax/<int:pk>/', views.ajax_cliente_detail, name='ajax_cliente_detail'),
    path('ajax/<int:pk>/editar/', views.ajax_cliente_update, name='ajax_cliente_update'),
    
    # URLs para contactos
    path('<int:cliente_id>/contactos/crear/', views.contacto_create, name='contacto_create'),
    path('<int:cliente_id>/contactos/<int:contacto_id>/editar/', views.contacto_update, name='contacto_update'),
    path('<int:cliente_id>/contactos/<int:contacto_id>/eliminar/', views.contacto_delete, name='contacto_delete'),
]