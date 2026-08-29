# OPT-20 · Cronómetro sincrónico único + autoguardado/autoenvío

**Severidad: media (capacidad + carga operativa).** Origen: mini-auditoría
`hallazgos/auditor-operacion-vivo__OPT-20__2026-08-28.md` (H-opt20-1..6, R1-R10,
D1-D8) y `hallazgos/auditor-operacion-vivo__2026-08-28.md` (H-vivo-3 = OPT-6).
**Absorbe OPT-6.**

> Plan grande: se entrega en **4 fases** ordenadas por dependencia y riesgo.
> Cada fase es un lote aprobable/commiteable por separado. **F1 cierra OPT-6.**

---

## Problema

El día del examen conviven **dos relojes que no se comunican** (mapa completo en
la mini-auditoría):

- **Reloj A — `LiveSession`** (`entities.py:397`): fila única por evento, la maneja
  solo `POST /live/control` (`operational.py:138`), la ve solo el panel `/live` por
  WebSocket. `compute_remaining_seconds` (`helpers.py:152`) deriva el restante real
  del reloj del servidor.
- **Reloj B — ventana por check-in**: función pura
  `checkin_submission_deadline(checkin, station) = checkin.confirmed_at +
  station.station_time_minutes` (`helpers.py:94`), validada al escribir por
  `ensure_checkin_within_time` (`helpers.py:111`). **Una ventana independiente por
  cada `StationCheckIn`**, anclada a su `confirmed_at`. Es lo que realmente gobierna
  los envíos de `/student`, `/kiosk` y `/evaluator`.

Consecuencias:

- **H-opt20-2 / H-vivo-3 / OPT-6** — kiosko, evaluador y estudiante **no abren
  WebSocket**; cuentan contra su Reloj B con `Date.now()`. Al **pausar** el circuito
  desde `/live`, sus contadores siguen corriendo: los kioscos **autoenvían
  formularios incompletos** al llegar a 0 y los evaluadores pierden el registro a
  medio llenar. Cada pausa = una tanda de reingresos por contingencia (uno por
  estudiante del circuito) bajo presión.
- **H-opt20-1 / R3** — **no hay ningún autoenvío autoritativo server-side** (sin
  scheduler, sin job, sin `asyncio.create_task` en `backend/app/`). Todo el
  autoenvío es client-side (`student/page.tsx:208`, `kiosk/page.tsx:210`) y depende
  de que el navegador esté vivo, en primer plano y con el reloj correcto. Tablet
  bloqueada / pestaña en segundo plano / batería agotada = **no se captura nada**.
  El evaluador **nunca** autoenvía (`evaluator/page.tsx:148`) — un `EvaluatorRecord`
  a medio llenar cuando suena el buzzer se pierde.
- **H-opt20-4 / R2** — `/ws/live/{id}` (`operational.py:58-106`) solo admite
  `admin_ecoe`/`coordinador_operativo`/`cronometrador` vía cookie/bearer de usuario;
  **rechaza evaluador y estudiante (1008)** y **no tiene forma de autenticar el
  token de kiosko** (`X-Kiosk-Token`, no cookie). Prerequisito bloqueante.
- **H-opt20-3 / R1** — divergencia posible entre `ecoe_event.station_time_minutes`
  (Reloj A) y `station.station_time_minutes` (Reloj B, `entities.py:287`): sin
  constraint, solo sincronizadas por convención en el builder (`stations.py:254`) y
  por el flag opcional `sync_existing_stations` (`ecoe.py:255`).
- **H-opt20-1 / R4** — no hay persistencia server-side del borrador: los borradores
  del estudiante/kiosko solo viven en `localStorage` (`kiosk-draft-*`,
  `student-station-draft-*`); el evaluador no persiste nada. Un autoenvío
  server-side no tendría **qué** enviar.
- **R9 / D4** — una respuesta autoenviada en blanco (`answers={}`) hoy es
  indistinguible de una entrega real: `apply_auto_grading` la califica 0 y nadie
  sabe que fue una omisión, ni el corrector ni el acta.

## Causa raíz

`checkin_submission_deadline` no mira `LiveSession`; `compute_remaining_seconds` no
mira check-ins. Pausar/reiniciar/avanzar el Reloj A no mueve ninguna ventana B
(`helpers.py:94-129` vs `:152-157`). El autoenvío se diseñó como un `useEffect` de
cliente porque nunca hubo un canal server→pantallas operativas ni un tick de
servidor. `StationCheckIn` no tiene columna de "envío en blanco / automático" y
`EvaluatorRecord` tampoco (`entities.py:467-487`); `by_contingency` significa otra
cosa (registro fuera de ventana metido por coordinación).

## Decisiones de PRODUCTO ya tomadas por el usuario (2026-08-28) — el plan se construye sobre estas

