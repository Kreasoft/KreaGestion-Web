from django.urls import path
from . import views

app_name = 'documentos'

urlpatterns = [
    # Dashboard de documentos
    path('', views.dashboard_documentos, name='dashboard_documentos'),
    
    # CRUD de documentos de compra
    path('documentos/', views.documento_compra_list, name='documento_compra_list'),
    path('documentos/crear/', views.documento_compra_create, name='documento_compra_create'),
    path('documentos/<int:pk>/', views.documento_compra_detail, name='documento_compra_detail'),
    path('documentos/<int:pk>/editar/', views.documento_compra_update, name='documento_compra_update'),
    path('documentos/<int:pk>/eliminar/', views.documento_compra_delete, name='documento_compra_delete'),
    path('documentos/<int:pk>/aprobar/', views.documento_compra_aprobar, name='documento_compra_aprobar'),
    
    # AJAX endpoints
    path('ajax/articulo-info/<int:articulo_id>/', views.get_articulo_info, name='get_articulo_info'),
    
]