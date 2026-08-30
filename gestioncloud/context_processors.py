"""
Context processors globales para GestionCloud
"""
from urllib.parse import urlencode

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

	fondo = 'foto'
	menu_layout = 'lateral'
	if hasattr(request, 'session'):
		fondo = request.session.get('dashboard_fondo', 'foto')
		if fondo not in ('foto', 'suave'):
			fondo = 'foto'
		menu_layout = request.session.get('menu_layout') or request.COOKIES.get('menu_layout', 'lateral')
		if menu_layout not in ('lateral', 'superior'):
			menu_layout = 'lateral'

	full_path = ''
	if getattr(request, 'get_full_path', None):
		full_path = request.get_full_path()

	correo_smtp_listo = False
	try:
		from utilidades.utils import datos_smtp
		correo_smtp_listo = bool(datos_smtp(empresa)['listo'])
	except Exception:
		correo_smtp_listo = False

	return {
		'APP_NAME': 'GestionCloud',
		'DEBUG': settings.DEBUG,
		'empresa': empresa,
		'sucursal_activa': sucursal_activa,
		'dashboard_fondo': fondo,
		'fondo_foto': fondo != 'suave',
		'menu_layout': menu_layout,
		'menu_superior': menu_layout == 'superior',
		'return_url_q': urlencode({'return_url': full_path}) if full_path else '',
		'correo_smtp_listo': correo_smtp_listo,
	}
