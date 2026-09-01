from django.db import migrations


class Migration(migrations.Migration):
    """Une las ramas 0046 (celular app) y 0049 (impresora vales)."""

    dependencies = [
        ("ventas", "0046_vendedor_telefono_app"),
        ("ventas", "0049_estaciontrabajo_impresora_vales"),
    ]

    operations = []
