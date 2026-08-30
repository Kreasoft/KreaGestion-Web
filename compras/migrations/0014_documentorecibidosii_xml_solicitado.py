from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('compras', '0013_documentorecibidosii_estado_rcv_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='documentorecibidosii',
            name='xml_solicitado_a',
            field=models.EmailField(blank=True, max_length=254, verbose_name='XML solicitado a'),
        ),
        migrations.AddField(
            model_name='documentorecibidosii',
            name='xml_solicitado_en',
            field=models.DateTimeField(blank=True, null=True, verbose_name='XML solicitado el'),
        ),
    ]
