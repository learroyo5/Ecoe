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

## Sesion 2026-10-09 — Auditoria UX de la intranet (UX-1..UX-7)

Auditoria de navegacion, barra lateral y flujos (`docs/optimizacion/hallazgos/auditoria-ux-navegacion__2026-10-09.md`) e implementacion completa en 7 ramas apiladas, solo frontend, sin migraciones ni cambios de permisos. Triage y estado en `docs/optimizacion/BACKLOG.md` (Grupo D).

- `ux/01-consistencia`: `useConfirm()` (modal propio en vez de `window.confirm`), etiquetas legibles de estado/tipo, tuteo, tildes.
- `ux/02-encabezado`: titulo por pantalla; barra "ECOE activo" con estado y fecha; confirmacion al cambiar de ECOE en ejecucion.
- `ux/03-barra-lateral`: `NAV_ITEMS` con `group`/`icon`/`hidden`; barra agrupada por fase, scroll propio, activo por prefijo. `allowedFor` identico a `main`.
- `ux/04-inicio`: fases del ciclo + "Siguiente paso" (`lib/ecoe-cycle.ts`).
- `ux/05-gestion-ecoe`: `/ecoe` con pestanas y dialogo de creacion; `/ecoe/[id]` redirige a `/ecoe`; el shell se refresca tras cada cambio de estado.
- `ux/06-dia-examen`: pantalla `/kiosks` (todos los enlaces de una vez) y controles del panel en vivo deshabilitados segun estado (`lib/live-controls.ts`).
- `ux/07-resultados`: Resultados en pestanas; incluye ademas el ajuste del e2e al modal propio y la correccion de contraste del item activo.

Verificacion sobre `ux/07-resultados`: `tsc` limpio, `eslint` sin errores (2 avisos previos en `media-preview.tsx`), 127 tests vitest, `next build`, y flujo dorado Playwright 5/5 contra el stack e2e desechable. Backend sin cambios (no se corrio pytest).

Mergeado a `main` (`3397cb4`) y desplegado el 2026-10-09 (solo se reconstruyo `ecoe-frontend`; backend y BD sin tocar). La imagen anterior quedo etiquetada `ecoe-frontend:pre-ux-2026-10-09` por si hay que volver atras.

Node en el host (2026-10-09): Node 22 instalado a nivel de usuario con nvm (`~/.nvm`), con enlaces `node`/`npm`/`npx` en `~/.local/bin` para shells no interactivos. `npm run lint`, `npm test` y `npm run build` ya corren directo en `frontend/`. `./scripts/run_e2e.sh` tambien corre nativo (4/4 del flujo dorado) tras instalar las librerias del sistema de Chromium con `sudo env "PATH=$HOME/.local/bin:$PATH" npx playwright install-deps chromium` (`sudo` no ve el `npx` del usuario sin pasarle el PATH).

## Sesion 2026-10-09 (b) — Auditoria del proceso ECOE

Ramas `ux/01…07` borradas (local y remoto) tras el merge. Auditoria de coherencia, flujos, perdida de informacion, zonas sin cubrir y seguridad sobre backend + BD + frontend: `docs/optimizacion/hallazgos/auditoria-proceso-ecoe__2026-10-09.md`, 21 hallazgos (PROC-1…21) en el Grupo E de `docs/optimizacion/BACKLOG.md`, todos en estado `nuevo`. Incluye una propuesta de coordinacion de personas y dispositivos para el dia del examen. Nada implementado: espera triage del usuario.

Lo mas urgente antes de cualquier prueba con personas: PROC-1 (confirmar al estudiante durante la transicion le autoenvia la estacion en blanco) y PROC-4 (la clave de respuestas viaja al dispositivo del estudiante).

## Sesion 2026-10-09 (c) — Correcciones de la auditoria de proceso (PROC + coordinacion)

Seis ramas apiladas, **sin merge ni deploy** (decision del usuario; incluyen 3 migraciones Alembic: `r8s9t0u1v2w3`, `s9t0u1v2w3x4`, `t0u1v2w3x4y5`, todas aditivas y sin backfill):

- `proc/01-transicion-y-clave`: check-in en transicion/pausa pertenece a la fase siguiente; el formulario llega al estudiante sin la clave; confirmar al siguiente conserva el borrador del anterior.
- `proc/02-anulacion-y-contingencia`: anular ingreso, aviso de estudiante en otra estacion de la misma rotacion, contingencia sustituye autoenvios y rectifica evaluaciones; pantalla `/contingency`.
- `proc/03-candados-por-estado`: `services/event_lock.py` (estructura bloqueada desde `publicado`, todo congelado en `cerrado`/`archivado`), 409 legibles, AuditLog de estructura.
- `proc/04-cierre`: cierre bloqueado con incompletos (forzable → 0), reapertura `cerrado → en_ejecucion` (admin, motivo, auditada), `archivado` terminal, acta con identidad.
- `proc/05-vivo-y-validacion`: LiveSession limpia al iniciar ejecucion, pausa que recuerda la fase, puntaje del evaluador validado contra la pauta, rondas por circuito espejo, vacios de validacion.
- `proc/06-tablero-en-vivo`: senal de vida de kioscos/evaluadores, `GET /live/{id}/board`, verificacion previa y tablero en `/live`.

Verificacion sobre `proc/06-tablero-en-vivo`: backend 503 tests en SQLite y en PostgreSQL con migraciones (eran 429); frontend `tsc`/`eslint` sin errores, 136 tests (eran 127), y flujo dorado Playwright 5/5.

Cambios de comportamiento que afectan la operacion (ya reflejados en `docs/OPERACION_DIA_EXAMEN.md`): desde `publicado` no se edita estructura (hay que despublicar); el cierre exige resolver incompletos o forzarlo; el check-in avisa por otra estacion u otro circuito; el circuito automatico cuenta rondas por circuito.

Pendiente: plan de rotacion generado (COORD-3), respaldo frecuente en ejecucion (COORD-4), identificacion del estudiante en kiosco para estaciones sin evaluador (PROC-12), y los de severidad baja PROC-17/18/20. Para correr pytest en este servidor: contenedor `ecoe-backend` + pytest (no hay pytest en el host).

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
