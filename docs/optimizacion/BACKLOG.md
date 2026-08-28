# Backlog de optimización

Estado: `nuevo` → `triado` → `aprobado` → `en-plan` → `implementando` → `en-verificación` → `hecho` | `descartado` | `diferido`

El `optimizador` agrega y triage. El **usuario** cambia a `aprobado` / `descartado` / `diferido`. El orquestador mueve el resto.

Triage: 2026-08-28, sobre las 4 tandas de hallazgos (`auditor-admin-ecoe`, `auditor-roles-usuario`,
`auditor-operacion-vivo`, `auditor-correccion-resultados`). 27 hallazgos → 19 items.
Esfuerzo: XS (<½ día) · S (~1 día) · M (2–4 días) · L (1–2 sem) · XL (>2 sem).

## Grupo A — Estabilización (fixes acotados, candidatos a hacer ya)

| ID | Título | Origen (hallazgo) | Severidad | Impacto | Factibilidad | Estado | Plan |
|----|--------|-------------------|-----------|---------|--------------|--------|------|
| OPT-1 | Inmutabilidad de resultados tras el cierre | H-corr-1, H-corr-2, H-corr-3, H-dato-6 | bloqueante | integridad de resultados / acta de examen | S–M · sin migración | triado | `PLANES/OPT-1__inmutabilidad-resultados.md` |
| OPT-2 | Aislamiento pilotaje/ejecución en trazabilidad, cierre y cola de corrección | H-vivo-1, H-vivo-4, H-vivo-6, H-dato-5, H-corr-4 | alta | señal de contingencia del día del examen; trabajo perdido del corrector | M · migración opcional (gate humano) | triado | `PLANES/OPT-2__aislamiento-mode.md` |
| OPT-3 | Autorización de UI por rol de evento, no por rol global | H-admin-ecoe-1, H-roles-usuario-1, H-roles-usuario-3 | alta | funcionalidad inaccesible (duplicar ECOE, editar estaciones multi-rol) | S · solo frontend | triado | `PLANES/OPT-3__gating-rol-evento.md` |
| OPT-4 | Blocker fantasma "No existe sesión en vivo" antes de publicar | H-admin-ecoe-3, H-vivo-2 | media | fricción-UX en `/validation` y `/publication` | XS · sin migración | triado | `PLANES/OPT-4__blocker-fantasma-sesion-vivo.md` |
| OPT-5 | Alta individual de evaluador sin estación (coherencia UI/endpoint) | H-admin-ecoe-2 | media | fricción en setup de staff | XS–S | triado | `PLANES/OPT-5__evaluador-sin-estacion.md` |
| OPT-8 | `/kiosk/submit` debe exigir el check-in confirmado vigente | H-vivo-5 | baja (integridad/permiso) | atribución de respuesta a check-in previo en ventana | XS–S | triado | `PLANES/OPT-8__kiosk-submit-checkin-activo.md` |
| OPT-9 | Endurecer `/live/control` | H-vivo-8 | baja | 500 con id inválido; "Iniciar" reinicia reloj sin confirmar | S | triado | — (pendiente de aprobación) |
| OPT-10 | Empty-state para cuenta sin eventos accesibles | H-roles-usuario-4 | baja | caso borde: error técnico en vez de estado vacío | XS · solo frontend | triado | — |
| OPT-11 | Limpieza de campos decorativos y código muerto | H-admin-ecoe-5, H-admin-ecoe-6 | baja | expectativas falsas + mantenibilidad | S | triado | — |
| OPT-12 | Consistencia de forma de API (`ecoe_event_id` en body) | H-admin-ecoe-7 | baja | solo consistencia; frontend ya lo maneja | S · toca contrato de 3 endpoints | triado | — (candidato a descartar) |
| OPT-13 | Correcciones a la matriz de permisos (documentación) | H-roles-usuario-2 | baja | doc induce a error | XS · solo `.md` | triado | — |
| OPT-14 | Backplane para `LiveTimerManager` multi-worker | H-vivo-7 | baja (latente) | n/a hoy (1 worker); riesgo pre-escalado | L | triado | — (diferir) |