| # | Decisión |
|---|----------|
| **D1** | **Reloj global único para todo el circuito.** El `LiveSession` es la única autoridad de tiempo. El deadline efectivo de envío pasa a derivarse del `LiveSession` (fase actual + `phase_started_at`/`remaining_seconds`), **no** de `confirmed_at + station_time_minutes`. |
| **D2** | **El alumno que hace check-in tarde pierde ese tiempo.** El deadline es el de la rotación en curso; entrar tarde da menos tiempo. |
| **D3** | **Evaluador: autoguardar borrador server-side, NO enviar.** Al expirar el reloj con un `EvaluatorRecord` a medio llenar, se persiste como **borrador** (flag/estado nuevo), no como registro final. El evaluador lo completa en la ventana de contingencia. |
| **D4** | **Marcar explícitamente "sin respuesta".** Distinguir en datos un 0-por-error de un 0-por-omisión, en `StudentResponse` y `EvaluatorRecord`. Requiere migración. Un blanco **suma 0 pero se marca** (no cambia la aritmética del consolidado, sí la trazabilidad/export). |

Lo que sigue son decisiones **de implementación** (las resuelve el equipo técnico /
el usuario al aprobar el plan), no de producto — van marcadas 🔧.

---

## Cambio propuesto — visión de conjunto

El invariante nuevo: **el deadline de envío de cualquier pantalla operativa = fin
de la fase actual del `LiveSession`**, calculado con el reloj del servidor, y
propagado a las pantallas por WebSocket. El servidor es quien cierra las ventanas
vencidas (autoenvío / autoguardado), no el navegador. El cliente pasa a ser
"mejor esfuerzo" que empuja su borrador seguido y deja de decidir.

```
                 ┌──────────────── LiveSession (Reloj A, único) ─────────────────┐
  /live/control ─┤  status: running | paused | transition | ready                │
  (operador)     │  phase_started_at + remaining_seconds  →  fin de fase (UTC)   │
                 └───────────────┬───────────────────────────────┬───────────────┘
                                 │ broadcast WS (timer_update)   │ lee al cerrar ventana
                   ┌─────────────┼─────────────┐                 │
                   ▼             ▼             ▼                 ▼
               /kiosk        /evaluator     /student     barrido server-side
            (WS + poll)     (WS)           (WS)         (idempotente, F2)
             cuenta = fin de fase       autoguarda borrador     finaliza lo vencido
             congela en `paused`        server-side seguido      → StudentResponse / EvaluatorRecord
             no autoenvía en `paused`                            marcados "auto" / "borrador" / "sin respuesta"
```

### Divergencia `station` vs `event` `station_time_minutes` (R1 / H-opt20-3)

Con D1, el deadline en ejecución **nunca lee `station.station_time_minutes`**: la
duración de la fase sale de `LiveSession.station_time_seconds` (global). La columna
por estación queda **informativa** (objetivo de diseño, se muestra en el Constructor
y en el pilotaje). Se añade una **advertencia blanda** en `compute_ecoe_validation`
si alguna `station.station_time_minutes != ecoe_event.station_time_minutes`, para
que el operador sepa que el proyector/fase no coincidirá con el tiempo nominal de
esa estación. 🔧 *Decisión: mantener la columna como informativa (recomendado) vs.
eliminarla del modelo y forzar todas = evento.*

### Pilotaje

Durante `en_pilotaje` puede no haber operador manejando `/live`. 🔧 *Decisión
recomendada: si el `LiveSession` está ausente/`idle`/`ready`, el deadline hace
**fallback al Reloj B** (`confirmed_at + station_time`), comportamiento actual —
mantiene el pilotaje de baja fricción. Alternativa: exigir manejar el `LiveSession`
también en pilotaje.*

### Kiosko sin conexión (D8)

El kiosko mantiene el **polling REST cada 3 s** como base; el WS es una mejora. El
`/kiosk/context` pasa a incluir `live_status`, `current_phase_ends_at` y `paused`,
así un kiosko sin WS se entera de la pausa y del deadline en el siguiente poll
(≤ 3 s de lag, aceptable). Si **ambos** canales caen: el kiosko muestra "sin
conexión" y **congela** el contador — **no autoenvía a ciegas**. El barrido
server-side (F2) captura el borrador cuando vuelve la conectividad o cuando el
operador avanza la fase. El borrador se empuja al servidor seguido (debounce por
cambio de respuesta + cada ~10 s) para que el servidor tenga siempre algo que
finalizar. Si la tablet muere del todo sin haber empujado nada: la estación queda
"sin respuesta" (D4) y coordinación resuelve por papel/contingencia — igual que
hoy, pero ahora marcado.

---

## FASE 1 — WebSocket operativo + propagación de pausa · **cierra OPT-6**

**Objetivo:** que kiosko/evaluador/estudiante reciban el estado del Reloj A y, en
`paused`, congelen su contador y **no** autoenvíen. Puramente **aditivo**: no
cambia todavía la semántica del deadline ni toca migraciones. Riesgo bajo.

