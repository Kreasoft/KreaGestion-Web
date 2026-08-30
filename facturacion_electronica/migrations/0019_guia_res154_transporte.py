from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("facturacion_electronica", "0018_ind_traslado_sii_catalogo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documentotributarioelectronico",
            name="tipo_traslado",
            field=models.CharField(
                blank=True,
                choices=[
                    ("1", "1 - Operación constituye venta"),
                    ("2", "2 - Ventas por efectuar"),
                    ("3", "3 - Consignaciones"),
                    ("4", "4 - Entrega gratuita"),
                    ("5", "5 - Traslados internos"),
                    ("6", "6 - Otros traslados no venta"),
                    ("7", "7 - Devolución de Mercaderías"),
                    ("8", "8 - Traslado para exportación"),
                    ("9", "9 - Ventas para exportación"),
                ],
                help_text="Motivo de emisión de la guía (solo para tipo 52)",
                max_length=2,
                null=True,
                verbose_name="Tipo de Traslado",
            ),
        ),
        migrations.AddField(
            model_name="documentotributarioelectronico",
            name="tipo_despacho_sii",
            field=models.CharField(
                blank=True,
                choices=[
                    ("1", "1 - Por cuenta del receptor"),
                    ("2", "2 - Por cuenta del emisor al cliente"),
                    ("3", "3 - Por cuenta del emisor a otras instalaciones"),
                ],
                help_text="TipoDespacho 1/2/3. Distinto de IndTraslado.",
                max_length=1,
                null=True,
                verbose_name="Tipo de Despacho SII",
            ),
        ),
        migrations.AddField(
            model_name="documentotributarioelectronico",
            name="patente_carro",
            field=models.CharField(
                blank=True,
                max_length=8,
                null=True,
                verbose_name="Patente carro o remolque",
            ),
        ),
        migrations.AddField(
            model_name="documentotributarioelectronico",
            name="fecha_salida",
            field=models.DateField(blank=True, null=True, verbose_name="Fecha de salida"),
        ),
        migrations.AddField(
            model_name="documentotributarioelectronico",
            name="hora_salida",
            field=models.TimeField(blank=True, null=True, verbose_name="Hora de salida"),
        ),
        migrations.AddField(
            model_name="documentotributarioelectronico",
            name="fecha_llegada",
            field=models.DateField(blank=True, null=True, verbose_name="Fecha de llegada"),
        ),
    ]
