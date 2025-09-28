from django.urls import path
from . import views

app_name = 'bodegas'

urlpatterns = [
    # Lista de bodegas
    path('', views.bodega_list, name='bodega_list'),
    
    # Modales AJAX
    path('crear-modal/', views.bodega_create_modal, name='bodega_create_modal'),
    path('editar-modal/<int:pk>/', views.bodega_update_modal, name='bodega_update_modal'),
    path('eliminar-modal/<int:pk>/', views.bodega_delete_modal, name='bodega_delete_modal'),
]