> **Estado 2026-08-28 — implementada, en-verificación** (rama `opt/OPT-20-F1`).
> - [x] Backend: guard de `/ws/live/{id}` ampliado a `evaluador`/`estudiante` +
>   token de kiosko por query param (validado con `authenticate_kiosk_token`,
>   exige `kiosk.ecoe_event_id == ecoe_event_id`). WS solo lectura: los frames
>   entrantes se ignoran.
> - [x] Backend: `live_status` / `current_phase_ends_at` / `paused` agregados a
>   `/kiosk/context`, `/evaluator/context/{id}`, `/student/access` (helper
>   `helpers.py::live_phase_snapshot`).
> - [x] Frontend: hook `useLiveTimer(eventId, { kioskToken? })` en `src/lib/ws.ts`;
>   `live/page.tsx` refactorizado para usarlo sin cambiar comportamiento.
> - [x] Frontend: `kiosk/page.tsx` y `student/page.tsx` — overlay "PAUSA", contador
>   congelado, autoenvío detrás de `status === "running"` (o sin `LiveSession`).
> - [x] Frontend: `evaluator/page.tsx` — banner de pausa + "Guardar evaluación"
>   deshabilitado con leyenda "Pausa en curso" (registro sigue editable).
> - [x] Tests backend (`tests/test_ws_live_screen.py`) incl. negativos; vitest
>   `src/app/kiosk/__tests__/page.test.tsx` (pausa → no autoenvía).
> - [x] `python3 -m pytest` (SQLite y Postgres) · `npm run lint && npm run build`
>   · `npx vitest run` — todo verde; ningún test previo debilitado.
> - [ ] `./scripts/run_e2e.sh` — escenario de pausa agregado al flujo dorado, no
>   ejecutable en la sesión de implementación (sandbox sin Docker).
> - [ ] **Prerequisito de despliegue** (no bloquea el código): headers
>   `Upgrade`/`Connection: upgrade` en `location /api/` del `nginx` público real.

### Backend

- `app/api/routes/operational.py` — WebSocket. Ampliar el acceso a las pantallas
  operativas. 🔧 *Decisión: (a) ampliar el guard del `/ws/live/{id}` existente para
  aceptar además `evaluador` y `estudiante` (sólo lectura — el server sólo hace
  `receive_text` de keep-alive), o (b) un segundo endpoint `/ws/live/{id}/screen`.*
  Recomendado (a) con el rol resuelto por `ensure_event_access` como hoy.
- **Auth del token de kiosko en WS**: el navegador no puede mandar headers propios
  en un WebSocket. 🔧 *Decisión: pasar el token como query param
  (`/ws/live/{id}?kiosk_token=…`) o como `Sec-WebSocket-Protocol`.* El handler
  valida con `authenticate_kiosk_token` (`services/kiosk.py:64`) y exige que
  `kiosk.ecoe_event_id == ecoe_event_id`. Riesgo: el token en la URL puede quedar
  en logs de acceso — mitigado por TTL corto y scope de estación; documentarlo.
- `live_session_state` ya incluye `status`, `phase_started_at`, `remaining_seconds`,
  `server_now` — no hace falta payload nuevo. Confirmar que `pause` emite
  `timer_update` con `status: "paused"` (ya lo hace, `operational.py:167-171,193`).
- `/kiosk/context`, `/evaluator/context/{id}`, `/student/access`: añadir al response
  `live_status`, `current_phase_ends_at` (UTC ISO, derivado del `LiveSession`),
  `paused` — para el fallback sin-WS y para que la primera pintura sea correcta
  antes de que llegue el primer frame WS.

### Frontend

- `src/lib/ws.ts` — `resolveLiveWsUrl` ya resuelve la URL; extraer un hook
  reutilizable `useLiveTimer(eventId, { kioskToken? })` con la reconexión
  automática que hoy vive inline en `live/page.tsx:128-209`.
- `src/app/kiosk/page.tsx` — abrir el WS; al recibir `status === "paused"`:
  overlay "PAUSA — el cronómetro está detenido", **congelar** `remainingSeconds`
  (no avanzar `nowMs`), y **guardar** el `useEffect` de autoenvío detrás de
  `status === "running"`. Mantener el polling de 3 s como está.
- `src/app/(app)/evaluator/page.tsx` — abrir el WS; banner de pausa; al pausar,
  ocultar/deshabilitar el botón "Guardar evaluación" con la leyenda "pausa en
  curso" (el registro sigue editable, sólo no se envía).
- `src/app/(app)/student/page.tsx` — idéntico a kiosko (mismo patrón de autoenvío).

### Migración / máquina de estados

- **Ninguna.** No toca `ALLOWED_STATUS_TRANSITIONS` ni `ecoe-form.tsx`.

### Prerequisito operativo

- El `nginx` público real necesita los headers `Upgrade`/`Connection: upgrade` en
  `location /api/` para proxyar estos WS (ya corregido en la copia de referencia
  del repo; el server real fuera de Docker requiere el cambio manual —
  `datos_proyecto/operacion_despliegue.md`, ver memoria *project-websocket-bug*).
  Sin esto, F1 funciona en local/e2e pero no en producción.

### Tests (incluye negativos — toca auth de WS)

- `test_ws_live_accepts_evaluator_of_event` / `…_student_of_event` — 101, recibe
  `timer_update` tras `start`.
