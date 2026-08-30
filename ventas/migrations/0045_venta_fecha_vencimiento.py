from datetime import timedelta

from django.db import migrations, models


def backfill_fecha_vencimiento(apps, schema_editor):
    Venta = apps.get_model('ventas', 'Venta')
    batch = []
    qs = Venta.objects.filter(fecha_vencimiento__isnull=True).select_related('cliente')
    for venta in qs.iterator(chunk_size=500):
        dias = 0
        if venta.cliente_id:
            dias = int(getattr(venta.cliente, 'plazo_pago', 0) or 0)
            if dias < 0:
                dias = 0
        if not venta.fecha:
            continue
        venta.fecha_vencimiento = venta.fecha + timedelta(days=dias) if dias else venta.fecha
        batch.append(venta)
        if len(batch) >= 500:
            Venta.objects.bulk_update(batch, ['fecha_vencimiento'])
            batch = []
    if batch:
        Venta.objects.bulk_update(batch, ['fecha_vencimiento'])


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0044_ind_traslado_sii_catalogo'),
    ]

    operations = [
        migrations.AddField(
            model_name='venta',
            name='fecha_vencimiento',
            field=models.DateField(
                blank=True,
                help_text='Se calcula con los días de pago del cliente. Sin plazo, vence el mismo día de emisión.',
                null=True,
                verbose_name='Fecha de Vencimiento',
            ),
        ),
        migrations.RunPython(backfill_fecha_vencimiento, migrations.RunPython.noop),
    ]
