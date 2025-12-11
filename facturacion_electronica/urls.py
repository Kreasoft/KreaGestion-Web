from django.urls import path
from . import views
from . import views_dte

app_name = 'facturacion_electronica'

urlpatterns = [
    # Archivos CAF
    path('caf/', views.caf_list, name='caf_list'),
    path('caf/nuevo/', views.caf_create, name='caf_create'),
    path('caf/<int:pk>/', views.caf_detail, name='caf_detail'),
    path('caf/<int:pk>/ajustar-folio/', views.caf_ajustar_folio, name='caf_ajustar_folio'),
    path('caf/<int:pk>/anular/', views.caf_anular, name='caf_anular'),
    
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
]

