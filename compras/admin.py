from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    OrdenCompra, ItemOrdenCompra, RecepcionMercancia, 
    ItemRecepcion
)


class ItemOrdenCompraInline(admin.TabularInline):
    model = ItemOrdenCompra
    extra = 0
    fields = ['articulo', 'cantidad_solicitada', 'precio_unitario', 'descuento_porcentaje', 'impuesto_porcentaje', 'total_item']
    readonly_fields = ['total_item']
    
    def total_item(self, obj):
        if obj.pk:
            return f"${obj.total_item:,.0f}"
        return "-"
    total_item.short_description = "Total Item"


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = [
        'numero_orden', 'proveedor', 'fecha_orden', 'estado_orden_badge', 
        'estado_pago_badge', 'prioridad_badge', 'total_formateado', 'fecha_creacion'
    ]
    list_filter = ['estado_orden', 'estado_pago', 'prioridad', 'fecha_orden', 'fecha_creacion']
    search_fields = ['numero_orden', 'proveedor__nombre', 'proveedor__rut']
    readonly_fields = [
        'numero_orden', 'subtotal', 'descuentos_totales', 'impuestos_totales', 'total_orden', 
        'fecha_creacion', 'fecha_modificacion', 'aprobado_por', 'fecha_aprobacion'
    ]
    inlines = [ItemOrdenCompraInline]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('empresa', 'sucursal', 'proveedor', 'bodega', 'numero_orden')
        }),
        ('Fechas', {
            'fields': ('fecha_orden', 'fecha_entrega_esperada', 'fecha_entrega_real')
        }),
        ('Estado y Prioridad', {
            'fields': ('estado_orden', 'estado_pago', 'prioridad')
        }),
        ('Condiciones', {
            'fields': ('condiciones_pago', 'plazo_entrega', 'observaciones')
        }),
        ('Totales', {
            'fields': ('subtotal', 'descuentos_totales', 'impuestos_totales', 'total_orden'),
            'classes': ('collapse',)
        }),
        ('Auditoría', {
            'fields': ('creado_por', 'aprobado_por', 'fecha_aprobacion', 'fecha_creacion', 'fecha_modificacion'),
            'classes': ('collapse',)
        }),
    )
    
    def estado_orden_badge(self, obj):
        colors = {
            'borrador': 'secondary',
            'pendiente_aprobacion': 'warning',
            'aprobada': 'info',
            'en_proceso': 'primary',
            'parcialmente_recibida': 'warning',
            'completamente_recibida': 'success',
            'cancelada': 'danger',
            'cerrada': 'dark',
        }
        color = colors.get(obj.estado_orden, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_estado_orden_display()
        )
    estado_orden_badge.short_description = 'Estado Orden'
    
    def estado_pago_badge(self, obj):
        colors = {
            'pagada': 'success',
            'credito': 'info',
            'parcial': 'warning',
            'vencida': 'danger',
        }
        color = colors.get(obj.estado_pago, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_estado_pago_display()
        )
    estado_pago_badge.short_description = 'Estado Pago'
    
    def prioridad_badge(self, obj):
        colors = {
            'baja': 'success',
            'normal': 'primary',
            'alta': 'warning',
            'urgente': 'danger',
        }
        color = colors.get(obj.prioridad, 'primary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_prioridad_display()
        )
    prioridad_badge.short_description = 'Prioridad'
    
    def total_formateado(self, obj):
        return f"${obj.total_orden:,.0f}"
    total_formateado.short_description = 'Total'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filtrar por empresa si no es superusuario
        empresa = request.session.get('empresa_activa')
        if empresa:
            return qs.filter(empresa=empresa)
        return qs.none()


class ItemRecepcionInline(admin.TabularInline):
    model = ItemRecepcion
    extra = 0
    fields = ['item_orden', 'cantidad_recibida', 'calidad_aceptable', 'observaciones_calidad']
    readonly_fields = ['item_orden']


@admin.register(RecepcionMercancia)
class RecepcionMercanciaAdmin(admin.ModelAdmin):
    list_display = [
        'numero_recepcion', 'orden_compra', 'fecha_recepcion', 
        'estado_badge', 'transportista', 'recibido_por'
    ]
    list_filter = ['estado', 'fecha_recepcion', 'fecha_creacion']
    search_fields = ['numero_recepcion', 'orden_compra__numero_orden', 'transportista']
    readonly_fields = ['numero_recepcion', 'fecha_creacion']
    inlines = [ItemRecepcionInline]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('orden_compra', 'numero_recepcion', 'fecha_recepcion')
        }),
        ('Estado', {
            'fields': ('estado',)
        }),
        ('Transporte', {
            'fields': ('transportista', 'numero_guia')
        }),
        ('Observaciones', {
            'fields': ('observaciones',)
        }),
        ('Auditoría', {
            'fields': ('recibido_por', 'revisado_por', 'fecha_revision', 'fecha_creacion'),
            'classes': ('collapse',)
        }),
    )
    
    def estado_badge(self, obj):
        colors = {
            'pendiente': 'warning',
            'en_revision': 'info',
            'aprobada': 'success',
            'rechazada': 'danger',
        }
        color = colors.get(obj.estado, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_estado_display()
        )
    estado_badge.short_description = 'Estado'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filtrar por empresa si no es superusuario
        empresa = request.session.get('empresa_activa')
        if empresa:
            return qs.filter(orden_compra__empresa=empresa)
        return qs.none()


# Configuración adicional
admin.site.site_header = "GestionCloud - Administración"
admin.site.site_title = "GestionCloud Admin"
admin.site.index_title = "Panel de Administración"