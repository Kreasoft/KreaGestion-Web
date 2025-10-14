"""
Modelos para el módulo de usuarios
"""
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class PerfilUsuario(models.Model):
	"""
	Perfil extendido del usuario que incluye la empresa y sucursal a la que pertenece
	"""
	TIPO_USUARIO_CHOICES = [
		('administrador', 'Administrador'),
		('vendedor', 'Vendedor'),
		('cajero', 'Cajero'),
	]
	
	usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
	empresa = models.ForeignKey('empresas.Empresa', on_delete=models.CASCADE, verbose_name='Empresa')
	sucursal = models.ForeignKey('empresas.Sucursal', on_delete=models.PROTECT, null=True, blank=True, verbose_name='Sucursal', related_name='usuarios')
	tipo_usuario = models.CharField(max_length=20, choices=TIPO_USUARIO_CHOICES, default='vendedor', verbose_name='Tipo de Usuario')
	es_activo = models.BooleanField(default=True, verbose_name='Usuario activo')
	fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')
	fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name='Fecha de actualización')

	class Meta:
		verbose_name = 'Perfil de Usuario'
		verbose_name_plural = 'Perfiles de Usuarios'
		db_table = 'usuarios_perfil_usuario'

	def __str__(self):
		return f"{self.usuario.username} - {self.empresa.nombre}"

	@property
	def nombre_completo(self):
		return f"{self.usuario.first_name} {self.usuario.last_name}".strip() or self.usuario.username
	
	@property
	def es_administrador(self):
		"""Verifica si el usuario es administrador de empresa"""
		return self.tipo_usuario == 'administrador'
	
	@property
	def es_vendedor(self):
		"""Verifica si el usuario es vendedor"""
		return self.tipo_usuario == 'vendedor'
	
	@property
	def es_cajero(self):
		"""Verifica si el usuario es cajero"""
		return self.tipo_usuario == 'cajero'


@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
	"""
	Crear automáticamente un perfil cuando se crea un usuario
	"""
	if created:
		# Solo crear perfil si no es superusuario
		if not instance.is_superuser:
			# Por defecto asignar a la primera empresa disponible
			from empresas.models import Empresa
			empresa_default = Empresa.objects.first()
			if empresa_default:
				PerfilUsuario.objects.create(usuario=instance, empresa=empresa_default)


@receiver(post_save, sender=User)
def guardar_perfil_usuario(sender, instance, **kwargs):
	"""
	Guardar el perfil cuando se actualiza el usuario
	"""
	if hasattr(instance, 'perfil'):
		instance.perfil.save()
