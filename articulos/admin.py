from django.contrib import admin
from .models import Articulo, CategoriaArticulo, UnidadMedida, StockArticulo, ImpuestoEspecifico


@admin.register(ImpuestoEspecifico)
class ImpuestoEspecificoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'porcentaje', 'empresa', 'activa', 'fecha_creacion']
    list_filter = ['activa', 'empresa', 'fecha_creacion']
    search_fields = ['nombre', 'descripcion']
    list_editable = ['activa']
    ordering = ['nombre']


@admin.register(CategoriaArticulo)
class CategoriaArticuloAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'empresa', 'exenta_iva', 'impuesto_especifico', 'activa', 'fecha_creacion']
    list_filter = ['activa', 'exenta_iva', 'impuesto_especifico', 'empresa', 'fecha_creacion']
    search_fields = ['nombre', 'descripcion']
    list_editable = ['activa']
    ordering = ['nombre']


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'simbolo', 'empresa', 'activa', 'fecha_creacion']
    list_filter = ['activa', 'empresa', 'fecha_creacion']
    search_fields = ['nombre', 'simbolo']
    list_editable = ['activa']
    ordering = ['nombre']


@admin.register(StockArticulo)
class StockArticuloAdmin(admin.ModelAdmin):
    list_display = ['articulo', 'sucursal', 'cantidad_disponible', 'cantidad_reservada', 'cantidad_total', 'fecha_actualizacion']
    list_filter = ['sucursal', 'articulo__categoria', 'fecha_actualizacion']
    search_fields = ['articulo__nombre', 'articulo__codigo', 'sucursal__nombre']
    readonly_fields = ['fecha_actualizacion']
    ordering = ['articulo__nombre']


@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    list_display = [
        'codigo', 'nombre', 'categoria', 'precio_costo', 'precio_venta', 
        'precio_final', 'margen_porcentaje', 'activo', 'fecha_creacion'
    ]
    list_filter = [
        'activo', 'control_stock', 'categoria', 'unidad_medida', 
        'empresa', 'fecha_creacion'
    ]
    search_fields = ['codigo', 'nombre', 'descripcion']
    list_editable = ['activo']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    ordering = ['nombre']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'categoria', 'unidad_medida', 'codigo', 'nombre', 'descripcion')
        }),
        ('Precios', {
            'fields': ('precio_costo', 'precio_venta', 'precio_final', 'margen_porcentaje')
        }),
        ('Control de Stock', {
            'fields': ('control_stock', 'stock_minimo', 'stock_maximo')
        }),
        ('Estado', {
            'fields': ('activo', 'fecha_creacion', 'fecha_actualizacion')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('categoria', 'unidad_medida', 'empresa')