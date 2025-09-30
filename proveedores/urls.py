from django.urls import path
from . import views

app_name = 'proveedores'

urlpatterns = [
    path('', views.proveedor_list, name='proveedor_list'),
    path('crear/', views.proveedor_create, name='proveedor_create'),
    path('<int:pk>/', views.proveedor_detail, name='proveedor_detail'),
    path('<int:pk>/editar/', views.proveedor_update, name='proveedor_update'),
    path('<int:pk>/eliminar/', views.proveedor_delete, name='proveedor_delete'),
    
    # URLs para contactos
    path('<int:proveedor_id>/contactos/crear/', views.contacto_create, name='contacto_create'),
    path('<int:proveedor_id>/contactos/<int:contacto_id>/editar/', views.contacto_update, name='contacto_update'),
    path('<int:proveedor_id>/contactos/<int:contacto_id>/eliminar/', views.contacto_delete, name='contacto_delete'),
]
