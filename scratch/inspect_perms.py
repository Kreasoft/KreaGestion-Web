import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.contrib.auth.models import Permission

print("=== TODOS LOS PERMISOS DE LA APP DOCUMENTOS ===")
for p in Permission.objects.filter(content_type__app_label='documentos'):
    print(f"  - {p.content_type.app_label}.{p.codename} | {p.name}")

print("\n=== TODOS LOS PERMISOS QUE CONTIENEN 'documento' ===")
for p in Permission.objects.filter(codename__icontains='documento'):
    print(f"  - {p.content_type.app_label}.{p.codename} | {p.name}")
