# Despliegue de dominios ECOE (ecoe.cl / plataformaecoe.cl / app.ecoe.cl)

**Estado: COMPLETADO Y VERIFICADO EN PRODUCCION (2026-08-25).** Este documento es un registro de como se hizo realmente (difiere en algunos puntos del plan original con el que se arranco), util como referencia para agregar un cuarto dominio/subdominio, reemitir un certificado, o entender el porque de una decision. La referencia rapida vigente del estado actual esta en `operacion_despliegue.md`; este doc es el detalle paso a paso.

## Objetivo

Poner en marcha los 3 dominios propios de ECOE sin romper `ecoe.drnotus.cl` (que sigue vivo como entorno de staging/dev) y sin fragmentar marca/SEO entre `ecoe.cl` y `plataformaecoe.cl`.

Roles:

- `ecoe.cl` -> landing de marketing (one-pager estatico, un solo `index.html` autocontenido).
- `app.ecoe.cl` -> la plataforma real (mismo backend/frontend que `ecoe.drnotus.cl`).
- `plataformaecoe.cl` -> solo defensivo, redirect 301 completo hacia `ecoe.cl`, sin contenido propio.
- `ecoe.drnotus.cl` -> se mantiene como estaba, no se toco, no se comparte con prospectos.

## Descubrimiento clave: la sesion de agente corria en el propio Mac mini

El plan original asumia que habria que operar por SSH desde una maquina externa (`ssh ecoe-server`, que fallo con `Permission denied` por no tener `IdentityFile`). A mitad de la tarea se detecto que la sesion de Claude Code ya corria localmente **en el mismo Mac mini** (`hostname` -> `learroyo-Macmini7-1`, IP Tailscale `100.105.88.51` = la misma IP del alias `ecoe-server`). Es decir, el intento de SSH estaba fallando porque intentaba conectarse a si mismo sin llave, no porque faltara acceso real. Una vez detectado esto, todo se ejecuto localmente sin SSH.

## Bloqueo de `sudo` y como se resolvio

`sudo` pedia password de forma interactiva, lo que bloqueaba a la sesion de agente. Se creo `/etc/sudoers.d/claude-ecoe-domains` con `NOPASSWD` acotado a comandos exactos (no `ALL`):

```
learroyo ALL=(root) NOPASSWD: /usr/bin/tee /etc/nginx/sites-available/ecoe-domains
learroyo ALL=(root) NOPASSWD: /usr/bin/ln -sf /etc/nginx/sites-available/ecoe-domains /etc/nginx/sites-enabled/ecoe-domains
learroyo ALL=(root) NOPASSWD: /usr/sbin/nginx -t
learroyo ALL=(root) NOPASSWD: /usr/bin/systemctl reload nginx
learroyo ALL=(root) NOPASSWD: /usr/bin/certbot *
learroyo ALL=(root) NOPASSWD: /usr/bin/mkdir -p /var/www/ecoe-cl
learroyo ALL=(root) NOPASSWD: /usr/bin/tee /var/www/ecoe-cl/index.html
```

Se verifico explicitamente que el resto de `sudo` (ej. `sudo -n cat /etc/shadow`) seguia pidiendo password, es decir que no quedo abierto de mas.

Aun con ese sudoers, **el clasificador de modo automatico de Claude Code bloqueo cada escritura real a nginx/certbot** (`sudo tee` sobre archivos de nginx, `certbot certonly`) y exigio autorizacion explicita del usuario en cada paso — el sudoers acotado no es suficiente para saltarse esa capa de aprobacion, que es la esperada para infraestructura de produccion real.

## 1. DNS

