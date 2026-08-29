# Mini-auditoría — auditor-correccion-resultados · OPT-15 · 2026-08-29

Fundamento para el plan de **OPT-15 — fricción del corrector en la evaluación
diferida** (hallazgos base H-corr-5 y H-corr-6). Rama auditada: `opt/backlog-grupo-b`
(post-merge Grupo A + OPT-20 F1–F4). Modo: código + API in-process (`TestClient`).

Scratch test usado y borrado: `tests/test_audit_opt15_scratch.py`
(`test_grading_endpoint_omits_assessment_tool` — verde; dump de claves de fila abajo).

---

## Resumen ejecutivo

| # | Tema | Estado hoy | Severidad del gap |
|---|---|---|---|
| 1 | Flujo del corrector | Lista FIFO plana; ~2 clics + N entradas numéricas por respuesta + scan manual y 1 clic para abrir la siguiente; refetch completo tras cada guardado | media (fricción-UX a escala) |
| 2 | `pending_count` | Sí está acotado al scope del corrector (vía query), pero **no** respeta el filtro de estación del cliente y **la UI no lo renderiza** (campo muerto tras el rewrite de OPT-20 F4) | baja (inconsistencia UI/backend) |
| 3 | Pauta de referencia | El endpoint **no** envía el `AssessmentTool` de la estación pese a FASE1 §Decisión 4; `apply_manual_scores` es número libre `[0,max]` por pregunta | media (gap vs. diseño) |
| 4 | Asignación de estaciones al corrector | Se crea desde el form de `/evaluators` (multi-select); la tabla "Reasignar" **excluye** a los correctores (`role_code !== "evaluador"` → "No aplica") → sin edición in-place | media (fricción-UX / operativo) |
| 5 | Cola personal / "siguiente" | No existe; todo lo resuelve el cliente sobre la lista completa | — (decisión de diseño) |
| 6 | OPT-20 F3/F4 | Ya aporta badges "automática/incompleta" y `answered` por pregunta → mejora el *triage*, no la cola ni la pauta | parcial |
| 7 | OPT-16 | Sin solape de archivos ni de datos si OPT-15 mantiene el puntaje en `StudentResponse.score_obtained` | sin conflicto |

---

## 1 · Estado actual del flujo del corrector

### Backend — `GET /api/grading/{ecoe_event_id}` → `list_gradable_responses`
`backend/app/api/routes/grading.py:56-124`

- Gate: `require_roles(*GRADING_ROLES)` con
  `GRADING_ROLES = (admin_ecoe, coeditor_docente, corrector)` (`grading.py:27-31`).
- `ensure_event_access` (evento) + `_corrector_station_scope` (`grading.py:40-53`):
  - `admin_ecoe` / `coeditor_docente` (`FULL_GRADING_ROLES`) → `None` = todas las
    estaciones.
  - `corrector` → set de `StaffAssignment.station_ids` de su **única** asignación
    `role_code == "corrector"` en ese evento.
  - Sin `StaffAssignment` corrector, o `station_ids` vacío/ inexistente → `set()`
    vacío → `return {"responses": [], "pending_count": 0}` (`grading.py:73-74`).
    **Indistinguible de "todo corregido"** → H-corr-6.
- Filtros de la query (`grading.py:67-75`): `ecoe_event_id`,
  `mode == ejecucion` (pilotaje nunca entra a la cola), `max_score IS NOT NULL`,
  y `station_id IN scope` sólo para el corrector.
- Orden: `submitted_at ASC, id ASC` (`grading.py:79`) — FIFO puro. **Sin
  agrupación por estudiante ni por estación**, sin prioridad (contingencia /
  draft_finalized / no-blanco primero).
- Cada fila (claves verificadas por el scratch test):
  `response_id, mode, submission_kind, by_contingency, student_id, student_name,
  student_ecoe_number, station_id, station_number, station_name, submitted_at,
  answers, grading, pending_questions, score_obtained, max_score, graded_by_email,
  graded_at, questions`.
  `questions` = `station.student_form_definition["questions"]`.
  **No hay `assessment_tool`** (ver §3).

### Frontend — `frontend/src/app/(app)/grading/page.tsx`

- Evento `cerrado/archivado` → aviso, cola no disponible (`page.tsx:232-253`).
- Header (`SectionCard`) + `<select>` de estación, sólo visible si
  `stationChoices.length > 1`; opciones `"Todas (N)"` + una por estación
  (`page.tsx:262-278`). Filtro **puramente cliente** (`visibleResponses`,
  `page.tsx:83-85`).
