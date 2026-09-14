from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pedidos', '0018_ordendespacho_bodega_ordendespacho_fecha_vencimiento_and_more')]
    operations = [migrations.AddField(
        model_name='ordendespacho', name='solicitud_id',
        field=models.UUIDField(null=True, blank=True, unique=True, editable=False),
    )]
