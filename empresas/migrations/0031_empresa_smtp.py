from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0030_remove_empresa_api_key_remove_empresa_api_url_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='smtp_host',
            field=models.CharField(
                blank=True,
                default='smtp.gmail.com',
                help_text='Ej: smtp.gmail.com',
                max_length=120,
                verbose_name='Servidor SMTP',
            ),
        ),
        migrations.AddField(
            model_name='empresa',
            name='smtp_puerto',
            field=models.PositiveIntegerField(default=587, verbose_name='Puerto SMTP'),
        ),
        migrations.AddField(
            model_name='empresa',
            name='smtp_usuario',
            field=models.CharField(
                blank=True,
                help_text='Normalmente el mismo Gmail que envía los documentos',
                max_length=120,
                verbose_name='Usuario SMTP',
            ),
        ),
        migrations.AddField(
            model_name='empresa',
            name='smtp_password',
            field=models.CharField(
                blank=True,
                help_text='Gmail: use una contraseña de aplicación, no la clave de la cuenta',
                max_length=200,
                verbose_name='Contraseña SMTP',
            ),
        ),
        migrations.AddField(
            model_name='empresa',
            name='smtp_usar_tls',
            field=models.BooleanField(default=True, verbose_name='SMTP usa TLS'),
        ),
    ]
