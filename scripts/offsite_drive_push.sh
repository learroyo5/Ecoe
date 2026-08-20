#!/usr/bin/env bash
set -euo pipefail

RCLONE_REMOTE="${RCLONE_REMOTE:?debes definir RCLONE_REMOTE}"
DUMP_FILE="${1:-}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Falta comando requerido: $1" >&2
    exit 1
  }
}

read_passphrase() {
  if [[ -n "${GPG_PASSPHRASE:-}" ]]; then
    printf "%s" "$GPG_PASSPHRASE"
    return
  fi
  if [[ -n "${GPG_PASSPHRASE_FILE:-}" && -f "${GPG_PASSPHRASE_FILE}" ]]; then
    head -n 1 "${GPG_PASSPHRASE_FILE}"
    return
  fi
  echo "Debes definir GPG_PASSPHRASE o GPG_PASSPHRASE_FILE" >&2
  exit 1
}

need_cmd rclone
need_cmd gpg
need_cmd sha256sum

if [[ -z "$DUMP_FILE" ]]; then
  DUMP_FILE="$(ls -1t backups/ecoe-*.sql.gz 2>/dev/null | head -n 1 || true)"
fi
if [[ -z "$DUMP_FILE" || ! -f "$DUMP_FILE" ]]; then
  echo "No hay dump válido. Uso: $0 backups/ecoe-archivo.sql.gz" >&2
  exit 1
fi

PASSPHRASE="$(read_passphrase)"
BASENAME="$(basename "$DUMP_FILE")"
ENC_NAME="${BASENAME}.gpg"
WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
ENC_PATH="${WORK_DIR}/${ENC_NAME}"
SUM_PATH="${WORK_DIR}/${ENC_NAME}.sha256"

echo "[offsite-push] dump: $DUMP_FILE"
echo "[offsite-push] remote: $RCLONE_REMOTE"

gpg --batch --yes --pinentry-mode loopback \
  --passphrase "$PASSPHRASE" \
  --symmetric --cipher-algo AES256 \
  --output "$ENC_PATH" "$DUMP_FILE"

# Store checksum using only the filename (no temp absolute path).
(cd "$WORK_DIR" && sha256sum "$ENC_NAME" > "$SUM_PATH")

rclone copyto "$ENC_PATH" "${RCLONE_REMOTE}/${ENC_NAME}"
rclone copyto "$SUM_PATH" "${RCLONE_REMOTE}/${ENC_NAME}.sha256"

echo "[offsite-push] OK: ${RCLONE_REMOTE}/${ENC_NAME}"
rclone lsf "$RCLONE_REMOTE" --files-only --max-depth 1 | tail -n 10

GPU_SERVER_HOST="${GPU_SERVER_HOST:-gpu-server}"
GPU_SERVER_BACKUP_DIR="${GPU_SERVER_BACKUP_DIR:?debes definir GPU_SERVER_BACKUP_DIR}"
echo "[offsite-push] gpu-server: ${GPU_SERVER_HOST}:${GPU_SERVER_BACKUP_DIR}"
scp -q "$ENC_PATH" "$SUM_PATH" "${GPU_SERVER_HOST}:${GPU_SERVER_BACKUP_DIR}/"
echo "[offsite-push] OK: ${GPU_SERVER_HOST}:${GPU_SERVER_BACKUP_DIR}/${ENC_NAME}"
