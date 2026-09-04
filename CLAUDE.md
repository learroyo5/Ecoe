# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proyecto

Plataforma web para planificación, pilotaje, ejecución y cierre de ECOE/OSCE (exámenes clínicos objetivos estructurados) en carreras de la salud. Backend FastAPI + SQLAlchemy + PostgreSQL con Alembic; frontend Next.js (App Router) + TypeScript + Tailwind. Docker Compose orquesta `frontend`, `backend` y `db`.

Lectura recomendada antes de cambios estructurales o funcionales, en este orden: `README.md`, `PROJECT_STATUS.md`, `NEXT_STEPS.md`, `datos_proyecto/README.md` (si existe), y `docs/architecture/` para decisiones de fondo (auditoría estructural, plan P0, matriz de permisos).

`AGENTS.md` en la raíz tiene reglas de trabajo adicionales (no exponer secretos de `backend/.env`, no revertir cambios del usuario sin permiso, agregar tests negativos en cambios de seguridad/permisos/auth, preferir commits pequeños y verificables).

## Comandos

### Backend (desde `backend/`)

```bash
# Tests — SQLite rápido por defecto (backend/pytest.ini fija pythonpath=. para que `import app` funcione)
python3 -m pytest                          # toda la suite
python3 -m pytest tests/test_api.py -v     # un archivo
python3 -m pytest tests/test_state_machine_and_modes.py::test_nombre -v   # un test puntual
python3 -m pytest -k "kiosk"               # por coincidencia de nombre

# Los mismos tests contra PostgreSQL real aplicando migraciones Alembic (lo que corre CI)
TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q

# Migraciones
alembic upgrade head
alembic revision --autogenerate -m "descripcion"

# Verificar migraciones desde base limpia sin tocar la BD real
DATABASE_URL=sqlite:////tmp/ecoe_alembic_check.db SECRET_KEY=test-secret ENVIRONMENT=test AUTO_SEED_DEMO=false alembic upgrade head

# Servir localmente
uvicorn app.main:app --reload
```

No hay linter Python configurado (sin ruff/black/flake8/mypy en el repo).

### Frontend (desde `frontend/`)

```bash
npm run dev            # servidor de desarrollo
npm run build           # build de producción (Next.js)
npm run lint            # eslint (eslint-config-next)
npm test                # vitest run — toda la suite unitaria
npx vitest run src/hooks/__tests__/archivo.test.ts   # un archivo puntual
npx vitest run -t "nombre del test"                  # por nombre
```

### E2E (Playwright, flujo dorado)

```bash
./scripts/run_e2e.sh              # levanta docker-compose.e2e.yml (puertos 13001/18001, BD desechable con seed demo), corre Playwright y SIEMPRE derriba el stack al final
./scripts/run_e2e.sh --grep "algo"   # argumentos extra se pasan a `npx playwright test`
```

Este stack e2e nunca debe apuntarse a producción: crea check-ins, evaluaciones y respuestas reales sobre el evento demo (ver comentario en `frontend/playwright.config.ts`).

### Docker Compose (stack completo)

```bash
docker compose up --build          # frontend :3000, backend :8000 (docs en /docs), db
```

En el servidor real, Docker solo expone a `127.0.0.1`; la salida pública va por `nginx` del sistema.

## Arquitectura

### Layout

```
backend/app/
├── api/routes/     # Routers REST + WebSocket (uno por dominio: ecoe, stations, students, staff,
│                   #   evaluator, student_access, kiosk, grading, contingency, invitations, users, auth, operational)
├── core/           # config (pydantic-settings, todo vía env) y security (JWT, hashing)
├── db/             # session, bootstrap y seed_data (datos demo)
├── models/         # SQLAlchemy ORM (entities.py) + enums (enums.py)
├── schemas/        # Pydantic
├── services/       # reglas de negocio: ecoe, validation (máquina de estados), kiosk, grading,
│                   #   results, websocket (live timer), authorization, dependencies (auth deps), invitations, media
└── utils/          # clock (reloj UTC naive centralizado), helpers (gates de envío), files, pagination

frontend/src/
├── app/(app)/...   # pantallas autenticadas por dominio (ecoe, stations, live, evaluator, student, grading, results, ...)
├── app/kiosk/       # modo kiosco (sin login de estudiante, token por estación)
├── components/      # app-shell, ecoe-form (UI de la máquina de estados), data-table, media-preview, confirm-dialog
├── hooks/use-api.ts # carga de datos
└── lib/             # api.ts (cliente HTTP), auth.tsx, ws.ts (WebSocket del timer), routes.ts, types.ts
```

