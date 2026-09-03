# M1 · Ciclo automático del circuito (cronómetro auto-cíclico)

**Severidad: media (carga operativa el día del examen).** Origen: retro del
Simulacro Integral ECOE (2026-09-02), ítem M1. Es la **"máquina de fases
explícita"** que se difirió de OPT-20 (`OPT-20__cronometro-sincronico.md` deja
el avance de estación como acción manual del operador).

> Depende de OPT-20 F1/F2 ya en producción: `LiveSession` es el reloj
> autoritativo único, `resolve_submission_deadline` deriva el deadline de la
> fase, `sweep_expired_phases` finaliza check-ins vencidos server-side, y el
> evaluador/kiosco ya consumen la fase por WebSocket (post-B1). M1 sólo agrega
> el **avance automático** encima de esa base.

---

## Problema

Hoy OPT-20 automatiza las 4 fases **dentro de una estación** (pre-entrada →
corriendo → transición), pero el salto a la **siguiente estación** y a la
**siguiente ronda** es un clic manual del operador en `/live`
(`POST /live/control` con `next_transition`). En un ECOE real sincrónico de
5×1 con 6 rondas eso son ~30 clics cronometrados a mano, cada uno bajo presión
y con el riesgo de desincronizar todos los paneles si se hace tarde o temprano.

El usuario lo describe así (2026-09-02):

> "si este ecoe es de 5×1 debe ser automático en ese sentido con timbre al
> terminar y comenzar las estaciones."

## Modelo de circuito (confirmado por el usuario, 2026-09-03)

- **1 circuito = N estaciones = N fases de trabajo + (N−1) transiciones
  internas.** Todos los estudiantes hacen **exactamente una vuelta completa**.
- **Tanda simultánea = N estudiantes** (uno por estación). Con 5 estaciones se
  evalúan 5 estudiantes por circuito completo.
- **Nº de rondas = ⌈estudiantes_activos / N⌉.** 30 estudiantes / 5 estaciones =
  **6 rondas**.
- **Tiempo de transición: único para todo el ciclo.** Se define al crear el
  ECOE y **no cambia** durante la ejecución. (Hoy el modelo lo guarda por
  estación en `Station.transition_time_minutes`; M1 pasa a usar **un solo
  valor** — ver Migración.)
- **Entre rondas hay una pausa de cambio de estudiantes** (más larga que la
  transición interna): sale la tanda anterior, entra la siguiente. Es un valor
  configurable nuevo.
- **Timbre** al terminar y al empezar cada fase de estación (el `chime` ya
  existe, M2).
- El operador conserva **pausa manual** (B1: congela, sin deadline) y puede
  forzar buzzer / saltar fase en cualquier momento.

M1 **no** necesita el mapa de rotación (qué estudiante en qué estación en qué
paso). Eso es puro tiempo: los check-ins siguen como están (evaluador manual /
kiosco autoservicio — ver 1-1). El mapa de rotación es un follow-up aparte
(1-1 opción C).

## Causa raíz

La máquina de fases de OPT-20 F2 avanza **sólo** por acción del operador
(`_SWEEP_TIMER_ACTIONS = {start, reset, next_transition, expire_phase}`) o por
el barrido perezoso de red de seguridad, que **finaliza** la fase vencida pero
**no la avanza**. No hay ningún componente que, al vencer el deadline de una
fase, dispare la siguiente. OPT-20 F2 lo evitó deliberadamente (sin scheduler,
sin `asyncio.create_task`).

## Cambio propuesto

### Migración (requiere aprobación explícita del usuario)

Una revisión Alembic nueva (`down_revision = p6q7r8s9t0u1`):

- **`ecoe_events.inter_round_pause_minutes`** `Float`, `nullable=False`,
  `server_default="5"`. Pausa de cambio de estudiantes entre rondas. Editable
  en el formulario del ECOE, se congela al pasar a `en_ejecucion`.
- **`live_sessions.auto_mode`** `Boolean`, `nullable=False`,
  `server_default=false`. El operador lo activa antes de arrancar el circuito.
