from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    # Usuarios
    path('', views.usuario_list, name='usuario_list'),
    path('crear/', views.usuario_create, name='usuario_create'),
    path('<int:user_id>/editar/', views.usuario_edit, name='usuario_edit'),
    path('<int:user_id>/eliminar/', views.usuario_delete, name='usuario_delete'),
    path('<int:user_id>/toggle-estado/', views.usuario_toggle_estado, name='usuario_toggle_estado'),
    path('<int:user_id>/asignar-grupo/', views.usuario_asignar_grupo, name='usuario_asignar_grupo'),
    
    # Grupos/Roles
    path('grupos/', views.grupo_list, name='grupo_list'),
    path('grupos/crear/', views.grupo_create, name='grupo_create'),
    path('grupos/<int:grupo_id>/editar/', views.grupo_edit, name='grupo_edit'),
    path('grupos/<int:grupo_id>/eliminar/', views.grupo_delete, name='grupo_delete'),
]