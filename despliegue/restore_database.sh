#!/bin/bash
# ============================================
# SCRIPT DE RESTAURACIÓN DE BASE DE DATOS
# GestionCloud - Sistema de Gestión
# ============================================
# USO: ./restore_database.sh archivo_backup.sql.gz

set -e

if [ -z "$1" ]; then
    echo "ERROR: Debes especificar el archivo de backup a restaurar"
    echo "Uso: $0 archivo_backup.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "ERROR: El archivo de backup no existe: $BACKUP_FILE"
    exit 1
fi

# Cargar variables de entorno
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "============================================"
echo "RESTAURACIÓN DE BASE DE DATOS"
echo "============================================"
echo
echo "ADVERTENCIA: Esta operación reemplazará todos los datos actuales."
echo "Archivo de backup: $BACKUP_FILE"
echo
read -p "¿Estás seguro de continuar? (escribe 'SI' para confirmar): " confirmacion

if [ "$confirmacion" != "SI" ]; then
    echo "Operación cancelada."
    exit 0
fi

# Detener servicio si está corriendo
if systemctl is-active --quiet gestioncloud 2>/dev/null; then
    echo "Deteniendo servicio GestionCloud..."
    sudo systemctl stop gestioncloud
fi

# Descomprimir si es necesario
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "Descomprimiendo backup..."
    TEMP_FILE="${BACKUP_FILE%.gz}"
    gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
    BACKUP_FILE="$TEMP_FILE"
fi

# Restaurar base de datos
echo "Restaurando base de datos..."
PGPASSWORD=${DB_PASSWORD} psql -h ${DB_HOST:-localhost} \
        -p ${DB_PORT:-5432} \
        -U ${DB_USER:-postgres} \
        -d ${DB_NAME:-gestioncloud} \
        -f "$BACKUP_FILE" \
        --verbose

# Limpiar archivo temporal si se descomprimió
if [ -f "$TEMP_FILE" ]; then
    rm "$TEMP_FILE"
fi

# Reiniciar servicio
if systemctl is-enabled --quiet gestioncloud 2>/dev/null; then
    echo "Reiniciando servicio GestionCloud..."
    sudo systemctl start gestioncloud
fi

echo
echo "============================================"
echo "RESTAURACIÓN COMPLETADA"
echo "============================================"









