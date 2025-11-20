"""
Script para gestionar credenciales de usuarios
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

def crear_superusuario():
    """Crea un nuevo superusuario"""
    print("\n" + "="*60)
    print("CREAR NUEVO SUPERUSUARIO")
    print("="*60)
    
    username = input("\nNombre de usuario: ").strip()
    
    if User.objects.filter(username=username).exists():
        print(f"El usuario '{username}' ya existe.")
        return
    
    email = input("Email (opcional): ").strip() or ""
    first_name = input("Nombre: ").strip() or ""
    last_name = input("Apellido: ").strip() or ""
    
    password = input("Contrasena: ").strip()
    if not password:
        print("La contrasena no puede estar vacia.")
        return
    
    confirm_password = input("Confirmar contrasena: ").strip()
    if password != confirm_password:
        print("Las contrasenas no coinciden.")
        return
    
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_superuser=True,
            is_staff=True,
            is_active=True
        )
        print(f"\nSuperusuario '{username}' creado exitosamente!")
        print(f"Puedes iniciar sesion con estas credenciales.")
    except Exception as e:
        print(f"\nError al crear usuario: {str(e)}")

def restablecer_password():
    """Restablece la contraseña de un usuario"""
    print("\n" + "="*60)
    print("RESTABLECER CONTRASEÑA")
    print("="*60)
    
    username = input("\nNombre de usuario: ").strip()
    
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        print(f"El usuario '{username}' no existe.")
        return
    
    print(f"\nUsuario encontrado: {user.username}")
    print(f"  Email: {user.email or 'Sin email'}")
    print(f"  Nombre: {user.first_name} {user.last_name}")
    
    password = input("\nNueva contrasena: ").strip()
    if not password:
        print("La contrasena no puede estar vacia.")
        return
    
    confirm_password = input("Confirmar contrasena: ").strip()
    if password != confirm_password:
        print("Las contrasenas no coinciden.")
        return
    
    user.set_password(password)
    user.save()
    
    print(f"\nContrasena restablecida exitosamente para '{username}'!")

def crear_usuario_demo():
    """Crea un usuario de demostración con credenciales conocidas"""
    print("\n" + "="*60)
    print("CREAR USUARIO DEMO")
    print("="*60)
    
    # Obtener o crear empresa
    empresa = Empresa.objects.first()
    if not empresa:
        print("No hay empresas en el sistema. Crea una empresa primero.")
        return
    
    username = 'admin'
    password = 'admin123'
    
    if User.objects.filter(username=username).exists():
        user = User.objects.get(username=username)
        user.set_password(password)
        user.is_superuser = True
        user.is_staff = True
        user.is_active = True
        user.save()
        print(f"\nUsuario '{username}' actualizado!")
        print(f"Contrasena restablecida a: {password}")
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
        print(f"\nUsuario demo creado exitosamente!")
    
    print(f"\nCREDENCIALES:")
    print(f"  Usuario: {username}")
    print(f"  Contrasena: {password}")
    print(f"  Empresa: {empresa.nombre}")

def main():
    """Menú principal"""
    while True:
        print("\n" + "="*60)
        print("GESTION DE CREDENCIALES - GestionCloud")
        print("="*60)
        print("\n1. Listar usuarios")
        print("2. Crear superusuario")
        print("3. Restablecer contrasena")
        print("4. Crear usuario demo (admin/admin123)")
        print("5. Salir")
        
        opcion = input("\nSelecciona una opcion (1-5): ").strip()
        
        if opcion == '1':
            listar_usuarios()
        elif opcion == '2':
            crear_superusuario()
        elif opcion == '3':
            restablecer_password()
        elif opcion == '4':
            crear_usuario_demo()
        elif opcion == '5':
            print("\nHasta luego!")
            break
        else:
            print("\nOpcion invalida. Intenta de nuevo.")

if __name__ == '__main__':
    main()
