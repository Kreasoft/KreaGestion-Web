#!/bin/bash
# ============================================
# SCRIPT DE BACKUP DE BASE DE DATOS
# GestionCloud - Sistema de Gestión
# ============================================

set -e

# Cargar variables de entorno
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Configuración
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/gestioncloud_backup_${TIMESTAMP}.sql"

# Crear directorio de backups si no existe
mkdir -p "${BACKUP_DIR}"

# Realizar backup
echo "Realizando backup de la base de datos..."
pg_dump -h ${DB_HOST:-localhost} \
        -p ${DB_PORT:-5432} \
        -U ${DB_USER:-postgres} \
        -d ${DB_NAME:-gestioncloud} \
        -F c \
        -f "${BACKUP_FILE}.dump" \
        --verbose

# También crear un SQL plano (opcional, más lento pero más compatible)
echo "Creando backup SQL plano..."
pg_dump -h ${DB_HOST:-localhost} \
        -p ${DB_PORT:-5432} \
        -U ${DB_USER:-postgres} \
        -d ${DB_NAME:-gestioncloud} \
        -f "${BACKUP_FILE}" \
        --verbose

# Comprimir backup SQL
echo "Comprimiendo backup..."
gzip -f "${BACKUP_FILE}"

echo "Backup completado: ${BACKUP_FILE}.gz"
echo "Backup binario: ${BACKUP_FILE}.dump"

# Eliminar backups antiguos (mantener últimos 7 días)
echo "Limpiando backups antiguos (más de 7 días)..."
find "${BACKUP_DIR}" -name "gestioncloud_backup_*.sql.gz" -mtime +7 -delete
find "${BACKUP_DIR}" -name "gestioncloud_backup_*.dump" -mtime +7 -delete

echo "Proceso de backup finalizado."






