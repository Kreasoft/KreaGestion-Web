from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('caja', '0007_codigovinculoimpresion'),
    ]

    operations = [
        migrations.AddField(
            model_name='caja',
            name='agente_ultimo_ping',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Último ping del agente de impresión',
            ),
        ),
    ]
