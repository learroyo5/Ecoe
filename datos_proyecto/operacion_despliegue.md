# Operacion y Despliegue

Referencia rapida para recuperar el entorno del proyecto en este servidor.

## Servidor actual

- Host Tailscale: `learroyo-macmini7-1`
- IP Tailscale: `100.105.88.51`
- IP LAN reservada objetivo: `192.168.0.2`
- Dominio ECOE de staging/dev (no se comparte con prospectos): `ecoe.drnotus.cl`
- Dominios propios de producto, en produccion desde 2026-08-25: `ecoe.cl` (landing), `app.ecoe.cl` (plataforma), `plataformaecoe.cl` (solo redirect 301 a `ecoe.cl`) — ver detalle abajo y en `despliegue_dominios_ecoe.md`

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

Archivos relevantes:

- `/etc/nginx/sites-available/drnotus-multisite` — todo `*.drnotus.cl` (drnotus.cl, transcripcion, presenta, asistente, cmc, **ecoe.drnotus.cl**). No tocar para nada de ECOE.CL.
- `/etc/nginx/sites-available/ecoe-domains` — archivo separado, solo para `ecoe.cl` / `app.ecoe.cl` / `plataformaecoe.cl`. Se separo a proposito de `drnotus-multisite` para no arriesgar el resto de produccion al tocar dominios nuevos.

Host de ECOE (staging/dev):

- `ecoe.drnotus.cl` -> proxy a `127.0.0.1:3000`
- `ecoe.drnotus.cl/api/` -> proxy a `127.0.0.1:8000`

Dominios propios de producto (3 roles distintos, solo uno toca el backend):

- `ecoe.cl` (+`www`) -> **estatico, sin backend**, `root /var/www/ecoe-cl/index.html` (landing de marketing, un solo archivo HTML autocontenido; incluye `charset utf-8` explicito en el bloque nginx y `<meta charset="UTF-8">` en el HTML porque sin eso los acentos se ven mal, `Ã¡` en vez de `á`)
- `app.ecoe.cl` -> **la plataforma real**, proxy a `127.0.0.1:3000`, `/api/` -> `127.0.0.1:8000` (clon exacto del bloque de `ecoe.drnotus.cl`, mismo backend/frontend Docker)
- `plataformaecoe.cl` (+`www`) -> **sin backend, sin contenido propio**, `return 301 https://ecoe.cl$request_uri`

Certificados Let's Encrypt independientes por dominio (`certbot certonly --nginx`, no `certbot --nginx` a secas — asi no modifica el bloque automaticamente y se controla el contenido a mano):

- `/etc/letsencrypt/live/ecoe.cl/`
- `/etc/letsencrypt/live/app.ecoe.cl/`
- `/etc/letsencrypt/live/plataformaecoe.cl/`

Expiran 2026-11-23, renovacion automatica ya configurada por certbot (`systemctl list-timers | grep certbot`).

### DNS de ecoe.cl / plataformaecoe.cl

A diferencia del router-forwarding descrito abajo para `drnotus.cl`, estos dos dominios se agregaron como zonas nuevas en la **misma cuenta de Cloudflare**: NS delegados en el registrador, registros `A` proxied (🟠) para `ecoe.cl`, `www`, `app`, `plataformaecoe.cl`, `www.plataformaecoe.cl` apuntando a la IP publica del origen (ver nota de IP mas abajo).

SSL/TLS mode de esas zonas: `Full (strict)`, confirmado por el usuario el 2026-08-25 (se dejo en `Full` durante el despliegue mientras el origen no tenia certificado real, y se subio a `Full (strict)` una vez emitidos los 3 certificados). Verificado con `curl` que los 5 hosts siguen respondiendo igual (`ecoe.cl` 200, `www.ecoe.cl`/`plataformaecoe.cl`/`www.plataformaecoe.cl` 301, `app.ecoe.cl` 307) tras el cambio.

### Permisos usados para aplicar esto sin password interactivo

`/etc/sudoers.d/claude-ecoe-domains` con `NOPASSWD` acotado a comandos exactos: `tee` sobre `ecoe-domains` y `/var/www/ecoe-cl/index.html`, `ln -sf` del symlink a `sites-enabled`, `nginx -t`, `systemctl reload nginx`, `certbot *`, `mkdir -p /var/www/ecoe-cl`. No es `NOPASSWD: ALL` — el resto de `sudo` (ej. leer `/etc/shadow`) sigue pidiendo password. Se puede borrar (`sudo rm /etc/sudoers.d/claude-ecoe-domains`) si no se va a seguir iterando sobre estos dominios desde una sesion de agente.

## Reglas criticas del router

Para que Cloudflare llegue al origen:

- `TCP 80 -> 192.168.0.2:80`
- `TCP 443 -> 192.168.0.2:443`

Error detectado en marzo 2026:

- el router reenviaba a `102.168.0.18`
- eso provocaba `Cloudflare 523 Origin is unreachable`

## DNS esperado en Cloudflare

Zona `drnotus.cl`, minimo recomendado:

- `A @ -> 190.160.164.137` proxied
- `CNAME www -> drnotus.cl` proxied
- `A ecoe -> 190.160.164.137` proxied
- `A transcripcion -> 190.160.164.137` proxied

Zonas nuevas `ecoe.cl` y `plataformaecoe.cl` (mismo origen fisico que `drnotus.cl` arriba):

- `ecoe.cl`: `A @`, `A www`, `A app` -> IP publica del origen, proxied
- `plataformaecoe.cl`: `A @`, `A www` -> IP publica del origen, proxied

**Nota sobre la IP:** al desplegar estos dos dominios (2026-08-25) la IP publica real del origen era `190.95.99.45` (verificada con `curl -4 ifconfig.me` desde el propio servidor), distinta de `190.160.164.137` que aparece arriba para `drnotus.cl`. Es la misma conexion residencial — la IP publica no es estatica y cambio entre cuando se documento `drnotus.cl` y ahora. **No asumir ninguna de las dos IPs como vigente, y ojo con como verificarlo**: como todos los dominios (`drnotus.cl` incluido) estan proxied (🟠) en Cloudflare, `dig <dominio> +short` **nunca** muestra la IP real del origen, solo IPs anycast de Cloudflare (`104.21.x.x`/`172.67.x.x`) — no sirve para detectar si la IP del origen cambio. Para verificar de verdad: `curl -4 ifconfig.me` desde el propio servidor, y comparar ese valor contra el contenido real del registro `A` en el dashboard de Cloudflare (DNS -> click en el registro) para cada zona. Si no coincide, la IP cambio y hay que actualizar el valor del registro `A` en todas las zonas, no solo en las nuevas.

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
