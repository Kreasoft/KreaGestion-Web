"""
URLs para el módulo de ventas
"""
from django.urls import path
from . import views

app_name = 'ventas'

urlpatterns = [
    # Vendedores
    path('vendedores/', views.vendedor_list, name='vendedor_list'),
    path('vendedores/crear/', views.vendedor_create, name='vendedor_create'),
    path('vendedores/<int:pk>/', views.vendedor_detail, name='vendedor_detail'),
    path('vendedores/<int:pk>/editar/', views.vendedor_update, name='vendedor_update'),
    path('vendedores/<int:pk>/eliminar/', views.vendedor_delete, name='vendedor_delete'),
    
    # Formas de Pago
    path('formas-pago/', views.formapago_list, name='formapago_list'),
    path('formas-pago/crear/', views.formapago_create, name='formapago_create'),
    path('formas-pago/<int:pk>/', views.formapago_detail, name='formapago_detail'),
    path('formas-pago/<int:pk>/editar/', views.formapago_update, name='formapago_update'),
    path('formas-pago/<int:pk>/eliminar/', views.formapago_delete, name='formapago_delete'),
    
    # Estaciones de Trabajo
    path('estaciones-trabajo/', views.estaciontrabajo_list, name='estaciontrabajo_list'),
    path('estaciones-trabajo/crear/', views.estaciontrabajo_create, name='estaciontrabajo_create'),
    path('estaciones-trabajo/<int:pk>/', views.estaciontrabajo_detail, name='estaciontrabajo_detail'),
    path('estaciones-trabajo/<int:pk>/editar/', views.estaciontrabajo_edit, name='estaciontrabajo_edit'),
    path('estaciones-trabajo/<int:pk>/eliminar/', views.estaciontrabajo_delete, name='estaciontrabajo_delete'),
    
    # POS (Punto de Venta)
    path('pos/', views.pos_seleccion_estacion, name='pos_seleccion'),
    path('pos/iniciar/', views.pos_iniciar, name='pos_iniciar'),
    path('pos/session-info/', views.pos_session_info, name='pos_session_info'),
    path('pos/venta/', views.pos_view, name='pos_view'),
    path('pos/buscar-articulo/', views.pos_buscar_articulo, name='pos_buscar_articulo'),
    path('pos/agregar-articulo/', views.pos_agregar_articulo, name='pos_agregar_articulo'),
    path('pos/actualizar-detalle/', views.pos_actualizar_detalle, name='pos_actualizar_detalle'),
    path('pos/eliminar-detalle/', views.pos_eliminar_detalle, name='pos_eliminar_detalle'),
    path('pos/actualizar-venta/', views.pos_actualizar_venta, name='pos_actualizar_venta'),
    path('pos/detalles-venta/<int:venta_id>/', views.pos_detalles_venta, name='pos_detalles_venta'),
    
    # POS - Gestión de clientes y preventas
    path('pos/buscar-cliente/', views.pos_buscar_cliente, name='pos_buscar_cliente'),
    path('pos/crear-cliente-boleta/', views.pos_crear_cliente_boleta, name='pos_crear_cliente_boleta'),
    path('pos/crear-cliente/', views.pos_crear_cliente, name='pos_crear_cliente'),
    path('pos/procesar-preventa/', views.pos_procesar_preventa, name='pos_procesar_preventa'),
    
    # Cotizaciones
    path('cotizaciones/', views.cotizacion_list, name='cotizacion_list'),
    path('cotizaciones/<int:pk>/', views.cotizacion_detail, name='cotizacion_detail'),
    path('cotizaciones/<int:pk>/pdf/', views.cotizacion_pdf, name='cotizacion_pdf'),
    path('cotizaciones/<int:pk>/html/', views.cotizacion_html, name='cotizacion_html'),
    path('cotizaciones/<int:pk>/cambiar-estado/', views.cotizacion_cambiar_estado, name='cotizacion_cambiar_estado'),
    path('cotizaciones/<int:pk>/convertir-venta/', views.cotizacion_convertir_venta, name='cotizacion_convertir_venta'),
]
