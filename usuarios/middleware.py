"""
Middleware para manejo de multi-tenancy
"""
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.conf import settings


class EmpresaMiddleware:
	"""
	Middleware que identifica automáticamente la empresa del usuario
	y la agrega al request para uso en vistas
	"""
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		# Agregar empresa al request si el usuario está autenticado
		if request.user.is_authenticated:
			if request.user.is_superuser:
				# Superusuario puede acceder a todas las empresas
				from empresas.models import Empresa
				# Verificar si hay una empresa seleccionada en la sesión
				empresa_id = request.session.get('empresa_activa_id')
				if empresa_id:
					try:
						request.empresa = Empresa.objects.get(id=empresa_id)
					except Empresa.DoesNotExist:
						request.empresa = Empresa.objects.first()
						if request.empresa:
							request.session['empresa_activa_id'] = request.empresa.id
				else:
					# Asignar la primera empresa disponible
					request.empresa = Empresa.objects.first()
					if request.empresa:
						request.session['empresa_activa_id'] = request.empresa.id
			else:
				# Usuario normal debe tener un perfil con empresa
				try:
					if hasattr(request.user, 'perfil') and request.user.perfil:
						request.empresa = request.user.perfil.empresa
					else:
						# Crear perfil si no existe
						from usuarios.models import PerfilUsuario
						from empresas.models import Empresa
						
						empresa_default = Empresa.objects.first()
						if empresa_default:
							perfil, created = PerfilUsuario.objects.get_or_create(
								usuario=request.user,
								defaults={'empresa': empresa_default, 'es_activo': True}
							)
							request.empresa = perfil.empresa
							if created:
								print(f"Perfil creado automáticamente para {request.user.username}")
						else:
							request.empresa = None
				except Exception as e:
					print(f"Error en middleware: {e}")
					request.empresa = None
		else:
			request.empresa = None

		response = self.get_response(request)
		return response


class AccesoEmpresaMiddleware:
	"""
	Middleware que verifica que el usuario tenga acceso a la empresa
	"""
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		# URLs que no requieren verificación de empresa
		exempt_urls = [
			'/admin/',
			'/accounts/login/',
			'/accounts/logout/',
			'/static/',
			'/media/',
		]

		# Verificar si la URL actual está exenta
		url_exempta = any(request.path.startswith(url) for url in exempt_urls)

		if not url_exempta and request.user.is_authenticated and not request.user.is_superuser:
			# Verificar que el usuario tenga empresa asignada
			if not hasattr(request, 'empresa') or not request.empresa:
				# En desarrollo, permitir acceso temporal
				if not settings.DEBUG:
					messages.error(request, 'No tiene acceso a ninguna empresa. Contacte al administrador.')
					return redirect('logout')

		response = self.get_response(request)
		return response

		# Verificar si la URL actual está exenta
		url_exempta = any(request.path.startswith(url) for url in exempt_urls)

		if not url_exempta and request.user.is_authenticated and not request.user.is_superuser:
			# Verificar que el usuario tenga empresa asignada
			if not hasattr(request, 'empresa') or not request.empresa:
				# En desarrollo, permitir acceso temporal
				if not settings.DEBUG:
					messages.error(request, 'No tiene acceso a ninguna empresa. Contacte al administrador.')
					return redirect('logout')

		response = self.get_response(request)
		return response
