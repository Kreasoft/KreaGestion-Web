from django.db import migrations


def backfill_archivocaf_ambiente(apps, schema_editor):
    ArchivoCAF = apps.get_model("facturacion_electronica", "ArchivoCAF")

    for caf in ArchivoCAF.objects.select_related("empresa").all():
        ambiente_empresa = getattr(caf.empresa, "ambiente_sii", None) or "certificacion"
        if caf.ambiente != ambiente_empresa:
            caf.ambiente = ambiente_empresa
            caf.save(update_fields=["ambiente"])


class Migration(migrations.Migration):

    dependencies = [
        ("facturacion_electronica", "0016_remove_archivocaf_facturacion_empresa_bf9045_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill_archivocaf_ambiente, migrations.RunPython.noop),
    ]
