from django.contrib import admin
from .models import Vendedor, FormaPago, EstacionTrabajo, Venta, VentaDetalle
# Pedido, Devolucion temporalmente deshabilitados


@admin.register(Vendedor)
class VendedorAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'porcentaje_comision', 'activo', 'empresa']
    list_filter = ['activo', 'empresa']
    search_fields = ['codigo', 'nombre']
    ordering = ['codigo', 'nombre']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'codigo', 'nombre')
        }),
        ('Comisiones', {
            'fields': ('porcentaje_comision',)
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
    )


@admin.register(FormaPago)
class FormaPagoAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nombre', 'es_cuenta_corriente', 'requiere_cheque', 'activo', 'empresa']
    list_filter = ['es_cuenta_corriente', 'requiere_cheque', 'activo', 'empresa']
    search_fields = ['codigo', 'nombre']
    ordering = ['codigo', 'nombre']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'codigo', 'nombre')
        }),
        ('Configuración', {
            'fields': ('es_cuenta_corriente', 'requiere_cheque')
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
    )


@admin.register(EstacionTrabajo)
class EstacionTrabajoAdmin(admin.ModelAdmin):
    list_display = ['numero', 'nombre', 'puede_facturar', 'puede_boletar', 'puede_guia', 'puede_cotizar', 'puede_vale', 'activo', 'empresa']
    list_filter = ['puede_facturar', 'puede_boletar', 'puede_guia', 'puede_cotizar', 'puede_vale', 'activo', 'empresa']
    search_fields = ['numero', 'nombre']
    ordering = ['numero', 'nombre']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'numero', 'nombre', 'descripcion')
        }),
        ('Tipos de Documentos Permitidos', {
            'fields': ('puede_facturar', 'puede_boletar', 'puede_guia', 'puede_cotizar', 'puede_vale')
        }),
        ('Límites de Items', {
            'fields': ('max_items_factura', 'max_items_boleta', 'max_items_guia', 'max_items_cotizacion', 'max_items_vale')
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
    )


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ['numero_venta', 'cliente', 'fecha', 'tipo_documento', 'estado', 'total', 'empresa']
    list_filter = ['estado', 'tipo_documento', 'empresa']
    search_fields = ['numero_venta', 'cliente__nombre']
    ordering = ['-fecha_creacion']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'numero_venta', 'fecha', 'cliente', 'vendedor', 'forma_pago', 'estacion_trabajo', 'tipo_documento')
        }),
        ('Totales', {
            'fields': ('subtotal', 'descuento', 'neto', 'iva', 'impuesto_especifico', 'total')
        }),
        ('Estado y Observaciones', {
            'fields': ('estado', 'observaciones')
        }),
    )


@admin.register(VentaDetalle)
class VentaDetalleAdmin(admin.ModelAdmin):
    list_display = ['venta', 'articulo', 'cantidad', 'precio_unitario', 'precio_total']
    list_filter = ['venta__empresa']
    search_fields = ['venta__numero_venta', 'articulo__nombre']
    ordering = ['-fecha_creacion']


# Temporalmente comentados
# @admin.register(Pedido)
# class PedidoAdmin(admin.ModelAdmin):
#     list_display = ['numero_pedido', 'cliente', 'fecha_pedido', 'estado', 'total', 'empresa']
#     list_filter = ['estado', 'tipo_entrega', 'empresa']
#     search_fields = ['numero_pedido', 'cliente__nombre']
#     ordering = ['-fecha_pedido']


# @admin.register(Venta)
# class VentaAdmin(admin.ModelAdmin):
#     list_display = ['numero_venta', 'cliente', 'fecha_venta', 'estado', 'forma_pago', 'total', 'empresa']
#     list_filter = ['estado', 'forma_pago', 'empresa']
#     search_fields = ['numero_venta', 'cliente__nombre']
#     ordering = ['-fecha_venta']


# @admin.register(Devolucion)
# class DevolucionAdmin(admin.ModelAdmin):
#     list_display = ['numero_devolucion', 'venta', 'cliente', 'fecha_devolucion', 'estado', 'total']
#     list_filter = ['estado']
#     search_fields = ['numero_devolucion', 'venta__numero_venta', 'cliente__nombre']
#     ordering = ['-fecha_devolucion']