- `test_ws_live_rejects_evaluator_of_other_event` (negativo) — 1008.
- `test_ws_live_accepts_valid_kiosk_token` — token vigente de la estación conecta.
- `test_ws_live_rejects_revoked_or_expired_kiosk_token` (negativo) — 1008.
- `test_ws_live_rejects_kiosk_token_of_other_event` (negativo).
- `test_ws_live_screen_cannot_control_timer` (negativo) — un frame de control por
  el WS no muta nada (el WS es sólo lectura).
- Frontend (vitest): kiosko con `status:"paused"` no dispara `kioskSubmit` al
  llegar a 0; el contador queda congelado.
- e2e: ampliar el flujo dorado con una pausa — el kiosko muestra "PAUSA" y no
  autoenvía; al reanudar, sigue.

### Riesgos / alcance

- Más conexiones WS por evento (cada kiosko + evaluador + estudiante, vs sólo
  coordinación). 1 worker hoy → `LiveTimerManager` en memoria aguanta; si se
  escala a >1 worker hace falta back-plane (**R7 / OPT-14**, ya diferido). Anotar.
- Token de kiosko en la URL del WS: TTL corto + scope de estación lo acotan.
- Commit acotado: auth del WS + un hook + 3 pantallas suscritas + banner.

**Esfuerzo: M (2–4 días).**

---

## FASE 2 — Deadline autoritativo desde `LiveSession` + autoenvío server-side (D1, D2)

**Objetivo:** el deadline de envío deja de derivarse del check-in y pasa a derivarse
de la fase del `LiveSession`; el servidor cierra las ventanas vencidas. **Cambia
comportamiento observable el día del examen** (D2).

### Backend

1. **Helper nuevo** en `app/utils/helpers.py`:
   `resolve_submission_deadline(db, ecoe_event, checkin, station, *, for_evaluator=False) -> datetime`
   - Lee el `LiveSession` del evento.
   - `status == "running"` → `phase_started_at + timedelta(seconds=remaining_seconds)`
     (fin de la fase de estación en curso).
   - `status == "transition"` → para estudiante/kiosko la ventana ya cerró (fin de
     la fase de estación previa); para evaluador (`for_evaluator=True`) el deadline
     es el fin de la fase de transición.
   - `status == "paused"` → sin deadline efectivo (devuelve un centinela futuro /
     `None` → los writes se aceptan mientras esté en pausa).
   - `LiveSession` ausente / `idle` / `ready` → **fallback Reloj B**
     (`checkin_submission_deadline`, comportamiento actual). 🔧
   - `for_evaluator=True` en `running` → deadline = fin de fase de estación **+**
     duración de la fase de transición (`transition_time_seconds`), aprox. del
     "estación + transición" actual, para no bloquear al evaluador antes de que el
     operador pulse `next_transition`. 🔧 *Decisión: fin de la fase de transición
     real vs. `+ transition_time_seconds` fijo.*
   - Siempre `+ SUBMISSION_GRACE_SECONDS` de gracia como hoy.
2. **Recablear** `ensure_checkin_within_time` para usar el helper nuevo (o un
   `ensure_within_live_phase`); mantener la firma para no tocar los 4 call-sites
   (`kiosk.py:212`, `student_access.py:147`, `evaluator.py:283`, y contingencia
   sigue **saltándose** la ventana como hoy).
3. **Context endpoints** (`/kiosk/context`, `/evaluator/context`, `/student/access`)
   devuelven `submission_deadline` / `evaluator_deadline` calculados con el helper
   nuevo (hoy `checkin_submission_deadline`).
4. **Persistencia server-side del borrador (R4)**. 🔧 *Decisión: tabla dedicada vs.
   reusar filas existentes.* Recomendado: tablas `station_response_drafts`
   (`checkin_id` UNIQUE, `answers` JSON, `updated_at`) — aislamiento limpio, se
   borran al finalizar. Endpoints:
   - `PUT /student/draft` y `PUT /kiosk/draft` (auth por cuenta / token de kiosko),
     upsert del borrador del check-in activo. Pasan por `ensure_submission_stage`.
   - El frontend (`/student`, `/kiosk`) empuja el borrador con debounce (cada cambio
     de respuesta + cada ~10 s) además de mantener el `localStorage` como respaldo
     local.
