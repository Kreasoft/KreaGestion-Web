from django.db import migrations
from decimal import Decimal


def recalcular_totales_ordenes_pedido(apps, schema_editor):
    OrdenPedido = apps.get_model('pedidos', 'OrdenPedido')
    ItemOrdenPedido = apps.get_model('pedidos', 'ItemOrdenPedido')

    for pedido in OrdenPedido.objects.all():
        items = ItemOrdenPedido.objects.filter(orden_pedido=pedido)
        if not items.exists():
            continue

        subtotal = 0
        descuentos_totales = 0
        impuestos_totales = 0

        for item in items:
            item_subtotal = int(Decimal(str(item.cantidad)) * Decimal(str(item.precio_unitario)))
            desc_pct = item.descuento_porcentaje if item.descuento_porcentaje is not None else Decimal('0')
            item_desc = int(item_subtotal * Decimal(str(desc_pct)) / Decimal('100'))
            base_imponible = item_subtotal - item_desc
            imp_pct = item.impuesto_porcentaje if item.impuesto_porcentaje is not None else Decimal('19')
            item_imp = int(base_imponible * Decimal(str(imp_pct)) / Decimal('100'))

            subtotal += item_subtotal
            descuentos_totales += item_desc
            impuestos_totales += item_imp

        total_pedido = subtotal - descuentos_totales + impuestos_totales

        OrdenPedido.objects.filter(pk=pedido.pk).update(
            subtotal=subtotal,
            descuentos_totales=descuentos_totales,
            impuestos_totales=impuestos_totales,
            total_pedido=total_pedido,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0022_ordendespacho_ciudad_entrega_and_more'),
    ]

    operations = [
        migrations.RunPython(recalcular_totales_ordenes_pedido, reverse_code=migrations.RunPython.noop),
    ]