## Grupo B — Fricción operativa / de rol (dimensionar)

| ID | Título | Origen (hallazgo) | Severidad | Impacto | Factibilidad | Estado | Plan |
|----|--------|-------------------|-----------|---------|--------------|--------|------|
| OPT-6 | Visibilidad de pausa del cronómetro en evaluador y kiosko | H-vivo-3 | media | carga operativa: 1 contingencia por estudiante del circuito por cada pausa | M–L · decisión de enfoque | triado | — |
| OPT-7 | CRUD de instrumentos / plantillas / pacientes simulados | H-admin-ecoe-4 | media | banco institucional se llena de pautas muertas; no se corrige una pauta con error | M · impacto cross-event | triado | — |
| OPT-15 | Fricción del corrector (cola personal, siguiente-pendiente, rúbrica de referencia) | H-corr-5, H-corr-6 | media | corrección diferida a escala; gap vs. diseño FASE1 §Decisión 4 | M · sin migración | triado | — |

## Grupo C — Capacidad de análisis de datos (Fase 2 — features grandes, requieren dimensionamiento y definición metodológica del usuario)

| ID | Título | Origen (hallazgo) | Severidad | Impacto | Factibilidad | Estado | Plan |
|----|--------|-------------------|-----------|---------|--------------|--------|------|
| OPT-16 | Resultado por estación (poblar `StationResult`) + desglose `by_station` | H-dato-1 | alta (capacidad) | ancla del análisis final; hoy imposible ver desempeño por estación | M · sin migración (tabla ya existe) | triado | `PLANES/FASE2_ANALISIS_DATOS__scoping.md` |
| OPT-17 | Ponderación y estándar por estación | H-dato-3 | alta (capacidad) | una estación de `max_score` alto domina la nota; no hay estándar conjuntivo | L · migración + decisión de producto | triado | `PLANES/FASE2_ANALISIS_DATOS__scoping.md` |
| OPT-18 | Analítica psicométrica (ejecución + pilotaje) | H-dato-2 | alta (capacidad) | `pilotaje_validado` es un click sin respaldo cuantitativo | L–XL | triado | `PLANES/FASE2_ANALISIS_DATOS__scoping.md` |
| OPT-19 | Export enriquecido + renombrar "Export PDF" de Resultados | H-dato-4 | media (capacidad) | análisis externo imposible; etiqueta engañosa en `/results` | S (etiqueta) / M–L (export) | triado | `PLANES/FASE2_ANALISIS_DATOS__scoping.md` |

---

## Notas de triage

### OPT-1 · Inmutabilidad de resultados tras el cierre — **BLOQUEANTE**
**Confirmado** (código leído: `app/api/routes/operational.py:325-333`, `app/api/routes/grading.py:107-144`,
`app/services/grading.py:97-148`, `app/services/results.py:42-116`, `app/services/validation.py:453-468`).

- **Causa raíz A (H-corr-1)**: `GET /results/{id}` y `GET /results/{id}/export/excel` llaman `compute_results()`
  en vivo (`operational.py:326`, `:349`). `ECOEResult` **solo se escribe** (`results.py:104-113` desde
  `persist_results`), ningún endpoint la lee (`grep ECOEResult`). El número mostrado depende del estado mutable
  de `StudentResponse`/`EvaluatorRecord` en el instante de la consulta.
- **Causa raíz B (H-corr-2)**: `grade_response` (`grading.py:107`) no llama `ensure_submission_stage` ni mira
  `ecoe_event.status`. Corregir tras `cerrado`/`archivado` responde 200. Contraste: `routes/evaluator.py` y
  `student_access` sí gatean.
- **Causa raíz C (H-corr-3)**: `apply_manual_scores` (`grading.py:100-126`) — `pending` incluye TODAS las claves
  `kind=="manual"` (también las ya resueltas); `missing` solo exige las que aún son `None`. Reenviar `scores`
  sobre una respuesta ya corregida la sobrescribe sin aviso (`score_obtained`, `graded_by_email`, `graded_at`).
- **Causa raíz D (H-dato-6)**: `POST /results/{id}/consolidate` (`operational.py:336`) y la rama de cierre no
  escriben `AuditLog`; `ECOEResult` solo tiene `TimestampMixin`, sin actor de consolidación.
