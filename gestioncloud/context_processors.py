"""
Context processors globales para GestionCloud
"""
import subprocess
import time
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone

from empresas.models import Empresa

_GIT_VERSION_CACHE = {'value': None, 'ts': 0.0}


def _get_git_version():
	"""
	Obtiene la versión de Git del repositorio actual (con caché de 60s).
	Si existe un tag en HEAD lo usa; de lo contrario combina rama/versión,
	contador de commits y hash corto (ej: v2.145 (eb789bc)).
	"""
	now = time.time()
	if _GIT_VERSION_CACHE['value'] and (now - _GIT_VERSION_CACHE['ts']) < 60:
		return _GIT_VERSION_CACHE['value']

	base_dir = str(getattr(settings, 'BASE_DIR', '.'))

	def _run_git(*args):
		res = subprocess.run(
			['git', *args],
			cwd=base_dir,
			capture_output=True,
			text=True,
			timeout=2,
			check=False,
		)
		return res.stdout.strip() if res.returncode == 0 else ''

	try:
		short_hash = _run_git('rev-parse', '--short', 'HEAD')
		tag = _run_git('describe', '--tags', '--exact-match')
		if tag:
			version_str = f'{tag} ({short_hash})' if short_hash else tag
		else:
			branch = _run_git('rev-parse', '--abbrev-ref', 'HEAD')
			count = _run_git('rev-list', '--count', 'HEAD')
			if branch.lower().startswith('version-'):
				ver_num = branch.split('-', 1)[1]
				prefix = f'v{ver_num}.{count}' if count else f'v{ver_num}'
			elif branch and branch != 'HEAD':
				prefix = f'{branch}.{count}' if count else branch
			else:
				prefix = f'r{count}' if count else ''

			if prefix and short_hash:
				version_str = f'{prefix} ({short_hash})'
			elif short_hash:
				version_str = short_hash
			else:
				version_str = prefix or '1.0'
	except Exception:
		version_str = '1.0'

	_GIT_VERSION_CACHE['value'] = version_str
	_GIT_VERSION_CACHE['ts'] = now
	return version_str


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
		'CURRENT_YEAR': timezone.localdate().year,
		'GIT_VERSION': _get_git_version(),
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

