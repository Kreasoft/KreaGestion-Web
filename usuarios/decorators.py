"""
Decoradores para control de acceso multi-empresa
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def requiere_empresa(view_func):
	"""
	Decorador que verifica que el usuario tenga una empresa asignada
	"""
	@wraps(view_func)
	def _wrapped_view(request, *args, **kwargs):
		if not request.user.is_authenticated:
			return redirect('login')
		
		if request.user.is_superuser:
			# Superusuario puede acceder a todo
			return view_func(request, *args, **kwargs)
		
		if not hasattr(request, 'empresa') or not request.empresa:
			messages.error(request, 'No tiene acceso a ninguna empresa. Contacte al administrador.')
			return redirect('logout')
		
		return view_func(request, *args, **kwargs)
	return _wrapped_view


def solo_superusuario(view_func):
	"""
	Decorador que solo permite acceso a superusuarios
	"""
	@wraps(view_func)
	def _wrapped_view(request, *args, **kwargs):
		if not request.user.is_authenticated:
			return redirect('login')
		
		if not request.user.is_superuser:
			messages.error(request, 'Acceso denegado. Solo los administradores pueden realizar esta acción.')
			raise PermissionDenied("Acceso denegado")
		
		return view_func(request, *args, **kwargs)
	return _wrapped_view


def filtrar_por_empresa(model_class):
	"""
	Decorador que filtra automáticamente los querysets por empresa
	"""
	def decorator(view_func):
		@wraps(view_func)
		def _wrapped_view(request, *args, **kwargs):
			if request.user.is_superuser:
				# Superusuario ve todos los datos
				return view_func(request, *args, **kwargs)
			
			# Filtrar por empresa del usuario
			if hasattr(request, 'empresa') and request.empresa:
				# Si el modelo tiene campo empresa, filtrar por él
				if hasattr(model_class, 'empresa'):
					kwargs['queryset'] = model_class.objects.filter(empresa=request.empresa)
				# Si el modelo tiene campo sucursal, filtrar por empresa de la sucursal
				elif hasattr(model_class, 'sucursal'):
					kwargs['queryset'] = model_class.objects.filter(sucursal__empresa=request.empresa)
			
			return view_func(request, *args, **kwargs)
		return _wrapped_view
	return decorator
