"""
Comando para crear usuarios de demostración
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from empresas.models import Empresa, Sucursal
from usuarios.models import PerfilUsuario


class Command(BaseCommand):
	help = 'Crea usuarios de demostración para probar el sistema multi-empresa'

	def handle(self, *args, **options):
		self.stdout.write('Creando usuarios de demostración...')
		
		# Crear empresa de demostración
		empresa, created = Empresa.objects.get_or_create(
			rut='76.123.456-7',
			defaults={
				'nombre': 'Empresa Demo SPA',
				'razon_social': 'Empresa Demo Sociedad Por Acciones',
				'giro': 'Servicios de Tecnología',
				'direccion': 'Av. Providencia 1234',
				'comuna': 'Providencia',
				'ciudad': 'Santiago',
				'region': 'Metropolitana',
				'telefono': '+56 2 2345 6789',
				'email': 'contacto@empresademo.cl',
				'estado': 'activa',
				'regimen_tributario': '19',
			}
		)
		
		if created:
			self.stdout.write(f'Empresa creada: {empresa.nombre}')
		else:
			self.stdout.write(f'Empresa existente: {empresa.nombre}')
		
		# Crear sucursal principal
		from datetime import time
		sucursal, created = Sucursal.objects.get_or_create(
			nombre='Sucursal Principal',
			empresa=empresa,
			defaults={
				'codigo': 'SP001',
				'direccion': 'Av. Providencia 1234',
				'comuna': 'Providencia',
				'ciudad': 'Santiago',
				'region': 'Metropolitana',
				'telefono': '+56 2 2345 6789',
				'email': 'sucursal@empresademo.cl',
				'es_principal': True,
				'estado': 'activa',
				'horario_apertura': time(8, 0),
				'horario_cierre': time(18, 0),
			}
		)
		
		if created:
			self.stdout.write(f'Sucursal creada: {sucursal.nombre}')
		else:
			self.stdout.write(f'Sucursal existente: {sucursal.nombre}')
		
		# Crear usuario normal
		usuario, created = User.objects.get_or_create(
			username='demo',
			defaults={
				'first_name': 'Usuario',
				'last_name': 'Demo',
				'email': 'usuario@empresademo.cl',
				'is_staff': False,
				'is_superuser': False,
			}
		)
		
		if created:
			usuario.set_password('demo123')
			usuario.save()
			self.stdout.write(f'Usuario creado: {usuario.username}')
		else:
			self.stdout.write(f'Usuario existente: {usuario.username}')
		
		# Crear o actualizar perfil
		perfil, created = PerfilUsuario.objects.get_or_create(
			usuario=usuario,
			defaults={
				'empresa': empresa,
				'es_activo': True,
			}
		)
		
		if created:
			self.stdout.write(f'Perfil creado para: {usuario.username}')
		else:
			# Actualizar empresa si cambió
			if perfil.empresa != empresa:
				perfil.empresa = empresa
				perfil.save()
				self.stdout.write(f'Perfil actualizado para: {usuario.username}')
		
		self.stdout.write(
			self.style.SUCCESS(
				f'Usuarios de demostración creados exitosamente!\n'
				f'Usuario: {usuario.username}\n'
				f'Contraseña: demo123\n'
				f'Empresa: {empresa.nombre}'
			)
		)
