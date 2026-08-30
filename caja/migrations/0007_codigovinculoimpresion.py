from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('empresas', '0030_remove_empresa_api_key_remove_empresa_api_url_and_more'),
        ('caja', '0006_alter_colaimpresion_estado'),
    ]

    operations = [
        migrations.CreateModel(
            name='CodigoVinculoImpresion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=8, unique=True)),
                ('api_base_url', models.CharField(max_length=300)),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True)),
                ('fecha_expiracion', models.DateTimeField()),
                ('caja', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='caja.caja')),
                ('creado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user')),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='empresas.empresa')),
                ('sucursal', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='empresas.sucursal')),
            ],
            options={
                'verbose_name': 'Código de vinculación de impresora',
                'verbose_name_plural': 'Códigos de vinculación de impresora',
                'ordering': ['-fecha_creacion'],
            },
        ),
    ]
