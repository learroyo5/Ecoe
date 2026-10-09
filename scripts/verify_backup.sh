#!/usr/bin/env bash
# Ensayo de restauración SIN tocar producción (F0.8).
#
# Restaura un respaldo en un PostgreSQL desechable y comprueba que quedó
# utilizable: versión de migraciones y conteos de las tablas principales.
# No modifica la base real ni detiene ningún servicio.
#
# Uso:
#   ./scripts/verify_backup.sh                      # el respaldo diario más reciente
#   ./scripts/verify_backup.sh backups/ecoe-....sql.gz
set -euo pipefail

cd "$(dirname "$0")/.."
BACKUP_FILE="${1:-$(ls -1t backups/ecoe-*.sql.gz 2>/dev/null | head -n 1)}"
if [ -z "${BACKUP_FILE:-}" ] || [ ! -f "$BACKUP_FILE" ]; then
  echo "No se encontró un respaldo que verificar." >&2
  exit 1
fi

NAME="ecoe-verify-$$"
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

START=$(date +%s)
echo "→ Respaldo: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"
gzip -t "$BACKUP_FILE"
gunzip -c "$BACKUP_FILE" | grep -q "PostgreSQL database dump complete" \
  || { echo "El volcado está incompleto (falta el marcador final)." >&2; exit 1; }

docker run -d --name "$NAME" -e POSTGRES_USER=ecoe -e POSTGRES_PASSWORD=verify \
  -e POSTGRES_DB=ecoe postgres:16-alpine >/dev/null
for _ in $(seq 1 30); do
  docker exec "$NAME" pg_isready -U ecoe -d ecoe >/dev/null 2>&1 && break
  sleep 1
done
sleep 1

echo "→ Restaurando en un PostgreSQL desechable..."
gunzip -c "$BACKUP_FILE" | docker exec -i "$NAME" psql -U ecoe -d ecoe -q -v ON_ERROR_STOP=1 >/dev/null

echo "→ Contenido restaurado:"
docker exec -i "$NAME" psql -U ecoe -d ecoe -tA -F ' = ' <<'SQL'
SELECT 'migración', version_num FROM alembic_version;
SELECT 'eventos', count(*) FROM ecoe_events;
SELECT 'estaciones', count(*) FROM stations;
SELECT 'estudiantes', count(*) FROM students;
SELECT 'usuarios', count(*) FROM users;
SELECT 'evaluaciones', count(*) FROM evaluator_records;
SELECT 'respuestas', count(*) FROM student_responses;
SELECT 'actas', count(*) FROM ecoe_results;
SELECT 'auditoría', count(*) FROM audit_logs;
SQL

STORAGE_FILE="$(ls -1t backups/storage-*.tar.gz 2>/dev/null | head -n 1 || true)"
if [ -n "$STORAGE_FILE" ]; then
  gzip -t "$STORAGE_FILE"
  echo "→ Archivos: $STORAGE_FILE ($(tar tzf "$STORAGE_FILE" | grep -vc '/$') archivos)"
else
  echo "→ Archivos: todavía no hay respaldo del volumen multimedia."
fi

echo "Restauración verificada en $(( $(date +%s) - START )) s."
