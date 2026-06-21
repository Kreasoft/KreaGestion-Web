from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("empresas", "0028_plansaas_empresa_auto_suspender_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="empresa",
            name="venta_movil_permite_sin_stock",
            field=models.BooleanField(
                default=True,
                help_text="Permite que la app móvil agregue y sincronice artículos sin stock disponible.",
                verbose_name="Ventas Móviles Permiten Sin Stock",
            ),
        ),
    ]