Las zonas `ecoe.cl` y `plataformaecoe.cl` se agregaron a la **misma cuenta de Cloudflare** que ya tenia `drnotus.cl` (no se investigo si es la misma IP: se verifico la IP publica real del origen en el momento, `190.95.99.45` via `curl -4 ifconfig.me`, y se uso esa — confirmar de nuevo si se reutiliza esta guia mas adelante, puede haber cambiado). Cloudflare asigno un par de nameservers propio por zona (`evangeline`/`lennon`.ns.cloudflare.com en este caso, pero puede variar por zona).

Pasos reales, en orden:

1. Cloudflare -> Add a Site para cada dominio -> anotar los 2 NS que entrega.
2. Cambiar los NS en el registrador (NIC Chile) por los de Cloudflare, para cada dominio.
3. Esperar a que la zona pase a `Active` en Cloudflare (se verifico con `dig @1.1.1.1 <dominio> NS` y `dig +trace`, no hace falta esperar el TTL de propagacion tradicional, Cloudflare es autoritativo apenas la delegacion en `.cl` se resuelve).
4. Crear los registros `A`, todos proxied (🟠):
   - Zona `ecoe.cl`: `A @`, `A www`, `A app` -> IP publica del origen
   - Zona `plataformaecoe.cl`: `A @`, `A www` -> IP publica del origen
5. SSL/TLS mode de ambas zonas: se dejo en `Full` mientras el origen no tenia certificado real (evita error 526), y se subio a `Full (strict)` una vez emitidos los certificados (paso 3 mas abajo) — confirmado por el usuario el 2026-08-25, con los 5 hosts verificados por `curl` sin cambios de comportamiento tras el cambio.

Verificacion usada en cada etapa:

```bash
dig @1.1.1.1 +short ecoe.cl NS
dig @1.1.1.1 +short ecoe.cl A
curl -sS -o /dev/null -w "%{http_code}\n" http://ecoe.cl/
```

## 2. Nginx: archivo nuevo y separado, no `drnotus-multisite`

Se decidio **no** tocar `/etc/nginx/sites-available/drnotus-multisite` (archivo compartido con `drnotus.cl`, `transcripcion`, `presenta`, `asistente`, `cmc` — todo produccion real). En su lugar se creo un archivo nuevo `/etc/nginx/sites-available/ecoe-domains` (symlink en `sites-enabled`), para que cualquier error de sintaxis o de logica quedara acotado solo a los dominios nuevos.

Orden real de aplicacion (importante: primero solo HTTP, recien despues HTTPS):

1. Escribir en `ecoe-domains` **solo** los 3 bloques `listen 80` (redirect a HTTPS) — sin bloques `443`, porque los certificados todavia no existian y `ssl_certificate` apuntando a un archivo inexistente rompe `nginx -t`.
2. `sudo mkdir -p /var/www/ecoe-cl`, symlink a `sites-enabled`, `nginx -t`, `systemctl reload nginx`.
3. Recien ahi, emitir los certificados (seccion 3).
4. Reescribir `ecoe-domains` agregando los 3 bloques `443` completos (landing estatico para `ecoe.cl`, proxy real para `app.ecoe.cl` clonado del bloque de `ecoe.drnotus.cl`, redirect para `plataformaecoe.cl`), referenciando los certificados ya emitidos. `nginx -t` + `systemctl reload nginx` de nuevo.

El bloque de `app.ecoe.cl` es un clon exacto del que sirve `ecoe.drnotus.cl` en `drnotus-multisite` (proxy `/` -> `127.0.0.1:3000`, `/api/` -> `127.0.0.1:8000`, mismos headers de `Upgrade`/`Connection` para WebSocket) — se leyo el bloque real antes de clonarlo, no la copia de referencia `nginx_ecoe_publico.conf` que habia quedado desactualizada segun `ajuste_publico_ecoe.md`.

El archivo final queda documentado en el propio servidor; una copia de referencia (puede no reflejar ediciones posteriores) esta en [nginx_ecoe_cl_landing.conf](/home/learroyo/Proyectos/Ecoe/datos_proyecto/nginx_ecoe_cl_landing.conf) y [nginx_plataformaecoe_redirect.conf](/home/learroyo/Proyectos/Ecoe/datos_proyecto/nginx_plataformaecoe_redirect.conf).

