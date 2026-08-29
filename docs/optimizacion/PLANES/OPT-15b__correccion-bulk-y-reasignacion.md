# OPT-15b · Bulk "puntuar 0 los blancos" + reasignar correctores in-place

**Severidad: baja.** Origen: H-corr-5 §C + mini-auditoría OPT-15 §4 y §6
(`docs/optimizacion/hallazgos/auditor-correccion-resultados__OPT-15__2026-08-29.md`).
Follow-up de **OPT-15** (ya en `main` @ `b297df5`), fuera del núcleo. Se apoya en
señales que ya aporta **OPT-20 F4** (`submission_kind`, `grading[k].answered`).

## Problema

Dos residuos de fricción del corrector que OPT-15 dejó explícitamente fuera:

### 1 · Los autoenvíos en blanco se resuelven de a uno

Tras OPT-20 F4, cuando el cronómetro vence el servidor cierra la respuesta con
`submission_kind = "auto"` y cada ítem manual queda `answered: false`
(`backend/app/services/grading.py:22-34, 55-81`). Esas respuestas igual caen en
"Pendientes de corrección" y el corrector tiene que **abrir → escribir 0 →
guardar** una por una (`frontend/src/app/(app)/grading/page.tsx:297-336`). En una
estación con 30 alumnos y varios ausentes eso son decenas de ciclos de 3 clics
para un resultado predecible (0/max).

### 2 · No se pueden cambiar las estaciones de un corrector sin borrarlo

`frontend/src/app/(app)/evaluators/page.tsx:526-604` — las columnas "Estación
principal" y "Reasignar" cortan con `"No aplica"` para **todo**
`staff.role_code !== "evaluador"` (`:531`, `:546-548`). Un `corrector` es
multi-estación (`STATION_SCOPED_ROLE_CODES` + `MULTI_STATION_ROLE_CODES`,
`backend/app/api/routes/staff.py:33`) y hoy la única forma de cambiar sus
estaciones es **borrarlo y recrearlo** (el form de alta rechaza correo
duplicado). `api.updateStaff` (`PATCH /api/staff/{id}`,
`frontend/src/lib/api.ts:167`) **ya soporta** editar `station_ids` de cualquier
rol (`staff.py:144-168` → `_resolve_staff_station_ids`, que para `corrector` no
trunca y exige ≥1 estación). Sólo falta la UI.

**No es un bug de permisos**: los negativos de
`backend/tests/test_deferred_grading.py` están verdes.

## Causa raíz

- **Parte 1**: `grade_response` (`backend/app/api/routes/grading.py:206-262`)
  opera una respuesta por request; no hay endpoint de lote.
  `apply_manual_scores` (`services/grading.py:119-181`) resuelve una respuesta.
- **Parte 2**: la tabla de `/evaluators` se construyó para el modelo *una
  estación principal* del evaluador — `station_ids[0]`, `<select>` de valor
  único, `role_code !== "evaluador"` hardcodeado (`evaluators/page.tsx:531,
  546-550`). En FASE1 se extendió sólo el **form de alta** (multi-select para
  corrector, `page.tsx:229-234`), no la tabla de reasignación.

## Cambio propuesto

**Sin migración. Sin máquina de estados. Sin permisos nuevos.**

### Parte 1 — Bulk-0 de blancos por estación

**Backend — `backend/app/api/routes/grading.py`:**

Endpoint nuevo:
`POST /api/grading/{ecoe_event_id}/stations/{station_id}/zero-blank`

- Gate: `require_roles(*GRADING_ROLES)` + `ensure_event_access(*GRADING_ROLES)` +
  `_corrector_station_scope` → **si el actor es corrector, `station_id` debe
  estar en su scope**, si no → 403 (mismo guard que `grade_response`,
  `grading.py:223-228`).