- **`live_sessions.current_round`** `Integer`, `nullable=False`,
  `server_default="1"`.
- **`live_sessions.total_rounds`** `Integer`, `nullable=True`. Se calcula al
  arrancar (`⌈active_students / station_slots⌉`) y se congela; `NULL` mientras
  no haya arrancado.
- **`live_sessions.inter_round_pause_seconds`** `Integer`, `nullable=False`,
  `server_default="300"`. Copiado de `ecoe_events.inter_round_pause_minutes` al
  arrancar (mismo patrón que `station_time_seconds` / `transition_time_seconds`
  ya existentes en `LiveSession`).

`LiveSession.status` es string libre (no enum): se agregan dos valores nuevos
—**`round_pause`** (pausa entre rondas, con deadline) y **`circuit_complete`**
(circuito terminado)— sin migración de tipo.

**Sobre el tiempo de transición único:** no se borra
`Station.transition_time_minutes` (columna legada, patrón OPT-11b). Al arrancar,
`LiveSession.transition_time_seconds` se toma de `ecoe_event.transition_time_minutes`
(el valor de evento, no el de estación) y es el único que la máquina lee. El
builder de estaciones deja de pedir transición por estación (se deriva del
evento) — cambio de UI menor, sin tocar datos.

### Backend

- **`app/services/live_cycle.py` (nuevo)** — la máquina de fases explícita.
  Función pura `advance_if_expired(db, ecoe_event, *, now, force=False)` que,
  dado el estado actual de `LiveSession`, decide la siguiente fase de forma
  **determinista e idempotente** y puede **fast-forward** por varias fases
  vencidas de una (si nadie polleó en un rato, al llegar el poll el servidor
  recorre todas las fases transcurridas hasta la actual):
  - `running` (estación `i`) vencida → si `i < N`: `transition`, `phase_started_at = deadline previo`.
    Corre `sweep_expired_phases` para finalizar los check-ins de la estación `i`.
  - `transition` vencida → `running` estación `i+1`, timbre de inicio.
  - `running` (estación `N`) vencida → fin de ronda:
    - si `current_round < total_rounds`: `round_pause`, `current_station_index = 1`.
      `sweep_expired_phases(force=True)` cierra todo lo de la ronda.
    - si no: `circuit_complete`. (No consolida resultados: eso lo sigue
      haciendo la transición `en_ejecucion → cerrado`.)
  - `round_pause` vencida → `running` estación 1, `current_round += 1`, timbre.
  - Sólo actúa si `session.auto_mode and session.status not in {"paused", "idle", "ready", "circuit_complete"}`.
    La **pausa manual del operador (B1) tiene prioridad**: `paused` congela y
    `advance_if_expired` no hace nada hasta el `resume`.
- **`POST /live/control`** — acciones nuevas:
  - `enable_auto` / `disable_auto`: setean `auto_mode`. `enable_auto` sólo si
    `status in {idle, ready}`; calcula y congela `total_rounds` e
    `inter_round_pause_seconds`.
  - `next_round`: variante manual del avance de ronda (por si el operador
    quiere acortar la pausa). Reusa la lógica de `live_cycle`.
  - `start` con `auto_mode` on arranca la ronda 1, estación 1.
  - `pause` / `resume` / `expire_phase` / `reset` siguen igual; `reset` limpia
    `current_round → 1`, `total_rounds → NULL`, `status → ready`.
- **Barrido perezoso** — los context endpoints operativos (`/live/{id}`,
  contexto de evaluador y de kiosco) que ya llaman al sweep pasan a llamar
  primero `advance_if_expired` cuando `auto_mode` está on. Reusa exactamente el
  patrón OPT-20 F2 (avance perezoso disparado por el polling que ya existe).
