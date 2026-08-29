# Backlog de optimización

Estado: `nuevo` → `triado` → `aprobado` → `en-plan` → `implementando` → `en-verificación` → `hecho` | `descartado` | `diferido`

El `optimizador` agrega y triage. El **usuario** cambia a `aprobado` / `descartado` / `diferido`. El orquestador mueve el resto.

Triage: 2026-08-28, sobre las 4 tandas de hallazgos (`auditor-admin-ecoe`, `auditor-roles-usuario`,
`auditor-operacion-vivo`, `auditor-correccion-resultados`). 27 hallazgos → 19 items.
Ampliación 2026-08-28: mini-auditoría de tiempo (`auditor-operacion-vivo__OPT-20`) → OPT-20, que absorbe OPT-6.
**CIERRE 2026-08-29**: TODO mergeado a `main` y **desplegado** en el servidor (migración prod `j0e1f2a3b4c5 → o5p6q7r8s9t0`, CI verde, 394 backend + 78 frontend). Grupo A + OPT-20 F1–F4 + OPT-7/7b/7c + OPT-15/15b + OPT-11b + Fase 2 (OPT-16..19) → **`hecho`**. OPT-12 `descartado`. OPT-14 y OPT-17b `diferido` (requieren escalado horizontal / cambio a estándar conjuntivo). Pendiente operativo: pilotar el cambio de deadline de OPT-20 antes de un examen real.
Esfuerzo: XS (<½ día) · S (~1 día) · M (2–4 días) · L (1–2 sem) · XL (>2 sem).

## Grupo A — Estabilización (fixes acotados, candidatos a hacer ya)

| ID | Título | Origen (hallazgo) | Severidad | Impacto | Factibilidad | Estado | Plan |
|----|--------|-------------------|-----------|---------|--------------|--------|------|
| OPT-1 | Inmutabilidad de resultados tras el cierre | H-corr-1, H-corr-2, H-corr-3, H-dato-6 | bloqueante | integridad de resultados / acta de examen | S–M · sin migración | hecho (desplegado 2026-08-29) | `PLANES/OPT-1__inmutabilidad-resultados.md` |
| OPT-2 | Aislamiento pilotaje/ejecución en trazabilidad, cierre y cola de corrección | H-vivo-1, H-vivo-4, H-vivo-6, H-dato-5, H-corr-4 | alta | señal de contingencia del día del examen; trabajo perdido del corrector | M · migración opcional (gate humano) | hecho (desplegado 2026-08-29) | `PLANES/OPT-2__aislamiento-mode.md` |
| OPT-3 | Autorización de UI por rol de evento, no por rol global | H-admin-ecoe-1, H-roles-usuario-1, H-roles-usuario-3 | alta | funcionalidad inaccesible (duplicar ECOE, editar estaciones multi-rol) | S · solo frontend | hecho (desplegado 2026-08-29) | `PLANES/OPT-3__gating-rol-evento.md` |
| OPT-4 | Blocker fantasma "No existe sesión en vivo" antes de publicar | H-admin-ecoe-3, H-vivo-2 | media | fricción-UX en `/validation` y `/publication` | XS · sin migración | hecho (desplegado 2026-08-29) | `PLANES/OPT-4__blocker-fantasma-sesion-vivo.md` |
| OPT-5 | Alta individual de evaluador sin estación (coherencia UI/endpoint) | H-admin-ecoe-2 | media | fricción en setup de staff | XS–S | hecho (desplegado 2026-08-29) | `PLANES/OPT-5__evaluador-sin-estacion.md` |
| OPT-8 | `/kiosk/submit` debe exigir el check-in confirmado vigente | H-vivo-5 | baja (integridad/permiso) | atribución de respuesta a check-in previo en ventana | XS–S | hecho (desplegado 2026-08-29) | `PLANES/OPT-8__kiosk-submit-checkin-activo.md` |
| OPT-9 | Endurecer `/live/control` | H-vivo-8 | baja | 500 con id inválido; "Iniciar" reinicia reloj sin confirmar | S | hecho (desplegado 2026-08-29) | — (quick win, sin plan formal) |
| OPT-10 | Empty-state para cuenta sin eventos accesibles | H-roles-usuario-4 | baja | caso borde: error técnico en vez de estado vacío | XS · solo frontend | hecho (desplegado 2026-08-29) | — (quick win, sin plan formal) |
| OPT-11 | Limpieza de campos decorativos y código muerto | H-admin-ecoe-5, H-admin-ecoe-6 | baja | expectativas falsas + mantenibilidad | S | hecho (desplegado 2026-08-29) | — (quick win, sin plan formal) |
| OPT-11b | Quitar (o derivar) `total_stations`/`total_students` del backend | H-admin-ecoe-5 (residuo de OPT-11) | baja | la pantalla de detalle sigue mostrando "Total de estaciones: 8" junto a 6 reales | S · opción (b) sin migración / opción (a) con `drop_column` ×2 | hecho (desplegado 2026-08-29) | `PLANES/OPT-11b__quitar-campos-decorativos.md` |
| OPT-12 | Consistencia de forma de API (`ecoe_event_id` en body) | H-admin-ecoe-7 | baja | solo consistencia; frontend ya lo maneja | S · toca contrato de 3 endpoints | descartado | — |
| OPT-13 | Correcciones a la matriz de permisos (documentación) | H-roles-usuario-2 | baja | doc induce a error | XS · solo `.md` | hecho (desplegado 2026-08-29) | — (aplicado en `P0_MATRIZ_PERMISOS.md`) |
| OPT-14 | Backplane para `LiveTimerManager` multi-worker | H-vivo-7 | baja (latente) | n/a hoy (1 worker); riesgo pre-escalado | L | diferido | — |

