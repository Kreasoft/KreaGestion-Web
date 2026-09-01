from django.db import migrations


class Migration(migrations.Migration):
    """Une 0008 (ping del agente) y 0009 (impresoras / nombre cola)."""

    dependencies = [
        ("caja", "0008_caja_agente_ultimo_ping"),
        ("caja", "0009_impresoraagente_colaimpresion_nombre"),
    ]

    operations = []