Alembic (`backend/alembic/`) es la única forma soportada de crear/actualizar el schema en producción; `create_all` es un fallback opt-in solo para entornos locales desechables (`ALLOW_CREATE_ALL_FALLBACK=true`, usado por defecto en tests SQLite).

### Máquina de estados del ECOE — autoridad en el backend

El ciclo de vida del ECOE (`borrador → en_configuracion → listo_para_pilotaje → en_pilotaje → pilotaje_validado → publicado → en_ejecucion → cerrado → archivado`, con retrocesos permitidos en varios tramos) vive como grafo en `backend/app/services/validation.py::ALLOWED_STATUS_TRANSITIONS`, consumido por `update_ecoe_status`. Este grafo **debe reflejar** el que ofrece la UI en `frontend/src/components/ecoe-form.tsx` — el backend es la autoridad real: cualquier salto fuera del grafo se rechaza aunque el cliente arme la request a mano. Cambiar uno sin el otro rompe la UX (botones que la UI ofrece pero el backend rechaza) o la seguridad (grafo laxo en backend). Transiciones específicas disparan efectos colaterales dentro de la misma transacción: publicar crea la `LiveSession` inicial y pasa estaciones a `publicada`; entrar a `en_ejecucion` cierra todos los check-ins `confirmado` residuales (son del pilotaje: el gate de envíos no permite check-ins reales antes) para que el panel del evaluador/kiosco no muestre un estudiante viejo como activo ni cuente en la trazabilidad real; cerrar consolida resultados (`persist_results`) y fuerza el cierre de todos los check-ins abiertos, congelando la operación.

### Separación pilotaje/ejecución y gate de envíos

`backend/app/utils/helpers.py` tiene dos funciones clave que no deben confundirse:
- `resolve_session_mode(ecoe_event)`: no-raising, para scoping de lecturas (duplicados, exists).
- `ensure_submission_stage(ecoe_event)`: autoritativo para escrituras (check-ins, evaluaciones, respuestas). Solo acepta `en_pilotaje` o `en_ejecucion`; cualquier otro estado devuelve 409. Esto es lo que impide que un registro de ensayo contamine resultados reales o que se grabe algo mientras el evento está "publicado" pero aún no en ejecución.

El barrido de autoenvío server-side (`services/live_sweep.py::sweep_expired_phases`, OPT-20 F2) respeta este gate: nunca inserta nada fuera de `en_pilotaje`/`en_ejecucion` ni tras `cerrado`/`archivado` (re-lee el estado al arrancar para acotar la carrera contra la transición de cierre), y estampa el modo del evento en cada `StudentResponse` que crea. Las respuestas llevan `submission_kind` (`manual` / `auto` / `contingency`) — lo pone el servidor, nunca el cliente; un `auto` en blanco suma 0 pero queda marcado para la trazabilidad (D4).

### Deadlines autoritativos del servidor

El cronómetro central es autoridad de servidor, no de cliente: `compute_remaining_seconds` (en `helpers.py`) calcula el tiempo restante a partir de `phase_started_at` y el reloj del servidor (`app/utils/clock.py::utcnow_naive`, wrapper de `datetime.now(timezone.utc)` naive) en vez de confiar en el timer del navegador del evaluador/estudiante.

