from django.contrib import admin
from django.utils.html import format_html
from .models import DocumentoCompra, ItemDocumentoCompra, HistorialPagoDocumento, FormaPagoPago


class ItemDocumentoCompraInline(admin.TabularInline):
    model = ItemDocumentoCompra
    extra = 1
    fields = ['articulo', 'cantidad', 'precio_unitario', 'descuento_porcentaje', 'impuesto_porcentaje', 'total_item']
    readonly_fields = ['total_item']


class FormaPagoPagoInline(admin.TabularInline):
    model = FormaPagoPago
    extra = 0
    fields = ['forma_pago', 'monto', 'numero_cheque', 'banco_cheque', 'numero_transferencia', 'banco_transferencia']


class HistorialPagoDocumentoInline(admin.TabularInline):
    model = HistorialPagoDocumento
    extra = 0
    fields = ['fecha_pago', 'monto_total_pagado', 'observaciones', 'registrado_por']
    readonly_fields = ['registrado_por']
    inlines = [FormaPagoPagoInline]


@admin.register(DocumentoCompra)
class DocumentoCompraAdmin(admin.ModelAdmin):
    list_display = [
        'numero_documento', 'tipo_documento', 'proveedor', 'fecha_emision', 
        'estado_documento', 'estado_pago', 'total_documento', 'saldo_pendiente'
    ]
    list_filter = [
        'tipo_documento', 'estado_documento', 'estado_pago', 
        'fecha_emision', 'empresa', 'en_cuenta_corriente'
    ]
    search_fields = [
        'numero_documento', 'proveedor__nombre', 'observaciones'
    ]
    readonly_fields = [
        'subtotal', 'descuentos_totales', 'impuestos_totales', 'total_documento',
        'saldo_pendiente', 'creado_por', 'fecha_creacion', 'fecha_modificacion',
        'fecha_registro_cc'
    ]
    
    fieldsets = (
        ('Información del Documento', {
            'fields': (
                'empresa', 'proveedor', 'bodega',
                'tipo_documento', 'numero_documento'
            )
        }),
        ('Fechas', {
            'fields': ('fecha_emision', 'fecha_vencimiento')
        }),
        ('Estados', {
            'fields': ('estado_documento', 'estado_pago')
        }),
        ('Totales', {
            'fields': (
                'subtotal', 'descuentos_totales', 'impuestos_totales', 
                'total_documento', 'monto_pagado', 'saldo_pendiente'
            ),
            'classes': ('collapse',)
        }),
        ('Cuenta Corriente', {
            'fields': ('en_cuenta_corriente', 'fecha_registro_cc'),
            'classes': ('collapse',)
        }),
        ('Información Adicional', {
            'fields': ('observaciones', 'archivo_documento'),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('creado_por', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [ItemDocumentoCompraInline, HistorialPagoDocumentoInline]
    
    def save_model(self, request, obj, form, change):
        if not change:  # Es un nuevo objeto
            obj.creado_por = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        try:
            return queryset.filter(empresa=request.user.perfil.empresa)
        except:
            return queryset.none()


@admin.register(ItemDocumentoCompra)
class ItemDocumentoCompraAdmin(admin.ModelAdmin):
    list_display = [
        'documento_compra', 'articulo', 
        'cantidad', 'precio_unitario', 'total_item'
    ]
    list_filter = ['documento_compra__tipo_documento', 'documento_compra__empresa']
    search_fields = ['articulo__nombre', 'articulo__codigo', 'documento_compra__numero_documento']
    readonly_fields = ['subtotal', 'descuento_monto', 'impuesto_monto', 'total_item']
    
    fieldsets = (
        ('Información del Item', {
            'fields': ('documento_compra', 'articulo')
        }),
        ('Cantidades y Precios', {
            'fields': ('cantidad', 'precio_unitario')
        }),
        ('Descuentos e Impuestos', {
            'fields': ('descuento_porcentaje', 'impuesto_porcentaje')
        }),
        ('Totales', {
            'fields': ('subtotal', 'descuento_monto', 'impuesto_monto', 'total_item'),
            'classes': ('collapse',)
        }),
    )


@admin.register(HistorialPagoDocumento)
class HistorialPagoDocumentoAdmin(admin.ModelAdmin):
    list_display = [
        'documento_compra', 'fecha_pago', 'monto_total_pagado', 
        'registrado_por'
    ]
    list_filter = [
        'fecha_pago', 'documento_compra__empresa'
    ]
    search_fields = [
        'documento_compra__numero_documento', 'observaciones'
    ]
    readonly_fields = ['registrado_por']
    inlines = [FormaPagoPagoInline]
    
    fieldsets = (
        ('Información del Pago', {
            'fields': ('documento_compra', 'fecha_pago', 'monto_total_pagado')
        }),
        ('Información Adicional', {
            'fields': ('observaciones', 'registrado_por')
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Es un nuevo objeto
            obj.registrado_por = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        try:
            return queryset.filter(documento_compra__empresa=request.user.perfil.empresa)
        except:
            return queryset.none()


@admin.register(FormaPagoPago)
class FormaPagoPagoAdmin(admin.ModelAdmin):
    list_display = [
        'pago', 'forma_pago', 'monto', 'numero_cheque', 
        'banco_cheque', 'numero_transferencia'
    ]
    list_filter = [
        'forma_pago', 'pago__documento_compra__empresa'
    ]
    search_fields = [
        'pago__documento_compra__numero_documento', 
        'numero_cheque', 'numero_transferencia', 'numero_tarjeta'
    ]
    
    fieldsets = (
        ('Información de la Forma de Pago', {
            'fields': ('pago', 'forma_pago', 'monto')
        }),
        ('Información de Cheque', {
            'fields': ('numero_cheque', 'banco_cheque', 'fecha_vencimiento_cheque'),
            'classes': ('collapse',)
        }),
        ('Información de Transferencia', {
            'fields': ('numero_transferencia', 'banco_transferencia'),
            'classes': ('collapse',)
        }),
        ('Información de Tarjeta', {
            'fields': ('numero_tarjeta', 'codigo_autorizacion'),
            'classes': ('collapse',)
        }),
        ('Información Adicional', {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        try:
            return queryset.filter(pago__documento_compra__empresa=request.user.perfil.empresa)
        except:
            return queryset.none()