5. **Barrido / autoenvío autoritativo server-side (R3, R5)**. Evaluadas las 3
   opciones de trigger:

   | Opción | Cómo | Pros | Contras |
   |---|---|---|---|
   | **1. Scheduler** (APScheduler / `asyncio` task) | tick cada N s, busca fases vencidas y cierra ventanas | oportuno, independiente del cliente | dependencia de infra nueva; debe sobrevivir reinicios; duplicación con >1 worker; manejo de sesión DB en async |
   | **2. Lazy en el próximo request** | cualquier `GET /kiosk/context` / `/evaluator/context` / `/live/{id}` barre los check-ins vencidos de ese evento | sin infra nueva; idempotente por construcción; corre en la sesión del request | sólo dispara si alguien consulta (el kiosko pollea cada 3 s → en la práctica continuo durante un circuito vivo); un evento abandonado no barre hasta que alguien abra una pantalla (aceptable: cerrar el ECOE también consolida) |
   | **3. En `/live/control`** | al `next_transition` / `start` / `reset` (y una acción nueva `expire_phase`), el backend finaliza los check-ins aún abiertos de la(s) estación(es) cuya fase terminó | determinista, atado a la señal real de rotación, único choke point | depende de que el operador avance el reloj; el buzzer (`remaining==0`) hoy no es un evento |

   **Recomendación: híbrido 2 + 3, sin scheduler.** Trigger primario = transiciones
   de `/live/control` (+ acción nueva `expire_phase` para el buzzer sin avanzar de
   estación, que también responde a **H-opt20-6 / H-vivo-8** sin auto-avanzar el
   índice). Red de seguridad = barrido lazy en los context endpoints operativos.
   Así se evita el scheduler (respeta el "fuera de alcance P0: Redis/broker") y aun
   así se garantiza captura si una tablet muere. Documentar que el scheduler
   (opción 1) es la solución limpia a futuro, atada a OPT-14 / escalado.
6. **Lógica del barrido** (`app/services/` — módulo nuevo, p. ej.
   `services/live_sweep.py`):
   - Para cada `StationCheckIn` `confirmado` cuya fase venció (helper del punto 1) y
     sin `StudentResponse`/`EvaluatorRecord` `mode == <modo del evento>`:
     - **Estudiante**: crear `StudentResponse` con `answers` = borrador server-side
       (o `{}` si no hay), `locked=True`, `submission_kind="auto"` (F4), correr
       `apply_auto_grading`. Cerrar el check-in.
     - **Evaluador** (D3): **no** crear registro final. Si hay borrador de evaluador
       (F3), dejarlo como `is_draft=True`. Si no hay nada, no crear fila (la
       trazabilidad lo mostrará como "sin evaluación" → resolver por contingencia).
   - **Idempotencia (R5)**: el `UniqueConstraint (event, station, student, mode)` es
     el candado. El insert usa `ON CONFLICT DO NOTHING` / captura `IntegrityError`.
     Carrera entre autoenvío client-side viejo, barrido server-side y envío manual /
     contingencia (4 escritores sobre la misma clave): **gana el primero**; el resto
     recibe 409/400. El cliente pasa a tratar "ya enviada" como éxito (re-fetch del
     contexto → pantalla "enviado"), en vez de mostrar error (hoy el kiosko lo
     traga en `.catch`, el estudiante lo muestra).
   - **Nunca** después de `cerrado`/`archivado` (respeta `ensure_submission_stage` y
     `FROZEN_RESULT_STATUSES`); cuidado con la carrera contra la transición de
     cierre (que ya cierra check-ins y consolida) — el barrido y el cierre toman el
     mismo lock de fila o el cierre corre primero.
7. **Cliente = mejor esfuerzo**: el autoenvío de `student/page.tsx:208` y
   `kiosk/page.tsx:210` se mantiene pero (a) sólo dispara con `status === "running"`
   y `remaining <= 0`, (b) su fallo por "ya enviada" es éxito. El barrido
   server-side es la autoridad.

### Frontend

- `/student`, `/kiosk`: endpoint de borrador + push con debounce; tratar 409 "ya
  enviada" como éxito.
- Contadores: ya leen `submission_deadline` del context (F2 sólo cambia cómo se
  calcula ese valor en el backend) — verificar que el WS de F1 y el `submission_deadline`
  del REST no se contradigan (fuente única: el `current_phase_ends_at` del WS manda
  cuando hay WS; el REST es el arranque/fallback).

### Migración / máquina de estados

- Tabla nueva `station_response_drafts` (**requiere aprobación** — es schema, aunque
  trivial y sin backfill).
- Acción nueva `expire_phase` en `TimerAction.action` (validación en
  `operational.py`, no toca el grafo de estados del ECOE).
- **Actualizar** `docs/OPERACION_DIA_EXAMEN.md` §"Durante el examen": la pausa ahora
  **sí** congela para todos y el que entra tarde tiene menos tiempo (D2). Actualizar
  también CLAUDE.md §"Deadlines autoritativos" y §"Separación pilotaje/ejecución".

### Tests (incluye negativos — toca datos, tiempo y auth)

- `test_deadline_follows_live_phase_running` — dos check-ins con `confirmed_at`
  distinto en la misma fase → **mismo** `submission_deadline` (fin de fase).
- `test_late_checkin_gets_less_time` (D2) — check-in confirmado a mitad de fase →
  deadline = fin de fase, no `confirmed_at + station_time`.
- `test_paused_session_freezes_deadline` — con `status="paused"`, un envío que sin
  pausa estaría vencido se **acepta**; al `resume`, la ventana se reanuda.
- `test_deadline_fallback_to_checkin_window_when_no_live_session` — pilotaje sin
  `LiveSession` activo usa el Reloj B.
- `test_server_sweep_creates_blank_student_response_on_phase_expiry` — check-in sin
  respuesta al vencer la fase → `StudentResponse` `locked`, `submission_kind="auto"`,
  auto-calificada.
