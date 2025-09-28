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
	sucursal_activa = None
	if empresa is not None:
		# Sucursal activa: principal o la primera disponible
		sucursal_activa = empresa.sucursales.filter(es_principal=True).first() or empresa.sucursales.first()

	return {
		'APP_NAME': 'GestionCloud',
		'DEBUG': settings.DEBUG,
		'empresa': empresa,
		'sucursal_activa': sucursal_activa,
	}