- Dos `SectionCard`: `Pendientes de corrección (${pending.length})` y
  `Corregidas (${graded.length})`, ambos contadores **recalculados en el cliente**
  sobre `visibleResponses` (`page.tsx:86-87, 300, 309`). `data.pending_count` del
  backend **no se renderiza en ninguna parte** (sólo aparece en tipos y en el stub
  de evento cerrado: `page.tsx:60, 63, 208`).
- Tarjeta de fila: alumno, estación, modo (`Pilotaje`/`Ejecución`), timestamp,
  badges OPT-20 F4 (`Respuesta automática` / `submissionKindLabel` / `Incompleta —
  ítems sin responder`), badge de puntaje o `Pendiente (N)`, botón `Corregir`.
- Expandida: por cada `pending_question` → label, badge `Sin responder` si
  `answered === false`, texto de la respuesta, `<input type=number min=0
  max=<item.max> step=0.5>`. Botón `Guardar corrección` deshabilitado hasta que
  todos los inputs tengan valor (`page.tsx:196`).

### Clics para corregir una respuesta y pasar a la siguiente

1. (una vez por sesión) elegir ECOE en el selector global de `app-shell`.
2. abrir `/grading`.
3. (opcional, si hay >1 estación) elegir estación en el filtro.
4. **clic `Corregir`** → expande la fila.
5. escribir **un número por cada pregunta manual** (sin submit por teclado).
6. **clic `Guardar corrección`**.
7. al guardar: `api.gradeResponse` → **`api.gradingList(eventId)` completo otra
   vez** → `setExpandedId(null)` → mensaje *"Corrección guardada; el puntaje ya
   suma al consolidado."* (`page.tsx:203-212`).
8. para la siguiente: **scan visual** de la lista re-ordenada + **clic `Corregir`**
   en la próxima fila `Pendiente`.

≈ **2 clics + N entradas numéricas por respuesta**, más 1 clic y un barrido visual
para localizar la siguiente. Sin "siguiente pendiente", sin autoavance, sin
progreso personal ("te quedan N"), sin atajo de teclado. El refetch completo tras
cada guardado es O(todas las respuestas del evento) por corrección.

---

## 2 · `pending_count` / contadores

- Cálculo: `grading.py:123` → `sum(1 for row in rows if row["pending_questions"])`.
  `pending_questions` = `pending_manual_keys(response)`
  (`services/grading.py:111-116`): entradas `kind == "manual"` con `earned is None`.
- **Scope real**: para el corrector, `rows` ya viene filtrado a sus estaciones, así
  que `pending_count` **sí** está acotado a su asignación (la afirmación de
  H-corr-5 "global, no respeta el scope del corrector" es imprecisa en este punto).
  Para `admin_ecoe`/`coeditor_docente` es global al evento (correcto para ese rol).
- Lo que **no** respeta: el `stationFilter` del cliente (es post-fetch) — y, más
  de fondo, **la UI no usa el campo**: los números visibles se recalculan en el
  cliente. `pending_count` es hoy un campo muerto en la respuesta.
- Qué debería mostrar por corrector: progreso personal
  **"N de M corregidas en tus estaciones"**, idealmente desglosado por estación
  (`pending_by_station`), y coherente con el filtro activo. Que `grade_response`
  devuelva el contador scopeado actualizado para el feedback post-guardado.

---

## 3 · La pauta de referencia

- **El endpoint no devuelve los ítems del `AssessmentTool` de la estación.**
  `list_gradable_responses` sólo adjunta `questions` del
  `student_form_definition` (`grading.py:119-121`). Scratch test
  `test_grading_endpoint_omits_assessment_tool` (verde): la fila **no** tiene
  clave `assessment_tool` aun con `station.assessment_tool_id` poblado y el tool
  con 2 `AssessmentItem`.
  El serializador ya existe y ya se usa en el flujo presencial:
  `app/utils/serializers.py::serialize_assessment_tool`, invocado en
  `routes/evaluator.py:129` y `:272`. Reutilización trivial.
- **`apply_manual_scores` es entrada numérica libre**, no estructurada
  (`services/grading.py:119-182`): un `float` por clave de pregunta manual,
  acotado a `[0, item["max"]]`. Sin puntuación por ítem de rúbrica, sin comentario
  por ítem. Re-puntuar una pregunta ya resuelta está prohibido (409 → flujo de
  rectificación).