- **Ticker de timbre (best-effort)** — en `LiveTimerManager` (singleton en
  memoria por evento, ya sabe qué clientes WS están conectados): **mientras
  haya al menos un cliente WS** para el evento y `auto_mode` esté on, un
  `asyncio` task por evento se despierta en el deadline de la fase, llama a
  `advance_if_expired` y hace `broadcast` del `timer_update` + un evento
  `phase_bell` (`{"kind": "start"|"end", "station": i}`). **No es autoritativo**:
  si el proceso se reinicia o no hay clientes, la corrección de estado la
  garantiza el barrido perezoso desde `phase_started_at`; sólo el timbre puede
  llegar tarde o perderse. El task se cancela cuando se va el último cliente.

### Frontend

- **`/live`** — toggle "Circuito automático" (visible sólo en `idle`/`ready`).
  Con auto on: muestra "Ronda X / T · Estación i / N", cuenta regresiva de la
  fase, y el próximo hito ("→ transición en …", "→ ronda 2 en …"). El operador
  conserva pausa, buzzer y "saltar a siguiente". El timbre se dispara desde el
  evento WS `phase_bell` (además del cruce local por 0 que ya existe, M2).
- **`/evaluator`, `/kiosk`** — ya consumen la fase del `LiveSession` por WS
  (evaluador post-B1). Agregan la etiqueta "Ronda X · Estación i". El timbre de
  inicio/fin ya está cableado (M2); se engancha también a `phase_bell`.
- **Formulario del ECOE** (`ecoe-form.tsx` / `ecoe-form` builder) — campo
  "Pausa entre rondas (cambio de estudiantes)" en minutos, junto a tiempo de
  estación y transición. El de transición pasa a ser único del evento (ya lo
  es en la práctica).

### Máquina de estados del ECOE

No toca `ALLOWED_STATUS_TRANSITIONS`. `circuit_complete` es un estado del
`LiveSession`, no del `ECOEEvent`; el cierre del evento
(`en_ejecucion → cerrado`) sigue siendo manual y consolida resultados como hoy.

## Tests (incluye negativos — toca datos operativos y ventana de envío)

- `test_auto_cycle_advances_through_a_full_round` — 3 estaciones, manipular
  `phase_started_at`; verificar `running(1) → transition → running(2) →
  transition → running(3) → round_pause` sin ninguna acción de operador, con
  deadlines derivados de `station_time_seconds` / `transition_time_seconds`.
- `test_auto_cycle_fast_forwards_multiple_expired_phases` — no pollear por
  varias fases; un solo `advance_if_expired` deja el estado en la fase correcta
  y `phase_started_at` coherente.
- `test_round_pause_has_deadline_and_closes_round_checkins` — al final de la
  ronda, `round_pause` con deadline; los check-ins de la ronda quedan cerrados
  (como `expire_phase`); ningún envío nuevo se acepta durante `round_pause`.
- `test_circuit_completes_after_ceil_students_over_stations_rounds` — 12
  estudiantes / 5 estaciones → 3 rondas; tras la ronda 3 estación N →
  `circuit_complete`, no avanza más.
- `test_manual_operator_pause_overrides_auto_advance` (B1) — `pause` en medio
  de `running`; `advance_if_expired` no hace nada aunque el deadline pase;
  `resume` reancla `phase_started_at` y sigue.
- `test_auto_mode_off_keeps_manual_behaviour` (regresión) — con `auto_mode`
  false, el circuito no avanza solo; `next_transition` manual funciona igual
  que hoy.
- `test_sweep_still_frozen_after_cerrado` — `advance_if_expired` respeta
  `FROZEN_RESULT_STATUSES` y `ensure_submission_stage` (nada fuera de
  `en_pilotaje`/`en_ejecucion`).
- `test_enable_auto_rejected_mid_run` — `enable_auto` con `status=running` → 409.
- `test_total_rounds_frozen_at_start` — cambiar el nº de estudiantes activos
  después de arrancar no mueve `total_rounds`.
- Frontend (`vitest`): `/live` muestra ronda/estación y el próximo hito; el
  toggle desaparece una vez arrancado.

## Riesgos / alcance

