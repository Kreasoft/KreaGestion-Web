from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proveedores', '0003_alter_proveedor_region'),
    ]

    operations = [
        migrations.AddField(
            model_name='proveedor',
            name='plazo_pago',
            field=models.IntegerField(
                default=0,
                help_text='Días de crédito. 0 = vence el mismo día de emisión de la factura.',
                verbose_name='Plazo de Pago (días)',
            ),
        ),
    ]
