from django.db import migrations

def sincronizar_permisos_admin(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    User = apps.get_model('auth', 'User')
    PerfilUsuario = apps.get_model('usuarios', 'PerfilUsuario')
    
    valid_apps = [
        'articulos', 'bodegas', 'caja', 'clientes', 'compras',
        'documentos', 'empresas', 'facturacion_electronica', 'informes',
        'inventario', 'pedidos', 'produccion', 'proveedores', 'tesoreria',
        'usuarios', 'utilidades', 'ventas', 'auth'
    ]
    
    admin_group = Group.objects.filter(name__iexact='administrador').first()
    if not admin_group:
        admin_group = Group.objects.filter(name__icontains='admin').first()
        
    if admin_group:
        perms = Permission.objects.filter(content_type__app_label__in=valid_apps)
        admin_group.permissions.set(perms)
        
    # Asegurar que todos los usuarios en grupos de administradores o con tipo_usuario='administrador' sean consistentes
    for u in User.objects.all():
        es_admin_grupo = u.groups.filter(name__icontains='admin').exists()
        perfil = PerfilUsuario.objects.filter(usuario=u).first()
        if es_admin_grupo or (perfil and perfil.tipo_usuario == 'administrador'):
            if not u.is_staff:
                u.is_staff = True
                u.save()
            if perfil and perfil.tipo_usuario != 'administrador':
                perfil.tipo_usuario = 'administrador'
                perfil.save()

def revertir_sincronizacion(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0002_perfilusuario_sucursal_perfilusuario_tipo_usuario'),
    ]

    operations = [
        migrations.RunPython(sincronizar_permisos_admin, revertir_sincronizacion),
    ]