- **FASE1 §Decisión 4** dice: `apply_manual_scores` se mantiene (número por
  pregunta, `[0,max]`); **si la estación tiene `assessment_tool_id`, la pantalla la
  muestra como referencia**; la puntuación estructurada contra ítems es **Fase 2**.
  → **Lo que falta** para cumplir el diseño: que el endpoint envíe el tool
  serializado y que `/grading` lo pinte como panel de referencia. Es sólo eso
  (≈XS). La pauta estructurada **no** está pedida por el doc para esta fase.
- Contexto para decidir el alcance: **ni siquiera el camino del evaluador
  presencial es estructurado server-side.** `POST /evaluator/submit` recibe un
  `score_obtained` total calculado por el cliente + un `answers` JSON libre; el
  servidor sólo valida `0 ≤ total ≤ authoritative_max`
  (`routes/evaluator.py:456-500`). Hacer el corrector item-structured *validado en
  backend* sería más estricto que el evaluador de hoy.
- Además, hoy **no hay relación 1:1** entre las preguntas manuales del formulario y
  los `AssessmentItem` del tool (una estación puede tener un tool de 6 ítems y un
  formulario con un solo `short_text` de 6 puntos). Cablear puntuación por ítem
  obliga a decidir *qué* puntúa el corrector (los ítems del tool, con el formulario
  como artefacto a leer) — decisión de producto, no refactor.

---

## 4 · Asignación de estaciones al corrector

