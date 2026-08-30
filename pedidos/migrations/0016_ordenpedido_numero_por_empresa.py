from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pedidos', '0015_alter_ordenpedido_unique_together_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ordenpedido',
            name='numero_pedido',
            field=models.CharField(max_length=20, verbose_name='Número de Pedido'),
        ),
        migrations.AddConstraint(
            model_name='ordenpedido',
            constraint=models.UniqueConstraint(
                fields=('empresa', 'numero_pedido'),
                name='pedido_numero_unico_por_empresa',
            ),
        ),
    ]