- `test_server_sweep_is_idempotent` — correr el barrido dos veces no duplica ni
  pisa; una respuesta manual previa gana y el barrido no la toca.
- `test_server_sweep_does_not_run_after_close` (negativo) — evento `cerrado` → el
  barrido no inserta nada.
- `test_server_sweep_respects_mode_scoping` (negativo) — no mete un registro de
  `ejecucion` durante `en_pilotaje` ni viceversa.
- `test_evaluator_deadline_includes_transition_phase`.
- `test_client_autosubmit_conflict_is_treated_as_success` (frontend/vitest).
- Correr la suite **contra Postgres** (constraint única + migración).

### Riesgos / alcance

- **Cambio observable el día del examen** (D2) — comunicar, actualizar doc, idealmente
  pilotar antes.
- La lógica de fallback del helper (session ausente / `idle` / `paused` / `transition`)
  es sutil: riesgo de rechazar envíos válidos o aceptar inválidos. Gracia + tests
  exhaustivos + logging del deadline resuelto.
- Barrido metiendo filas en blanco: debe respetar etapa, modo y no correr tras
  cierre; carrera con la transición de cierre.
- 4 escritores sobre la clave única — definir y testear el ganador.

**Esfuerzo: L (1–2 semanas).**

---

## FASE 3 — Borrador server-side del `EvaluatorRecord` (D3)

**Objetivo:** que el registro del evaluador a medio llenar cuando suena el buzzer se
persista como **borrador** (no como 0 final) y se pueda completar en contingencia.

### Backend

- **Migración**: `evaluator_records.is_draft` (`Boolean`, `nullable=False`,
  `server_default=false`, `default=False`). Backfill: todo lo existente `False`.
  🔧 *Alternativa: columna `status` `String(16)` (`borrador`/`final`) por consistencia
  con otros `mode`/`status` del esquema — decidir.*
- Endpoint `PUT /evaluator/draft` — upsert de un `EvaluatorRecord` parcial
  (`score_obtained` provisional, `answers`/item-scores, `observation`) con
  `is_draft=True`, `by_contingency=False`. Pasa por `ensure_submission_stage`,
  scoping por estación asignada, y la ventana **del evaluador** (F2, incluye
  transición). El `UniqueConstraint (event, station, student, mode)` ya impide dos
  filas: el borrador **es** la fila, se promueve a final al completarse.
- `POST /evaluator/submit` (final): si ya existe una fila `is_draft=True` para la
  tupla, **promoverla** (flip `is_draft=False`, recalcular `max_score`
  autoritativo, validar rango) en vez de rechazar por "ya existe".
- **Barrido (F2)**: al vencer la fase del evaluador, si hay borrador → se deja
  `is_draft=True` (no se promueve). Si no hay borrador → no se crea fila.
- `compute_results` (`results.py:57-71`): **añadir filtro `EvaluatorRecord.is_draft
  == False`** — hoy los `EvaluatorRecord` se suman incondicionalmente; un borrador
  no debe entrar al consolidado.
- `build_traceability_report` (`results.py:211-217, 292, 329`): un borrador **no**
  cuenta como evaluación completa (`has_expected_evaluations`), y aparece en la
  trazabilidad como "borrador pendiente" (nuevo contador, análogo a
  `pending_deferred_gradings`).
- **Contingencia** (`contingency.py:68-115`): hoy `/contingency/evaluator-record`
  rechaza si `existing_record`. Cambiar: si el existente es `is_draft=True`,
  **permitir** que el flujo de contingencia lo **finalice** (promover + set score
  autoritativo + `by_contingency=True` + audit), en vez de bloquear. 🔧 *Decisión:
  reusar el endpoint existente con esta rama, o un `POST
  /contingency/evaluator-record/finalize` explícito.*
- `compute_ecoe_validation` / advertencia del modal de cierre: incluir "N registros
  de evaluador en borrador sin finalizar" junto a la de corrección diferida
  pendiente.

### Frontend (`src/app/(app)/evaluator/page.tsx`)

- Autosave del borrador (debounce por cambio + al perder foco); indicador
  "✓ borrador guardado hh:mm:ss" (ya existe el patrón en kiosko/estudiante).
- Al expirar la fase (WS `running`→`transition`/fin): mensaje "Tiempo agotado — tu
  registro quedó guardado como **borrador**. Complétalo con coordinación en la
  ventana de contingencia." (hoy sólo deshabilita el botón, `evaluator/page.tsx:384`).
- Pantalla de contingencia de coordinación: listar borradores pendientes por
  estación y permitir finalizarlos.

### Migración / máquina de estados

- 1 columna nueva (`evaluator_records.is_draft`). **Requiere aprobación.**
- No toca `ALLOWED_STATUS_TRANSITIONS`.

### Tests (incluye negativos — datos + resultados)

- `test_evaluator_draft_not_counted_in_results` — un `is_draft=True` no suma a
  `compute_results` ni marca la evaluación como completa en la trazabilidad.
- `test_evaluator_draft_promoted_on_final_submit` — `POST /evaluator/submit` sobre
  una tupla con borrador la promueve, no da 400.
