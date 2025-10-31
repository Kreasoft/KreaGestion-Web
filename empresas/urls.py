"""
URLs para el módulo de empresas
"""
from django.urls import path
from . import views
from . import api_views

app_name = 'empresas'

urlpatterns = [
	# API Endpoints
	path('api/configuracion/', api_views.api_configuracion, name='api_configuracion'),
	
	path('', views.home, name='home'),
	path('empresas/', views.empresa_list, name='empresa_list'),
	path('empresas/nueva/', views.empresa_create, name='empresa_create'),
	path('empresas/<int:pk>/', views.empresa_detail, name='empresa_detail'),
	path('empresas/<int:pk>/editar/', views.empresa_update, name='empresa_update'),
	path('empresas/<int:pk>/eliminar/', views.empresa_delete, name='empresa_delete'),
	# URLs para sucursales (empresa activa)
	path('sucursales/', views.sucursal_list, name='sucursal_list'),
	path('sucursales/nueva/', views.sucursal_create, name='sucursal_create'),
	path('sucursales/<int:pk>/', views.sucursal_detail, name='sucursal_detail'),
	path('sucursales/<int:pk>/editar/', views.sucursal_update, name='sucursal_update'),
	path('sucursales/<int:pk>/eliminar/', views.sucursal_delete, name='sucursal_delete'),
	# Configuración de empresa
	path('configuracion/', views.empresa_configuracion, name='empresa_configuracion'),
	path('configuraciones/', views.empresa_configuraciones, name='empresa_configuraciones'),
	# Configuración de impresoras
	path('configuracion/impresoras/', views.configurar_impresoras, name='configurar_impresoras'),
	# Paleta de colores
	path('paleta-colores/', views.paleta_colores, name='paleta_colores'),
	# Seleccionar empresa (solo superusuarios)
	path('seleccionar-empresa/', views.seleccionar_empresa, name='seleccionar_empresa'),
	path('editar-empresa-activa/', views.editar_empresa_activa, name='editar_empresa_activa'),
]
