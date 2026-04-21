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
