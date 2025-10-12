from django.urls import path
from . import views

app_name = 'articulos'

urlpatterns = [
    # Artículos
    path('', views.articulo_list, name='articulo_list'),
    path('crear/', views.articulo_create, name='articulo_create'),
    path('<int:pk>/', views.articulo_detail, name='articulo_detail'),
    path('<int:pk>/editar/', views.articulo_update, name='articulo_update'),
    path('<int:pk>/eliminar/', views.articulo_delete, name='articulo_delete'),
    
    # Categorías
    path('categorias/', views.categoria_list, name='categoria_list'),
    path('categorias/crear/', views.categoria_create, name='categoria_create'),
    path('categorias/<int:pk>/editar/', views.categoria_update, name='categoria_update'),
    path('categorias/<int:pk>/eliminar/', views.categoria_delete, name='categoria_delete'),
    
    # Unidades de Medida
    path('unidades/', views.unidad_medida_list, name='unidad_medida_list'),
    path('unidades/crear/', views.unidad_medida_create, name='unidad_medida_create'),
    path('unidades/<int:pk>/editar/', views.unidad_medida_update, name='unidad_medida_update'),
    # path('unidades/<int:pk>/eliminar/', views.unidad_medida_delete, name='unidad_medida_delete'),
    
    # Impuestos Específicos
    path('impuestos/', views.impuesto_especifico_list, name='impuesto_especifico_list'),
    path('impuestos/crear/', views.impuesto_especifico_create, name='impuesto_especifico_create'),
    path('impuestos/<int:pk>/editar/', views.impuesto_especifico_update, name='impuesto_especifico_update'),
    path('impuestos/<int:pk>/eliminar/', views.impuesto_especifico_delete, name='impuesto_especifico_delete'),
    
    # Cálculos de Precios
    path('calcular-precios/', views.calcular_precios_articulo, name='calcular_precios_articulo'),
    
    # Impuesto específico de categoría
    path('categoria/<int:categoria_id>/impuesto-especifico/', views.categoria_impuesto_especifico, name='categoria_impuesto_especifico'),
    path('buscar-por-codigo-barras/', views.buscar_por_codigo_barras, name='buscar_por_codigo_barras'),
    path('stock-actual/', views.stock_actual, name='stock_actual'),
    
    # Listas de Precios
    path('listas-precios/', views.lista_precio_list, name='lista_precio_list'),
    path('listas-precios/crear/', views.lista_precio_create, name='lista_precio_create'),
    path('listas-precios/<int:pk>/', views.lista_precio_detail, name='lista_precio_detail'),
    path('listas-precios/<int:pk>/editar/', views.lista_precio_update, name='lista_precio_update'),
    path('listas-precios/<int:pk>/eliminar/', views.lista_precio_delete, name='lista_precio_delete'),
    path('listas-precios/<int:pk>/gestionar-precios/', views.lista_precio_gestionar_precios, name='lista_precio_gestionar_precios'),
    path('listas-precios/<int:pk>/exportar-excel/', views.lista_precio_exportar_excel, name='lista_precio_exportar_excel'),
    path('listas-precios/<int:pk>/exportar-pdf/', views.lista_precio_exportar_pdf, name='lista_precio_exportar_pdf'),
    
    # API
    path('api/listas-precios/', views.api_listas_precios, name='api_listas_precios'),
]
