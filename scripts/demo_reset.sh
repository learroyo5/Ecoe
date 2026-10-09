#!/usr/bin/env bash
# Deja la instancia demo recién cargada: borra SU base (nunca la de
# producción) y vuelve a crear los dos ECOE de muestra.
#
# Uso: ./scripts/demo_reset.sh          (pide confirmación)
#      ./scripts/demo_reset.sh --yes    (sin preguntar; para automatizar)
set -euo pipefail
cd "$(dirname "$0")/.."
DEMO=(docker compose -p ecoe-demo -f docker-compose.demo.yml --env-file demo.env)

if [ "${1:-}" != "--yes" ]; then
  read -r -p "Esto BORRA los datos de demo.ecoe.cl y los vuelve a cargar. Escribe 'demo' para continuar: " OK
  [ "$OK" = "demo" ] || { echo "Cancelado."; exit 1; }
fi

"${DEMO[@]}" up -d db
"${DEMO[@]}" stop backend frontend >/dev/null 2>&1 || true
for _ in $(seq 1 60); do
  docker exec ecoe-demo-db pg_isready -U ecoe -d postgres >/dev/null 2>&1 && break
  sleep 1
done
sleep 2  # el init de la imagen reinicia postgres una vez tras crear la base
docker exec ecoe-demo-db psql -U ecoe -d postgres -q -c "DROP DATABASE IF EXISTS ecoe;" -c "CREATE DATABASE ecoe OWNER ecoe;"
"${DEMO[@]}" up -d
echo "→ Esperando al backend demo (aplica migraciones al arrancar)..."
for _ in $(seq 1 60); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' ecoe-demo-backend 2>/dev/null)" = healthy ] && break
  sleep 3
done
docker exec ecoe-demo-backend python -m app.db.seed_demo
