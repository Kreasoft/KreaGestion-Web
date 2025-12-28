from django.urls import path
from . import views
from . import views_dte
from . import views_caf
from . import views_monitor

app_name = 'facturacion_electronica'

urlpatterns = [
    # Archivos CAF - Nuevas vistas con soporte de sucursal
    path('caf/', views_caf.listar_cafs, name='listar_cafs'),
    path('caf/cargar/', views_caf.cargar_caf, name='cargar_caf'),
    path('caf/<int:caf_id>/ocultar/', views_caf.ocultar_caf, name='ocultar_caf'),
    path('caf/<int:caf_id>/mostrar/', views_caf.mostrar_caf, name='mostrar_caf'),
    path('caf/<int:caf_id>/eliminar/', views_caf.eliminar_caf, name='eliminar_caf'),
    path('caf/ocultar-agotados/', views_caf.ocultar_cafs_agotados, name='ocultar_cafs_agotados'),
    path('caf/mostrar-ocultos/', views_caf.mostrar_cafs_ocultos, name='mostrar_cafs_ocultos'),
    path('caf/eliminar-sin-uso/', views_caf.eliminar_cafs_sin_uso, name='eliminar_cafs_sin_uso'),
    
    # Archivos CAF - Vistas antiguas (mantener por compatibilidad)
    path('caf/legacy/', views.caf_list, name='caf_list'),
    path('caf/legacy/nuevo/', views.caf_create, name='caf_create'),
    path('caf/legacy/<int:pk>/', views.caf_detail, name='caf_detail'),
    path('caf/legacy/<int:pk>/ajustar-folio/', views.caf_ajustar_folio, name='caf_ajustar_folio'),
    path('caf/legacy/<int:pk>/anular/', views.caf_anular, name='caf_anular'),
    
    # Alertas de Folios
    path('alertas-folios/', views.alertas_folios_config, name='alertas_folios_config'),
    
    # DTEs - Lista y detalle
    path('dte/', views_dte.dte_list, name='dte_list'),
    path('dte/<int:pk>/', views_dte.dte_detail, name='dte_detail'),
    
    # DTEs - Generación y envío
    path('venta/<int:venta_id>/generar-dte/', views_dte.generar_dte_venta, name='generar_dte_venta'),
    path('dte/<int:dte_id>/enviar/', views_dte.enviar_dte_sii, name='enviar_dte'),
    path('dte/<int:dte_id>/consultar-estado/', views_dte.consultar_estado_dte, name='consultar_estado_dte'),
    path('dte/<int:dte_id>/ver-factura/', views_dte.ver_factura_electronica, name='ver_factura_electronica'),
    path('nota-credito/<int:notacredito_id>/ver/', views_dte.ver_notacredito_electronica, name='ver_notacredito_electronica'),
    
    # DTEBox - Prueba
    path('dte/<int:dte_id>/probar-dtebox/', views_dte.probar_dtebox, name='probar_dtebox'),
    path('dtebox/probar-xml-ejemplo/', views_dte.probar_dtebox_xml_ejemplo, name='probar_dtebox_xml_ejemplo'),
    path('dte/<int:dte_id>/descargar-pdf-gdexpress/', views_dte.descargar_pdf_gdexpress, name='descargar_pdf_gdexpress'),
    
    # Monitor de envíos
    path('monitor/', views_monitor.monitor_envios, name='monitor_envios'),
    path('monitor/reenviar/<int:dte_id>/', views_monitor.reenviar_dte, name='reenviar_dte'),
    path('monitor/reenviar-multiples/', views_monitor.reenviar_multiples, name='reenviar_multiples'),
    path('monitor/stats/', views_monitor.stats_envios, name='stats_envios'),
]

