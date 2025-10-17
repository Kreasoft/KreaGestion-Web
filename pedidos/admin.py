from django.contrib import admin
from .models import OrdenPedido, ItemOrdenPedido


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
