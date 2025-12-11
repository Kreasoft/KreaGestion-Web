"""
Script para recuperar o restablecer credenciales de usuario
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestioncloud.settings')

try:
    django.setup()
except Exception as e:
    print(f"Error al configurar Django: {e}")
    sys.exit(1)

from django.contrib.auth.models import User
from empresas.models import Empresa

def listar_usuarios():
    """Lista todos los usuarios del sistema"""
    print("\n" + "="*60)
    print("USUARIOS EN EL SISTEMA")
    print("="*60)
    
    usuarios = User.objects.all().order_by('username')
    
    if not usuarios.exists():
        print("No hay usuarios en el sistema.")
        return
    
    for u in usuarios:
        superuser = "SI" if u.is_superuser else "NO"
        activo = "SI" if u.is_active else "NO"
        email = u.email if u.email else "Sin email"
        nombre = f"{u.first_name} {u.last_name}".strip() or "Sin nombre"
        
        print(f"\nUsuario: {u.username}")
        print(f"  Nombre: {nombre}")
        print(f"  Email: {email}")
        print(f"  Superusuario: {superuser}")
        print(f"  Activo: {activo}")
        
        # Mostrar empresa si tiene perfil
        if hasattr(u, 'perfil'):
            print(f"  Empresa: {u.perfil.empresa.nombre}")
    
    print("\n" + "="*60)

def crear_usuario_admin():
    """Crea o restablece un usuario admin con contraseña conocida"""
    print("\n" + "="*60)
    print("CREAR/RESTABLECER USUARIO ADMIN")
    print("="*60)
    
    username = 'admin'
    password = 'admin123'
    
    # Obtener o crear empresa
    empresa = Empresa.objects.first()
    
    if User.objects.filter(username=username).exists():
        user = User.objects.get(username=username)
        user.set_password(password)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()
        print(f"\n[OK] Usuario '{username}' actualizado!")
        print(f"     Contrasena restablecida a: {password}")
    else:
        user = User.objects.create_user(
            username=username,
            email='admin@gestioncloud.cl',
            password=password,
            first_name='Administrador',
            last_name='Sistema',
            is_superuser=True,
            is_staff=True,
            is_active=True
        )
        print(f"\n[OK] Usuario '{username}' creado exitosamente!")
    
    print(f"\n" + "="*60)
    print("CREDENCIALES DE ACCESO:")
    print("="*60)
    print(f"  Usuario: {username}")
    print(f"  Contrasena: {password}")
    if empresa:
        print(f"  Empresa: {empresa.nombre}")
    print("="*60)

if __name__ == '__main__':
    import sys
    
    print("\n" + "="*60)
    print("RECUPERACION DE CREDENCIALES - GestionCloud")
    print("="*60)
    
    # Primero listar usuarios existentes
    listar_usuarios()
    
    # Crear/restablecer usuario admin automáticamente
    print("\n\nCreando/restableciendo usuario admin...")
    crear_usuario_admin()

