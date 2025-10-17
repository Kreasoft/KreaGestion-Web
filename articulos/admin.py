from django.contrib import admin
from .models import (
    Articulo, CategoriaArticulo, UnidadMedida, StockArticulo, 
    ImpuestoEspecifico, ListaPrecio, PrecioArticulo,
    RecetaProduccion, InsumoReceta, OrdenProduccion
)


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


# ==================== ADMIN DE PRODUCCIÓN ====================

class InsumoRecetaInline(admin.TabularInline):
    model = InsumoReceta
    extra = 1
    fields = ['articulo', 'cantidad', 'orden', 'notas']
    autocomplete_fields = ['articulo']


@admin.register(RecetaProduccion)
class RecetaProduccionAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'producto_final', 'cantidad_producir', 'unidad_medida', 'tipo_industria', 'activo']
    list_filter = ['activo', 'producto_final__tipo_produccion', 'empresa']
    search_fields = ['codigo', 'nombre', 'producto_final__nombre']
    list_editable = ['activo']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion', 'costo_total_insumos', 'costo_unitario']
    inlines = [InsumoRecetaInline]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'codigo', 'nombre', 'descripcion', 'producto_final')
        }),
        ('Cantidades y Tiempos', {
            'fields': ('cantidad_producir', 'merma_estimada', 'tiempo_estimado')
        }),
        ('Configuración Específica', {
            'fields': ('temperatura_proceso',),
            'classes': ('collapse',)
        }),
        ('Costos', {
            'fields': ('costo_total_insumos', 'costo_unitario'),
            'classes': ('collapse',)
        }),
        ('Estado', {
            'fields': ('activo', 'fecha_creacion', 'fecha_actualizacion')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('empresa', 'producto_final')


@admin.register(InsumoReceta)
class InsumoRecetaAdmin(admin.ModelAdmin):
    list_display = ['receta', 'articulo', 'cantidad', 'costo_unitario', 'costo_total', 'orden']
    list_filter = ['receta__producto_final__tipo_produccion']
    search_fields = ['receta__nombre', 'articulo__nombre', 'articulo__codigo']
    ordering = ['receta', 'orden']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('receta', 'articulo')


@admin.register(OrdenProduccion)
class OrdenProduccionAdmin(admin.ModelAdmin):
    list_display = [
        'numero_orden', 'receta', 'cantidad_planificada', 'cantidad_producida', 
        'porcentaje_completado', 'estado', 'fecha_planificada', 'responsable'
    ]
    list_filter = ['estado', 'sucursal', 'fecha_planificada', 'receta__producto_final__tipo_produccion']
    search_fields = ['numero_orden', 'receta__nombre', 'responsable', 'lote_produccion']
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion', 'porcentaje_completado', 'costo_total']
    date_hierarchy = 'fecha_planificada'
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'sucursal', 'numero_orden', 'receta', 'responsable')
        }),
        ('Planificación', {
            'fields': ('cantidad_planificada', 'fecha_planificada', 'estado')
        }),
        ('Producción Real', {
            'fields': ('cantidad_producida', 'merma_real', 'fecha_inicio', 'fecha_fin', 'porcentaje_completado')
        }),
        ('Trazabilidad (Cárnico)', {
            'fields': ('lote_produccion', 'fecha_vencimiento', 'temperatura_proceso'),
            'classes': ('collapse',)
        }),
        ('Costos y Observaciones', {
            'fields': ('costo_total', 'observaciones')
        }),
        ('Auditoría', {
            'fields': ('fecha_creacion', 'fecha_actualizacion'),
            'classes': ('collapse',)
        }),
    )
    
    def porcentaje_completado(self, obj):
        """Muestra el porcentaje completado con formato"""
        porcentaje = obj.porcentaje_completado
        return f"{porcentaje:.1f}%"
    porcentaje_completado.short_description = '% Completado'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('empresa', 'sucursal', 'receta', 'receta__producto_final')