"""
Configuración de Gunicorn para GestionCloud
"""
import multiprocessing
import os

# Configuración del servidor
bind = f"0.0.0.0:{os.environ.get('GUNICORN_PORT', '8000')}"
workers = int(os.environ.get('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
threads = int(os.environ.get('GUNICORN_THREADS', 2))
worker_class = 'sync'
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = os.environ.get('GUNICORN_ACCESS_LOG', '/var/log/gestioncloud/gunicorn_access.log')
errorlog = os.environ.get('GUNICORN_ERROR_LOG', '/var/log/gestioncloud/gunicorn_error.log')
loglevel = os.environ.get('LOG_LEVEL', 'info').lower()

# Proceso
daemon = False
pidfile = '/var/run/gestioncloud/gunicorn.pid'
umask = 0o007
user = os.environ.get('GUNICORN_USER', None)
group = os.environ.get('GUNICORN_GROUP', None)

# Preload
preload_app = True

# Worker timeout
graceful_timeout = 30

# Max requests (reciclar workers después de N requests)
max_requests = 1000
max_requests_jitter = 50

# StatsD (opcional)
# statsd_host = 'localhost:8125'

def when_ready(server):
    """Callback cuando el servidor está listo"""
    server.log.info("GestionCloud está listo para recibir conexiones")

def on_exit(server):
    """Callback cuando el servidor se detiene"""
    server.log.info("GestionCloud se está deteniendo")









