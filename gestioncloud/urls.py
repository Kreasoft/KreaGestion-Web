"""
URLs principales de GestionCloud
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from . import views
from . import views_asistente
from usuarios.views import CustomLoginView
from ventas import views as ventas_views

def dashboard_view(request):
    """Vista del dashboard principal"""
    return views.dashboard(request)

@login_required
def opciones_principales_view(request):
    """Centro de ayuda operativo de GestionCloud."""
    return render(request, 'opciones_principales.html')

def paleta_colores_view(request):
    """Vista de paleta de colores del sistema"""
    return render(request, 'paleta_colores.html')

def zenith_os_view(request):
    """Experimento de interfaz basada en iconos (Zenith OS)"""
    return render(request, 'zenith_os.html')


urlpatterns = [
	path('admin/', admin.site.urls),
	path('accounts/login/', CustomLoginView.as_view(), name='login'),
	path('accounts/', include('django.contrib.auth.urls')),
	path('', dashboard_view, name='dashboard'),
	path('resumen/', views_asistente.resumen_dueno, name='resumen_dueno'),
	path('asistente/preguntar/', views_asistente.asistente_preguntar, name='asistente_preguntar'),
	path('dashboard/', dashboard_view, name='dashboard_alt'),
	path('dashboard-nuevo/', dashboard_view, name='dashboard_moderno'),
	path('dashboard-clasico/', dashboard_view, name='dashboard_clasico'),
	path('opciones/', opciones_principales_view, name='opciones_principales'),
	path('paleta-colores/', paleta_colores_view, name='paleta_colores'),
	path('zenith-os/', zenith_os_view, name='zenith_os'),
	path('ventas/facturador-directo/', ventas_views.facturar_directo, name='facturar_directo'),
	path('empresas/', include('empresas.urls')),
	path('articulos/', include('articulos.urls')),
	path('inventario/', include('inventario.urls')),
    path('bodegas/', include('bodegas.urls')),
	path('ventas/', include('ventas.urls')),
	path('compras/', include('compras.urls')),
	path('pedidos/', include('pedidos.urls')),
	path('clientes/', include('clientes.urls')),
	path('documentos/', include('documentos.urls')),
	path('proveedores/', include('proveedores.urls')),
	path('reportes/', include('reportes.urls')),
	path('usuarios/', include('usuarios.urls')),
	path('tesoreria/', include('tesoreria.urls')),
	path('caja/', include('caja.urls')),
	path('facturacion-electronica/', include('facturacion_electronica.urls')),
	# Alias histórico: conserva los enlaces antiguos sin registrar dos veces
	# el namespace principal ``facturacion_electronica``.
	path(
		'facturacion_electronica/',
		include('facturacion_electronica.urls', namespace='facturacion_electronica_legacy'),
	),
	path('utilidades/', include('utilidades.urls')),
	path('informes/', include('informes.urls')),
	path('produccion/', include('produccion.urls')),
]

handler403 = 'gestioncloud.views_errores.permiso_denegado'

# Configuración para archivos estáticos y media en desarrollo
if settings.DEBUG:
	urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
	urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
