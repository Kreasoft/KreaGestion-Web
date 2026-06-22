import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')
django.setup()

from django.contrib.auth.models import User

print("=== STARTING USER PROFILE SYNCHRONIZATION ===")
for u in User.objects.all():
    if hasattr(u, 'perfil') and u.perfil:
        g = u.groups.first()
        if g:
            name_lower = g.name.lower()
            if 'administrador' in name_lower:
                tipo_usuario = 'administrador'
            elif 'cajero' in name_lower:
                tipo_usuario = 'cajero'
            else:
                tipo_usuario = 'vendedor'
        else:
            if u.is_superuser:
                tipo_usuario = 'administrador'
            else:
                tipo_usuario = 'vendedor'
        
        if u.perfil.tipo_usuario != tipo_usuario:
            print(f"Updating user '{u.username}': profile '{u.perfil.tipo_usuario}' -> '{tipo_usuario}'")
            u.perfil.tipo_usuario = tipo_usuario
            u.perfil.save()
        else:
            print(f"User '{u.username}' already in sync (profile: '{u.perfil.tipo_usuario}', group: '{g.name if g else 'None'}')")
print("=== SYNCHRONIZATION FINISHED ===")
