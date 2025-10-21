from django.contrib import admin
from .models import Vendedor, FormaPago, EstacionTrabajo, Venta, VentaDetalle, Devolucion, DevolucionDetalle, PrecioClienteArticulo, VentaReferencia, NotaCredito, NotaCreditoDetalle


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
    list_display = ['numero', 'nombre', 'modo_pos', 'puede_facturar', 'puede_boletar', 'puede_guia', 'puede_cotizar', 'puede_vale', 'activo', 'empresa']
    list_filter = ['modo_pos', 'puede_facturar', 'puede_boletar', 'puede_guia', 'puede_cotizar', 'puede_vale', 'activo', 'empresa']
    search_fields = ['numero', 'nombre']
    ordering = ['numero', 'nombre']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'numero', 'nombre', 'descripcion')
        }),
        ('Configuración POS', {
            'fields': ('modo_pos',)
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


@admin.register(Devolucion)
class DevolucionAdmin(admin.ModelAdmin):
    list_display = ['numero_devolucion', 'venta', 'cliente', 'fecha_devolucion', 'estado', 'monto_total', 'empresa']
    list_filter = ['estado', 'motivo', 'empresa']
    search_fields = ['numero_devolucion', 'venta__numero_ticket', 'cliente__nombre']
    ordering = ['-fecha_devolucion']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'numero_devolucion', 'fecha_devolucion', 'venta', 'cliente')
        }),
        ('Motivo', {
            'fields': ('motivo', 'descripcion_motivo')
        }),
        ('Estado y Montos', {
            'fields': ('estado', 'monto_total')
        }),
        ('Usuarios', {
            'fields': ('usuario_creacion', 'usuario_aprobacion', 'fecha_aprobacion')
        }),
        ('Observaciones', {
            'fields': ('observaciones',)
        }),
    )


@admin.register(DevolucionDetalle)
class DevolucionDetalleAdmin(admin.ModelAdmin):
    list_display = ['devolucion', 'articulo', 'cantidad_devuelta', 'precio_unitario', 'subtotal']
    list_filter = ['devolucion__empresa']
    search_fields = ['devolucion__numero_devolucion', 'articulo__nombre']
    ordering = ['-fecha_creacion']


@admin.register(PrecioClienteArticulo)
class PrecioClienteArticuloAdmin(admin.ModelAdmin):
    list_display = ['cliente', 'articulo', 'precio_especial', 'descuento_porcentaje', 'activo', 'fecha_inicio', 'fecha_fin', 'empresa']
    list_filter = ['activo', 'empresa', 'fecha_inicio', 'fecha_fin']
    search_fields = ['cliente__nombre', 'cliente__rut', 'articulo__nombre', 'articulo__codigo']
    ordering = ['cliente__nombre', 'articulo__nombre']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'cliente', 'articulo')
        }),
        ('Precio y Descuento', {
            'fields': ('precio_especial', 'descuento_porcentaje')
        }),
        ('Vigencia', {
            'fields': ('activo', 'fecha_inicio', 'fecha_fin')
        }),
        ('Auditoría', {
            'fields': ('creado_por',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('creado_por', 'fecha_creacion', 'fecha_modificacion')
    
    def save_model(self, request, obj, form, change):
        if not change:  # Si es nuevo
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(VentaReferencia)
class VentaReferenciaAdmin(admin.ModelAdmin):
    list_display = ['venta', 'tipo_referencia', 'folio_referencia', 'fecha_referencia']
    list_filter = ['tipo_referencia', 'fecha_referencia']
    search_fields = ['venta__numero_venta', 'folio_referencia']
    ordering = ['-fecha_creacion']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('venta', 'tipo_referencia', 'folio_referencia', 'fecha_referencia')
        }),
        ('Detalles', {
            'fields': ('razon_referencia',)
        }),
    )


class NotaCreditoDetalleInline(admin.TabularInline):
    model = NotaCreditoDetalle
    extra = 1
    fields = ['articulo', 'codigo', 'descripcion', 'cantidad', 'precio_unitario', 'descuento', 'total']
    readonly_fields = ['total']


@admin.register(NotaCredito)
class NotaCreditoAdmin(admin.ModelAdmin):
    list_display = ['numero', 'fecha', 'cliente', 'tipo_nc', 'numero_doc_afectado', 'estado', 'total', 'empresa']
    list_filter = ['estado', 'tipo_nc', 'tipo_doc_afectado', 'empresa', 'fecha']
    search_fields = ['numero', 'cliente__nombre', 'cliente__rut', 'numero_doc_afectado', 'motivo']
    ordering = ['-fecha', '-numero']
    date_hierarchy = 'fecha'
    inlines = [NotaCreditoDetalleInline]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'sucursal', 'numero', 'fecha', 'cliente', 'vendedor', 'bodega', 'usuario_creacion')
        }),
        ('Tipo de Nota de Crédito', {
            'fields': ('tipo_nc',)
        }),
        ('Documento Afectado', {
            'fields': ('tipo_doc_afectado', 'numero_doc_afectado', 'fecha_doc_afectado', 'motivo')
        }),
        ('Montos', {
            'fields': ('subtotal', 'descuento', 'iva', 'total')
        }),
        ('Estado', {
            'fields': ('estado', 'dte')
        }),
    )
    
    readonly_fields = ['usuario_creacion', 'fecha_creacion', 'fecha_modificacion']


@admin.register(NotaCreditoDetalle)
class NotaCreditoDetalleAdmin(admin.ModelAdmin):
    list_display = ['nota_credito', 'articulo', 'codigo', 'cantidad', 'precio_unitario', 'descuento', 'total']
    list_filter = ['nota_credito__empresa']
    search_fields = ['nota_credito__numero', 'articulo__nombre', 'articulo__codigo', 'codigo']
    ordering = ['-fecha_creacion']
