#!/usr/bin/env bash
# Publica el núcleo actual en producción Y en la instancia demo.
#
# Construye las imágenes una sola vez y reinicia con ellas ambos stacks, así
# demo.ecoe.cl siempre corre la misma versión que producción. Cada backend
# aplica sus migraciones sobre SU base al arrancar. Los datos del demo no se
# tocan (para recargarlos: ./scripts/demo_reset.sh).
#
# Antes de un cambio con migraciones, respaldar producción:
#   docker exec ecoe-db pg_dump -U ecoe ecoe | gzip | \
#     docker exec -i ecoe-db-backup sh -c 'cat > /backups/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz'
set -euo pipefail
cd "$(dirname "$0")/.."

wait_healthy() {
  for _ in $(seq 1 60); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' "$1" 2>/dev/null)" = healthy ] && return 0
    sleep 3
  done
  echo "ERROR: $1 no quedó saludable" >&2
  return 1
}

echo "→ Construyendo imágenes..."
docker compose build backend frontend

echo "→ Producción..."
docker compose up -d --no-deps backend
wait_healthy ecoe-backend
docker compose up -d --no-deps frontend
wait_healthy ecoe-frontend

if [ -f demo.env ]; then
  echo "→ Demo..."
  docker compose -p ecoe-demo -f docker-compose.demo.yml --env-file demo.env up -d
  wait_healthy ecoe-demo-backend
  wait_healthy ecoe-demo-frontend
else
  echo "→ Demo omitido (no existe demo.env)."
fi

echo "Listo. Versión desplegada: $(git rev-parse --short HEAD)"