- **Impacto**: admin_ecoe / coeditor / corrector. Etapa cierre y post-cierre. Compromete la integridad de
  resultados: cualquier rol de corrección puede alterar notas ya consolidadas y el endpoint de lectura las
  refleja como si fueran las oficiales. Sin trazabilidad de "consolidado el X por Y". Un acta de examen sale de
  aquí.
- **Factibilidad**: S–M. **Sin migración** — `ecoe_results` ya existe en `c7d8e9f00123_baseline_schema.py:337`
  y `TimestampMixin.updated_at` sirve de "fecha de consolidación". Toca: lógica de lectura de `/results` + export,
  gate de estado en `/grading`, guard de re-corrección en `apply_manual_scores`, `AuditLog` en consolidación.
  Riesgo medio: hay que decidir cuándo el GET sirve snapshot vs. recálculo en vivo. **Tests negativos
  obligatorios** (permiso + datos).
- **Decisión de producto pendiente**: ¿la corrección tardía post-cierre queda **prohibida** (409, recomendado —
  coincide con `EVALUACION_DIFERIDA_FASE1.md` §Alcance y CLAUDE.md "congelando la operación") o **permitida** como
  caso operativo re-disparando `persist_results`?
- **Prioridad**: P0 inmediata. Primer item del lote.

### OPT-2 · Aislamiento pilotaje/ejecución en trazabilidad, cierre y corrección
**Confirmado** (`app/services/results.py:119-152` y `:295-335`; `app/api/routes/grading.py:52-64`;
`app/services/validation.py:217-235`; `app/models/entities.py:443-457` — `StationCheckIn` **no tiene columna
`mode`**).

- **Causa raíz**: `build_traceability_report` carga `checkins`, `evaluator_records`, `student_responses`
  **sin filtro de `mode`** (a diferencia de `compute_results`, que fija `mode == ejecucion`). Alimenta
  `completion_status`, `missing_*`, contadores de `summary` y el `activity_log` (que además hardcodea
  `"mode": "ejecucion"` en las entradas de check-in, `results.py:312` — H-vivo-6). Lo mismo en la cola de
  `/grading` (`grading.py:52`, sin filtro `mode`) y en `pending_deferred_grading_station_numbers`
  (`validation.py:220-232`, sin filtro `mode`), que dispara la advertencia del modal de cierre.
- **Efecto compuesto**: un estudiante con SÓLO actividad de pilotaje aparece `completo` con 0 evaluaciones
  reales; el corrector ve respuestas de pilotaje mezcladas y corregir una es trabajo perdido silencioso; la
  advertencia de cierre se enciende por pendientes de pilotaje. **Las notas del consolidado NO se afectan**
  (ya filtran `mode`).
- **H-vivo-4** (mismo grupo): la transición `publicado → en_ejecucion` no tiene efectos colaterales; los
  check-ins `confirmado` del pilotaje sobreviven y `evaluator_context`/`kiosk_context` pueden mostrar un
  estudiante viejo como activo hasta el primer check-in real.
