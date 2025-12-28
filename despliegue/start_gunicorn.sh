#!/bin/bash
# ============================================
# SCRIPT PARA INICIAR GUNICORN
# GestionCloud - Sistema de Gestión
# ============================================

# Cargar variables de entorno
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Activar entorno virtual
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Cambiar al directorio del proyecto
cd "$(dirname "$0")/.."

# Iniciar Gunicorn
exec gunicorn gestioncloud.wsgi:application \
    --config despliegue/gunicorn_config.py \
    --bind 0.0.0.0:${GUNICORN_PORT:-8000} \
    --workers ${GUNICORN_WORKERS:-4} \
    --threads ${GUNICORN_THREADS:-2} \
    --timeout 30 \
    --access-logfile /var/log/gestioncloud/gunicorn_access.log \
    --error-logfile /var/log/gestioncloud/gunicorn_error.log \
    --log-level info








