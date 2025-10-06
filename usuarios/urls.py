from django.urls import path
from . import views

app_name = 'usuarios'

urlpatterns = [
    path('', views.usuario_list, name='usuario_list'),
    path('<int:user_id>/toggle-estado/', views.usuario_toggle_estado, name='usuario_toggle_estado'),
    path('<int:user_id>/asignar-grupo/', views.usuario_asignar_grupo, name='usuario_asignar_grupo'),
]