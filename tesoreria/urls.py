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
    path('detalle-pago/<int:pago_id>/', views.detalle_pago, name='detalle_pago'),
    path('editar-pago/<int:pago_id>/', views.editar_pago, name='editar_pago'),
]
