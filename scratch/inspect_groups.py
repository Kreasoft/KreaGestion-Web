import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.contrib.auth.models import Group

for g in Group.objects.all():
    if 'vendedor' in g.name.lower():
        print(f"\nGrupo: {g.name} (ID: {g.id})")
        compras_perms = g.permissions.filter(content_type__app_label__in=['compras', 'documentos', 'proveedores'])
        print(f"Permisos de Compras/Documentos/Proveedores en el grupo (Total: {compras_perms.count()}):")
        for p in compras_perms:
            print(f"  - {p.content_type.app_label}.{p.codename} | {p.name}")
        
        other_perms = g.permissions.exclude(content_type__app_label__in=['compras', 'documentos', 'proveedores'])
        print(f"Otros permisos en el grupo (Total: {other_perms.count()}):")
