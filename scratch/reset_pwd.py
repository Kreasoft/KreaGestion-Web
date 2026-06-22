from django.contrib.auth import get_user_model
User = get_user_model()
try:
    u = User.objects.get(username='krea')
    u.set_password('123')
    u.is_superuser = True
    u.is_staff = True
    u.save()
    print("Contraseña actualizada para el usuario 'krea'.")
except User.DoesNotExist:
    u = User.objects.create_superuser('krea', 'krea@example.com', '123')
    print("Usuario 'krea' creado como superusuario con contraseña '123'.")
