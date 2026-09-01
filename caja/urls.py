"""
URLs para el módulo de caja
"""
from django.urls import path
from . import views
from . import views_procesar_caja
from . import views_impresion

app_name = 'caja'

urlpatterns = [
    # Gestión de Cajas
    path('cajas/', views.caja_list, name='caja_list'),
    path('cajas/crear/', views.caja_create, name='caja_create'),
    path('cajas/<int:pk>/editar/', views.caja_update, name='caja_update'),
    
    # Aperturas y Cierres
    path('aperturas/', views.apertura_list, name='apertura_list'),
    path('aperturas/crear/', views.apertura_create, name='apertura_create'),
    path('aperturas/<int:pk>/', views.apertura_detail, name='apertura_detail'),
    path('aperturas/<int:pk>/cerrar/', views.apertura_cerrar, name='apertura_cerrar'),
    path('cerrar/', views.cierre_caja_activa, name='cierre_caja'),
    path('aperturas/<int:pk>/imprimir/', views.apertura_imprimir, name='apertura_imprimir'),
    
    # Procesamiento de Ventas
    path('procesar-venta/', views.procesar_venta_buscar, name='procesar_venta_buscar'),
    path('procesar-venta/<int:ticket_id>/', views_procesar_caja.procesar_venta_caja, name='procesar_venta'),
    path('procesar-venta/<int:ticket_id>/eliminar/', views.eliminar_ticket_caja, name='eliminar_ticket_caja'),

    # Estado CAF (AJAX)
    path('estado-caf/', views.estado_caf_pos, name='estado_caf_pos'),
    
    # Movimientos Manuales
    path('aperturas/<int:apertura_id>/movimiento/', views.movimiento_create, name='movimiento_create'),

    path('impresora/', views_impresion.conectar_impresora, name='conectar_impresora'),
    path('impresora/descargar-agente/', views_impresion.descargar_agente, name='descargar_agente'),

    # API Agente Impresión Local
    path('api/impresion/vincular/', views_impresion.vincular_agente, name='api_impresion_vincular'),
    path('api/impresion/destinos/', views_impresion.listar_destinos, name='api_impresion_destinos'),
    path('api/impresion/pendientes/', views_impresion.obtener_pendientes, name='api_impresion_pendientes'),
    path('api/impresion/marcar-impreso/', views_impresion.marcar_impreso, name='api_impresion_marcar_base'),
    path('api/impresion/marcar-impreso/<int:trabajo_id>/', views_impresion.marcar_impreso, name='api_impresion_marcar'),
]

