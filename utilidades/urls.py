from django.urls import path
from . import views

app_name = 'utilidades'

urlpatterns = [
    path('', views.utilidades_dashboard, name='dashboard'),
    path('importar/', views.importar_datos, name='importar_datos'),
    path('importar/conectar/', views.conectar_mysql, name='conectar_mysql'),
    path('importar/mapear/', views.mapear_campos, name='mapear_campos'),
    path('importar/ejecutar/', views.ejecutar_importacion, name='ejecutar_importacion'),
    path('exportar/', views.exportar_datos_view, name='exportar_datos'),
    path('mantenimiento/', views.mantenimiento_view, name='mantenimiento'),
    
    # URLs de mantenimiento
    path('mantenimiento/optimizar-tablas/', views.optimizar_tablas, name='optimizar_tablas'),
    path('mantenimiento/crear-backup/', views.crear_backup, name='crear_backup'),
    path('mantenimiento/verificar-integridad/', views.verificar_integridad, name='verificar_integridad'),
    path('mantenimiento/limpiar-sesiones/', views.limpiar_sesiones, name='limpiar_sesiones'),
    path('mantenimiento/detectar-duplicados/', views.detectar_duplicados, name='detectar_duplicados'),
    path('mantenimiento/limpiar-archivos/', views.limpiar_archivos, name='limpiar_archivos'),
    path('mantenimiento/ver-logs/', views.ver_logs, name='ver_logs'),
    path('mantenimiento/exportar-logs/', views.exportar_logs, name='exportar_logs'),
    path('mantenimiento/purgar-logs/', views.purgar_logs, name='purgar_logs'),
]