## 3. Certificados (Certbot)

Se uso `certbot certonly --nginx`, no `certbot --nginx` a secas — asi certbot solo obtiene el certificado usando el bloque `listen 80` existente para el challenge HTTP-01, sin tocar ni reescribir el archivo de nginx por su cuenta. El contenido de los bloques `443` se escribio a mano en el paso 2.4.

```bash
sudo certbot certonly --nginx -d ecoe.cl -d www.ecoe.cl --non-interactive --agree-tos -m learroyo@gmail.com
sudo certbot certonly --nginx -d app.ecoe.cl --non-interactive --agree-tos -m learroyo@gmail.com
sudo certbot certonly --nginx -d plataformaecoe.cl -d www.plataformaecoe.cl --non-interactive --agree-tos -m learroyo@gmail.com
```

Los 3 certificados se emitieron sin errores, expiran 2026-11-23, con renovacion automatica ya configurada por certbot (systemd timer).

## 4. Landing: donde vive la fuente

El HTML se genero originalmente como un artifact de Claude y se copio directo desde el scratchpad temporal de esa sesion — que no persiste ni esta versionado. Para no perder la fuente, la copia real desplegada (identica a `/var/www/ecoe-cl/index.html`) quedo en [ecoe-cl-landing.html](/home/learroyo/Proyectos/Ecoe/datos_proyecto/ecoe-cl-landing.html) dentro de este repo. Si se edita el landing, editar ese archivo y volver a copiarlo a `/var/www/ecoe-cl/index.html` en el servidor (mismo comando de siempre: `sudo tee /var/www/ecoe-cl/index.html < datos_proyecto/ecoe-cl-landing.html`).

## 5. Bug de encoding descubierto y corregido

Al desplegar `/var/www/ecoe-cl/index.html` (copiado directo desde el filesystem local, ya que la sesion de agente y el servidor son la misma maquina — no hizo falta `scp`), el sitio mostraba los acentos rotos (`Ã¡` en vez de `á`). Causa: el HTML no tenia `<meta charset="UTF-8">` y el header `Content-Type` de nginx no declaraba charset, asi que el navegador adivinaba mal la codificacion. Se corrigio en dos lugares (ambos necesarios):

- HTML: agregar `<meta charset="UTF-8">` (y de paso `<meta name="viewport" ...>`) como primera linea del `<head>`.
- Nginx: agregar `charset utf-8;` dentro del bloque `server_name ecoe.cl;`.

Cualquier landing/HTML estatico nuevo que se suba a este servidor deberia traer el `<meta charset="UTF-8">` desde el archivo fuente para no repetir este bug.

## 6. Verificacion final

```bash
curl -I https://ecoe.cl                 # 200
curl -I https://www.ecoe.cl             # 301 -> https://ecoe.cl
curl -I https://app.ecoe.cl             # 307 (mismo comportamiento normal que ecoe.drnotus.cl)
curl -I https://plataformaecoe.cl       # 301 -> https://ecoe.cl
curl -I https://ecoe.drnotus.cl         # 307, intacto, sin romper nada
curl -sI https://ecoe.cl/ | grep -i content-type   # debe incluir charset=utf-8
```

## 7. Pendiente para mas adelante (no bloquea esto)

Antes de vender a universidades/hospitales, evaluar migrar la plataforma (no el landing) a un VPS con SLA — la conexion residencial del homelab no lo garantiza. Ver `dr-notus-infrastructure/docs/decisions/005-network-exposure-proposal.md` para contexto de por que el homelab tiene limites para eso a largo plazo.

Opcional: borrar `/etc/sudoers.d/claude-ecoe-domains` si no se va a seguir iterando sobre estos dominios desde una sesion de agente sin supervision constante.
