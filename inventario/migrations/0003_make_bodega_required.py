from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0002_auto_20250927_2247"),
        ("bodegas", "0001_initial"),
    ]

    operations = [
        # Hacer que bodega sea obligatorio (no nullable)
        migrations.AlterField(
            model_name='stock',
            name='bodega',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, 
                related_name='stocks',
                to='bodegas.bodega'
            ),
        ),
    ]
