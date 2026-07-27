#!/usr/bin/env bash
# Restaura un backup de la BD ECOE generado por el servicio db-backup.
#
# Uso:
#   ./scripts/restore_db.sh backups/ecoe-YYYYMMDD-HHMMSS.sql.gz
#
# ADVERTENCIA: reemplaza TODO el contenido de la base de datos "ecoe".
# El backend debe detenerse durante el restore.
set -euo pipefail

BACKUP_FILE="${1:?Uso: $0 <ruta-al-backup.sql.gz>}"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "No existe el archivo: $BACKUP_FILE" >&2
  exit 1
fi

echo "Este restore BORRA la base 'ecoe' actual y la reemplaza por el backup."
read -r -p "Escribe 'restaurar' para continuar: " CONFIRM
if [ "$CONFIRM" != "restaurar" ]; then
  echo "Cancelado."
  exit 1
fi

echo "→ Deteniendo backend..."
docker compose stop backend

echo "→ Recreando base de datos..."
docker exec ecoe-db psql -U ecoe -d postgres -c "DROP DATABASE IF EXISTS ecoe;"
docker exec ecoe-db psql -U ecoe -d postgres -c "CREATE DATABASE ecoe OWNER ecoe;"

echo "→ Restaurando ${BACKUP_FILE}..."
gunzip -c "$BACKUP_FILE" | docker exec -i ecoe-db psql -U ecoe -d ecoe -q

echo "→ Levantando backend..."
docker compose start backend

echo "Restore completado. Verifica con: curl -s http://127.0.0.1:8000/health"
