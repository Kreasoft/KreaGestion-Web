from django.contrib import admin
from .models import CuentaCorrienteProveedor, MovimientoCuentaCorriente, CuentaCorrienteCliente, MovimientoCuentaCorrienteCliente, DocumentoCliente, PagoDocumentoCliente


@admin.register(CuentaCorrienteCliente)
class CuentaCorrienteClienteAdmin(admin.ModelAdmin):
    list_display = [
        'cliente',
        'empresa',
        'saldo_total',
        'saldo_pendiente',
        'saldo_vencido',
        'limite_credito',
        'dias_credito'
    ]
    list_filter = ['empresa', 'cliente']
    search_fields = ['cliente__nombre', 'cliente__rut', 'empresa__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']

    fieldsets = (
        ('Información General', {
            'fields': ('empresa', 'cliente', 'limite_credito', 'dias_credito')
        }),
        ('Saldos', {
            'fields': ('saldo_total', 'saldo_pendiente', 'saldo_vencido')
        }),
        ('Auditoría', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )

    def calcular_saldos_action(self, request, queryset):
        for cuenta in queryset:
            cuenta.calcular_saldos()
        self.message_user(request, f"Se recalcularon los saldos de {queryset.count()} cuentas corrientes.")

    actions = [calcular_saldos_action]


@admin.register(MovimientoCuentaCorrienteCliente)
class MovimientoCuentaCorrienteClienteAdmin(admin.ModelAdmin):
    list_display = [
        'cuenta_corriente',
        'tipo_movimiento',
        'monto',
        'fecha_movimiento',
        'estado',
        'registrado_por'
    ]
    list_filter = ['tipo_movimiento', 'estado', 'fecha_movimiento', 'cuenta_corriente__empresa']
    search_fields = ['cuenta_corriente__cliente__nombre', 'observaciones']
    readonly_fields = ['fecha_movimiento', 'saldo_anterior', 'saldo_nuevo']

    fieldsets = (
        ('Información General', {
            'fields': ('cuenta_corriente', 'venta', 'tipo_movimiento', 'monto', 'estado')
        }),
        ('Saldos', {
            'fields': ('saldo_anterior', 'saldo_nuevo')
        }),
        ('Observaciones', {
            'fields': ('observaciones',)
        }),
        ('Auditoría', {
            'fields': ('fecha_movimiento', 'registrado_por'),
            'classes': ('collapse',)
        }),
    )


@admin.register(CuentaCorrienteProveedor)
class CuentaCorrienteProveedorAdmin(admin.ModelAdmin):
    list_display = [
        'proveedor',
        'empresa',
        'saldo_total',
        'saldo_pendiente',
        'saldo_vencido'
    ]
    list_filter = ['empresa', 'proveedor']
    search_fields = ['proveedor__nombre', 'proveedor__rut', 'empresa__nombre']
    readonly_fields = ['fecha_creacion', 'fecha_modificacion']

    fieldsets = (
        ('Información General', {
            'fields': ('empresa', 'proveedor')
        }),
        ('Saldos', {
            'fields': ('saldo_total', 'saldo_pendiente', 'saldo_vencido')
        }),
        ('Auditoría', {
            'fields': ('fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MovimientoCuentaCorriente)
class MovimientoCuentaCorrienteAdmin(admin.ModelAdmin):
    list_display = [
        'cuenta_corriente',
        'tipo_movimiento',
        'monto',
        'fecha_movimiento',
        'estado',
        'registrado_por'
    ]
    list_filter = ['tipo_movimiento', 'estado', 'fecha_movimiento', 'cuenta_corriente__empresa']
    search_fields = ['cuenta_corriente__proveedor__nombre', 'observaciones']
    readonly_fields = ['fecha_movimiento', 'saldo_anterior', 'saldo_nuevo']

    fieldsets = (
        ('Información General', {
            'fields': ('cuenta_corriente', 'documento_compra', 'tipo_movimiento', 'monto', 'estado')
        }),
        ('Saldos', {
            'fields': ('saldo_anterior', 'saldo_nuevo')
        }),
        ('Observaciones', {
            'fields': ('observaciones',)
        }),
        ('Auditoría', {
            'fields': ('fecha_movimiento', 'registrado_por'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DocumentoCliente)
class DocumentoClienteAdmin(admin.ModelAdmin):
    list_display = [
        'numero_documento',
        'tipo_documento',
        'cliente',
        'empresa',
        'fecha_emision',
        'total',
        'saldo_pendiente',
        'estado_pago'
    ]
    list_filter = ['tipo_documento', 'estado_pago', 'empresa', 'fecha_emision']
    search_fields = ['numero_documento', 'cliente__nombre', 'cliente__rut']
    readonly_fields = ['creado_por', 'fecha_creacion', 'fecha_modificacion']
    
    fieldsets = (
        ('Información del Documento', {
            'fields': ('empresa', 'cliente', 'tipo_documento', 'numero_documento', 'fecha_emision', 'fecha_vencimiento')
        }),
        ('Montos', {
            'fields': ('total', 'monto_pagado', 'saldo_pendiente', 'estado_pago')
        }),
        ('Información Adicional', {
            'fields': ('observaciones',)
        }),
        ('Auditoría', {
            'fields': ('creado_por', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PagoDocumentoCliente)
class PagoDocumentoClienteAdmin(admin.ModelAdmin):
    list_display = [
        'documento',
        'fecha_pago',
        'monto',
        'forma_pago',
        'registrado_por'
    ]
    list_filter = ['fecha_pago', 'forma_pago', 'documento__empresa']
    search_fields = ['documento__numero_documento', 'documento__cliente__nombre', 'observaciones']
    readonly_fields = ['fecha_creacion', 'registrado_por']
    
    fieldsets = (
        ('Información del Pago', {
            'fields': ('documento', 'fecha_pago', 'monto', 'forma_pago')
        }),
        ('Observaciones', {
            'fields': ('observaciones',)
        }),
        ('Auditoría', {
            'fields': ('registrado_por', 'fecha_creacion'),
            'classes': ('collapse',)
        }),
    )
