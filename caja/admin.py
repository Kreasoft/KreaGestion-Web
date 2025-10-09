from django.contrib import admin
from .models import Caja, AperturaCaja, MovimientoCaja, VentaProcesada


@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'nombre', 'empresa', 'sucursal', 'estacion_trabajo', 'activo')
    list_filter = ('empresa', 'activo')
    search_fields = ('numero', 'nombre')


@admin.register(AperturaCaja)
class AperturaCajaAdmin(admin.ModelAdmin):
    list_display = ('caja', 'fecha_apertura', 'fecha_cierre', 'estado', 'usuario_apertura', 'monto_inicial', 'monto_final')
    list_filter = ('estado', 'fecha_apertura')
    search_fields = ('caja__nombre', 'usuario_apertura__username')
    readonly_fields = ('total_ventas_efectivo', 'total_ventas_tarjeta', 'total_ventas_transferencia', 'total_ventas_cheque', 'total_ventas_credito')


@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(admin.ModelAdmin):
    list_display = ('apertura_caja', 'tipo', 'fecha', 'monto', 'forma_pago', 'usuario')
    list_filter = ('tipo', 'fecha', 'forma_pago')
    search_fields = ('descripcion', 'usuario__username')


@admin.register(VentaProcesada)
class VentaProcesadaAdmin(admin.ModelAdmin):
    list_display = ('venta_preventa', 'venta_final', 'fecha_proceso', 'usuario_proceso', 'stock_descontado', 'cuenta_corriente_actualizada')
    list_filter = ('fecha_proceso', 'stock_descontado', 'cuenta_corriente_actualizada')
    search_fields = ('venta_preventa__numero_venta', 'venta_final__numero_venta')
    readonly_fields = ('fecha_proceso',)
