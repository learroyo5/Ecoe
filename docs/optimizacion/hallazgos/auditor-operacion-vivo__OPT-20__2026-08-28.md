# Mini-auditoría — auditor-operacion-vivo · OPT-20 · 2026-08-28

Mapeo profundo del **modelo de tiempo** de la operación en vivo, para fundamentar
el plan de **OPT-20** (cronómetro sincrónico único + autoguardado/autoenvío;
absorbe OPT-6 / H-vivo-3).

**Alcance acotado**: NO es una pasada general. Solo los dos relojes, sus lectores,
las transiciones de fase de `LiveSession`, el autoenvío, y el impacto de unificar
el reloj.

**Método**: lectura de código backend + frontend en la rama
`opt/OPT-2-aislamiento-mode`; ejercicio in-process de los helpers de tiempo con
`pytest` (tests scratch `test_audit_opt20_*`, ya borrados; 3/3 verdes). No se
levantó servidor, Docker ni navegador. Lo relativo al comportamiento del
WebSocket real queda como "requiere confirmación del usuario".

Rama auditada: `opt/OPT-2-aislamiento-mode` (tip del Grupo A).

---

## Mapa de los dos relojes (6 bullets)

- **Reloj A — `LiveSession` (reloj del circuito, panel `/live`).** Fila única por
  evento (`entities.py:397`, `UniqueConstraint("ecoe_event_id")`). Campos:
  `status` (`idle`/`ready`/`running`/`paused`/`transition`), `station_time_seconds`,
  `transition_time_seconds`, `current_station_index`, `remaining_seconds` (valor
  congelado en el último cambio de estado), `phase_started_at`. El restante real
  lo deriva `compute_remaining_seconds` (`helpers.py:152`) de
  `remaining_seconds - (utcnow_naive() - phase_started_at)` cuando está
  `running`/`transition`. Se escribe SOLO desde `POST /live/control`
  (`operational.py:138`, roles `admin_ecoe`/`coordinador_operativo`/`cronometrador`)
  y se copia de minutos del evento al crearse (`validation.py:486` al publicar,
  `operational.py:154` como fallback) o al re-sincronizar timing con
  `sync_existing_stations` (`ecoe.py:264`).

- **Reloj B — ventana por check-in (lo que se aplica a los envíos).**
  No es una fila: es una función pura,
  `checkin_submission_deadline(checkin, station) = checkin.confirmed_at +
  station.station_time_minutes` (`helpers.py:94`), con variante
  `+ station.transition_time_minutes` para el registro del evaluador. La escritura
  se valida con `ensure_checkin_within_time` (`helpers.py:111`,
  `utcnow_naive() > deadline + 30 s` de gracia → HTTP 400). Hay **una ventana
  independiente por cada `StationCheckIn`**, anclada a SU `confirmed_at`.

- **Quién lee A**: solo `/live` (`frontend/src/app/(app)/live/page.tsx` — único que
  abre el WebSocket vía `resolveLiveWsUrl`) y el dashboard de coordinación
  (`dashboard.py:57`, snapshot REST). El WS (`LiveTimerManager`,
  `websocket.py`) hace broadcast de `timer_update` / incidencias a los clientes
  suscritos a `/ws/live/{event_id}`.

- **Quién lee B**: **todas** las pantallas operativas.
  `student_access.py` (`/student/access`, `submission_deadline`),
  `evaluator.py` (`/evaluator/context`, `submission_deadline` + `evaluator_deadline`),
  `kiosk.py` (`/kiosk/context`, `submission_deadline`). Los tres frontends
  (`student/page.tsx`, `evaluator/page.tsx`, `kiosk/page.tsx`) cuentan hacia ese
  deadline con `Date.now() + clockOffsetMs(server_now)` y **no abren ningún
  WebSocket**. La autoridad de escritura final es `ensure_checkin_within_time`.

- **A y B no se comunican.** `checkin_submission_deadline` no mira `LiveSession`;
  `compute_remaining_seconds` no mira check-ins. Pausar/reiniciar/avanzar el
  Reloj A no mueve ninguna ventana B. `current_station_index` es puramente
  decorativo (rótulo "Estación N" en el panel y el proyector; no scoped a ninguna
  query).