## Grupo B — Fricción operativa / de rol (dimensionar)

| ID | Título | Origen (hallazgo) | Severidad | Impacto | Factibilidad | Estado | Plan |
|----|--------|-------------------|-----------|---------|--------------|--------|------|
| OPT-6 | Visibilidad de pausa del cronómetro en evaluador y kiosko | H-vivo-3 | media | carga operativa: 1 contingencia por estudiante del circuito por cada pausa | M–L · decisión de enfoque | **absorbido por OPT-20** (su entregable = F1, en-verificación) | `PLANES/OPT-20__cronometro-sincronico.md` (F1) |
| OPT-7 | CRUD de instrumentos (`AssessmentTool`) | H-admin-ecoe-4 | media | banco institucional se llena de pautas muertas; no se corrige una pauta con error | M · migración (columnas + `ondelete`) · impacto cross-event | **hecho** (desplegado 2026-08-29) | `PLANES/OPT-7__crud-instrumentos.md` |
| OPT-7b | CRUD de plantillas (`StationTemplate`) y pacientes simulados (`SimulatedPatient`) | H-admin-ecoe-4 §6 | baja | mismo patrón solo-creación; sin riesgo de trazabilidad ni huérfanas de alto volumen | S · migración (columnas ×2 + `ondelete` ×4) · UPDATE libre + soft-delete | **hecho** (desplegado 2026-08-29) | `PLANES/OPT-7b__crud-plantillas-pacientes.md` |
| OPT-7c | Modo "editar esta pauta" en el Constructor de estaciones | OPT-7 §Decisión 5 (pendiente) | baja–media | el Constructor sigue creando una pauta nueva al "corregir" → huérfanas | M · solo frontend · sin migración | **hecho** (desplegado 2026-08-29) | `PLANES/OPT-7c__editar-pauta-constructor.md` |
| OPT-15 | Cola del corrector (núcleo: pauta de referencia, autoavance, progreso, empty-states) | H-corr-5, H-corr-6 | media | corrección diferida a escala; gap vs. diseño FASE1 §Decisión 4 | M · sin migración · sin endpoints nuevos | **hecho** (desplegado 2026-08-29) | `PLANES/OPT-15__cola-corrector.md` |
| OPT-15b | Corrector: bulk "puntuar 0 los blancos" + "Reasignar" in-place para correctores | H-corr-5 §C, auditoría OPT-15 §4/§6 | baja | residuo de fricción; hoy delete+recreate para cambiar estaciones de un corrector | S–M · sin migración (`api.updateStaff` ya lo soporta; bulk = endpoint nuevo) | **hecho** (desplegado 2026-08-29) | `PLANES/OPT-15b__correccion-bulk-y-reasignacion.md` |
| OPT-20 | Cronómetro sincrónico único + autoguardado/autoenvío (absorbe OPT-6) | mini-auditoría OPT-20 (H-opt20-1..6, D1–D8) + H-vivo-3 | media (capacidad + carga operativa) | día del examen: el buzzer no garantiza captura; cada pausa dispara reingresos por contingencia; el registro del evaluador a medio llenar se pierde | XL · 4 fases (M + L + M–L + M) · 2 migraciones (F2/F3; F4 sin migración) — gate humano · cambia comportamiento observable (D2) | **hecho** (desplegado 2026-08-29) | `PLANES/OPT-20__cronometro-sincronico.md` |