- **Evento cerrado/archivado → 409** (`CLOSED_EVENT_STATUSES`, espejo exacto de
  `grade_response` `grading.py:217-221`).
  > Nota: `grade_response` **no** llama `ensure_submission_stage` hoy; sólo
  > bloquea `cerrado`/`archivado`. Este endpoint replica ese invariante (la
  > corrección diferida ocurre legítimamente con el evento `en_ejecucion`). Si el
  > usuario quiere el gate completo de etapa, es una decisión que también afecta a
  > `grade_response` — ver §Decisiones.
- Selección: `StudentResponse` con `ecoe_event_id`, `station_id`,
  `mode == ejecucion`, `max_score IS NOT NULL`, `submission_kind == "auto"`, y
  `pending_manual_keys(response)` no vacío **y todas** esas claves pendientes con
  `grading[k].answered is False`. (Es decir: un autoenvío en blanco de verdad, no
  una respuesta parcial que además venció.)
- Efecto por respuesta: para cada clave manual pendiente,
  `grading[k] = {**item, "earned": 0.0}`; recomputar `score_obtained` (suma),
  `graded_by_email = user.email`, `graded_at = utcnow_naive()`. Reusar
  `apply_manual_scores(response, {k: 0 for k in pending}, graded_by_email=...)`
  (respeta el guard de re-corrección 409 y el rango `[0, max]`).
- `AuditLog` **uno por respuesta** (`action="grade_student_response"`,
  `payload={"bulk": "zero_blank", ...}`) para que la trazabilidad sea idéntica a
  la corrección individual.
- Respuesta: `{ "zeroed": N, "pending_remaining": int, "response_ids": [...] }`
  (misma query scopeada que `_scoped_pending_responses`).

**Frontend — `frontend/src/app/(app)/grading/page.tsx`:**

- El cliente ya tiene por fila `submission_kind` y `grading[k].answered`
  (`GradableResponse`). Calcular por estación
  `blankAutoCount = filas de esa estación con submission_kind === "auto" &&
  pending_questions.length > 0 && todas las pending con grading[k].answered === false`.
- En el bloque de progreso por estación (`grading/page.tsx:387-399`, los chips
  `stationProgress`) o en el header de cada `SectionCard` de estación: botón
  **"Puntuar 0 los blancos (N)"**, visible sólo si `blankAutoCount > 0` y
  `!eventClosed`.
- `ConfirmDialog`: "Se asignará 0 a N respuestas automáticas sin contenido de la
  Estación X. Suman al consolidado de inmediato."
- Al confirmar: `api.gradingZeroBlank(eventId, stationId)` → mutar las filas
  locales afectadas (`pending_questions: []`, `score_obtained: 0`) y
  `pending_by_station` / `pending_count` con la respuesta, **sin refetch**
  (patrón `saveGrading`, `page.tsx:132-159`).
- `frontend/src/lib/api.ts`: `gradingZeroBlank(eventId, stationId)` →
  `POST /grading/${eventId}/stations/${stationId}/zero-blank`.
- `frontend/src/lib/types.ts`: tipo del retorno.

### Parte 2 — Reasignar correctores in-place

**Frontend — `frontend/src/app/(app)/evaluators/page.tsx:526-604`:**

- **Columna "Estación principal"** (`:526-536`): para
  `role_code === "corrector"`, en vez de `[0]`, renderizar la lista de nombres de
  las estaciones asignadas (`station_ids.map(id => stationOptions.find(...)?.label)`),
  o "N estaciones". Mantener "No aplica" sólo para los roles de evento completo
  (admin/coeditor/coordinador).
- **Columna "Reasignar"** (`:537-604`): para `role_code === "corrector"`,
  renderizar un `<select multiple>` (mismo patrón que el form de alta,
  `evaluators/page.tsx` selector de estaciones de corrector) ligado a un draft
  **multi**:
  - hoy `assignmentDrafts` es `Record<string, string>` (single). Agregar
    `correctorDrafts: Record<string, string[]>` (o generalizar a `string[]`).
  - "Guardar" → `api.updateStaff(Number(staff.id), { role_code: "corrector",
    station_ids: draft.map(Number) })`.
  - `_resolve_staff_station_ids` exige ≥1 estación para corrector
    (`staff.py:42-49`, 400 *"El corrector debe tener al menos una estación…"*) →
    deshabilitar "Guardar" con selección vacía + surfacear el 400 si llega.
  - cada `station_id` debe pertenecer al ECOE (`staff.py:50-63`) — el
    `<select>` ya sólo ofrece estaciones del evento.