- **Divergencia de duración ya posible hoy.** Reloj A usa
  `ecoe_event.station_time_minutes`; Reloj B usa `station.station_time_minutes`
  (columna propia, `entities.py:287`). El builder de estaciones fuerza
  `station.station_time_minutes = ecoe_event.station_time_minutes` en cada PATCH
  (`stations.py:254`) y `update_ecoe_timing` re-sincroniza solo si
  `sync_existing_stations=True` (`ecoe.py:255`). No hay constraint que lo
  garantice: si se cambia el timing del evento sin marcar el sync y no se re-guarda
  cada estación, el panel `/live` y las ventanas de envío cuentan minutos
  distintos.

---

## Respuestas a las 6 preguntas

### 1. Mapa completo de los dos relojes — ¿kiosko y evaluador leen `LiveSession`?

**No.** Confirmado por lectura de código:

| Pantalla | Fuente de su cronómetro | ¿Abre WebSocket? | Autoridad al enviar |
|---|---|---|---|
| `/live` (coordinación) | Reloj A vía WS `timer_update` + resync REST `GET /live/{id}` | **Sí** (`live/page.tsx:128-209`) | n/a (no envía respuestas) |
| `/evaluator` | Reloj B: `activeCheckin.evaluator_deadline` (`confirmed_at + station_time + transition_time`), offset con `server_now` (`evaluator/page.tsx:68,119-137`) | **No** | `ensure_checkin_within_time(..., extra_minutes=transition)` (`evaluator.py:283`) |
| `/kiosk` | Reloj B: `active.submission_deadline` (`confirmed_at + station_time`) (`kiosk/page.tsx:191-208`) | **No** (polling REST cada 3 s, `kiosk/page.tsx:19,115-170`) | `ensure_checkin_within_time` (`kiosk.py:212`) |
| `/student` | Reloj B: `context.submission_deadline`, idéntico a kiosko (`student/page.tsx:56,143-161`) | **No** | `ensure_checkin_within_time` (`student_access.py:147`) |

El Reloj A es visible únicamente para el equipo de coordinación. El estudiante,
el kiosko y el evaluador viven exclusivamente en el Reloj B, cada uno con su
propia ventana anclada al `confirmed_at` de su check-in.

### 2. Transiciones de fase del `LiveSession` — ¿hay "rotación N" / tandas escalonadas?

**No hay tandas escalonadas. Es un solo reloj para todo el circuito.** `LiveSession`
es una fila por evento; `current_station_index` es un entero global. `total_groups`
existe en `ECOEEvent` pero no está cableado al timer.

Transiciones, todas disparadas manualmente desde `POST /live/control`
(`operational.py:162-186`), sin ningún job automático:

| `action` | Efecto |
|---|---|
| `start` | `status=running`, `remaining_seconds = station_time_seconds`, `phase_started_at = now` |
| `pause` | congela: `remaining_seconds = compute_remaining_seconds(session)`, `status=paused`, `phase_started_at=None` |
| `resume` | `status=running`, `phase_started_at = now` (reanuda desde el `remaining_seconds` congelado) |
| `reset` | `status=ready`, `current_station_index=1`, `remaining_seconds = station_time_seconds`, `phase_started_at=None` |
| `next_transition` | `status=transition`, `remaining_seconds = transition_time_seconds`, `current_station_index += 1`, `phase_started_at = now` |

Notas:
- **No existe una acción "estación siguiente" que reinicie el tiempo de estación.**
  Tras `next_transition` (que cuenta la transición), el operador tiene que volver
  a pulsar `start` para la siguiente estación. `start` a mitad de rotación
  reinicia el reloj sin confirmación (ya documentado en H-vivo-8).
- Al llegar a 0 **no pasa nada**: el backend no cambia `status` ni avanza el
  índice. `compute_remaining_seconds` satura en 0 y ahí queda hasta la próxima
  acción manual.
