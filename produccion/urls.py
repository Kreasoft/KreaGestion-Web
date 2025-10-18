from django.urls import path
from . import views

app_name = 'produccion'

urlpatterns = [
    # Recetas de Producción
    path('recetas/', views.receta_list, name='receta_list'),
    path('recetas/crear/', views.receta_create, name='receta_create'),
    path('recetas/<int:pk>/', views.receta_detail, name='receta_detail'),
    path('recetas/<int:pk>/editar/', views.receta_update, name='receta_update'),
    path('recetas/<int:pk>/eliminar/', views.receta_delete, name='receta_delete'),
    
    # Órdenes de Producción
    path('ordenes/', views.orden_list, name='orden_list'),
    path('ordenes/crear/', views.orden_create, name='orden_create'),
    path('ordenes/<int:pk>/', views.orden_detail, name='orden_detail'),
    path('ordenes/<int:pk>/detalle-json/', views.orden_detail_json, name='orden_detail_json'),
    path('ordenes/<int:pk>/editar/', views.orden_update, name='orden_update'),
    path('ordenes/<int:pk>/eliminar/', views.orden_delete, name='orden_delete'),
    path('ordenes/<int:pk>/iniciar/', views.orden_iniciar, name='orden_iniciar'),
    path('ordenes/<int:pk>/finalizar/', views.orden_finalizar, name='orden_finalizar'),
    path('ordenes/<int:pk>/cancelar/', views.orden_cancelar, name='orden_cancelar'),
    
    # Reportes
    path('reportes/', views.reportes, name='reportes'),
    path('reportes/produccion/', views.reporte_produccion, name='reporte_produccion'),
    path('reportes/produccion/excel/', views.exportar_reporte_produccion_excel, name='exportar_reporte_produccion_excel'),
    path('reportes/produccion/pdf/', views.exportar_reporte_produccion_pdf, name='exportar_reporte_produccion_pdf'),
    path('reportes/costos/', views.reporte_costos, name='reporte_costos'),
    path('ordenes/<int:pk>/excel/', views.exportar_orden_excel, name='exportar_orden_excel'),
]