Desde OPT-20 F2 el **deadline de envío de cualquier pantalla operativa se deriva de la fase del `LiveSession`**, no de `confirmed_at + station_time`. `helpers.py::resolve_submission_deadline(db, ecoe_event, checkin, station, *, for_evaluator=False)` es la única fuente:
- `running` → fin de la fase de estación (`phase_started_at + remaining_seconds`); para el evaluador, `+` la duración de la transición (en `transition` real, hasta el fin de esa fase).
- `paused` → `None`: sin deadline efectivo, los envíos se aceptan hasta reanudar (D2: el que entra tarde hereda menos tiempo).
- `round_pause` / `circuit_complete` (M1) → deadline en el pasado: entre rondas nadie está registrado y tras el circuito no hay nada que enviar, cualquier escritura se rechaza.
- sin `LiveSession` o `idle`/`ready` (pilotaje sin operador) → **fallback al Reloj B** (`checkin_submission_deadline`, comportamiento histórico).
`ensure_checkin_within_time` (los 3 call-sites: kiosko, estudiante, evaluador) usa ese helper; contingencia sigue saltándose la ventana. El servidor cierra las ventanas vencidas él mismo (`services/live_sweep.py`), disparado por `/live/control` (`start`/`next_transition`/`reset`/`expire_phase` — esta última es el buzzer: finaliza la fase sin avanzar de estación) y como red de seguridad por un barrido perezoso en los context endpoints operativos que el circuito pollea. El cliente pasa a ser "mejor esfuerzo": empuja su borrador al servidor (`PUT /student/draft`, `PUT /kiosk/draft` → tabla `station_response_drafts`) y trata "ya enviada" como éxito.

**M1 F1 — circuito automático.** Con `LiveSession.auto_mode` activo (acción `/live/control` `enable_auto`, sólo antes de arrancar), `services/live_cycle.py::advance_if_expired` avanza el circuito sin operador: `running(estación i)` → `transition` → `running(i+1)` → … → `running(N)` → `round_pause` (cambio de estudiantes, `ecoe_events.inter_round_pause_minutes`) → `running(1, ronda+1)` → … → `circuit_complete`. Es determinista, idempotente y hace *fast-forward* por varias fases vencidas de una pasada; **no hay scheduler** — lo disparan el polling de los context endpoints (igual que el barrido OPT-20 F2) y `/live/control`. `total_rounds` = ⌈estudiantes_activos / nº estaciones⌉, congelado al `enable_auto`/`start`. El tiempo de transición es **único del evento** (`ecoe_event.transition_time_minutes`), no por estación. `skip_phase` adelanta la fase automática actual; `disable_auto` vuelve al control manual.

**M1 F2 — timbre puntual server-push.** `websocket.py::LiveTimerManager` mantiene un task `asyncio` por evento mientras haya ≥1 cliente WS: despierta en el deadline de la fase (`live_cycle.pump_auto_cycle`), avanza el circuito y hace broadcast de `timer_update` + un frame `phase_bell` (`{type, kind: "start"|"end", station}`). Es **best-effort**: no es autoridad del reloj (lo es `phase_started_at` + el barrido perezoso), sólo hace puntual el timbre y mantiene sincronizadas las pantallas desatendidas entre acciones del operador. `advance_if_expired` toma `SELECT … FOR UPDATE` sobre la `LiveSession` para serializar ticker vs. pollers concurrentes. En el frontend `useLiveTimer` expone `onPhaseBell`; `/live`, `/kiosk` y `/evaluator` lo tocan con `chime()` y silencian su timbre local derivado mientras el server-push está activo (`auto_mode && wsConnected`). `LiveTimerManager.ticker_enabled=False` bajo el TestClient síncrono.

Los endpoints de contingencia auditan envíos fuera de ventana en vez de simplemente rechazarlos, porque el día del examen algunas situaciones (un envío que se venció antes de alcanzar a pausar, papel tras una caída de red) se resuelven operativamente, no técnicamente — ver `docs/OPERACION_DIA_EXAMEN.md`.

### Consolidación de resultados y nota agregada

`backend/app/services/results.py` es la autoridad de la nota. Dos capas:

- **Nota por (estudiante, estación)** — `compute_station_results` (OPT-16) suma `EvaluatorRecord` (`is_draft=False`) + `StudentResponse` (`score_obtained IS NOT NULL`) por par, `mode=ejecucion`; `persist_results` la congela en `station_results` al cierre.
- **Nota agregada por estudiante** — `compute_results`. Desde **OPT-17** el `percentage` es el **promedio de los `percent_score` por estación** del estudiante (cada estación normalizada a su propio máximo → todas pesan igual), **no** la razón de sumas crudas `sum(obtenido)/sum(máx)*100`. El estándar sigue siendo **compensatorio**: un solo umbral global (`ECOEEvent.passing_reference_percent`) sobre ese promedio, sin lógica conjuntiva ni umbral por estación. `compute_equivalent_grade` mapea ese promedio a la escala 1.0–7.0 y **no se toca**. `total_score`/`max_score` de la respuesta se mantienen como **suma cruda** informativa: para eventos con estaciones de máximo heterogéneo ya no cuadran con `percentage`. Campo `stations_counted` = nº de estaciones puntuables que entraron al promedio (sólo en el recálculo en vivo; el snapshot `ECOEResult` no lo persiste, no hay migración).

**Inmutabilidad (OPT-1):** con el evento `cerrado`/`archivado` y snapshot `ECOEResult`, `read_results` sirve el número congelado tal como se consolidó — los eventos cerrados antes de OPT-17 conservan su razón-de-sumas vieja. Sólo los eventos que se **consoliden desde OPT-17 en adelante** usan la fórmula nueva, y sólo cambian de nota si tienen estaciones de máximo heterogéneo (con todas las estaciones del mismo máximo, `promedio(%) == razón de sumas` exactamente). Un evento cerrado **sin** snapshot cae al recálculo en vivo → ya usa la fórmula nueva.

### Modo kiosco

`backend/app/services/kiosk.py`: en vez de que cada estudiante haga login en una tablet compartida por estación, la estación tiene un único token (generado con `secrets.token_urlsafe`, solo su SHA-256 se guarda en BD — mismo patrón que las invitaciones de usuario). Emitir un token nuevo revoca automáticamente el anterior (un solo dispositivo activo por estación). El backend resuelve quién responde a partir del check-in activo confirmado en esa estación, no de una sesión de usuario.

### Autorización por capas

`backend/app/services/dependencies.py::require_roles` combina tres fuentes en orden: rol global del usuario (`admin_global` es el único bypass universal) → `StaffAssignment` (rol por evento) → `ECOEPermission` (permiso explícito por evento). Esto es una puerta gruesa; la autorización fina por evento la hace después `ensure_event_access` en `services/authorization.py`. `require_global_roles` es distinto y deliberadamente no acepta roles delegados por evento — existe para recursos institucionales (gestión de usuarios) donde un permiso de ECOE nunca debe alcanzar.

### WebSocket / panel en vivo

`backend/app/services/websocket.py::LiveTimerManager` es un singleton en memoria que agrupa conexiones por `ecoe_event_id` y hace broadcast a todos los clientes conectados a ese evento (start/pause/resume/reset/next_transition, incidencias). El frontend se conecta desde `frontend/src/lib/ws.ts`. Al no persistir el estado de las conexiones, un reinicio del proceso backend implica que los clientes deben reconectar (manejado en frontend con reconexión automática visible en UI).

### Frontend: proxy interno a la API

`frontend/next.config.ts` reescribe `/api/:path*` hacia `INTERNAL_API_URL` (backend) vía `rewrites()`, así la UI nunca depende de `localhost` del cliente al accederse desde otra máquina de la red. También define una CSP explícita que debe ampliarse si se agregan nuevos orígenes de media o WebSocket.

### Tests backend: SQLite local vs Postgres real

`backend/tests/conftest.py` decide el engine según `TEST_DATABASE_URL`: sin definir, usa SQLite (`test.db`, rápido, con `Base.metadata.create_all`, fixture-friendly). Si se define a una URL Postgres, recrea el schema `public` y aplica las migraciones Alembic reales — esto es lo que corre CI (ver `.github/workflows/ci.yml`) y es lo único que ejercita constraints únicas que SQLite no valida. Al cambiar modelos o migraciones, correr la suite contra Postgres antes de confiar en que SQLite "pasó".