- `test_sweep_keeps_evaluator_record_as_draft` — al vencer la fase, el borrador
  sigue `is_draft=True` y no entra al consolidado.
- `test_contingency_finalizes_evaluator_draft` — coordinación completa el borrador;
  queda `is_draft=False`, `by_contingency=True`, auditado, score autoritativo.
- `test_evaluator_draft_scoping` (negativo) — un evaluador no puede guardar borrador
  de una estación no asignada.
- `test_close_warning_counts_pending_evaluator_drafts`.
- Migración verificada contra Postgres desde base limpia + `downgrade`.

### Riesgos / alcance

- `compute_results` cambia (nuevo filtro): revisar que ningún test asuma que un
  `EvaluatorRecord` cuenta sin mirar `is_draft`.
- La promoción borrador→final debe recalcular `max_score` autoritativo (no confiar
  en el guardado en el borrador).

**Esfuerzo: M–L (~1 semana).**

---

## FASE 4 — "Sin respuesta" explícito + trazabilidad (D4)

**Objetivo:** distinguir en datos y en el export un 0-por-omisión de un 0-por-error,
sin cambiar la aritmética del consolidado.

### Backend

- **Migración** (una sola, dos columnas):
  - `student_responses.submission_kind` `String(16)` `server_default='manual'`
    (`manual` / `auto` / `contingency`). Backfill: `by_contingency=True` →
    `'contingency'`, resto `'manual'`.
  - `evaluator_records.submission_kind` `String(16)` `server_default='manual'`
    (`manual` / `contingency` / `draft_finalized`). Mismo backfill.
  - 🔧 *`by_contingency` (bool) queda redundante con `submission_kind='contingency'`
    — decidir si se deja por compatibilidad o se deriva.*
- **Nivel pregunta** (`services/grading.py::grade_answers`): añadir `"answered":
  bool` a cada entrada de `per_question` (`answers.get(key)` no vacío). Así el
  corrector y el export ven qué ítems quedaron en blanco dentro de una respuesta
  parcial, no sólo el total.
- **`submission_kind` lo estampa**: `student_access.submit_student_response` →
  `manual`; el barrido F2 → `auto`; `contingency.*` → `contingency`; la promoción de
  borrador de evaluador (F3) → `draft_finalized`. El cliente **nunca** lo elige
  (se excluye del `model_dump` como `mode`/`by_contingency`).
- **`compute_results`**: sin cambios en la aritmética — un blanco `auto` suma
  `0 / max_score` como cualquier respuesta (D4: "suma 0 pero se marca"). 🔧 *Nota de
  interacción con Fase 2 de análisis (OPT-17): si a futuro se quiere tratar una
  estación entera "sin respuesta / ausente" como excluida del denominador en vez de
  0/max, eso es decisión metodológica de OPT-17, no de OPT-20.*
- **Trazabilidad / export**:
  - `build_traceability_report`: `activity_log` etiqueta "Respuesta del estudiante
    (automática / en blanco)" según `submission_kind` y si `answers` está vacío;
    contador `blank_auto_submissions` por estudiante y por estación.
  - `export_results_excel`: columna nueva por estación o indicador
    "auto/blanco/contingencia" en el consolidado enriquecido (se cruza con
    **OPT-19** — coordinar formato).
- `read_results` congelado: sin cambio (el snapshot `ECOEResult` no lleva esto; es
  metadato de trazabilidad, no de nota).

### Frontend

- `/grading` (corrección): mostrar un badge "respuesta automática / incompleta" y,
  por ítem, marcar los "sin responder" — para que el corrector sepa que no fue una
  entrega deliberada (`EVALUACION_DIFERIDA_FASE1.md` §Decisión 4).
- `/results`: badge en la trazabilidad y en la bitácora.

### Migración / máquina de estados

- 2 columnas nuevas (una migración). **Requiere aprobación.** No toca el grafo.

### Tests (incluye negativos — datos + export)

- `test_auto_submitted_blank_marked_but_scores_zero` — respuesta del barrido con
  `answers={}` → `submission_kind="auto"`, `score_obtained=0` (o `None` si hay
  manual pendiente), `max_score` intacto, consolidado suma `0/max`.
- `test_submission_kind_not_client_settable` (negativo) — el cliente manda
  `submission_kind="manual"` en un envío que en realidad es contingencia → se ignora.
- `test_manual_submission_kind_is_manual`.
- `test_grading_per_question_answered_flag`.
- `test_traceability_flags_blank_auto_submissions`.
- `test_export_excel_includes_submission_kind_column`.
- Migración contra Postgres desde base limpia + `downgrade` + backfill correcto
  (`by_contingency=True` → `'contingency'`).

### Riesgos / alcance

- Migración sobre dos tablas con datos (en dev/demo); backfill simple pero
  verificar contra Postgres.
- Coordinar el formato del export con OPT-19 para no hacer el trabajo dos veces.
- Bajo riesgo de lógica (es marcado, no cambia scoring).

**Esfuerzo: M (2–4 días).**

---

## Qué queda FUERA de OPT-20 (follow-ups)

