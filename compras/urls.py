"""
URLs para el módulo de compras
"""
from django.urls import path
from . import views

app_name = 'compras'

urlpatterns = [
    # Dashboard de compras
    path('', views.orden_compra_list, name='orden_compra_list'),
    path('dashboard/', views.orden_compra_list, name='dashboard_compras'),
    
    # Órdenes de compra
    path('ordenes/', views.orden_compra_list, name='orden_compra_list'),
    path('ordenes/crear/', views.orden_compra_create, name='orden_compra_create'),
    path('ordenes/<int:pk>/', views.orden_compra_detail, name='orden_compra_detail'),
    path('ordenes/<int:pk>/editar/', views.orden_compra_update, name='orden_compra_update'),
    path('ordenes/<int:pk>/eliminar/', views.orden_compra_delete, name='orden_compra_delete'),
    path('ordenes/<int:pk>/aprobar/', views.orden_compra_aprobar, name='orden_compra_aprobar'),
    
    # Recepciones (DESHABILITADO - No se usa por el momento)
    # path('ordenes/<int:orden_id>/recepcion/crear/', views.recepcion_create, name='recepcion_create'),
    # path('recepciones/<int:pk>/', views.recepcion_detail, name='recepcion_detail'),
    
    # AJAX endpoints
    path('ajax/articulo-info/', views.get_articulo_info, name='get_articulo_info'),
    path('ajax/proveedor/crear/', views.proveedor_create_ajax, name='proveedor_create_ajax'),

    # Facturas recibidas del SII
    path('facturas-sii/', views.facturas_recibidas_sii, name='facturas_recibidas_sii'),
    path('facturas-sii/sincronizar/', views.sincronizar_facturas_recibidas_sii, name='sincronizar_facturas_sii'),
    path('facturas-sii/importar/', views.importar_factura_recibida_xml, name='importar_factura_xml'),
    path('facturas-sii/<int:pk>/consultar/', views.consultar_eventos_factura_sii, name='consultar_eventos_sii'),
    path('facturas-sii/<int:pk>/chequear-xml/', views.chequear_xml_factura_sii, name='chequear_xml_sii'),
    path('facturas-sii/<int:pk>/pedir-xml/', views.solicitar_xml_factura_sii, name='solicitar_xml_sii'),
    path('facturas-sii/<int:pk>/evento/', views.registrar_evento_factura_sii, name='registrar_evento_sii'),
    path('facturas-sii/xml/<int:pk>/', views.descargar_xml_factura_sii, name='descargar_xml_factura_sii'),
    path('facturas-sii/<int:pk>/rcv.xml', views.ver_registro_rcv_xml, name='ver_registro_rcv_xml'),
    path('facturas-sii/<int:pk>/rcv.pdf', views.ver_registro_rcv_pdf, name='ver_registro_rcv_pdf'),
]
