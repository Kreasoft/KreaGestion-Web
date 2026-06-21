from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventas", "0037_estaciontrabajo_copias_notacredito"),
    ]

    operations = [
        migrations.AddField(
            model_name="ventadetalle",
            name="descripcion",
            field=models.TextField(blank=True, verbose_name="Descripcion extendida"),
        ),
    ]
