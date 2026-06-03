# Project Status

## Proyecto

- Nombre: `Proyecto Tecnologico ECOE`
- Objetivo: plataforma web para planificacion, pilotaje, ejecucion, contingencia y cierre de ECOE/OSCE para carreras de la salud.
- Estado actual: `v2 funcional`

## Estado general

La v2 del producto esta completa: CRUD del ECOE con transiciones de estado guiadas, constructor de estaciones con multimedia, panel en vivo con WebSocket, gestion de incidencias en tiempo real, y suite de tests (23/23 pasando). El proyecto corre con Docker Compose en este servidor, tiene salida publica por `nginx` y esta listo para seguir evolucionando desde la rama `main`.

## Arquitectura implementada

- Frontend:
  - Next.js con App Router
  - TypeScript
  - Tailwind CSS
  - layout con menu lateral y pantallas operativas
  - ruta dinamica `/ecoe/[id]` para vista de detalle
- Backend:
  - FastAPI
  - SQLAlchemy ORM
  - Pydantic
  - WebSocket para tiempo real
  - autenticacion JWT (cookie + Bearer) por rol
  - migraciones Alembic
  - tests con pytest + SQLite
- Base de datos:
  - PostgreSQL en Docker Compose
- Infraestructura:
  - `frontend`, `backend` y `db` separados en `docker-compose.yml`

## Modulos implementados

- Autenticacion:
  - login con JWT (cookie + Bearer)
  - sesion por token
  - proteccion por rol
  - panel de gestion de usuarios (admin)
- Gestion ECOE:
  - listado con selector de ECOE activo
  - formulario completo en 3 secciones con validacion frontend
  - transiciones de estado guiadas con modales de confirmacion
  - duplicado con opcion de copiar evaluadores y estaciones
  - vista de detalle `/ecoe/[id]` con 4 tabs (General, Estaciones, Participantes, Pilotajes)
- Estudiantes:
  - alta manual
  - importacion CSV/Excel
  - listado con paginacion
- Evaluadores y colaboradores:
  - alta manual
  - importacion CSV/Excel
  - listado con paginacion
- Estaciones:
  - listado con cards y badges de estado
  - constructor con 4 pasos guiados
  - edicion de estaciones existentes
  - asociacion de plantilla, instrumento y paciente simulado
  - upload de multimedia con preview inline (MediaPreview)
- Banco de plantillas
- Banco de instrumentos
- Gestor de paciente simulado
- Pilotaje:
  - creacion
  - listado
  - archivado
  - separacion de datos de prueba
- Panel en vivo:
  - cronometro central sincronizado via WebSocket
  - start/pause/resume/reset/transition
  - broadcast de estado en tiempo real a todos los clientes
- Incidencias:
  - creacion rapida con severidad (baja/media/alta/critica)
  - resolucion y reapertura
  - broadcast en tiempo real via WebSocket
  - contadores de activas/resueltas
- Interfaz evaluador:
  - identificacion de estudiante
  - render dinamico de instrumentos (checklist + puntaje numerico)
  - bloqueo efectivo por tiempo (timer rojo, campos deshabilitados)
- Interfaz estudiante:
  - identificacion por numero ECOE
  - formulario dinamico (3 tipos de pregunta)
  - auto-guardado local y envio automatico al expirar el tiempo
  - visualizacion de multimedia
- Resultados:
  - consolidacion automatica
  - porcentaje
  - nota equivalente
  - exportacion Excel
  - exportacion PDF de contingencia

## Datos demo cargados

- 1 ECOE de ejemplo
- 5 estaciones
- 10 estudiantes
- 3 evaluadores/colaboradores
- 1 paciente simulado
- 1 pilotaje

## Verificaciones ya realizadas

- `npm run build`
- 23 tests backend con `pytest` cubriendo: health, auth, CRUD ECOE, estaciones, incidencias (crear/resolver/reabrir), paginacion, seguridad de archivos
- `docker compose up --build -d`
- acceso UI por red local
- acceso backend por healthcheck y endpoints autenticados
- verificacion local de `http://127.0.0.1:3000`
- verificacion local de `http://127.0.0.1:8000/health`
- verificacion publica de `https://ecoe.drnotus.cl`
- verificacion publica de `https://ecoe.drnotus.cl/api/health`

## Decisiones importantes tomadas

- El frontend consume la API mediante proxy interno (`/backend/api`) para evitar romper acceso desde otras maquinas de la red.
- La persistencia usa migraciones Alembic + creacion automatica de tablas en startup como respaldo.
- El control de permisos es por rol, simple y claro, sin ACL avanzada.
- El cronometro es manual y operativo, sincronizado entre clientes via WebSocket.
- Pilotaje y ejecucion real estan separados a nivel de modelo y registros.
- Las incidencias se transmiten en tiempo real via WebSocket.
- El storage path de multimedia es configurable via `STORAGE_PATH`.

## Limites actuales de esta v2

- No hay reproduccion real de audio integrada en el cronometro; solo estructura preparada.
- No hay ACL avanzada por recurso (solo control por rol).
- No hay backups automatizados de PostgreSQL.
- No hay filtros/buscadores avanzados en las tablas de datos.
- No hay tests de frontend (solo backend).
- La operacion publica depende de configuracion externa de `nginx`, router y Cloudflare, no solo del repo.

## Repo y continuidad

- Repo remoto: `git@github.com:learroyo5/Ecoe.git`
- Rama principal de trabajo: `main`
- Fuente de verdad del proyecto: este repositorio
- Ultimo commit: `cc8b2e2` — feat: evaluator time blocking, tests, Alembic migration, storage path fix

## Recomendacion para continuar en otro servidor

1. Clonar repo desde GitHub.
2. Levantar con Docker Compose.
3. Leer `README.md`, este archivo, `NEXT_STEPS.md` y `datos_proyecto/README.md`.
4. Ejecutar `alembic upgrade head` para asegurar que el schema este al dia.
5. Ejecutar `pytest` para verificar integridad.
6. Continuar por iteraciones pequenas con commit frecuente.