- El broadcast WS del nuevo estado va como `background_task`
  (`operational.py:193`); si el proceso reinicia, el estado de `LiveSession`
  persiste en BD pero las conexiones WS se pierden (reconexión + resync en
  frontend, `live/page.tsx:145-160`).

### 3. Qué se necesita para autoenvío al buzzer — ¿hay job server-side?

**No hay ningún trigger server-side.** No hay APScheduler, `asyncio.create_task`,
`repeat_every`, Celery ni cron en `backend/app/` (verificado con grep). El único
`while True` es el keep-alive del WebSocket (`operational.py:100`).

Todo el autoenvío existente es **client-side y por Reloj B**:
- **`/student`** (`student/page.tsx:208-223`): al llegar `remainingSeconds` a 0,
  `submitResponse("automatico")` — `POST /student/submit` con lo que haya en
  `answers` (borrador en `localStorage`).
- **`/kiosk`** (`kiosk/page.tsx:210-224`): idéntico, `autoSubmitAttemptedRef`
  guarda contra doble envío; además, si llega otro check-in mientras hay un
  borrador sin enviar, intenta enviarlo sobre el check-in original
  (`kiosk/page.tsx:133-144`).
- **`/evaluator`**: **NO autoenvía.** Al expirar solo deshabilita el botón y
  muestra "Tiempo agotado / registro por contingencia" (`evaluator/page.tsx:148,
  384-388, 516-527`). Un `EvaluatorRecord` a medio llenar cuando suena el buzzer
  **se pierde** salvo que el evaluador alcance a pulsar "Guardar" o coordinación
  lo reingrese por contingencia.

Dónde se engancharía un autoenvío autoritativo server-side (OPT-20):
- **`StudentResponse`**: un job que, al vencer la ventana de un check-in
  `confirmado` sin `StudentResponse` para `(event, station, student, mode)`, inserta
  una respuesta vacía/parcial `locked=True`. Reusa `apply_auto_grading` y el
  `UniqueConstraint (ecoe_event_id, station_id, student_id, mode)` como candado de
  idempotencia. Necesita persistir el borrador en el servidor (hoy solo vive en
  `localStorage` del kiosko/estudiante) — ver decisión D4.
- **`EvaluatorRecord`**: mismo patrón, pero un registro de evaluador vacío es
  peor que ausente (metería un 0 en resultados). Probablemente el autoenvío del
  evaluador debe ser "autoguardar borrador" + alerta, no "enviar 0". Ver D3.
- El gate `ensure_submission_stage` (solo `en_pilotaje`/`en_ejecucion`) y el
  scoping por `mode` ya protegen contra contaminar resultados; el job debe pasar
  por las mismas reglas.

### 4. Impacto de "un solo reloj para todas las estaciones" sobre el modelo actual

- **Hoy, un alumno que hace check-in tarde obtiene el tiempo COMPLETO de
  estación**, desfasado. Demostrado: `checkin_submission_deadline` = `confirmed_at
  + station_time`, evaluado por check-in. Dos alumnos confirmados con 5 min de
  diferencia terminan con 5 min de diferencia, ambos con sus 8 min completos.
  Con un reloj único sincrónico, ese alumno tardío obtendría **menos** tiempo (lo
  que quede del reloj común) — que es exactamente lo que el usuario pidió, pero
  **es un cambio de comportamiento observable** que hoy actúa como colchón para
  descoordinaciones de la rotación (el evaluador que tarda en confirmar no le
  "roba" tiempo al alumno).
- **No rompe ningún escalonamiento de rotaciones porque no existe** (respuesta 2).
  El único acoplamiento a romper/rehacer es el desfase natural entre estaciones
  de un mismo circuito: si el reloj es único y global, todas las estaciones
  arrancan y terminan juntas, y la rotación pasa a depender de que el circuito
  esté físicamente sincronizado (todos los evaluadores confirman en la misma
  ventana). Eso es el modelo ECOE clásico, pero hoy la plataforma tolera
  desincronización y con OPT-20 dejaría de hacerlo.
