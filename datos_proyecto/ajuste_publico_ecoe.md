# Ajuste publico de ECOE en Dr. Notus

## Objetivo

Dejar `ecoe.drnotus.cl` funcionando como producto independiente, sin loop HTTPS y con una sola entrada publica de API en `/api`.

## Estado ya aplicado en el proyecto

Se actualizo la aplicacion para usar:

- frontend -> `/api`
- archivos multimedia -> `/api/media/file/:id`
- exports -> `/api/results/...`
- rewrite interno de Next -> `/api/*` hacia `http://backend:8000/api/*`

## Ajuste pendiente en Nginx

No pude aplicarlo directamente desde esta sesion porque el archivo de Nginx requiere `sudo`.

Usa como bloque de referencia:

- [nginx_ecoe_publico.conf](/home/learroyo/Proyectos/Ecoe/datos_proyecto/nginx_ecoe_publico.conf)

## Cambios que debes hacer en `/etc/nginx/sites-available/drnotus-multisite`

1. Eliminar `ecoe.drnotus.cl` del bloque HTTPS redirigido por Certbot.

Actualmente esta mezclado en un bloque multi-host que hace:

- `return 301 https://$host$request_uri`

Eso provoca loop en `https://ecoe.drnotus.cl`.

2. Eliminar `ecoe.drnotus.cl` del bloque final de `listen 80` que hoy devuelve `404`.

3. Mantener o reemplazar el bloque propio de ECOE por el contenido de:

- [nginx_ecoe_publico.conf](/home/learroyo/Proyectos/Ecoe/datos_proyecto/nginx_ecoe_publico.conf)

## Secuencia sugerida

```bash
sudo cp /etc/nginx/sites-available/drnotus-multisite /etc/nginx/sites-available/drnotus-multisite.bak.$(date +%F-%H%M%S)
sudo nano /etc/nginx/sites-available/drnotus-multisite
sudo nginx -t
sudo systemctl reload nginx
```

## Verificaciones

```bash
curl -I http://ecoe.drnotus.cl
curl -I https://ecoe.drnotus.cl
curl -I https://ecoe.drnotus.cl/api/health
```

Resultado esperado:

- `http://ecoe.drnotus.cl` -> `301` a `https://ecoe.drnotus.cl`
- `https://ecoe.drnotus.cl` -> `200`
- `https://ecoe.drnotus.cl/api/health` -> `200`
