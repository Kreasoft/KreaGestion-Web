#!/bin/bash
# ============================================
# SCRIPT DE ACTUALIZACIÓN
# GestionCloud - Sistema de Gestión
# ============================================

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}ACTUALIZACIÓN DE GestionCloud${NC}"
echo -e "${GREEN}============================================${NC}"
echo

# Verificar que estamos en el directorio correcto
if [ ! -f "manage.py" ]; then
    echo -e "${RED}ERROR: No se encuentra manage.py${NC}"
    exit 1
fi

# Hacer backup antes de actualizar
echo -e "${YELLOW}Haciendo backup de la base de datos...${NC}"
if [ -f "despliegue/backup_database.sh" ]; then
    bash despliegue/backup_database.sh
else
    echo -e "${YELLOW}ADVERTENCIA: Script de backup no encontrado, continuando sin backup...${NC}"
fi

# Detener servicio
if systemctl is-active --quiet gestioncloud 2>/dev/null; then
    echo -e "${YELLOW}Deteniendo servicio...${NC}"
    sudo systemctl stop gestioncloud
fi

# Activar entorno virtual
if [ -d ".venv" ]; then
    echo -e "${YELLOW}Activando entorno virtual...${NC}"
    source .venv/bin/activate
fi

# Actualizar código
echo -e "${YELLOW}Actualizando código desde Git...${NC}"
git pull origin main

# Actualizar dependencias
echo -e "${YELLOW}Actualizando dependencias...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Aplicar migraciones
echo -e "${YELLOW}Aplicando migraciones...${NC}"
python manage.py migrate --no-input

# Recolectar archivos estáticos
echo -e "${YELLOW}Recolectando archivos estáticos...${NC}"
python manage.py collectstatic --no-input --clear

# Limpiar cache
echo -e "${YELLOW}Limpiando cache...${NC}"
python manage.py clearsessions
find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Verificar configuración
echo -e "${YELLOW}Verificando configuración...${NC}"
python manage.py check --deploy

# Reiniciar servicio
if systemctl is-enabled --quiet gestioncloud 2>/dev/null; then
    echo -e "${YELLOW}Reiniciando servicio...${NC}"
    sudo systemctl start gestioncloud
    sleep 2
    sudo systemctl status gestioncloud --no-pager
fi

echo
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}ACTUALIZACIÓN COMPLETADA${NC}"
echo -e "${GREEN}============================================${NC}"