- **La divergencia de duración por estación (bullet 6 del mapa) hay que
  resolverla**: si OPT-20 unifica en un solo reloj, o bien se prohíbe
  `station.station_time_minutes` distinto del evento, o el "reloj único" pasa a
  ser "un reloj por estación pero sincrónico entre alumnos de esa estación". Ver
  D1.
- **Contingencia y "pausa no extiende ventana"** (`OPERACION_DIA_EXAMEN.md:36`)
  cambian de sentido: con reloj único + pausa que sí congela para todos, la
  necesidad de reingresar por contingencia tras cada pausa desaparece (que es el
  objetivo de OPT-6). Pero los endpoints de contingencia
  (`contingency.py`, `get_latest_checkin_any_status`) siguen siendo necesarios
  para caídas de red por estación.

### 5. Solape con OPT-6 — la pausa del `LiveSession`, ¿kiosko/evaluador se enteran?

**No se enteran.** Es exactamente H-vivo-3 / OPT-6:
- `pause` en `/live/control` congela el Reloj A y hace broadcast WS, pero
  kiosko/evaluador/estudiante no están suscritos al WS y su Reloj B sigue
  corriendo contra `submission_deadline` con `Date.now()`.
- Consecuencia hoy: durante una pausa coordinada, **los kioscos y la vista del
  estudiante siguen el countdown y AUTO-ENVÍAN formularios incompletos** al llegar
  a 0; los evaluadores ven su semáforo pasar a rojo y el botón deshabilitarse sin
  ninguna señal de que hay pausa. Cada pausa se traduce en una tanda de
  reingresos por contingencia (uno por alumno del circuito en curso), bajo
  presión.
- OPT-20 **absorbe OPT-6**: si kiosko/evaluador/estudiante pasan a leer el Reloj A
  por WS y el autoenvío se dispara desde el servidor (o se suspende en `paused`),
  la pausa se propaga sola y el problema desaparece.

### 6. Riesgos y piezas faltantes para implementar OPT-20

| # | Pieza faltante | Estado hoy | Riesgo si se ignora |
|---|---|---|---|
| R1 | **WS en kiosko/evaluador/estudiante** | Solo `/live` abre WS; los demás hacen polling REST (kiosko 3 s) o nada (evaluador/estudiante recargan contexto puntualmente) | El "reloj único" no llega a las pantallas que deciden el envío; seguiría habiendo dos relojes |
| R2 | **Auth del WS para roles operativos** | `/ws/live/{id}` solo admite `admin_ecoe`/`coordinador_operativo`/`cronometrador` (`operational.py:86-96`); rechaza evaluador y estudiante, y **no hay auth de token de kiosko en el WS** | Hay que ampliar el guard del WS (o un segundo endpoint WS) para evaluador/estudiante y para el `X-Kiosk-Token` |
| R3 | **Autoenvío autoritativo server-side** | Inexistente; todo es client-side y depende de que el navegador esté vivo y con reloj correcto | Tablet bloqueada / pestaña en segundo plano / batería agotada = no hay autoenvío; el buzzer no garantiza nada |
| R4 | **Persistencia server-side del borrador** | Borradores solo en `localStorage` (`student-station-draft-*`, `kiosk-draft-*`); el evaluador no persiste nada | Un autoenvío server-side no tendría qué enviar; hoy si la tablet muere se pierde todo |
| R5 | **Idempotencia del autoenvío** | Parcial: `UniqueConstraint (event, station, student, mode)` + chequeo `existing_response`/`existing_record` en cada endpoint | Carrera entre autoenvío client-side viejo, autoenvío server-side nuevo y envío manual → hoy uno gana con 400; hay que definir cuál y que el 400 no rompa UX |
| R6 | **Estado del timer tras reinicio del backend** | `LiveSession` persiste en BD (bien), pero `phase_started_at` + reloj del server bastan para recomputar; las conexiones WS se pierden y reconectan | Bajo. Un job de autoenvío server-side sí necesita sobrevivir reinicios (idempotente + re-scan al arrancar) |
| R7 | **`LiveTimerManager` es singleton en memoria** (H-vivo-7) | 1 worker hoy; broadcast no cruza procesos | Si OPT-20 aumenta la carga de conexiones WS y se escala a >1 worker, hace falta back-plane (Redis pub/sub). OPT-14 ya lo cubre |
| R8 | **Divergencia `station` vs `event` station_time** | Sin constraint; sincronizado por convención en el builder | El "reloj único" sería ambiguo para estaciones con override |
| R9 | **Respuestas en blanco** | El autoenvío client-side ya manda `answers={}` si no hay nada; `apply_auto_grading` las califica (0 en lo objetivo, pendiente en lo manual) | Hay que decidir si una respuesta vacía autoenviada se distingue de una real (flag) para la trazabilidad y para el corrector — ver D4 |
| R10 | **Semántica de `next_transition` + `start`** | Dos pulsaciones por rotación; `start` reinicia sin confirmar (H-vivo-8) | Un reloj único que maneja N rotaciones necesita un modelo de fases más explícito (estación→transición→estación) o un operador muy disciplinado |