- **El `asyncio` ticker es superficie nueva.** Mitigación: no muta la BD de
  forma autoritativa (el avance real vive en `advance_if_expired`, llamado
  también por el barrido perezoso); si el task muere, la corrección de estado
  no se pierde, sólo el timbre es best-effort. Vive sólo mientras hay clientes
  WS. Un reinicio del proceso → los clientes reconectan (ya manejado) y el
  estado se recomputa desde `phase_started_at`.
- **Fast-forward determinista.** `advance_if_expired` debe ser idempotente y
  producir el mismo estado sin importar cuántas veces se llame ni con qué
  frecuencia se polleó. Se prueba explícitamente.
- **Interacción con la pausa manual (B1).** `paused` gana siempre; el `resume`
  reancla el reloj. Cubierto por test.
- **Migración con `server_default`** en `ecoe_events` e `live_sessions`:
  columnas nuevas con default, sin backfill manual. Verificar contra Postgres.
- Commit acotado: la base (reloj único, sweep, deadline por fase, WS en
  evaluador/kiosco) ya está en producción por OPT-20 + B1. M1 agrega una
  función pura + acciones de control + un task de broadcast + campos de UI.
- **Entrega sugerida en 2 fases:**
  - **F1** — migración + `live_cycle.advance_if_expired` + acciones de control
    + barrido perezoso + UI de `/live` (ronda/estación, toggle). Avance
    automático correcto aunque el timbre dependa del cruce por 0 local (M2).
  - **F2** — ticker de `LiveTimerManager` + evento `phase_bell` + enganche de
    timbre en los 3 paneles. Timbre puntual server-push.

## Verificación

- [ ] `cd backend && python3 -m pytest`
- [ ] contra Postgres (`TEST_DATABASE_URL=…`) — toca migración + constraints
- [ ] `DATABASE_URL=sqlite:////tmp/ecoe_m1_check.db … alembic upgrade head` desde base limpia
- [ ] `cd frontend && npm run lint && npm run build`
- [ ] Simulacro manual en el stack e2e: circuito de 2 rondas × 3 estaciones,
      verificar timbres y avance sin tocar `/live`.

## Estado de implementación

- **F1 ✅ (rama `opt/M1-F1-ciclo-automatico`)** — migración `q7r8s9t0u1v2`
  (`ecoe_events.inter_round_pause_minutes`, `live_sessions.auto_mode` /
  `current_round` / `total_rounds` / `inter_round_pause_seconds`),
  `services/live_cycle.py::advance_if_expired` (determinista, idempotente,
  fast-forward), acciones `enable_auto` / `disable_auto` / `skip_phase` en
  `/live/control`, avance perezoso en los 3 context endpoints
  (`/live/{id}`, `/kiosk/context`, `/evaluator/context`), `round_pause` /
  `circuit_complete` en `resolve_submission_deadline`, toggle + indicador de
  ronda/estación + botón "Adelantar fase" en `/live`, campo "Pausa entre rondas"
  en el formulario del ECOE, timbre de inicio por cambio de fase en `/live`.
  Tests: `backend/tests/test_m1_auto_cycle.py` (18). Suite: 423 SQLite.
- **F2 ⬜** — ticker de `LiveTimerManager` + evento `phase_bell` + enganche en
  los 3 paneles (timbre puntual server-push).

## Estado de aprobación

- Propuesto por: optimizador — 2026-09-03
- Modelo de circuito confirmado por el usuario: ✅ 2026-09-03 (transición única
  de evento; 1 vuelta de N estaciones; rondas = ⌈estudiantes/N⌉; pausa entre
  rondas)
- Migración aprobada por usuario: ✅ 2026-09-03
- Plan aprobado por usuario: ✅ 2026-09-03 — arrancar por F1
- 1-1 (estaciones solo-kiosco): usuario eligió **A** para el simulacro (coordinación
  cubre check-ins, sin código), **B** apenas se concrete el simulacro
  (autoidentificación en kiosco con confirmación de nombre). **C** queda absorbida
  por el mapa de rotación, follow-up de M1.
