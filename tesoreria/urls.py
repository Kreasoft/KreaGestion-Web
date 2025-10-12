from django.urls import path
from . import views

app_name = 'tesoreria'

urlpatterns = [
    path('cuenta-corriente-proveedor/', views.cuenta_corriente_proveedor_list, name='cuenta_corriente_proveedor_list'),
    path('cuenta-corriente-proveedor/<int:proveedor_id>/', views.cuenta_corriente_proveedor_detail, name='cuenta_corriente_proveedor_detail'),
    path('cuenta-corriente-cliente/', views.cuenta_corriente_cliente_list, name='cuenta_corriente_cliente_list'),
    path('registrar-pago/', views.registrar_pago, name='registrar_pago'),
    path('obtener-formas-pago/', views.obtener_formas_pago, name='obtener_formas_pago'),
    path('cambiar-empresa/', views.cambiar_empresa_activa, name='cambiar_empresa_activa'),
    path('historial-pagos/<int:documento_id>/', views.historial_pagos_documento, name='historial_pagos_documento'),
    path('detalle-pago/<int:pago_id>/', views.detalle_pago, name='detalle_pago'),
    path('editar-pago/<int:pago_id>/', views.editar_pago, name='editar_pago'),
    
    # CRUD Documentos Pendientes Proveedores
    path('documentos-pendientes/proveedores/', views.documento_pendiente_proveedor_list, name='documento_pendiente_proveedor_list'),
    path('documentos-pendientes/proveedores/crear/', views.documento_pendiente_proveedor_create, name='documento_pendiente_proveedor_create'),
    path('documentos-pendientes/proveedores/<int:pk>/editar/', views.documento_pendiente_proveedor_edit, name='documento_pendiente_proveedor_edit'),
    path('documentos-pendientes/proveedores/<int:pk>/eliminar/', views.documento_pendiente_proveedor_delete, name='documento_pendiente_proveedor_delete'),
    
    # CRUD Documentos Pendientes Clientes
    path('obtener-clientes/', views.obtener_clientes, name='obtener_clientes'),
    path('crear-documento-cliente/', views.crear_documento_cliente, name='crear_documento_cliente'),
    path('obtener-documento-cliente/<int:pk>/', views.obtener_documento_cliente, name='obtener_documento_cliente'),
    path('editar-documento-cliente/<int:pk>/', views.editar_documento_cliente, name='editar_documento_cliente'),
    path('eliminar-documento-cliente/<int:pk>/', views.eliminar_documento_cliente, name='eliminar_documento_cliente'),
    path('historial-pagos-cliente/<int:documento_id>/', views.historial_pagos_documento_cliente, name='historial_pagos_documento_cliente'),
    path('registrar-pago-cliente/', views.registrar_pago_cliente, name='registrar_pago_cliente'),
    
    # Pagos de movimientos de cuenta corriente
    path('registrar-pago-movimiento/', views.registrar_pago_movimiento, name='registrar_pago_movimiento'),
    path('historial-pagos-movimiento/<int:movimiento_id>/', views.historial_pagos_movimiento, name='historial_pagos_movimiento'),
]
