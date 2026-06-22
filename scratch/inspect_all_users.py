import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.contrib.auth.models import User

for u in User.objects.all():
    print(f"Usuario: {u.username} (Superuser: {u.is_superuser}, Staff: {u.is_staff}, Activo: {u.is_active})")
    print(f"Grupos: {[g.name for g in u.groups.all()]}")
    print("Permisos evaluados:")
    print(f"  perms.compras.view_ordencompra: {u.has_perm('compras.view_ordencompra')}")
    print(f"  perms.proveedores.view_proveedor: {u.has_perm('proveedores.view_proveedor')}")
    print(f"  perms.documentos.view_documentocompra: {u.has_perm('documentos.view_documentocompra')}")
    print(f"  perms.caja.view_caja: {u.has_perm('caja.view_caja')}")
    print(f"  perms.caja.view_aperturacaja: {u.has_perm('caja.view_aperturacaja')}")
    print("-" * 50)
