"""
Context processors globales para GestionCloud
"""
from django.conf import settings

from empresas.models import Empresa

def global_context(request):
	"""
	Contexto global disponible en todas las plantillas
	"""
	empresa = getattr(request, 'empresa', None)
	
	# Usar sucursal del middleware (si existe), sino usar la principal
	sucursal_activa = getattr(request, 'sucursal_activa', None)
	if sucursal_activa is None and empresa is not None:
		# Fallback: Sucursal principal o la primera disponible
		sucursal_activa = empresa.sucursales.filter(es_principal=True).first() or empresa.sucursales.first()

	return {
		'APP_NAME': 'GestionCloud',
		'DEBUG': settings.DEBUG,
		'empresa': empresa,
		'sucursal_activa': sucursal_activa,
	}
