from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0017_alter_notacredito_unique_together_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='estaciontrabajo',
            name='cierre_directo',
            field=models.BooleanField(default=False, verbose_name='Cierre directo (Cerrar y Emitir DTE)'),
        ),
        migrations.AddField(
            model_name='estaciontrabajo',
            name='flujo_cierre_directo',
            field=models.CharField(
                default='rut_final',
                max_length=20,
                choices=[('rut_inicio', 'RUT al inicio'), ('rut_final', 'RUT al final')],
                verbose_name='Flujo para cierre directo',
            ),
        ),
        migrations.AddField(
            model_name='estaciontrabajo',
            name='enviar_sii_directo',
            field=models.BooleanField(default=True, verbose_name='Enviar al SII automáticamente'),
        ),
    ]