- Los roles de evento completo (admin/coeditor/coordinador) siguen con "No
  aplica".

**Backend: sin cambios.** `PATCH /api/staff/{id}` ya cubre el caso
(`update_staff` → `_resolve_staff_station_ids` con `single=False` para
`corrector`). La delegación por `coeditor_docente` / `coordinador_operativo` ya
está permitida y testeada
(`test_coeditor_and_coordinator_can_delegate_corrector_multi_station`).

## Tests (incluye negativos — bulk toca datos con scoping; reasignación toca permisos)

### Backend — `backend/tests/test_grading_bulk_opt15b.py` (nuevo)

**Negativos obligatorios:**
- `test_zero_blank_only_touches_target_station` — corrector con `station_ids=[A]`,
  autoenvíos en blanco en A y B: `POST …/stations/A/zero-blank` puntúa sólo A; las
  de B quedan intactas.
- `test_zero_blank_station_outside_corrector_scope_returns_403` — corrector pide
  `…/stations/B/zero-blank` con B fuera de su asignación → 403; nada cambia.
- `test_zero_blank_after_close_returns_409` — evento `cerrado` → 409; ninguna
  respuesta se toca.
- `test_zero_blank_skips_non_blank_and_non_auto` — en la misma estación: una
  respuesta `submission_kind="manual"` pendiente, una `auto` con un ítem
  `answered=true`, y una `auto` totalmente en blanco → sólo la tercera se puntúa
  0; las otras dos siguen pendientes.
- `test_zero_blank_does_not_regrade_resolved` — una respuesta ya corregida no se
  toca (el guard 409 de `apply_manual_scores` no debe romper el lote: filtrar
  antes las ya resueltas).

**Positivos:**
- `test_zero_blank_scores_and_feeds_results` — tras el bulk, `compute_results`
  incorpora los 0 (las respuestas pasan a tener `score_obtained` definitivo).
- `test_zero_blank_writes_one_auditlog_per_response`.
- `test_zero_blank_returns_pending_remaining`.

### Backend — reasignación (extender `test_deferred_grading.py`)

- `test_corrector_station_ids_updated_in_place` — `PATCH /api/staff/{id}` con
  `station_ids` nuevo sobre un corrector existente → el scope de
  `GET /api/grading/{event}` cambia en consecuencia (regresión de que PATCH ya lo
  soporta).
- `test_corrector_cannot_be_left_without_stations` — `PATCH` con
  `station_ids: []` para un corrector → 400.
- `test_reassign_corrector_station_must_belong_to_event` — `station_id` de otro
  ECOE → 400.

### Frontend — vitest

- `grading/__tests__/page.test.tsx`: el botón "Puntuar 0 los blancos" aparece
  sólo cuando hay filas `auto` + todas `answered:false` pendientes en esa
  estación; al confirmar llama `api.gradingZeroBlank` y muta filas sin refetch
  (`api.gradingList` no se re-llama).
- `evaluators/__tests__/page.test.tsx`: para un `corrector`, la columna
  "Reasignar" muestra un multi-select y "Guardar" llama `api.updateStaff` con
  `station_ids` array; deshabilitado con selección vacía.

## Riesgos / alcance

- **Bulk-0 es una escritura de lote sobre notas** — mitigado: mismo gate que
  `grade_response`, `AuditLog` por respuesta (trazabilidad idéntica),
  criterio de selección estricto (sólo `auto` + todo `answered:false`), y reusa
  `apply_manual_scores` (no reimplementa la aritmética).
- **El criterio "blanco de verdad"**: si una respuesta es `auto` pero tiene 1 de
  3 ítems manuales respondidos, **no** entra al bulk (el corrector la revisa a
  mano). Explícito en el test `…skips_non_blank_and_non_auto`.