---

## Decisiones de diseño que el usuario debe tomar para OPT-20

- **D1 — ¿El reloj es único global, o único por estación?** El usuario dijo "el
  mismo en todas las estaciones". Si se toma literal: prohibir
  `station.station_time_minutes` ≠ evento (quitar el campo del builder o
  ignorarlo). Si algunas estaciones legítimamente duran distinto: el invariante
  pasa a ser "sincrónico entre los alumnos de una misma estación / rotación", no
  "el mismo número para todas". Esto define si OPT-20 toca el modelo de datos.

- **D2 — ¿Qué pasa con el alumno que entra tarde a una estación?** Hoy: tiempo
  completo desfasado. Con reloj sincrónico: termina cuando termina el circuito
  (menos tiempo). ¿Se acepta esa pérdida (modelo ECOE clásico) o el sistema debe
  auditar/compensar los check-ins tardíos? Afecta a `checkin_submission_deadline`
  y a la contingencia.

- **D3 — Autoenvío del evaluador: ¿enviar o solo autoguardar?** Un
  `EvaluatorRecord` con puntaje incompleto es un 0 en resultados. Opciones:
  (a) autoguardar borrador server-side + bloquear edición al buzzer + que
  coordinación lo confirme/complete por contingencia; (b) autoenviar tal cual con
  flag `by_contingency`/`incomplete`. Distinto del autoenvío del estudiante.

- **D4 — Respuestas en blanco / parciales: ¿se marcan?** Si el servidor autoenvía
  al buzzer, conviene un flag (`auto_submitted` / `blank`) en `StudentResponse`
  para distinguirlas en la bitácora y para que el corrector sepa que no fue una
  entrega deliberada. Hoy no existe ese flag (`by_contingency` es lo más cercano
  y significa otra cosa).

- **D5 — Fuente de verdad del autoenvío: servidor, cliente, o ambos.**
  Recomendado: **servidor autoritativo** (job/tick que cierra ventanas vencidas)
  + cliente como "mejor esfuerzo" que envía antes para no perder el borrador
  local. Definir el candado de idempotencia (R5) y qué error ve el cliente
  cuando el servidor ya autoenvió.

- **D6 — Modelo de fases del reloj único.** Para manejar N rotaciones con un solo
  reloj hace falta más que `start`/`pause`: al menos `estación en curso` →
  `transición` → `siguiente estación` como una máquina explícita, con el avance
  del `current_station_index` acoplado y (¿?) las ventanas de los check-ins
  abiertos re-ancladas en cada avance. Definir si el avance es manual
  (cronometrador) o automático al llegar a 0.

- **D7 — Pausa: ¿congela para todos?** Objetivo de OPT-6: al pausar el Reloj A,
  las ventanas B de la rotación en curso se congelan / extienden por el mismo
  tiempo, y el autoenvío se suspende. Confirmar que ese es el comportamiento
  deseado (vs. la doctrina actual "la pausa se resuelve por contingencia",
  `OPERACION_DIA_EXAMEN.md:36`) y actualizar ese doc.

