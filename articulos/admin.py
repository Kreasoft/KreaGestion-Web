from django.contrib import admin
from .models import Articulo, CategoriaArticulo, UnidadMedida, StockArticulo, ImpuestoEspecifico, ListaPrecio, PrecioArticulo


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


@admin.register(ListaPrecio)
class ListaPrecioAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'empresa', 'es_predeterminada', 'activa', 'fecha_creacion', 'fecha_actualizacion']
    list_filter = ['activa', 'es_predeterminada', 'empresa', 'fecha_creacion']
    search_fields = ['nombre', 'descripcion']
    list_editable = ['activa', 'es_predeterminada']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion']
    ordering = ['-es_predeterminada', 'nombre']


@admin.register(PrecioArticulo)
class PrecioArticuloAdmin(admin.ModelAdmin):
    list_display = ['articulo', 'lista_precio', 'precio', 'precio_con_iva_calculado', 'fecha_actualizacion']
    list_filter = ['lista_precio', 'fecha_actualizacion']
    search_fields = ['articulo__nombre', 'articulo__codigo', 'lista_precio__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion', 'precio_con_iva_calculado']
    ordering = ['lista_precio', 'articulo__nombre']
    
    def precio_con_iva_calculado(self, obj):
        """Muestra el precio con IVA calculado"""
        precio_iva = float(obj.precio) * 1.19
        return f"${precio_iva:,.0f}".replace(",", ".")
    precio_con_iva_calculado.short_description = 'Precio c/IVA'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('articulo', 'lista_precio')