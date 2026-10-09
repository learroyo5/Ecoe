#!/bin/sh
# Bucle de respaldo del servicio db-backup (docker-compose.yml).
#
# - Diario: pg_dump completo a /backups/ecoe-<ts>.sql.gz y, si el volumen de
#   archivos está montado en /storage, su tar a /backups/storage-<ts>.tar.gz.
#   Rotación: 14 días.
# - En vivo (F0.8): mientras haya algún ECOE `en_ejecucion`, un pg_dump cada
#   LIVE_INTERVAL_SECONDS a /backups/live/. Así lo máximo que se puede perder
#   ante una falla del servidor en pleno examen es ese intervalo, no un día.
#   Se conservan los LIVE_KEEP más recientes.
#
# Restauración: scripts/restore_db.sh. Ensayo sin tocar producción:
# scripts/verify_backup.sh.
set -u

DB_HOST="${DB_HOST:-db}"
DB_USER="${DB_USER:-ecoe}"
DB_NAME="${DB_NAME:-ecoe}"
DAILY_INTERVAL_SECONDS="${DAILY_INTERVAL_SECONDS:-86400}"
LIVE_INTERVAL_SECONDS="${LIVE_INTERVAL_SECONDS:-300}"
LIVE_KEEP="${LIVE_KEEP:-36}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p /backups/live

dump_to() {
  # $1 = archivo destino. Reintenta 3 veces; nunca deja un archivo a medias.
  target="$1"
  for attempt in 1 2 3; do
    if pg_dump -h "$DB_HOST" -U "$DB_USER" "$DB_NAME" | gzip > "$target.tmp" \
       && gzip -t "$target.tmp" && [ -s "$target.tmp" ]; then
      mv "$target.tmp" "$target"
      return 0
    fi
    rm -f "$target.tmp"
    sleep 10
  done
  return 1
}

daily_backup() {
  ts=$(date +%Y%m%d-%H%M%S)
  if dump_to "/backups/ecoe-$ts.sql.gz"; then
    echo "backup ok: ecoe-$ts.sql.gz"
  else
    echo "backup FAILED after 3 attempts: $ts" >&2
  fi
  if [ -d /storage ]; then
    if tar czf "/backups/storage-$ts.tar.gz.tmp" -C /storage . 2>/dev/null; then
      mv "/backups/storage-$ts.tar.gz.tmp" "/backups/storage-$ts.tar.gz"
      echo "storage backup ok: storage-$ts.tar.gz"
    else
      rm -f "/backups/storage-$ts.tar.gz.tmp"
      echo "storage backup FAILED: $ts" >&2
    fi
  fi
  find /backups -maxdepth 1 -name "ecoe-*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
  find /backups -maxdepth 1 -name "storage-*.tar.gz" -mtime +"$RETENTION_DAYS" -delete
}

live_backup() {
  ts=$(date +%Y%m%d-%H%M%S)
  if dump_to "/backups/live/ecoe-live-$ts.sql.gz"; then
    echo "live backup ok: ecoe-live-$ts.sql.gz"
  else
    echo "live backup FAILED: $ts" >&2
  fi
  # Conservar sólo los más recientes.
  ls -1t /backups/live/ecoe-live-*.sql.gz 2>/dev/null | tail -n +$((LIVE_KEEP + 1)) | xargs -r rm -f
}

exam_running() {
  count=$(psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM ecoe_events WHERE status = 'en_ejecucion'" 2>/dev/null || echo 0)
  [ "${count:-0}" -gt 0 ] 2>/dev/null
}

last_daily=0
while true; do
  now=$(date +%s)
  if [ $((now - last_daily)) -ge "$DAILY_INTERVAL_SECONDS" ]; then
    daily_backup
    last_daily=$now
  fi
  if exam_running; then
    live_backup
  fi
  sleep "$LIVE_INTERVAL_SECONDS"
done