- **D8 — Kiosko sin conexión.** El kiosko hoy tolera cortes (polling reintenta).
  Con reloj por WS, definir el fallback: si el WS cae, ¿el kiosko sigue con su
  último `submission_deadline` conocido (Reloj B como respaldo) o se bloquea? El
  autoenvío server-side (D5) hace esto menos crítico pero el UX del kiosco
  desconectado hay que definirlo.

---

## Hallazgos con severidad (acotados a OPT-20)

### H-opt20-1 · No existe autoenvío autoritativo server-side; el buzzer no garantiza captura — **media**
`backend/app/` sin scheduler alguno. El autoenvío vive en `student/page.tsx:208`
y `kiosk/page.tsx:210`, condicionado a que el navegador esté vivo, en primer
plano y con el reloj correcto. Una tablet de kiosko bloqueada o con la pestaña
en segundo plano al sonar el buzzer **no autoenvía**. El evaluador no autoenvía
en ningún caso. Es la brecha central que OPT-20 debe cerrar.

### H-opt20-2 · Kiosko/evaluador/estudiante ciegos a la pausa del circuito (= H-vivo-3 / OPT-6) — **media**
Ninguna de las tres pantallas abre WebSocket; cuentan contra `submission_deadline`
con `Date.now()`. Pausar el Reloj A no las afecta: los kioscos auto-envían
incompletos y los evaluadores pierden el registro. Carga operativa: un reingreso
por contingencia por alumno del circuito por cada pausa.

### H-opt20-3 · Dos definiciones de duración de estación sin constraint que las ate — **baja**
`ecoe_event.station_time_minutes` (Reloj A) vs `station.station_time_minutes`
(Reloj B). Sincronizadas por convención (`stations.py:254`,
`ecoe.py:255` con flag opcional), no por invariante. `PATCH /ecoe/{id}/timing`
sin `sync_existing_stations` deja el panel `/live` y las ventanas de envío
contando minutos distintos. Demostrado con test scratch.

### H-opt20-4 · `/ws/live/{id}` no admite roles operativos ni token de kiosko — **baja (bloqueante para OPT-20)**
`operational.py:86-96`: el WS solo deja entrar
`admin_ecoe`/`coordinador_operativo`/`cronometrador` vía cookie/bearer de usuario.
Evaluador y estudiante son rechazados (1008); el kiosko no tiene forma de
autenticarse (usa `X-Kiosk-Token`, no cookie). Ampliar el guard es prerequisito
de OPT-20.

### H-opt20-5 · Autoenvío del kiosko sobre check-in "rotado" es best-effort silencioso — **baja**
`kiosk/page.tsx:133-144`: si llega el siguiente estudiante con un borrador sin
enviar, se intenta enviar sobre el check-in anterior y el `.catch()` se traga el
error ("queda para contingencia"). Nadie se entera de que quedó pendiente. Con
OPT-20 server-side esto se vuelve determinista.

### H-opt20-6 · Al llegar a 0, el Reloj A no hace nada — **baja / cosmético**
`compute_remaining_seconds` satura en 0 pero `status` sigue `running` y
`current_station_index` no avanza hasta la próxima pulsación manual. Un reloj
único para N rotaciones necesita una máquina de fases explícita (D6).

---

## Top 3 para OPT-20

1. **H-opt20-1 + H-opt20-4** — autoenvío autoritativo server-side + WS accesible
   para las pantallas operativas. Es el corazón de OPT-20; sin esto sigue habiendo
   dos relojes y el buzzer no garantiza nada.
2. **H-opt20-2 (OPT-6)** — propagar `paused` a kiosko/evaluador/estudiante.
   OPT-20 lo absorbe gratis si se hace 1; si no, sigue siendo la mayor fuente de
   contingencia manual del día.
3. **D1 + D2 + H-opt20-3** — decidir si el reloj es único global o sincrónico por
   estación, y qué pasa con el check-in tardío. Es la decisión de producto que
   condiciona si OPT-20 toca el modelo de datos y cambia comportamiento observable
   el día del examen.
