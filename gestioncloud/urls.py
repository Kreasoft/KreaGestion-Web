"""
URLs principales de GestionCloud
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from . import views

def dashboard_view(request):
    """Vista del dashboard principal"""
    return views.dashboard(request)

def opciones_principales_view(request):
    """Vista de opciones principales del sistema"""
    return render(request, 'opciones_principales.html')

def paleta_colores_view(request):
    """Vista de paleta de colores del sistema"""
    return render(request, 'paleta_colores.html')


urlpatterns = [
	path('admin/', admin.site.urls),
	path('accounts/', include('django.contrib.auth.urls')),
	path('', dashboard_view, name='dashboard'),
	path('opciones/', opciones_principales_view, name='opciones_principales'),
	path('paleta-colores/', paleta_colores_view, name='paleta_colores'),
	path('empresas/', include('empresas.urls')),
	path('articulos/', include('articulos.urls')),
	path('inventario/', include('inventario.urls')),
    path('bodegas/', include('bodegas.urls')),
	path('ventas/', include('ventas.urls')),
	path('compras/', include('compras.urls')),
	path('clientes/', include('clientes.urls')),
	path('documentos/', include('documentos.urls')),
	path('proveedores/', include('proveedores.urls')),
	path('reportes/', include('reportes.urls')),
	path('usuarios/', include('usuarios.urls')),
	path('tesoreria/', include('tesoreria.urls')),
	path('caja/', include('caja.urls')),
	path('facturacion-electronica/', include('facturacion_electronica.urls')),
	path('utilidades/', include('utilidades.urls')),
]

# Configuración para archivos estáticos y media en desarrollo
if settings.DEBUG:
	urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
	urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