- **Máquina de fases explícita del reloj único** (D6 de la mini-auditoría, **no**
  está en las decisiones de producto tomadas): hoy el modelo de `start` / `pause` /
  `next_transition` sigue exigiendo un operador disciplinado; una máquina
  `estación → transición → estación` con avance automático al llegar a 0 es un
  cambio mayor. OPT-20 añade la acción `expire_phase` (buzzer sin avanzar) como
  mínimo viable; el resto queda para un plan propio.
- **Rotación autónoma en estaciones kiosko-solo** (`NEXT_STEPS.md` punto 3): quién
  confirma la identidad del siguiente estudiante sin evaluador. OPT-20 resuelve el
  *tiempo* pero no la *identidad*.
- **Back-plane multi-worker del `LiveTimerManager`** (R7 / OPT-14): sigue diferido;
  OPT-20 aumenta la carga de conexiones pero no cambia que hoy hay 1 worker.
- **Scheduler real server-side** (opción 1 de F2): el híbrido lazy + `/live/control`
  es suficiente para 1 worker; el scheduler se evalúa junto con el escalado.

---

## Orden recomendado y por qué

1. **F1 primero.** Mayor valor operativo inmediato (elimina la tanda de
   contingencias por cada pausa = **cierra OPT-6**), menor riesgo (aditivo, sin
   migración, sin cambio de semántica), y **desbloquea** F2 (el canal WS es
   prerequisito para que los clientes observen el estado dirigido por el servidor).
   Despeja además **H-opt20-4**, el bloqueante declarado.
2. **F2** — el corazón de OPT-20 (D1/D2 + autoenvío autoritativo). Depende de F1.
3. **F3** — borrador del evaluador (D3). Se apoya en el barrido de F2.
4. **F4** — marcado "sin respuesta" (D4). Va última: la forma de los datos queda
   informada por lo que F2/F3 realmente escriben, y es la fase con más peso de
   migración y menos de lógica.

## Verificación (cada fase)

- [ ] `cd backend && python3 -m pytest`
- [ ] `TEST_DATABASE_URL=postgresql+psycopg://…/ecoe_test python3 -m pytest -q` (F2/F3/F4 sí o sí — migraciones/constraints)
- [ ] `DATABASE_URL=sqlite:////tmp/ecoe_opt20_check.db … alembic upgrade head` + `downgrade` (F2/F3/F4)
- [ ] `cd frontend && npm run lint && npm run build`
- [ ] `./scripts/run_e2e.sh` — flujo dorado + escenario de pausa (F1) y de autoenvío (F2)

## Decisiones de implementación abiertas (🔧 — resolver al aprobar)

1. **Trigger del autoenvío** (F2): híbrido lazy + `/live/control` (recomendado, sin
   scheduler) vs. scheduler real.
2. **Almacén del borrador** (F2/F3): tablas `*_drafts` dedicadas (recomendado para
   estudiante) vs. reusar `StudentResponse.locked=False` / flag en `EvaluatorRecord`.
3. **Transporte del token de kiosko en el WS** (F1): query param vs.
   `Sec-WebSocket-Protocol`.
4. **Pilotaje** (F2): fallback a Reloj B cuando no hay `LiveSession` activo
   (recomendado) vs. exigir manejar el `LiveSession` también en pilotaje.
5. **`station.station_time_minutes`** (R1): mantener como informativo + advertencia
   de validación (recomendado) vs. eliminar del modelo.
6. **Ventana del evaluador tras la fase** (F2): fin de la fase de transición real
   vs. `fin de estación + transition_time_seconds` fijo.
7. **Buzzer server-side** (F2): acción `expire_phase` que finaliza sin avanzar el
   índice (recomendado) vs. dejar `remaining==0` sin efecto como hoy.
8. **`evaluator_records.is_draft`** (F3): columna booleana vs. columna `status`
   (`borrador`/`final`).
9. **`by_contingency` vs `submission_kind='contingency'`** (F4): mantener ambos vs.
   derivar uno del otro.

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-28
- Aprobado por usuario: ✅ 2026-08-28 — **plan completo F1–F4**. Implementación fase
  por fase con verificación entre cada una.
- **Decisiones de implementación 1–9: se toman las RECOMENDADAS** (por decisión del
  usuario, 2026-08-28). En concreto: (1) híbrido lazy + `/live/control` sin
  scheduler; (2) tablas `*_drafts` dedicadas para el borrador del estudiante;
  (3) token de kiosko por query param en el WS; (4) fallback a Reloj B en pilotaje
  cuando no hay `LiveSession` activo; (5) `station.station_time_minutes` queda
  informativo + advertencia de validación; (6) ventana del evaluador = fin de la
  fase de transición real; (7) acción `expire_phase` server-side para el buzzer;
  (8) `evaluator_records.is_draft` booleano; (9) mantener `by_contingency` y
  `submission_kind` derivando uno del otro. El implementador reporta desviaciones.
- Decisiones de producto D1–D4: tomadas 2026-08-28 (reloj global único; check-in
  tardío pierde tiempo; evaluador autoguarda borrador server-side; "sin respuesta"
  explícito).
