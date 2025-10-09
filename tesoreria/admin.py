from django.contrib import admin
from .models import CuentaCorrienteProveedor, MovimientoCuentaCorriente, CuentaCorrienteCliente, MovimientoCuentaCorrienteCliente


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
