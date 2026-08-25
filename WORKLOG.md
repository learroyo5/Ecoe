# Worklog

Guia corta para retomar trabajo sin reconstruir contexto desde cero.

## Flujo de sesion recomendado

1. Leer `README.md`.
2. Leer `PROJECT_STATUS.md`.
3. Leer `NEXT_STEPS.md`.
4. Leer `datos_proyecto/README.md`.
5. Revisar `git status --short`.
6. Confirmar que el stack responda con `docker compose ps`.
7. Ejecutar `pytest` para verificar integridad del backend.

## Convencion de trabajo

- Mantener cambios pequenos y verificables.
- Antes de tocar UX o flujo, revisar primero backend y tipos ya existentes.
- Si una nota operativa contradice al codigo activo, manda el codigo y la configuracion vigente.
- Al cerrar una sesion, dejar este archivo actualizado con foco en contexto util, no en detalle historico.
- Correr `npm run build` y `pytest` antes de commitear.

## Ahora mismo

- El despliegue actual funciona localmente y por `https://ecoe.drnotus.cl` (entorno de staging/dev, no se comparte con prospectos).
- Dominios propios en produccion desde 2026-08-25: `https://ecoe.cl` (landing de marketing), `https://app.ecoe.cl` (la plataforma, mismo backend que `ecoe.drnotus.cl`), `https://plataformaecoe.cl` (solo redirect 301 a `ecoe.cl`). Detalle completo en `datos_proyecto/operacion_despliegue.md` y `datos_proyecto/despliegue_dominios_ecoe.md`.
- Las credenciales vigentes del servidor actual estan en `backend/.env` y `datos_proyecto/credenciales_locales.md`.
- Usuario demo: `admin@ecoe.cl` (rol `admin_ecoe`).
- Stack: Next.js + FastAPI + PostgreSQL en Docker Compose, 3 servicios healthy.
- Version actual: `v2` — todas las prioridades altas del plan original completadas.

## Sesion 2026-06-03 — Evolucion v1 → v2

Se completaron las 4 fases planificadas en `NEXT_STEPS.md`:

### Fase 1: CRUD completo del ECOE
- Formulario reorganizado en 3 secciones (Datos generales, Configuracion del circuito, Parametros).
- `circuit_mode` ahora es un select con 4 modos documentados.
- Validacion frontend con errores inline por campo y campos requeridos marcados.
- `StatusTransitionBar`: transiciones de estado con botones y modales de confirmacion.
- Vista de detalle `/ecoe/[id]` con 4 tabs: General, Estaciones, Participantes, Pilotajes.

### Fase 2: Constructor de estaciones
- Listado de estaciones redisenado con cards, badges de estado y boton Editar.
- Selectores de plantilla, instrumento y paciente simulado (ya existian en el builder).
- MediaPreview integrado en la seccion de multimedia del builder.

### Fase 3: Ejecucion en vivo
- WebSocket ya implementado para sincronizacion del cronometro.
- Gestion de incidencias: modelo con `resolved`/`resolved_at`, endpoints POST/PATCH, broadcast WebSocket.
- Frontend: formulario de creacion rapida, cards con severidad, boton resolver/reabrir.

### Fase 4: Evaluacion + Persistencia
- Bloqueo efectivo por tiempo en evaluador: timer rojo, campos deshabilitados al expirar.
- 23 tests backend pasando (auth, ECOE, stations, incidents, pagination, media security).
- Migracion Alembic para `Incident.resolved` + `Incident.resolved_at`.
- Storage path de multimedia ahora usa config (`STORAGE_PATH`) en vez de hardcode `/app/storage`.

### Bugs corregidos
- `create_station`: `station_number` duplicado en `model_dump` + keyword explicito → se excluye del dump.
- Tests: credenciales actualizadas a `admin@ecoe.cl` / `ADMIN_PASSWORD`, rate limiter deshabilitado en tests.

## Proximo paso sugerido

Prioridades actuales (ver `NEXT_STEPS.md` para detalle):
- Mejoras de exportaciones (Excel, PDF).
- Seguridad operativa (logout, expiracion de token).
- UX/UI (tablet, filtros, feedback de guardado).
- Tests de frontend.
