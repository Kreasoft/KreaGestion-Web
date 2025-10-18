from django.contrib import admin

from .models import Inventario, Stock, TransferenciaInventario


@admin.register(Inventario)
class InventarioAdmin(admin.ModelAdmin):
    list_display = (
        "fecha_movimiento",
        "articulo",
        "tipo_movimiento",
        "cantidad",
        "bodega_origen",
        "bodega_destino",
        "estado",
    )
    list_filter = (
        "tipo_movimiento",
        "estado",
        "bodega_origen",
        "bodega_destino",
        "fecha_movimiento",
    )
    search_fields = (
        "articulo__nombre",
        "articulo__codigo",
        "motivo",
        "descripcion",
        "numero_documento",
        "proveedor",
    )
    autocomplete_fields = ("articulo", "transferencia")
    raw_id_fields = ("bodega_origen", "bodega_destino")
    readonly_fields = ("total",)
    date_hierarchy = "fecha_movimiento"


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("bodega", "articulo", "cantidad", "stock_minimo", "stock_maximo", "precio_promedio")
    list_filter = ("bodega", "articulo")
    search_fields = ("articulo__nombre", "articulo__codigo", "bodega__nombre")
    raw_id_fields = ("bodega", "articulo")


@admin.register(TransferenciaInventario)
class TransferenciaInventarioAdmin(admin.ModelAdmin):
    list_display = ("numero_folio", "bodega_origen", "bodega_destino", "fecha_transferencia", "estado")
    list_filter = ("estado", "fecha_transferencia", "bodega_origen", "bodega_destino")
    search_fields = ("numero_folio", "bodega_origen__nombre", "bodega_destino__nombre")
    raw_id_fields = ("bodega_origen", "bodega_destino", "creado_por")
