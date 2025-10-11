from django.urls import path
from . import views

app_name = 'utilidades'

urlpatterns = [
    path('', views.utilidades_dashboard, name='dashboard'),
    path('importar/', views.importar_datos, name='importar_datos'),
    path('importar/conectar/', views.conectar_mysql, name='conectar_mysql'),
    path('importar/mapear/', views.mapear_campos, name='mapear_campos'),
    path('importar/ejecutar/', views.ejecutar_importacion, name='ejecutar_importacion'),
]
