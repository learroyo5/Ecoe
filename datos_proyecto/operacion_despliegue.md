# Operacion y Despliegue

Referencia rapida para recuperar el entorno del proyecto en este servidor.

## Servidor actual

- Host Tailscale: `learroyo-macmini7-1`
- IP Tailscale: `100.105.88.51`
- IP LAN reservada objetivo: `192.168.0.2`
- Dominio ECOE publicado: `ecoe.drnotus.cl`

## Stack actual

- `ecoe-db`
- `ecoe-backend`
- `ecoe-frontend`
- `nginx` del sistema como reverse proxy publico

## Exposicion real

Docker no expone servicios a la LAN:

- `127.0.0.1:3000 -> frontend`
- `127.0.0.1:8000 -> backend`
- `127.0.0.1:5432 -> postgres`

La salida publica la hace `nginx`, no Docker.

## Proxy del servidor

Archivo relevante:

- `/etc/nginx/sites-available/drnotus-multisite`

Host de ECOE:

- `ecoe.drnotus.cl` -> proxy a `127.0.0.1:3000`
- `ecoe.drnotus.cl/api/` -> proxy a `127.0.0.1:8000`

## Reglas criticas del router

Para que Cloudflare llegue al origen:

- `TCP 80 -> 192.168.0.2:80`
- `TCP 443 -> 192.168.0.2:443`

Error detectado en marzo 2026:

- el router reenviaba a `102.168.0.18`
- eso provocaba `Cloudflare 523 Origin is unreachable`

## DNS esperado en Cloudflare

Minimo recomendado:

- `A @ -> 190.160.164.137` proxied
- `CNAME www -> drnotus.cl` proxied
- `A ecoe -> 190.160.164.137` proxied
- `A transcripcion -> 190.160.164.137` proxied

Evitar:

- registros `AAAA` inventados apuntando a IPs de Cloudflare

## Recuperacion tras corte de luz

1. Verificar que Docker este activo.
2. Verificar que el router mantenga la IP del servidor en `192.168.0.2`.
3. Verificar NAT `80/443 -> 192.168.0.2`.
4. Confirmar que `nginx` este activo.
5. Confirmar que el stack este arriba.

Comandos utiles:

```bash
docker compose ps
curl -s http://127.0.0.1:8000/health
wget -qO- --server-response http://127.0.0.1:3000 2>&1 | head -n 1
systemctl is-active nginx
systemctl is-active docker
```

## Reinicio automatico

Los servicios del proyecto quedaron con:

- `restart: unless-stopped`

en `docker-compose.yml`, por lo que deben volver tras reboot si Docker arranca normalmente.

Verificado en este servidor:

- `systemctl is-enabled docker` -> `enabled`
- `systemctl is-active docker` -> `active`
- `systemctl is-enabled nginx` -> `enabled`
- `systemctl is-active nginx` -> `active`

## Flujo de acceso seguro para desarrollo

Desde el Mac:

```bash
ssh ecoe-dev
```

Ese alias debe levantar tuneles a:

- `localhost:3000`
- `localhost:8000`
- `localhost:5432`

## Nota operativa

El endurecimiento actual protege el proyecto en LAN e internet directa. La exposicion publica depende del reverse proxy del sistema y del router, no del bind de Docker.

## Backups (C6)

- El servicio `db-backup` de `docker-compose.yml` hace `pg_dump` diario a `./backups/ecoe-YYYYMMDD-HHMMSS.sql.gz` con rotacion de 14 dias.
- Antes de cada ECOE real: forzar un backup manual con
  `docker exec ecoe-db pg_dump -U ecoe ecoe | gzip > backups/ecoe-pre-evento-$(date +%Y%m%d).sql.gz`
- Copia fuera del servidor: sincronizar `backups/` a otro equipo/nube (rsync/rclone) — pendiente de configurar destino.
- Restore: `./scripts/restore_db.sh backups/<archivo>.sql.gz` (detiene backend, recrea la BD, restaura, levanta backend). Probar el restore al menos una vez por semestre.
- El storage multimedia vive en el volumen `ecoe_backend_storage`; respaldarlo con
  `docker run --rm -v ecoe_backend_storage:/s -v $(pwd)/backups:/b alpine tar czf /b/storage-$(date +%Y%m%d).tar.gz -C /s .`

## Deploy con los cambios de hardening (2026-07-08)

1. `docker compose build backend frontend`
2. `docker compose up -d` (la migracion `d4e5f6a7b8c9` se aplica sola al arrancar)
3. El volumen de storage ya quedo con owner uid 1000 (backend ahora corre no-root).
4. `backend/.env` ya define `ENVIRONMENT=production` y `AUTO_SEED_DEMO=false`.

## Investigacion de WebSocket del panel en vivo (2026-07-08) — correccion

Durante el trabajo del item de calidad #11 se sospecho inicialmente un bug
de compatibilidad `uvicorn`+`websockets` en el backend, a partir de un
`HTTP 403` observado al probar `/api/ws/live/{id}` sin autenticacion.
**Esa sospecha era incorrecta** y quedo descartada tras escribir
`tests/test_live_timer.py::TestLiveTimerWebSocket`, que conecta con una
sesion autenticada real y confirma que el timer llega correctamente:
el `403` era el comportamiento esperado de uvicorn al recibir
`websocket.close()` antes de `websocket.accept()` (exactamente lo que hace
el codigo cuando falta el token), no una falla de la libreria. Se
reverifico manualmente con `websockets==16.0` y `websockets==13.1`: ambas
versiones pasan el mismo test autenticado. `backend/requirements.txt`
mantiene el pin `websockets<14` solo porque es la version efectivamente
probada extremo a extremo, no porque exista una incompatibilidad real.

Lo unico que sigue siendo una recomendacion valida (no verificada contra
el servidor real, pero es requisito documentado de nginx): el bloque
`location /api/` de la config publica no reenviaba los headers
`Upgrade`/`Connection: upgrade` (solo `location /` los tenia), lo cual
nginx necesita explicitamente para proxyar cualquier WebSocket. Ya
corregido en la copia de referencia `datos_proyecto/nginx_ecoe_publico.conf`.

**Accion pendiente del usuario (opcional, buena practica, no bloqueante):**
el nginx real que sirve `ecoe.drnotus.cl` corre como servicio del sistema
(fuera de Docker, fuera de este repo) — aplicar el mismo cambio a su
archivo de configuracion real (probablemente en `/etc/nginx/sites-enabled/`
o similar) y ejecutar `sudo nginx -t && sudo systemctl reload nginx`. No se
modifico automaticamente por ser infraestructura compartida fuera del
alcance de este repositorio.
