from django.contrib import admin
from .models import (
    OrdenPedido, ItemOrdenPedido, 
    OrdenDespacho, DetalleOrdenDespacho,
    Chofer, Vehiculo
)


# ===== CHOFERES =====
@admin.register(Chofer)
class ChoferAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'rut', 'activo', 'empresa')
    list_filter = ('activo', 'empresa')
    search_fields = ('codigo', 'nombre', 'rut')
    ordering = ['codigo']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'codigo', 'nombre', 'rut')
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
    )


# ===== VEHÍCULOS =====
@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ('patente', 'descripcion', 'capacidad', 'activo', 'empresa')
    list_filter = ('activo', 'empresa')
    search_fields = ('patente', 'descripcion')
    ordering = ['patente']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'patente', 'descripcion', 'capacidad')
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
    )


# ===== ÓRDENES DE PEDIDO =====
class ItemOrdenPedidoInline(admin.TabularInline):
    model = ItemOrdenPedido
    extra = 1
    fields = ('articulo', 'cantidad', 'precio_unitario', 'descuento_porcentaje', 'impuesto_porcentaje')


@admin.register(OrdenPedido)
class OrdenPedidoAdmin(admin.ModelAdmin):
    list_display = ('numero_pedido', 'cliente', 'fecha_pedido', 'estado', 'total_pedido', 'creado_por')
    list_filter = ('estado', 'fecha_pedido', 'empresa')
    search_fields = ('numero_pedido', 'cliente__nombre', 'numero_oc_cliente')
    inlines = [ItemOrdenPedidoInline]
    readonly_fields = ('numero_pedido', 'subtotal', 'descuentos_totales', 'impuestos_totales', 'total_pedido', 'fecha_creacion', 'fecha_modificacion')


@admin.register(ItemOrdenPedido)
class ItemOrdenPedidoAdmin(admin.ModelAdmin):
    list_display = ('orden_pedido', 'articulo', 'cantidad', 'precio_unitario', 'get_total')
    list_filter = ('orden_pedido__estado',)
    search_fields = ('articulo__nombre', 'orden_pedido__numero_pedido')


# ===== ÓRDENES DE DESPACHO =====
class DetalleOrdenDespachoInline(admin.TabularInline):
    model = DetalleOrdenDespacho
    extra = 1
    fields = ('item_pedido', 'cantidad', 'guia_despacho', 'factura', 'lote', 'fecha_vencimiento')
    autocomplete_fields = ['guia_despacho', 'factura']


@admin.register(OrdenDespacho)
class OrdenDespachoAdmin(admin.ModelAdmin):
    list_display = (
        'numero_despacho', 'orden_pedido', 'fecha_despacho', 'estado', 
        'chofer', 'vehiculo', 'creado_por', 'fecha_creacion'
    )
    list_filter = ('estado', 'fecha_despacho', 'empresa', 'chofer', 'vehiculo')
    search_fields = (
        'numero_despacho', 'orden_pedido__numero_pedido', 
        'orden_pedido__cliente__nombre', 'chofer__nombre', 
        'vehiculo__patente', 'transportista_externo'
    )
    inlines = [DetalleOrdenDespachoInline]
    readonly_fields = ('numero_despacho', 'fecha_creacion', 'fecha_modificacion')
    autocomplete_fields = ['chofer', 'vehiculo']
    
    fieldsets = (
        ('Información General', {
            'fields': ('numero_despacho', 'orden_pedido', 'empresa', 'estado')
        }),
        ('Fechas', {
            'fields': ('fecha_despacho', 'fecha_entrega_estimada', 'fecha_entrega_real')
        }),
        ('Transporte', {
            'fields': ('chofer', 'vehiculo', 'transportista_externo'),
            'description': 'Asignar chofer y vehículo propio, o especificar transportista externo'
        }),
        ('Información Adicional', {
            'fields': ('direccion_entrega', 'observaciones')
        }),
        ('Auditoría', {
            'fields': ('creado_por', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DetalleOrdenDespacho)
class DetalleOrdenDespachoAdmin(admin.ModelAdmin):
    list_display = (
        'orden_despacho', 'item_pedido', 'cantidad', 
        'guia_despacho', 'factura', 'lote'
    )
    list_filter = ('orden_despacho__estado', 'fecha_creacion')
    search_fields = (
        'orden_despacho__numero_despacho', 
        'item_pedido__articulo__nombre', 
        'lote'
    )
    autocomplete_fields = ['guia_despacho', 'factura']
