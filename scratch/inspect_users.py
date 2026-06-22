import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.contrib.auth.models import User
from usuarios.models import PerfilUsuario

print("=== USUARIOS VENDEDORES ===")
vendedores = User.objects.filter(perfil__tipo_usuario='vendedor')
for u in vendedores:
    print(f"\nUsuario: {u.username} (Superuser: {u.is_superuser}, Staff: {u.is_staff}, Activo: {u.is_active})")
    print(f"Empresa: {u.perfil.empresa.nombre}")
    
    # Comprobar permisos individuales
    print("Permisos directos:")
    for p in u.user_permissions.all():
        print(f"  - {p.content_type.app_label}.{p.codename}")
        
    print("Grupos:")
    for g in u.groups.all():
        print(f"  - {g.name}")
        
    # Comprobar si has_perm de compras es True
    print("Comprobaciones has_perm:")
    print(f"  perms.compras.view_ordencompra: {u.has_perm('compras.view_ordencompra')}")
    print(f"  perms.proveedores.view_proveedor: {u.has_perm('proveedores.view_proveedor')}")
    print(f"  perms.documentos.view_documento: {u.has_perm('documentos.view_documento')}")
