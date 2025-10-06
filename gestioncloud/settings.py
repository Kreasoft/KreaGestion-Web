"""
Configuración de GestionCloud
Sistema de Gestión de Ventas e Inventario Multiempresa
"""

import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=lambda v: [s.strip() for s in v.split(',')])

# Application definition
DJANGO_APPS = [
	'django.contrib.admin',
	'django.contrib.auth',
	'django.contrib.contenttypes',
	'django.contrib.sessions',
	'django.contrib.messages',
	'django.contrib.staticfiles',
	'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
	'rest_framework',
	'corsheaders',
	'crispy_forms',
	'crispy_bootstrap5',
	'django_tables2',
	'widget_tweaks',
	# 'django_bootstrap5',  # Comentado temporalmente
	# 'simple_history',  # Comentado temporalmente
]

LOCAL_APPS = [
	'empresas.apps.EmpresasConfig',
	'articulos.apps.ArticulosConfig',
	'inventario.apps.InventarioConfig',
	'bodegas.apps.BodegasConfig',
	'ventas.apps.VentasConfig',
	'clientes.apps.ClientesConfig',
	'documentos.apps.DocumentosConfig',
	'proveedores.apps.ProveedoresConfig',
	'compras.apps.ComprasConfig',
	'reportes.apps.ReportesConfig',
	'usuarios.apps.UsuariosConfig',
	'tesoreria.apps.TesoreriaConfig',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
	'corsheaders.middleware.CorsMiddleware',
	'django.middleware.security.SecurityMiddleware',
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.common.CommonMiddleware',
	'django.middleware.csrf.CsrfViewMiddleware',
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'django.contrib.messages.middleware.MessageMiddleware',
	'django.middleware.clickjacking.XFrameOptionsMiddleware',
	# 'simple_history.middleware.HistoryRequestMiddleware',  # Comentado temporalmente
	'usuarios.middleware.EmpresaMiddleware',
	'usuarios.middleware.AccesoEmpresaMiddleware',
]

ROOT_URLCONF = 'gestioncloud.urls'

TEMPLATES = [
	{
		'BACKEND': 'django.template.backends.django.DjangoTemplates',
		'DIRS': [BASE_DIR / 'templates'],
		'APP_DIRS': True,
		'OPTIONS': {
			'context_processors': [
				'django.template.context_processors.debug',
				'django.template.context_processors.request',
				'django.contrib.auth.context_processors.auth',
				'django.contrib.messages.context_processors.messages',
				'gestioncloud.context_processors.global_context',
			],
		},
	},
]

WSGI_APPLICATION = 'gestioncloud.wsgi.application'

# Database
DATABASES = {
	'default': {
		'ENGINE': config('DB_ENGINE', default='django.db.backends.sqlite3'),
		'NAME': config('DB_NAME', default=BASE_DIR / 'db.sqlite3'),
		'USER': config('DB_USER', default=''),
		'PASSWORD': config('DB_PASSWORD', default=''),
		'HOST': config('DB_HOST', default=''),
		'PORT': config('DB_PORT', default=''),
	}
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
	{
		'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
	},
	{
		'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
	},
	{
		'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
	},
	{
		'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
	},
]

# Internationalization
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
	BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Django Tables2
django_tables2_template = "django_tables2/bootstrap5.html"

# REST Framework
REST_FRAMEWORK = {
	'DEFAULT_AUTHENTICATION_CLASSES': [
		'rest_framework.authentication.SessionAuthentication',
		'rest_framework.authentication.TokenAuthentication',
	],
	'DEFAULT_PERMISSION_CLASSES': [
		'rest_framework.permissions.IsAuthenticated',
	],
	'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
	'PAGE_SIZE': 25,
	'DEFAULT_FILTER_BACKENDS': [
		'django_filters.rest_framework.DjangoFilterBackend',
		'rest_framework.filters.SearchFilter',
		'rest_framework.filters.OrderingFilter',
	],
}

# CORS
CORS_ALLOWED_ORIGINS = [
	"http://localhost:8000",
	"http://127.0.0.1:8000",
]

# CKEditor
CKEDITOR_CONFIGS = {
	'default': {
		'toolbar': 'Custom',
		'toolbar_Custom': [
			['Bold', 'Italic', 'Underline'],
			['NumberedList', 'BulletedList', '-', 'Outdent', 'Indent', '-', 'JustifyLeft', 'JustifyCenter', 'JustifyRight', 'JustifyBlock'],
			['Link', 'Unlink'],
			['RemoveFormat', 'Source']
		]
	}
}

# Auth redirects
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
LOGIN_URL = '/accounts/login/'

# MPTT
MPTT_ADMIN_LEVEL_INDENT = 20

# Logging
LOGGING = {
	'version': 1,
	'disable_existing_loggers': False,
	'handlers': {
		'file': {
			'level': 'INFO',
			'class': 'logging.FileHandler',
			'filename': BASE_DIR / 'logs' / 'gestioncloud.log',
		},
	},
	'loggers': {
		'django': {
			'handlers': ['file'],
			'level': 'INFO',
			'propagate': True,
		},
	},
}

# Crear directorio de logs si no existe
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

# Configuración de archivos
FILE_UPLOAD_HANDLERS = [
	'django.core.files.uploadhandler.MemoryFileUploadHandler',
	'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]

# Tamaño máximo de archivo (10MB)
MAX_UPLOAD_SIZE = 10485760

# Configuración de sesiones
SESSION_COOKIE_AGE = 3600  # 1 hora
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Configuración de archivos estáticos en producción
if not DEBUG:
	STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
