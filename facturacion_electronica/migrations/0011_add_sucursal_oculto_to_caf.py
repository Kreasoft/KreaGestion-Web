# Generated manually - Simplified version
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0001_initial'),
        ('facturacion_electronica', '0010_documentotributarioelectronico_fecha'),
    ]

    operations = [
        # Agregar campo oculto primero (más simple)
        migrations.AddField(
            model_name='archivocaf',
            name='oculto',
            field=models.BooleanField(
                default=False, 
                help_text='Si está marcado, el CAF no se mostrará en listados principales', 
                verbose_name='Oculto'
            ),
        ),
        # Agregar campo sucursal como nullable temporalmente
        migrations.AddField(
            model_name='archivocaf',
            name='sucursal',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='archivos_caf',
                to='empresas.sucursal',
                verbose_name='Sucursal',
                help_text='Sucursal a la que pertenece este CAF'
            ),
        ),
    ]
