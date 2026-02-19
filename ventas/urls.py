"""
URLs para el módulo de ventas
"""
from django.urls import path
from django.shortcuts import render, redirect
from . import views
from . import views_notas_credito
from . import api_views
from . import views_pos_procesar

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
    path('pos/cambiar-estacion/', views.pos_cambiar_estacion, name='pos_cambiar_estacion'),
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
    
    # POS - Procesar venta (vistas dedicadas para POS)
    # Modo VALE (cierre_directo=False): Solo genera vale
    path('pos/procesar-venta/<int:ticket_id>/', views_pos_procesar.procesar_venta_pos, name='procesar_venta_pos'),
    # Modo FACTURA DIRECTA (cierre_directo=True): Emite DTE inmediatamente
    path('pos/procesar-venta-directo/<int:ticket_id>/', views_pos_procesar.procesar_venta_pos_directo, name='procesar_venta_pos_directo'),
    
    # Vales/Tickets
    path('vales/', views.vale_list, name='vale_list'),
    path('vales/<int:pk>/html/', views.vale_html, name='vale_html'),
    path('vales/<int:pk>/termica/', views.vale_termica, name='vale_termica'),
    path('tickets/', views.ticket_list, name='ticket_list'),
    path('tickets/<int:pk>/', views.ticket_detail, name='ticket_detail'),
    path('tickets/<int:pk>/reimprimir/', views.ticket_reimprimir, name='ticket_reimprimir'),
    
    # Vista genérica de venta (auto-detecta tipo de documento)
    path('ventas/<int:pk>/html/', views.venta_html, name='venta_html'),
    # Vista wrapper: imprimir y volver al POS
    path('ventas/<int:pk>/imprimir-y-volver/', views.venta_imprimir_y_volver, name='venta_imprimir_y_volver'),
    
    # API para POS - Historial tickets del día
    path('pos/tickets-hoy/', views.pos_tickets_hoy, name='pos_tickets_hoy'),
    
    # TEST - Página de prueba para crear cliente
    path('test-crear-cliente/', lambda request: render(request, 'ventas/test_crear_cliente.html'), name='test_crear_cliente'),
    
    # Cotizaciones
    path('cotizaciones/', views.cotizacion_list, name='cotizacion_list'),
    path('cotizaciones/<int:pk>/', views.cotizacion_detail, name='cotizacion_detail'),
    path('cotizaciones/<int:pk>/pdf/', views.cotizacion_pdf, name='cotizacion_pdf'),
    path('cotizaciones/<int:pk>/html/', views.cotizacion_html, name='cotizacion_html'),
    path('cotizaciones/<int:pk>/debug/', views.cotizacion_html_debug, name='cotizacion_html_debug'),
    path('cotizaciones/<int:pk>/cambiar-estado/', views.cotizacion_cambiar_estado, name='cotizacion_cambiar_estado'),
    path('cotizaciones/<int:pk>/convertir-venta/', views.cotizacion_convertir_venta, name='cotizacion_convertir_venta'),
    
    # Dashboard Premium
    path('dashboard-premium/', lambda request: render(request, 'ventas/dashboard_premium.html'), name='dashboard_premium'),
    
    # Libro de Ventas
    path('libro-ventas/', lambda request: redirect('facturacion_electronica:dte_list', permanent=True), name='libro_ventas'),
    
    # Precios Especiales Clientes
    path('precios-clientes/', views.precio_cliente_list, name='precio_cliente_list'),
    path('precios-clientes/crear/', views.precio_cliente_create, name='precio_cliente_create'),
    path('precios-clientes/<int:pk>/editar/', views.precio_cliente_edit, name='precio_cliente_edit'),
    path('precios-clientes/<int:pk>/eliminar/', views.precio_cliente_delete, name='precio_cliente_delete'),
    
    # API Artículos
    path('articulos/api/articulo/<int:pk>/precio/', views.articulo_precio_api, name='articulo_precio_api'),
    path('api/precio-cliente/<int:cliente_id>/<int:articulo_id>/', views.precio_cliente_articulo_api, name='precio_cliente_articulo_api'),
    
    # API Vendedores
    path('api/vendedores/', api_views.api_vendedores, name='api_vendedores'),
    
    # Notas de Crédito
    path('notas-credito/', views_notas_credito.notacredito_list, name='notacredito_list'),
    path('notas-credito/crear/', views_notas_credito.notacredito_create, name='notacredito_create'),
    path('notas-credito/<int:pk>/', views_notas_credito.notacredito_detail, name='notacredito_detail'),
    path('notas-credito/<int:pk>/imprimir/', views_notas_credito.notacredito_print, name='notacredito_print'),
    
    # API AJAX para cargar items de venta
    path('ajax/cargar-items-venta/', views_notas_credito.ajax_cargar_items_venta, name='ajax_cargar_items_venta'),

    # API AJAX para buscar documentos afectados
    path('ajax/buscar-documento-afectado/', views_notas_credito.ajax_buscar_documento_afectado, name='ajax_buscar_documento_afectado'),

    # --- VENTAS MÓVILES (PWA / MOBILE) ---
    path('movil/', views.mobile_sales_app, name='mobile_sales_app'),
    path('movil/gestion/', views.mobile_sales_gestion, name='mobile_sales_gestion'),
    path('movil/gestion/dispositivo/<int:pk>/toggle/', views.mobile_api_toggle_device, name='mobile_api_toggle_device'),
    path('movil/api/sincronizar/', views.mobile_api_sync, name='mobile_api_sync'),
    path('movil/api/verificar-dispositivo/', views.mobile_api_verify_device, name='mobile_api_verify_device'),
    path('movil/api/guardar-venta/', views.mobile_api_save_sale, name='mobile_api_save_sale'),
    path('movil/api/guardar-cliente/', views.mobile_api_save_client, name='mobile_api_save_client'),
    path('movil/api/historial-ventas/', views.mobile_api_sales_history, name='mobile_api_sales_history'),
    path('movil/api/registrar-ubicacion/', views.mobile_api_register_location, name='mobile_api_register_location'),
    path('movil/api/cliente-historial/', views.mobile_api_cliente_historial, name='mobile_api_cliente_historial'),
    path('monitoreo/vendedores/', views.ventas_mapa_vendedores, name='ventas_mapa_vendedores'),
]