- **Impacto**: coordinador / admin_ecoe / corrector. Etapa cierre (checklist de "resolver faltantes por
  contingencia") y corrección. No corrompe notas, pero corrompe la señal que guía las decisiones de
  contingencia el día del examen y hace perder trabajo al corrector.
- **Factibilidad**: M. Dos partes:
  1. **Sin migración**: filtrar `EvaluatorRecord.mode == ejecucion` / `StudentResponse.mode == ejecucion` en
     `build_traceability_report`, en la cola de `/grading` y en el conteo de `validation.py`. Cerrar los
     check-ins `confirmado` al entrar a `en_ejecucion` (y/o al salir de `en_pilotaje`), como ya hace el cierre
     — resuelve H-vivo-4 y quita del conteo los check-ins de pilotaje residuales.
  2. **Con migración (gate humano)**: agregar columna `mode` a `station_checkins` (nullable, default
     `'ejecucion'`, backfill trivial). Es la solución completa y correcta para `activity_log` (H-vivo-6) y para
     distinguir check-ins históricos. Bajo riesgo, pero **requiere aprobación explícita del usuario**.
- **Recomendación**: hacer la parte (1) ya; presentar la parte (2) como decisión de schema en el mismo plan.
- **Prioridad**: P0, inmediatamente después de OPT-1.

### OPT-3 · Autorización de UI por rol de evento, no por rol global (patrón sistémico)
**Confirmado** (`frontend/src/app/(app)/ecoe/page.tsx:150`; `frontend/src/app/(app)/stations/page.tsx:74-79`;
`stations/builder/page.tsx:613-616,697`; `station-bank/page.tsx:35-40`; `login/page.tsx:64-70`;
`middleware.ts:68-69`). Backend verificado por los auditores: los endpoints aceptan la operación (200) — el
backend es la autoridad y ya valida por `ensure_event_access`; esto es **funcionalidad bloqueada en la UI**,
no un hueco de seguridad.

- **Causa raíz**: estas pantallas comprueban `user?.role` (rol GLOBAL del JWT) en vez de `eventRoles` (rol
  efectivo por evento), contra el principio de `P0_MATRIZ_PERMISOS.md:82`. El resto de la app ya migró al
  patrón `eventRoles` (sidebar, `/instruments`, `/templates`, `/evaluators`).
  - `/ecoe` "Duplicar ECOE": `disabled={... user?.role !== "admin_ecoe"}` → ningún rol del seed es literalmente
    `admin_ecoe` (el admin es `admin_global`), el botón queda deshabilitado **para todos**. El endpoint
    `POST /api/ecoe/{id}/duplicate` responde 200 a `admin_global`. Además `/ecoe/[id]` "Duplicar" redirige a
    `/ecoe` en vez de abrir el modal → callejón sin salida.
  - 3 guards de `/stations*` hacen `router.replace("/evaluator")` si `user?.role === "evaluador"`, expulsando
    a una cuenta cuyo rol global es `evaluador` pero que es `coeditor_docente`/`admin_ecoe` en el evento.
  - `login/page.tsx` y `middleware.ts` deciden el aterrizaje por rol global (H-roles-usuario-3) — recuperable
    (el sidebar usa `eventRoles`), baja prioridad; se puede dejar si se corrigen los guards.
- **Impacto**: `admin_global` (no puede duplicar ECOE — funcionalidad que la matriz promete) + cuentas
  multi-rol. Etapa setup. Frecuencia: todo `admin_global`.
- **Factibilidad**: S. **Solo frontend**, sin migración, sin backend. Patrón de reemplazo ya existe en el repo.
  Riesgo bajo. Conviene 1 test frontend/e2e que confirme que el botón Duplicar se habilita para `admin_global`.
- **Prioridad**: P0 (severidad alta, costo bajo).

### OPT-4 · Blocker fantasma "No existe sesión en vivo" antes de publicar
**Confirmado** (`app/services/validation.py:328` — el item se agrega a `blockers` cuando
`has_live_session == 0`, sin condicionar al estado; la `LiveSession` solo se crea en la transición a
`publicado`, `validation.py:433-444`; `can_publish` (`:278-282`) **no** depende de `has_live_session`, solo
`can_start_live` lo hace, `:286-289`). `live_checks` ya tiene "Sesión en vivo creada", así que el item en el
array genérico `blockers` es **redundante**.

- **Impacto**: admin_ecoe / coeditor. `/validation` y `/publication` muestran "Listo para publicar" + caja roja
  de bloqueo irresoluble simultáneamente. Fricción-UX; no bloquea nada real.
- **Factibilidad**: XS. Quitar la línea `:328` de `blockers` (queda cubierto por `live_checks`) o condicionarla
  a `ecoe_event.status in {publicado, en_ejecucion}`. Sin migración, sin permisos. 1 test.
- **Prioridad**: P1 — incluir en el primer lote por ser casi gratis y visible.

### OPT-5 · Alta individual de evaluador sin estación (coherencia UI/endpoint)
**Confirmado** (`frontend/src/app/(app)/evaluators/page.tsx:349,356-359`; `app/services/invitations.py:54-64`;
`app/api/routes/invitations.py:40` — `invite_event_member` NO pasa `require_evaluator_station=False`;
`app/api/routes/staff.py:279` — el import masivo SÍ lo pasa).

- **Causa raíz**: dos caminos de alta del mismo rol con reglas distintas y copy idéntico. El formulario
  individual ofrece "Sin estación asignada por ahora" y texto de ayuda que promete asignación diferida; el
  endpoint responde 400.
- **Impacto**: admin_ecoe. Etapa setup de staff. Fricción.
- **Factibilidad**: XS–S. Opción A (recomendada, coherente con el import): `invite_event_member` pasa
  `require_evaluator_station=False`. Opción B: la UI quita la opción y el texto para el alta individual. Toca
  invitaciones → test negativo + positivo.
- **Prioridad**: P1.

### OPT-6 · Visibilidad de pausa del cronómetro en evaluador y kiosko
**Confirmado** (`frontend/src/app/(app)/evaluator/page.tsx` deriva la cuenta regresiva de
`confirmedAt + timerDurationSeconds`, **no abre WebSocket**; `frontend/src/app/kiosk/page.tsx:208-224`
auto-envía al expirar `submission_deadline`). El servidor sigue siendo autoridad y la contingencia queda
auditada — **no es bug de datos**, es carga operativa.

- **Impacto**: evaluador / kiosko. Día del examen. Al pausar el circuito por incidencia, los kioscos siguen
  contando y auto-envían formularios incompletos; se traduce en una tanda de entradas manuales por
  contingencia (una por estudiante del circuito) bajo presión.
- **Factibilidad**: M–L. Requiere suscribir `/evaluator` y `/kiosk` al mismo WS del evento (hoy solo `/live` lo
  usa) y, en estado `paused`: ocultar el botón de envío + suspender el auto-submit del kiosko. Alternativa
  (cambio de semántica: la pausa extiende explícitamente las ventanas de los check-ins abiertos) = **gate
  humano** y más riesgo de regresión. Confirmación del comportamiento WS real pendiente del usuario.
- **Prioridad**: P1/P2 — **el usuario debe elegir enfoque** (señal visual pasiva vs. extensión de ventanas).

### OPT-7 · CRUD de instrumentos / plantillas / pacientes simulados
**Confirmado** (`app/api/routes/stations.py:54-129` — solo GET y POST para `/templates`, `/instruments`,
`/simulated-patients`; contraste: `/station-bank` sí tiene PUT+PATCH. `stations/builder/page.tsx:363-382` —
`saveInstrumentDraft` siempre hace `api.createInstrument`). Los bancos son institucionales (sin
`ecoe_event_id`).

- **Impacto**: admin_ecoe / coeditor. Setup y corrección de contenido. Cada edición de una pauta en el builder
  crea una `AssessmentTool` nueva y re-apunta la estación; las pautas huérfanas quedan visibles en el selector
  de **todos** los eventos, sin forma de borrarlas. Contra `P0_MATRIZ_PERMISOS.md:44,70` ("admin/coeditor
  pueden modificar").
- **Factibilidad**: M. Nuevos `PUT/DELETE /instruments/{id}` (+ templates, patients) con guarda: no
  mutar/borrar si hay `StudentResponse`/`EvaluatorRecord` que lo referencian en un evento cerrado. Frontend:
  copy-on-write explícito en el builder. **Impacto cross-event** (banco compartido) — cuidado. Tests de datos.
- **Prioridad**: P2 — dimensionar.

### OPT-8 · `/kiosk/submit` debe exigir el check-in confirmado vigente
**Confirmado** (`app/api/routes/kiosk.py::kiosk_submit` — `db.get(StationCheckIn, payload.checkin_id)` valida
solo `checkin.station_id == kiosk.station_id`, no que sea el check-in `confirmado` vigente).

- **Impacto**: kiosko. Día del examen. Ventana estrecha; requiere request manual desde un dispositivo ya
  confiable (token de kiosko válido). Puede atribuir respuestas a un estudiante anterior cuya ventana siga
  abierta y que aún no tenga respuesta registrada. Riesgo real bajo pero es un borde de integridad.
- **Factibilidad**: XS–S. Exigir que `payload.checkin_id` coincida con el check-in `confirmado` más reciente
  de la estación (o que su `confirmed_at` sea el máximo). **Tests negativos obligatorios** (permiso/integridad).
- **Prioridad**: P1 — barato y es endurecimiento; encaja en el espíritu P0.

### OPT-9 · Endurecer `/live/control`
**Confirmado** (`app/api/routes/operational.py::control_timer`). (a) sin `LiveSession`, `db.get(ECOEEvent, id)`
+ uso de `ecoe_event.station_time_minutes` sin comprobar `None` → 500 con id inválido. (b) no exige
`en_ejecucion` para operar el timer. (c) `next_transition` sin tope de estaciones; `start` resetea
`remaining_seconds` sin diálogo de confirmación en `/live/page.tsx` (solo `reset` lo pide).

- **Impacto**: coordinador / cronometrador. `/live`. Un click accidental en "Iniciar" a mitad de rotación
  reinicia el reloj para todos los paneles.
- **Factibilidad**: S. (a) `if not ecoe_event: raise 404`. (c) confirmación en el frontend + tope de índice.
  (b) opcional. Sin migración.
- **Prioridad**: P2.

### OPT-10 · Empty-state para cuenta sin eventos accesibles
**Confirmado** (`frontend/src/lib/auth.tsx:40-44,61-64,74-92` — `eventId` arranca en `1`, solo se corrige si
`list.length > 0`; con lista vacía llama `api.ecoe(1)` → 403 → `setLoadError(...)`).
`list_accessible_ecoe_events` devuelve `[]` para cuenta sin `ECOEPermission`/`StaffAssignment`/`Student`.

- **Impacto**: `miembro` / evaluador recién activado sin asignación activa. Login. Caso borde (el flujo normal
  de invitación crea el `StaffAssignment` junto con la cuenta). Ve error técnico rojo.
- **Factibilidad**: XS. Solo frontend: si `list.length === 0`, empty-state dedicado y no llamar `loadECOEData`.
- **Prioridad**: P2.

### OPT-11 · Limpieza de campos decorativos y código muerto
**Confirmado** (`frontend/src/components/ecoe-form.tsx:168-178` — "Total de estaciones/estudiantes" con
validación de mínimos pero `compute_ecoe_validation` usa conteos reales de filas, nunca
`ecoe_event.total_stations/total_students`; `ecoe-form.tsx:98,199-212` — `includeStatus` renderiza un `<select>`
de 9 estados sin guardas, nunca se pasa `true`; `frontend/src/lib/api.ts:163` — `createStaff` sin consumidor).

- **Impacto**: admin_ecoe. Expectativas falsas ("pongo Total = 8 y no pasa nada") + mantenibilidad.
- **Factibilidad**: S. Renombrar los campos a "estimado" con ayuda, o derivarlos de las filas reales; eliminar
  `includeStatus` y el `<select>`; eliminar `api.createStaff` (y evaluar el endpoint `create_staff`).
- **Prioridad**: P2/P3.

### OPT-12 · Consistencia de forma de API (`ecoe_event_id` en body)
**Confirmado** (`app/api/routes/stations.py:60-64,84-90,116-121` — `ecoe_event_id` como query param en el POST,
a diferencia del resto del dominio que lo lleva en body). El frontend ya lo maneja (`api.ts:251`).

- **Impacto**: solo consistencia de API; nadie está bloqueado. El recurso creado es institucional y descarta
  el `ecoe_event_id` tras el gate de permiso.
- **Factibilidad**: S, pero toca el contrato de 3 endpoints + frontend; relación beneficio/riesgo baja.
- **Prioridad**: P3 — **candidato a descartar** salvo que se toque esa zona por OPT-7.

### OPT-13 · Correcciones a la matriz de permisos (documentación)
**Confirmado** (`docs/architecture/P0_MATRIZ_PERMISOS.md:44` marca "Lectura" / "Lectura necesaria" de
instrumentos/plantillas/pacientes para evaluador y estudiante; `app/api/routes/stations.py:50` —
`CONTENT_MANAGER_ROLES` no los incluye; los GET responden 403. El dato llega por `/evaluator/context` y
`/student/access`). No es bug de seguridad; la celda induce a error.

- **Factibilidad**: XS. Solo `P0_MATRIZ_PERMISOS.md` (ya modificado sin commitear). Marcar esas celdas como
  "Vía /evaluator/context" / "Vía /student/access" o añadir nota al pie como la que ya existe para `corrector`.
- **Prioridad**: P2 — hacer junto al próximo commit que toque la matriz.

### OPT-14 · Backplane para `LiveTimerManager` multi-worker
**Confirmado** (`app/services/websocket.py` — `live_timer` es instancia de módulo; `backend/Dockerfile` arranca
`uvicorn` sin `--workers`). No aplica al despliegue actual (1 proceso).

- **Factibilidad**: L (Redis pub/sub o similar). **Explícitamente fuera de alcance P0**
  (`P0_PLAN_CORE_INSTITUCIONAL.md` §"Fuera de alcance": "Redis/broker para WebSocket multi-replica").
- **Prioridad**: DIFERIDO — anotar como riesgo conocido pre-escalado horizontal.

### OPT-15 · Fricción del corrector
**Confirmado** (`frontend/src/app/(app)/grading/page.tsx`; `app/api/routes/grading.py:60-104`). Lista FIFO
por `submitted_at`, sin agrupación, sin "siguiente pendiente", sin autoavance; `pending_count` global al evento
(no respeta el scope del corrector ni el filtro de estación); el endpoint no envía el `assessment_tool` de
referencia aunque `EVALUACION_DIFERIDA_FASE1.md` §Decisión 4 lo especifica; `corrector` sin `StaffAssignment`
ve lista vacía indistinguible de "todo corregido" (H-corr-6).

- **Impacto**: corrector. Corrección diferida a escala (un docente corrige decenas de informes de varias
  estaciones). Es UX de una feature ya entregada (Fase 1), no un bug de seguridad (los negativos de
  `test_deferred_grading.py` están verdes).
- **Factibilidad**: M. Endpoint: enviar `assessment_tool`, `pending_count` con scope, orden por prioridad.
  Frontend: autoavance, contador personal, empty-state distinguido. Sin migración.
- **Prioridad**: P2 — dimensionar (cierra el diseño de Fase 2 de evaluación diferida).

### OPT-16 a OPT-19 · Capacidad de análisis de datos — **Fase 2**
**Confirmados** todos (ver `PLANES/FASE2_ANALISIS_DATOS__scoping.md` para el detalle de evidencia por item).

- Son **capacidades ausentes**, no regresiones. Ninguna está en el alcance de la estabilización P0 vigente
  (`P0_PLAN_CORE_INSTITUCIONAL.md` §"Fuera de alcance": "Analitica curricular longitudinal").
- **Dependencias**: OPT-16 (resultado por estación) es el cimiento de OPT-17, OPT-18 y OPT-19. `station_results`
  y `ecoe_results` ya existen en la migración baseline — OPT-16 no necesita migración; OPT-17 sí (peso/umbral
  por estación).
- **Decisiones metodológicas que el usuario debe tomar antes de planificar**: modelo de estándar
  (compensatorio vs. conjuntivo vs. borderline-regression/Angoff), qué métricas psicométricas son requisito
  vs. deseables, formato del acta y del export para análisis externo.
- **Recomendación**: tratarlas como una fase propia con su propio ciclo auditor→plan, después de cerrar el
  lote de estabilización (OPT-1..5, OPT-8). El **único sub-fix barato que se puede adelantar**: renombrar el
  botón "Exportar PDF" de `/results` (hoy descarga el respaldo de contingencia, no resultados) — parte de
  OPT-19, ~XS.

---

## Lote recomendado para aprobación inmediata (estabilización P0)

`OPT-1` · `OPT-2` · `OPT-3` · `OPT-4` · `OPT-5` · `OPT-8` — planes redactados, ver `PLANES/`.

Quick wins que pueden ir en el mismo lote sin plan formal: `OPT-13` (doc), sub-fix de etiqueta de `OPT-19`.
