from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventas", "0039_remove_ventadetalle_descripcion"),
    ]

    operations = [
        migrations.AddField(
            model_name="ventadetalle",
            name="comentario",
            field=models.TextField(blank=True, verbose_name="Comentario"),
        ),
    ]