- **Modelo**: `StaffAssignment.station_ids` (JSON list) con
  `role_code == RoleCode.corrector`. `corrector ∈ MULTI_STATION_ROLE_CODES`
  (`utils/helpers.py`) → `normalize_station_ids(single=False)` (no trunca);
  `corrector ∈ STATION_SCOPED_ROLE_CODES` (`routes/staff.py:33`) → exige ≥1
  estación (`staff.py:42-49`, 400 *"El corrector debe tener al menos una estación
  de evaluación diferida asignada"*); cada `station_id` debe pertenecer al ECOE
  (`staff.py:50-63`).
- **Dónde se crea**:
  - `POST /api/staff` (`create_staff`, `staff.py:101`), `PATCH /api/staff/{id}`
    (`update_staff`, `staff.py:143`) — ambos vía `_resolve_staff_station_ids`.
  - Invitación (`assign_or_invite_member`, `routes/invitations.py`).
  - `POST /staff/import` (CSV) → **fuerza `station_ids=[]`** (`staff.py:266`) — un
    corrector importado queda sin estaciones y hay que completarlas después.
  - Delegable por `coeditor_docente` / `coordinador_operativo`
    (`ensure_staff_role_can_be_delegated`); test verde
    `test_coeditor_and_coordinator_can_delegate_corrector_multi_station`.
- **UI `/evaluators`**:
  - Form "Guardar asignación": selector de rol con
    `"Corrector (evaluación diferida)"` (`evaluators/page.tsx:334`); si
    `role_code === "corrector"` aparece un `<select multiple>` de estaciones
    (`page.tsx:363-389`); el submit envía `station_ids: form.station_ids.map(Number)`
    (`page.tsx:229-234`).
  - **Tabla "Equipo operativo" → columna "Reasignar"** (`page.tsx:537-604`): el
    `render` corta con *"No aplica (rol de evento completo)"* para **cualquier**
    `staff.role_code !== "evaluador"` (`page.tsx:546-548`). Igual la columna
    "Estación principal" (`page.tsx:531`, `[0]` del array). → **Un corrector ya
    creado no tiene ningún camino in-place para cambiar sus estaciones**: hay que
    borrarlo y recrearlo (el form rechaza correo duplicado). `api.updateStaff`
    (PATCH) lo soporta; la UI simplemente nunca lo llama para correctores.
- **Por qué**: la tabla se construyó para el modelo *una estación principal* del
  evaluador — `station_ids[0]`, `<select>` de valor único, `role_code !==
  "evaluador"` hardcodeado. En FASE1 se extendió sólo el form de alta (lista de
  cambios frontend, fila `evaluators/page.tsx`); la tabla de reasignación quedó
  fuera.

---

## 5 · Cola personal / "siguiente pendiente"

**No existe endpoint.** `GET /grading/{event}` devuelve la lista (scopeada) y el
cliente hace todo. Opciones:

- **(a) Mínima — sin endpoint nuevo (recomendada):** extender la respuesta actual
  con `assessment_tool` (serializado), `scope` (ver §C abajo) y
  `pending_by_station`. "Siguiente pendiente" = cliente: tras guardar, en vez de
  `setExpandedId(null)` + refetch completo, abrir la próxima fila con
  `pending_questions.length > 0`. Cambiar el post-save para **no** refetchear todo
  (actualizar la fila con el retorno de `grade_response`, o que `grade_response`
  devuelva `next`).
- **(b) `GET /api/grading/{event}/next?station_id=&after=`** → única próxima
  respuesta sin puntuar (más antigua primero, dentro del scope), o vacío. Útil sólo
  si aparece un dispositivo "corrector de a una" o eventos muy grandes. No
  necesario para la escala declarada (decenas–bajos cientos).
- **(c)** `grade_response` devuelve `{graded, score_obtained, max_score, next: {…},
  pending_remaining: N}` — evita el refetch y da el feedback de progreso.

**UI**: autoavance a la siguiente pendiente; header de progreso personal ("N de M
en tus estaciones" + chips por estación); empty-states diferenciados (§C);
submit con Enter.

---

## 6 · Interacción con OPT-20 F3/F4 (ya mergeado — `f5d43c3`, `9213269`)

- La fila ya trae `submission_kind` (`manual` / `auto` / `draft_finalized` / …) y
  `grading[key].answered: bool` (helper `is_answered`, `services/grading.py:22-34`).
  `/grading` pinta badges `Respuesta automática`, `Incompleta — ítems sin
  responder` y `Sin responder` por pregunta (`grading/page.tsx:121-141, 171-173`).
- **Qué cubre de H-corr-5**: mejora la **señal de triage** — el corrector distingue
  un autoenvío en blanco del barrido de una entrega deliberada, y puede
  fast-trackear los blancos. **No** toca cola / siguiente / progreso / pauta.
- **Qué queda**: los autoenvíos en blanco igual caen en "Pendientes" y hay que
  resolverlos **uno a uno** (abrir → escribir 0 → guardar). Un
  **"puntuar en 0 las N respuestas en blanco de esta estación"** (apoyado en
  `submission_kind == "auto"` + `answered == false`) es un add natural de OPT-15.
  El resto de H-corr-5 (cola "asignadas a mí", siguiente-pendiente, progreso
  personal, pauta de referencia) sigue abierto. H-corr-6 intacto.

---

## 7 · Solape con OPT-16

OPT-16 (`PLANES/FASE2_ANALISIS_DATOS__scoping.md`): poblar `StationResult` en
`persist_results` desde `EvaluatorRecord + StudentResponse` por (estudiante,
estación), `mode == ejecucion`; exponer `by_station` en `/results`. Sin migración.

- OPT-15 **no toca** `persist_results`, `compute_results`, ni dónde vive el puntaje
  (FASE1 §Decisión 3: sigue en `StudentResponse.score_obtained`;
  `compute_results` ya incorpora los `score_obtained` resueltos —
  `test_corrector_grades_only_assigned_station_and_feeds_results` verde).
- **Sin solape de archivos**: OPT-15 = `grading.py`, `grading/page.tsx`,
  `evaluators/page.tsx`, `routes/staff.py`; OPT-16 = `results.py`,
  `results/page.tsx`.
- **Única dependencia real de datos**: si OPT-15 evolucionara a puntuación por
  ítem persistida **fuera** de `score_obtained` (JSON paralelo / tabla nueva),
  OPT-16 (agregado por estación) y OPT-18 (item analysis) querrían leer eso. →
  **Regla para OPT-15**: mantener `score_obtained` como valor autoritativo y poner
  cualquier detalle por ítem **dentro del JSON `grading`** (mismo patrón que F4 usó
  para `answered`), nunca en un store paralelo. Con eso, cero conflicto y orden
  indistinto (hacer OPT-15 primero incluso ayuda: expone la realidad de
  "pendientes de corrección" antes de que `StationResult` empiece a snapshotear).

---

## Decisiones de diseño para OPT-15

### A · Alcance de la "pauta estructurada": **referencia, no puntuación por ítem**

Ceñirse a FASE1 §Decisión 4:

- **Incluir**: serializar `assessment_tool` (vía `serialize_assessment_tool`) en la
  respuesta de `GET /grading/{event}` y renderizarlo en `/grading` como panel de
  referencia colapsable junto a los inputs de las preguntas manuales.
- **Mantener** `apply_manual_scores` como número libre `[0,max]` por pregunta.
- **Motivos**: (1) es lo que el doc ya promete y es ≈XS; (2) la puntuación
  estructurada contra `assessment_tool.items` está explícitamente en Fase 2 y
  necesita el mismo renderer que la pantalla Evaluador + una decisión de modelo de
  datos (dónde viven los puntajes por ítem); (3) hoy no hay mapeo 1:1
  pregunta↔ítem, así que "puntuar por ítem" implica redefinir qué puntúa el
  corrector — decisión de producto.
- **Punto medio opcional** (si el usuario quiere más que referencia sin comprometer
  Fase 2): permitir que el corrector ingrese marcas por ítem que la UI **suma en el
  cliente** al puntaje de la pregunta (igual que hace hoy la pantalla Evaluador),
  guardando el desglose en `grading[key].items` (JSON) para el export. Sin cambio
  de endpoint/esquema más allá de aceptar/eco de ese JSON. Da dato item-level al
  análisis sin validación estructurada server-side.
- **Follow-up Fase 2 (anotar)**: puntuación estructurada real contra
  `assessment_tool.items` + comentario por ítem, compartiendo renderer con
  `/evaluator`.

### B · ¿La cola personal necesita endpoint nuevo? **No.**

- Extender `GET /grading/{event}` con `assessment_tool`, `scope` y
  `pending_by_station`; "siguiente pendiente" y progreso en el cliente.
- Cambiar el post-guardado para **no** refetchear la lista completa
  (`grading/page.tsx:206`): actualizar la fila con el retorno de `grade_response`,
  o que `grade_response` devuelva `{…, next, pending_remaining}`.
- `GET /grading/{event}/next` queda como pulido opcional — sólo si aparece un
  dispositivo "corrector de a una" o eventos muy grandes.

### C · Otros ítems concretos de OPT-15

| Ítem | Severidad | Nota |
|---|---|---|
| Distinguir empty-state (H-corr-6): añadir `scope: {is_corrector, has_assignment, assigned_station_ids}` a la respuesta para que la UI diga *"no tienes estaciones asignadas — pide al coordinador"* vs *"todo corregido ✓"* vs *"aún no hay respuestas"* | baja | el scope ya se computa en `_corrector_station_scope`; es exponerlo |
| Extender la columna "Reasignar" de `/evaluators` a `role_code === "corrector"` con multi-select ligado a `api.updateStaff(id, {role_code, station_ids})` | media | PATCH ya lo soporta; hoy sólo delete+recreate |
| Bulk "puntuar 0 las respuestas en blanco de esta estación" (usa `submission_kind == "auto"` + `answered == false`) | media | cierra el residuo de fricción de F4 |
| Feedback al guardar: `grade_response` devuelve contador scopeado → *"estación X de \<alumno\> cerrada; te quedan N en tus estaciones"* | baja | hoy devuelve sólo score/max |
| Orden de la cola: agrupar por estación (o priorizar `by_contingency` / `draft_finalized` / no-blanco) en vez de `submitted_at` FIFO | baja | `grading.py:79` |
| `pending_count`: o se usa en la UI (scopeado + coherente con el filtro) o se elimina de la respuesta | baja | inconsistencia UI/backend actual |
| Refetch completo tras cada guardado | baja (perf) | O(respuestas del evento) por corrección |
| CSV import fuerza `station_ids=[]` para corrector (`staff.py:266`) | baja | documentar / permitir columna de estaciones |

### Sin hallazgo (verificado)

- Seguridad del scoping del corrector: `test_deferred_grading.py` verde —
  evento A no ve B (403), estación fuera de `station_ids` (403), sin acceso a
  `/results` `/live` `/students` `/evaluator` `/dashboard`. OPT-15 es UX de una
  feature ya entregada, no un bug de permisos.
- Trazabilidad ya distingue "enviado" de "corregido":
  `build_traceability_report` marca `pending_deferred_gradings` y
  `completion_status = "parcial"` mientras haya respuestas sin puntuar en
  estaciones diferidas (`results.py:312-345`;
  `test_pending_deferred_grading_keeps_student_partial_and_is_reported` verde).
- El contador de cierre `pending_deferred_grading_stations` **sí** filtra
  `mode == ejecucion` (`validation.py:231`) — corregido respecto de lo anotado en
  H-corr-4/H-vivo-1.