## Grupo C — Capacidad de análisis de datos (Fase 2 — features grandes, requieren dimensionamiento y definición metodológica del usuario)

| ID | Título | Origen (hallazgo) | Severidad | Impacto | Factibilidad | Estado | Plan |
|----|--------|-------------------|-----------|---------|--------------|--------|------|
| OPT-16 | Resultado por estación (poblar `StationResult`) + desglose `by_station` | H-dato-1 | alta (capacidad) | ancla del análisis final; hoy imposible ver desempeño por estación | M · sin migración (tabla ya existe) | **hecho** (desplegado 2026-08-29) | `PLANES/OPT-16__resultado-por-estacion.md` |
| OPT-17 | Normalización por estación (promedio de %-de-logro) | H-dato-3 | alta (capacidad) | una estación de `max_score` alto domina la nota agregada | S/M · sin migración (bajó de L: decisiones metodológicas tomadas) | **hecho** (desplegado 2026-08-29) | `PLANES/OPT-17__normalizacion-por-estacion.md` |
| OPT-17b | Umbral de aprobación por estación (componente conjuntivo) | OPT-17 §"Umbral por estación" (evaluado y descartado) | media (capacidad) | permitiría un estándar híbrido; **contradice** el compensatorio puro elegido por el usuario | M · migración (`min_pass_percent` en `stations`) · cambia `compute_results` | diferido | — (recomendación en la nota de triage) |
| OPT-18 | Analítica psicométrica (ejecución + pilotaje, item analysis por criterio) | H-dato-2 | alta (capacidad) | `pilotaje_validado` es un click sin respaldo cuantitativo | L–XL · sin migración · 3 sub-fases | **hecho** (desplegado 2026-08-29) | `PLANES/OPT-18__psicometria.md` |
| OPT-19 | Export Excel enriquecido (multi-hoja) + limpieza `persist` muerto | H-dato-4 | media (capacidad) | análisis externo imposible; arg muerto viola "GET sin mutación" | M · sin migración (etiqueta ya hecha en `e642abd`) | **hecho** (desplegado 2026-08-29) | `PLANES/OPT-19__export-enriquecido.md` |

> **Fase 2 (OPT-16 a OPT-19): `hecho`, desplegado 2026-08-29.** Mergeada a `main` y en producción.

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
- **Estado 2026-08-28**: **completo (backend + frontend)**. Backend A/B/C/D en su rama (`read_results` +
  `frozen`/`consolidated_at` en `/results`, 409 en `grade_response`/`apply_manual_scores` sobre
  `cerrado`/`archivado`, `AuditLog` de consolidación). Frontend diferido cerrado en
  `opt/OPT-1b-frontend-inmutabilidad`: chip "Resultados consolidados el {fecha}" en `/results`, aviso "ECOE
  cerrado" que oculta la cola en `/grading`, `frozen`/`consolidated_at` en `ResultsResponse`, tests de página.
  Falta solo la corrida en Postgres del backend (sin Postgres en el entorno de implementación).

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