- **Reasignación**: cero riesgo backend (endpoint ya probado). El riesgo es de UI
  — el `DataTable` de `/evaluators` es compartido; el cambio es aditivo por
  `role_code`.
- Commits: 1 corte backend (endpoint bulk + tests), 1 corte frontend parte 1
  (botón + confirm), 1 corte frontend parte 2 (columnas corrector + tests). Se
  pueden hacer los tres por separado; la parte 2 es independiente de la parte 1.

## Esfuerzo

**S–M** (≈1,5 días). Parte 1: endpoint acotado + botón + confirm + mutación
local (~S). Parte 2: sólo UI, dos columnas de un `DataTable` + estado multi-draft
(~S). Los tests negativos suman.

## Verificación

- [ ] `cd backend && python3 -m pytest`
- [ ] `TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q`
- [ ] `cd frontend && npm run lint && npm run build && npx vitest run`
- [ ] `./scripts/run_e2e.sh --grep "grading"` sobre el stack de ramas (Docker)

## Decisiones para el usuario

1. **Gate de etapa del bulk-0**: ¿replicar exactamente el de `grade_response`
   (sólo bloquea `cerrado`/`archivado`) — recomendado, coherente — o exigir
   `ensure_submission_stage` (bloquea también `publicado`, `pilotaje_validado`,
   etc.)? Lo segundo sería más estricto que la corrección individual de hoy; si se
   quiere, conviene aplicarlo a ambos endpoints en un fix aparte.
2. **Ubicación del botón bulk-0**: ¿en los chips de progreso por estación
   (`grading/page.tsx:387-399`) o como acción en el header de cada estación?
   (recomendado: junto al chip, donde ya se ve "Estación 3: 4/12").
3. **Reasignación — "Estación principal" del corrector**: ¿mostrar la lista
   completa de nombres o un resumen "N estaciones" con tooltip? (recomendado:
   resumen + tooltip, la tabla ya es ancha).

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-29
- Aprobado por usuario: ✅ 2026-08-29 (decisiones: Bulk-0 = espejo de `grade_response`,
  solo bloquea `cerrado`/`archivado`, sin tocar `grade_response`; reasignación de
  correctores puramente UI).
- **Implementado: ✅ 2026-08-29** — rama `opt/OPT-15b-bulk-reasignacion` (desde
  `opt/followups`). Commits:
  - `feat(grading): puntuar 0 los autoenvíos en blanco de una estación en bloque (OPT-15b)`
    — `POST /api/grading/{event}/stations/{station_id}/zero-blank`,
    `tests/test_grading_bulk_opt15b.py` (negativos + positivos), reasignación in-place
    en `tests/test_deferred_grading.py`.
  - `feat(grading): botón "puntuar 0 los blancos" por estación en /grading (OPT-15b)`
    — `api.gradingZeroBlank`, `GradingZeroBlankResult`, botón + `ConfirmDialog`,
    mutación local sin refetch; vitest de la página.
  - `feat(evaluators): reasignar estaciones de un corrector in-place (OPT-15b)`
    — columnas "Estación principal" / "Reasignar" para `corrector` (multi-select +
    `api.updateStaff`); `evaluators/__tests__/page.test.tsx` nuevo.
  - `docs(optimizacion): OPT-15b → en-verificación`.
  **Estado: en-verificación** — suite SQLite (371) y Postgres verde;
  `npm run lint && build && vitest` (65) verde; `alembic upgrade head` sin migración.
  Falta revisión del usuario + e2e + merge/deploy.

## Verificación registrada

- [x] `cd backend && python3 -m pytest` → 371 passed (SQLite)
- [x] `TEST_DATABASE_URL=postgresql+psycopg://…/ecoe_test python3 -m pytest -q` → verde (Postgres + migraciones)
- [x] `cd backend && alembic upgrade head` desde base limpia → OK, sin migración nueva
- [x] `cd frontend && npm run lint && npm run build && npx vitest run` → lint sin errores, build ok, 65 tests verdes
- [ ] `./scripts/run_e2e.sh --grep "grading"` sobre el stack de ramas (Docker) — pendiente
