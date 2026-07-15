#!/usr/bin/env bash
# Corre las pruebas end-to-end del flujo dorado contra un stack efímero.
#
# Uso: ./scripts/run_e2e.sh [args extra de playwright]
#
# Levanta docker-compose.e2e.yml (proyecto ecoe-e2e, puertos 13001/18001,
# BD desechable con seed demo), espera a que el frontend responda, ejecuta
# Playwright y SIEMPRE derriba el stack al final. No toca el stack productivo.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT_DIR="$(pwd)"

# Ruta ABSOLUTA al compose: cleanup corre via trap después de `cd frontend`,
# y con ruta relativa el down fallaba en silencio dejando el stack (y sus
# datos sucios) vivo entre corridas.
COMPOSE=(docker compose -p ecoe-e2e -f "${ROOT_DIR}/docker-compose.e2e.yml")
BASE_URL="http://127.0.0.1:13001"

cleanup() {
  echo "→ Bajando stack e2e..."
  if ! "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1; then
    echo "ADVERTENCIA: no se pudo bajar el stack e2e; revisa 'docker compose -p ecoe-e2e ps'" >&2
  fi
}
trap cleanup EXIT

echo "→ Levantando stack e2e..."
"${COMPOSE[@]}" up --build -d

echo "→ Esperando frontend en ${BASE_URL}..."
for i in $(seq 1 60); do
  if curl -sf -o /dev/null "${BASE_URL}/login"; then
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "El frontend e2e no respondió a tiempo" >&2
    "${COMPOSE[@]}" logs --tail 30 backend frontend >&2 || true
    exit 1
  fi
  sleep 2
done

echo "→ Ejecutando Playwright..."
cd frontend
E2E_BASE_URL="$BASE_URL" npx playwright test "$@"
