from django.urls import path
from . import views

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
    
    # DTEs
    path('dte/', views.dte_list, name='dte_list'),
    path('dte/<int:pk>/', views.dte_detail, name='dte_detail'),
]

