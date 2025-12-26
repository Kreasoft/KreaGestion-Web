#!/bin/bash
# ============================================
# SCRIPT DE DESPLIEGUE PARA LINUX
# GestionCloud - Sistema de Gestión
# ============================================

set -e  # Salir si hay algún error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}DESPLIEGUE DE GestionCloud - LINUX${NC}"
echo -e "${GREEN}============================================${NC}"
echo

# Verificar que estamos en el directorio correcto
if [ ! -f "manage.py" ]; then
    echo -e "${RED}ERROR: No se encuentra manage.py. Ejecuta este script desde la raiz del proyecto.${NC}"
    exit 1
fi

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}ERROR: Python3 no está instalado.${NC}"
    exit 1
fi

# Crear directorios necesarios
echo -e "${YELLOW}Creando directorios necesarios...${NC}"
mkdir -p logs
mkdir -p staticfiles
mkdir -p media
mkdir -p /var/log/gestioncloud 2>/dev/null || true
mkdir -p /var/run/gestioncloud 2>/dev/null || true

# Crear/activar entorno virtual
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creando entorno virtual...${NC}"
    python3 -m venv .venv
fi

echo -e "${YELLOW}Activando entorno virtual...${NC}"
source .venv/bin/activate

# Actualizar pip
echo -e "${YELLOW}Actualizando pip...${NC}"
pip install --upgrade pip

# Instalar dependencias
echo -e "${YELLOW}Instalando dependencias...${NC}"
pip install -r requirements.txt

# Instalar Gunicorn si no está instalado
if ! pip show gunicorn &> /dev/null; then
    echo -e "${YELLOW}Instalando Gunicorn...${NC}"
    pip install gunicorn
fi

# Verificar archivo .env
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}ADVERTENCIA: No se encuentra archivo .env${NC}"
    if [ -f "despliegue/.env.production.example" ]; then
        echo -e "${YELLOW}Copiando ejemplo de configuración...${NC}"
        cp despliegue/.env.production.example .env
        echo -e "${RED}Por favor, edita el archivo .env con tus configuraciones antes de continuar.${NC}"
        exit 1
    fi
fi

# Cargar variables de entorno
if [ -f ".env" ]; then
    echo -e "${YELLOW}Cargando variables de entorno...${NC}"
    export $(cat .env | grep -v '^#' | xargs)
fi

# Aplicar migraciones
echo -e "${YELLOW}Aplicando migraciones de base de datos...${NC}"
python manage.py migrate --no-input

# Crear superusuario si no existe (opcional, comentar si prefieres crearlo manualmente)
echo -e "${YELLOW}Verificando superusuario...${NC}"
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    print("Creando superusuario por defecto (admin/admin123)...")
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
else:
    print("Superusuario ya existe.")
EOF

# Recolectar archivos estáticos
echo -e "${YELLOW}Recolectando archivos estáticos...${NC}"
python manage.py collectstatic --no-input --clear

# Verificar configuración
echo -e "${YELLOW}Verificando configuración de Django...${NC}"
python manage.py check --deploy

# Configurar permisos
echo -e "${YELLOW}Configurando permisos...${NC}"
chmod -R 755 staticfiles
chmod -R 755 media
chmod -R 755 logs

echo
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}DESPLIEGUE COMPLETADO${NC}"
echo -e "${GREEN}============================================${NC}"
echo
echo -e "${YELLOW}Para iniciar el servidor con Gunicorn:${NC}"
echo "  gunicorn gestioncloud.wsgi:application --config despliegue/gunicorn_config.py"
echo
echo -e "${YELLOW}O usar el script de inicio:${NC}"
echo "  ./despliegue/start_gunicorn.sh"
echo
echo -e "${YELLOW}Para configurar como servicio systemd:${NC}"
echo "  sudo cp despliegue/gestioncloud.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable gestioncloud"
echo "  sudo systemctl start gestioncloud"
echo