**ACTUALIZACIÓN 2026-08-28: OPT-6 queda absorbido por OPT-20.** La mini-auditoría de tiempo confirmó que
OPT-6 y OPT-20 comparten causa raíz (los dos relojes que no se comunican) y que resolver OPT-20 resuelve
OPT-6 "gratis". El usuario decidió el enfoque: **el `LiveSession` es la autoridad única de tiempo y la pausa
congela para todos** (D1/D7 — es la alternativa de "cambio de semántica", ya no la señal visual pasiva). La
**Fase 1 de OPT-20** (WS operativo + propagación de pausa + suspensión del autoenvío en `paused`) es
exactamente el entregable de OPT-6. No hacer OPT-6 por separado.

### OPT-20 · Cronómetro sincrónico único + autoguardado/autoenvío
**Confirmado** por la mini-auditoría `hallazgos/auditor-operacion-vivo__OPT-20__2026-08-28.md` (código leído:
`helpers.py:94-157`, `operational.py:58-199`, `websocket.py`, `kiosk.py`, `evaluator.py`, `student_access.py`,
`contingency.py`, `results.py:50-107,188-434`, `grading.py`, `entities.py:270-514`, y las 3 pantallas
frontend). Plan redactado: `PLANES/OPT-20__cronometro-sincronico.md`.

- **Causa raíz**: `checkin_submission_deadline` (Reloj B, ancla `confirmed_at + station.station_time_minutes`)
  y `compute_remaining_seconds` (Reloj A, `LiveSession`) no se miran entre sí. Solo `/live` abre WebSocket;
  kiosko/evaluador/estudiante cuentan client-side con `Date.now()`. No hay ningún trigger server-side de
  autoenvío (sin scheduler en `backend/app/`). El evaluador no autoenvía nada. `/ws/live/{id}` rechaza
  evaluador/estudiante y no admite token de kiosko.
- **Decisiones de producto tomadas por el usuario** (2026-08-28), sobre las que se construye el plan:
  D1 reloj global único (`LiveSession` = autoridad de deadline); D2 el check-in tardío pierde ese tiempo;
  D3 evaluador autoguarda **borrador** server-side, no envía; D4 marcar "sin respuesta" explícito (migración).
