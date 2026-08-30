from datetime import timedelta

from django.db import migrations


def backfill_fecha_vencimiento(apps, schema_editor):
    DocumentoCompra = apps.get_model('documentos', 'DocumentoCompra')
    batch = []
    qs = DocumentoCompra.objects.filter(fecha_vencimiento__isnull=True).select_related('proveedor')
    for doc in qs.iterator(chunk_size=500):
        dias = 0
        if doc.proveedor_id:
            dias = int(getattr(doc.proveedor, 'plazo_pago', 0) or 0)
            if dias < 0:
                dias = 0
        if not doc.fecha_emision:
            continue
        doc.fecha_vencimiento = doc.fecha_emision + timedelta(days=dias) if dias else doc.fecha_emision
        batch.append(doc)
        if len(batch) >= 500:
            DocumentoCompra.objects.bulk_update(batch, ['fecha_vencimiento'])
            batch = []
    if batch:
        DocumentoCompra.objects.bulk_update(batch, ['fecha_vencimiento'])


class Migration(migrations.Migration):

    dependencies = [
        ('documentos', '0011_alter_documentocompra_unique_together'),
        ('proveedores', '0004_proveedor_plazo_pago'),
    ]

    operations = [
        migrations.RunPython(backfill_fecha_vencimiento, migrations.RunPython.noop),
    ]