- **Factibilidad**: XL, dividido en 4 fases por dependencia/riesgo:
  - **F1** (M) — WS operativo para kiosko/evaluador/estudiante + auth (token de kiosko en WS) + propagación de
    `paused` + suspensión del autoenvío en pausa. Aditivo, sin migración. **Cierra OPT-6.**
    _Estado 2026-08-28: implementada en rama `opt/OPT-20-F1`, en-verificación. Backend + Postgres + lint +
    build + vitest verdes. Pendiente: correr `./scripts/run_e2e.sh` (escenario de pausa agregado al flujo
    dorado; no ejecutable en la sesión de implementación) y los headers `Upgrade` de nginx en el server real
    (no bloqueante del código: F1 funciona en local/e2e; solo el proxy público real necesita el ajuste manual)._
  - **F2** (L) — deadline derivado de la fase del `LiveSession` + barrido/autoenvío autoritativo server-side
    (híbrido lazy + `/live/control`, sin scheduler) + persistencia server-side del borrador. Migración:
    tabla `station_response_drafts` + `student_responses.submission_kind`. **Cambia comportamiento observable
    el día del examen (D2)** → `docs/OPERACION_DIA_EXAMEN.md` y CLAUDE.md actualizados.
    _Estado 2026-08-29: **F2 completa (backend + frontend), en-verificación total.** Backend en rama
    `opt/OPT-20-F2` (`resolve_submission_deadline`, `services/live_sweep.py`, `PUT /student|kiosk/draft`,
    acción `expire_phase`). Frontend en rama `opt/OPT-20-F2-frontend`: `/student` y `/kiosk` empujan el
    borrador con debounce (~0,8 s) + latido de 10 s manteniendo el `localStorage` como respaldo; el 400/409
    "ya fue enviada" del autoenvío y del envío manual se trata como éxito (re-fetch → pantalla enviado); el
    `phaseEndsAt` del WS manda sobre el `submission_deadline` del REST cuando hay conexión y fase corriendo;
    botón "Finalizar la estación en curso ahora" (`expire_phase`) con confirmación en `/live`. Backend +
    Postgres + alembic up/down verdes; 18 tests F2 backend + 2 vitest nuevos
    (`test_client_autosubmit_conflict_is_treated_as_success` + push de borrador con debounce); lint + build +
    vitest (47) verdes; `pytest -q` sigue en 249. **Pendiente**: `./scripts/run_e2e.sh` (escenario de
    autoenvío server-side; necesita Docker, no ejecutable en la sesión de implementación)._
  - **F3** (M–L) — borrador del `EvaluatorRecord` (`is_draft`) + finalización por contingencia + filtro en
    `compute_results`/trazabilidad. Migración: `evaluator_records.is_draft` + `submission_kind`.
    _Estado 2026-08-29: **F3 completa (backend + frontend), en-verificación total.** Rama `opt/OPT-20-F3`
    (desde `opt/OPT-20-F2-frontend`). Migración `m3n4o5p6q7r8` (`is_draft` bool server_default false +
    `submission_kind` String(16) default 'manual', backfill `by_contingency → 'contingency'`).
    `PUT /evaluator/draft` (upsert parcial, scoping por estación asignada, ventana del evaluador, gate de
    etapa); `POST /evaluator/submit` promueve el borrador en vez de rechazarlo; `compute_results` filtra
    `is_draft == False`; `build_traceability_report` cuenta `pending_evaluator_drafts` (estudiante/estación/
    resumen) + entrada de bitácora; `/contingency/evaluator-record` finaliza un borrador existente;
    `GET /contingency/evaluator-drafts/{id}` para coordinación; advertencia de cierre en
    `compute_ecoe_validation`. Frontend: autosave del borrador en `/evaluator` (debounce + latido + onBlur)
    con indicador, mensaje "quedó como borrador" al vencer la fase, y panel de finalización por contingencia
    en `/live` (`EvaluatorDraftsPanel`). `pytest` SQLite (259) + Postgres verdes; alembic up/down/up desde
    base limpia; lint + build + vitest (47) verdes. **Pendiente**: `./scripts/run_e2e.sh` (necesita Docker,
    no ejecutable en la sesión)._
  - **F4** (M) — `submission_kind` en `student_responses` y `evaluator_records` + flag `answered` por pregunta
    + marcado en trazabilidad/export.
    _Estado 2026-08-29: **F4 completa (backend + frontend), en-verificación total.** Rama `opt/OPT-20-F4`
    (desde `opt/OPT-20-F3`). **Sin migración**: las columnas `submission_kind` ya existían (F2 =
    `l2m3n4o5p6q7`, F3 = `m3n4o5p6q7r8`); `answered` vive dentro del JSON de `grading`. `grade_answers`
    agrega `"answered": bool` por ítem sin tocar la aritmética; reconciliación de F3 — la promoción de un
    borrador de evaluador (vía `/evaluator/submit` y vía contingencia) estampa `submission_kind =
    'draft_finalized'` en vez de `manual`/`contingency` (`by_contingency` se mantiene, decisión #9); el
    cliente nunca elige `submission_kind` (negativo). `build_traceability_report` etiqueta y cuenta
    `blank_auto_submissions` (estudiante/estación/resumen) + badge en la bitácora; `export_results_excel`
    agrega la hoja `trazabilidad_envios` (indicador mínimo por respuesta — el rediseño completo del export
    es **OPT-19**, que debe absorber esta hoja). Frontend: badges "Respuesta automática / incompleta" en
    `/grading` (respuesta e ítem) y en `/results` (bitácora + columna). `pytest` SQLite (270) + Postgres
    (270) verdes; lint + build + vitest (47) verdes; 12 tests F4 nuevos. **Pendiente**: `./scripts/run_e2e.sh`
    (necesita Docker)._
- **Toca**: máquina de estados (efecto colateral nuevo en `/live/control`, acción `expire_phase`; **no** el
  grafo `ALLOWED_STATUS_TRANSITIONS`), 2 migraciones (F2/F3 — **gate humano**; F4 no necesitó migración),
  auth de WebSocket (F1 — **tests negativos obligatorios**), aritmética de `compute_results` (F3 — filtro
  `is_draft`; F4 no la toca).
- **Prioridad**: P1 para **F1** (cierra OPT-6, alto valor operativo, bajo riesgo, desbloquea el resto).
  F2–F4 son P2, secuenciales. **9 decisiones de implementación abiertas** listadas en el plan (trigger del
  autoenvío, almacén del borrador, transporte del token de kiosko en WS, fallback de pilotaje, etc.).
- **Prerequisito operativo de F1**: el `nginx` público real necesita los headers `Upgrade`/`Connection` en
  `location /api/` (ya en la copia de referencia del repo; el server real requiere el cambio manual).

### OPT-7 · CRUD de instrumentos (`AssessmentTool`) — plantillas/pacientes → OPT-7b
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
- **Estado 2026-08-29**: **aprobado** — mini-auditoría de fundamento
  (`hallazgos/auditor-admin-ecoe__OPT-7__2026-08-29.md`) + decisiones de producto del usuario. Plan:
  `PLANES/OPT-7__crud-instrumentos.md`. Alcance recortado a **`AssessmentTool`** (plantillas/pacientes →
  OPT-7b). Edición in-place por ítem preservando `AssessmentItem.id`; editable sólo mientras ningún ECOE que
  lo use pasó a `en_pilotaje`+ → si no, 409. Soft-delete (`archived`) por defecto; hard-delete sólo vía
  `DELETE /api/instruments/{id}/purge` (`admin_ecoe`/`admin_global`, 0 referencias). Migración: `created_by`,
  `origin_event_id` (FK `ondelete SET NULL`), `archived` en `assessment_tools` + `ondelete` en las 3 FK de
  referencia — **requiere OK de schema del usuario**. Limpieza de huérfanas = comando opt-in, no en `upgrade`.

### OPT-7b · CRUD de plantillas y pacientes simulados
Follow-up de OPT-7. `StationTemplate` y `SimulatedPatient` comparten el patrón solo-creación
(`stations.py:76-95,293-312`) pero, según el hallazgo §6: `default_configuration` sólo se lee al aplicar la
plantilla en el Constructor (no en runtime) y `SimulatedPatient` no interviene en el cálculo de notas → editar
cualquiera es de bajo riesgo, sin el problema de `answers` keyed por `item.id`. CRUD: **UPDATE libre +
soft-delete** (`archived`), **sin** el gate `EDIT_BLOCKING_STATUSES` de OPT-7 (verificado: el contenido no
llega a runtime). Reusa la infraestructura de OPT-7 (regla de propiedad `ensure_tool_manage_permission`,
comando de purga). **Migración sí**: 3 columnas (`created_by`/`origin_event_id`/`archived`) ×2 tablas +
`ondelete="SET NULL"` en las 4 FK (`stations`/`station_bank` × `template_id`/`simulated_patient_id`,
anónimas en el baseline). **Estado**: `en-verificación` — rama `opt/OPT-7b-crud-plantillas`. Migración
`o5p6q7r8s9t0` (down_revision `n4o5p6q7r8s9`) verificada up/down/up y `delete_rule=SET NULL` en SQLite y
Postgres. `services/content_bank.py` concentra la regla de propiedad/gracia (genérica) + resumen de
referencias; endpoints PATCH (UPDATE libre, sin gate de estado) / DELETE(soft) / restore / purge / GET-by-id
en `/templates` y `/simulated-patients`; `include_archived` en el LIST; `_reject_archived_template/_patient`
en creación de estación/banco. Frontend: CRUD real en ambas pantallas. `scripts/purge_orphan_content.py`
(`--kind templates|patients`, dry-run por defecto). Tests: `tests/test_opt7b_content_crud.py`.

### OPT-7c · Modo "editar esta pauta" en el Constructor
El implementador de OPT-7 lo dejó pendiente marcándolo invasivo
(`PLANES/OPT-7__crud-instrumentos.md:307-310`). **Solo frontend**: el wizard
(`stations/builder/{page,shared,instrument-step}.tsx`) tiene `AssessmentMode = "existing" | "create"`,
`saveInstrumentDraft` **siempre** hace `api.createInstrument` (POST, `page.tsx:369-388`), y `applyStationLikeData`
(`page.tsx:495-568`) **no carga los ítems del tool** al abrir una estación que ya referencia uno
(`:550 setInstrumentDraft(defaultInstrumentDraft)`). Backend ya listo: `GET /api/instruments/{id}` (con `items` +
`id` + `reference_count`) y `PATCH /api/instruments/{id}` (in-place por `AssessmentItem.id`, 409 si el ECOE pasó a
`en_pilotaje`+) existen desde OPT-7; `api.instrument`/`api.updateInstrument` en `lib/api.ts:302-307`. Plan: (a)
cargar los ítems al abrir; (b) tercer modo `"edit"` (offer optimista — 409 al guardar → fallback "crear copia";
mejora backend `editable: bool` en el GET anotada como opcional); (c) `saveInstrumentDraft` bifurca PATCH/POST; (d)
copy del 409. **Sin migración.** **Estado**: `en-verificación` (rama `opt/OPT-7c-editar-pauta`) —
implementado: `AssessmentMode` gana `"edit"`, `page.tsx` carga el tool vía `api.instrument` en un
`useEffect` sobre `selectedAssessmentToolId` (no bloquea `applyStationLikeData`, que sigue síncrono y
entra en `"existing"`), `saveInstrumentDraft(mode)` bifurca PATCH/POST, el `patch` de ítems preserva
`id` para los existentes y lo omite para los nuevos, y el 409 enciende un fallback "Guardar como copia
nueva" (POST). `api.ts` adjunta `error.status` para detectar el 409 sin parsear el mensaje. Tests:
`stations/builder/__tests__/instrument-edit.test.tsx` (5 casos). — `PLANES/OPT-7c__editar-pauta-constructor.md`.
Esfuerzo M (toca la máquina de estados del wizard). **Con OPT-7c, OPT-7 queda 100% completo.**

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
- **Estado 2026-08-29**: **hecho** (desplegado 2026-08-29) |pilotaje` (router nuevo `routes/analytics.py`,
auth = `/results`). F2: `components/psychometrics-section.tsx` en `/results` y `/pilotage`. F3: el modal
«Validar pilotaje» fetchea la analítica de pilotaje y muestra advertencias no bloqueantes;
`AuditLog(validate_pilot)` en `update_ecoe_status`. Sin migración; `numpy>=1.26` explícito en
`requirements.txt`. `ALLOWED_STATUS_TRANSITIONS` y `compute_ecoe_validation` sin tocar. Backend 347
passed (SQLite + Postgres), frontend 61 passed / lint / build. Falta: validación cruzada en R/planilla
y `run_e2e.sh` (sandbox sin red).

**Actualización 2026-08-29 · OPT-17 → `en-verificación`** (rama `opt/OPT-17-normalizacion`, desde
`opt/OPT-16-station-results`). `compute_results` reescrito sobre `compute_station_results`: `percentage`
= promedio de los `percent_score` por estación (estaciones con `max > 0`); `total_score`/`max_score`
siguen crudos; campo nuevo `stations_counted` (sólo en vivo, no en el snapshot). `compute_equivalent_grade`
sin tocar. Sin migración (head sigue `n4o5p6q7r8s9`). 11 tests nuevos (`test_normalizacion_opt17.py`) +
invariante de OPT-16 reescrito. Backend 323 passed (SQLite + Postgres), frontend 59 passed / lint / build.
Falta: revisión manual sobre evento demo heterogéneo y `run_e2e.sh --grep results` (sandbox sin red).

**Actualización 2026-08-29 · OPT-16 → `en-plan`.** Mini-auditoría de fundamento
(`hallazgos/auditor-correccion-resultados__OPT-16__2026-08-29.md`) + plan redactado
(`PLANES/OPT-16__resultado-por-estacion.md`). Confirmado: `station_results` existe en el baseline
(`c7d8e9f00123_baseline_schema.py:409-425`) con la `UniqueConstraint` — **sin migración**. Alcance mecánico:
`persist_results` puebla `StationResult` (mismos filtros que `compute_results`: `mode=ejecucion`,
`is_draft=False`, `score_obtained IS NOT NULL`); `GET /results` expone `by_station` (nota por estudiante/
estación + agregado media/DE/n), congelado desde snapshot cuando el evento está cerrado (patrón OPT-1);
tabla nueva en `/results`. Sin endpoint/permiso/máquina de estados nuevos. La nota por estación es
**informativa** (alimentar un estándar por estación = OPT-17). 4 decisiones menores para el usuario en el
plan (todas no bloqueantes de la implementación).

### OPT-17b · Umbral de aprobación por estación — **DIFERIDO (recomendado)**
El implementador de OPT-17 evaluó "umbral por estación" y lo **descartó** para OPT-17
(`PLANES/OPT-17__normalizacion-por-estacion.md:252-257`): *"no es trivial, contradice el compensatorio"*.
El usuario eligió (2026-08-29) un estándar **puramente compensatorio**: un único umbral global
(`passing_reference_percent`) sobre el promedio de %-de-logro por estación; `compute_equivalent_grade` sin
tocar. Un **umbral por estación introduce un componente conjuntivo** — un modelo distinto del que se aprobó.

**Qué implicaría** (si el usuario lo pidiera):
- **Migración**: columna `min_pass_percent` (nullable, `Float`) en `stations` + UI en el Constructor de
  estaciones — gate humano.
- **Cálculo**: `compute_results` pasa a devolver `passed_stations` / `failed_stations` por estudiante
  (una estación "reprueba" si `percent_score < station.min_pass_percent`).
- **Decisión de producto no trivial**: ¿un fallo por estación **reprueba** al estudiante (conjuntivo duro),
  o sólo **advierte** en el acta (compensatorio + señal)? ¿cuántas estaciones se pueden fallar? ¿cómo
  interactúa con la nota 1.0–7.0 — se fuerza a < nota de aprobación, o se anota aparte?
- Toca `results.py`, `results/page.tsx`, el export (OPT-19), y probablemente el acta/PDF.

**Recomendación: dejarlo `diferido`** hasta que el usuario pida explícitamente un estándar
híbrido/conjuntivo. No vale la pena redactar el plan ahora — el estándar vigente es compensatorio por
decisión consciente. Si el usuario lo pide, es su propio ciclo auditor→plan (define primero el modelo de
estándar, luego se dimensiona). No es un bug ni un residuo: es una feature de otro modelo psicométrico.

---

## Lote recomendado para aprobación inmediata (estabilización P0)

`OPT-1` · `OPT-2` · `OPT-3` · `OPT-4` · `OPT-5` · `OPT-8` — planes redactados, ver `PLANES/`.

Quick wins que pueden ir en el mismo lote sin plan formal: `OPT-13` (doc), sub-fix de etiqueta de `OPT-19`.
