# Auditoría — Corrección, resultados y análisis de datos

Fecha: 2026-08-28
Auditor: `auditor-correccion-resultados`
Alcance: primera pasada, profundidad media-alta. Grading en vivo + diferido (rol
`corrector`), consolidación al cierre (`persist_results`), inmutabilidad
post-cierre, GETs de resultados sin mutación, completitud del dato para análisis
final. Método: lectura de código + ejercicio in-process con `TestClient` (tests
scratch `test_audit_correccion_*`, ya borrados).

## Resumen de severidades

### Sección A — Corrección y cierre
| Severidad | Nº |
|---|---|
| bloqueante | 1 (H-corr-1) |
| alta | 2 (H-corr-2, H-corr-3) |
| media | 2 (H-corr-4, H-corr-5) |
| baja | 1 (H-corr-6) |

### Sección B — Análisis de datos
| Severidad | Nº |
|---|---|
| alta | 3 (H-dato-1, H-dato-2, H-dato-3) |
| media | 2 (H-dato-4, H-dato-5) |
| baja | 1 (H-dato-6) |

### Bloqueantes
- **H-corr-1**: los resultados cambian después de `cerrado`. `GET /results/{id}`
  (y el export Excel) recalculan en vivo con `compute_results`; corregir o
  regrabar cualquier respuesta tras el cierre altera lo que devuelve el
  endpoint. No hay ningún camino de lectura que exponga un snapshot congelado.

### Gaps de dato más importantes para el análisis final
1. **No hay nota ni desglose por estación** en ningún endpoint (H-dato-1). El
   modelo `StationResult` existe en el schema pero está **muerto** (nadie lo
   escribe ni lo lee). Sin esto no hay ranking por estación, ni dificultad, ni
   discriminación, ni detección de estación-outlier.
2. **Cero psicometría** (H-dato-2): sin fiabilidad (alfa de Cronbach /
   inter-estación), sin índice de dificultad/discriminación por ítem o estación,
   sin punto-biserial, sin borderline/standard-setting. El "pilotaje", que es
   exactamente la fase donde se valida psicométricamente una estación, **no
   produce ninguna salida analítica** (`compute_results` filtra
   `mode == ejecucion`, así que los datos de pilotaje son inaccesibles vía
   Resultados).
3. **Suma cruda sin ponderación de estación** (H-dato-3): `total_score` suma los
   puntos de todas las estaciones tal cual; una estación de `max_score=20` pesa
   3× una de `max_score=6`. No hay pesos configurables ni normalización por
   estación, ni estándar conjuntivo (aprobar N de M estaciones).
4. **Export pobre** (H-dato-4): una sola hoja `consolidado` con la fila plana por
   estudiante. Sin hoja por estación, sin item analysis, sin metadatos del ECOE,
   sin identificación de evaluador/corrector. El "Export PDF" de Resultados es en
   realidad el respaldo de contingencia (instrucciones de estación), no
   resultados.

---

## SECCIÓN A — Corrección y cierre

### H-corr-1 · Los resultados cambian tras el cierre (no hay snapshot inmutable)
- **Rol / pantalla**: admin_ecoe / coeditor · `/results`, `/grading`
- **Severidad**: bloqueante
- **Tipo**: bug / dato
- **Evidencia**:
  - `app/api/routes/operational.py:326-333` — `GET /results/{id}` llama
    `compute_results(db, ...)` en vivo, nunca lee `ECOEResult`.
  - `app/api/routes/operational.py:347-355` — `GET .../export/excel` idem
    (`export_results_excel(..., persist=False)` → `compute_results`).
  - `app/services/validation.py:453-468` — cerrar corre `persist_results` pero…
  - `grep -rn "ECOEResult"` → solo se **escribe** (`results.py:104-113`); ningún
    endpoint la **lee**.
- **Reproducción** (test scratch, verificado):
  1. Evento en ejecución, estación de corrección diferida, 1 respuesta enviada
     sin puntuar.
  2. `PUT /ecoe/{id}` a `cerrado` → `ECOEResult` = `(total=0, max=0)`,
     `GET /results` = `(0, 0)`, check-in pasa a `cerrado`.
  3. `POST /api/grading/responses/{rid}` `{"scores": {"question_1": 6}}` →
     **HTTP 200** (ver H-corr-2).
  4. `GET /results/{id}` → ahora `(total=6, max=6)`. `ECOEResult` sigue
     `(0, 0)` (stale).
- **Esperado vs. observado**: esperado — después de `cerrado` los resultados
  están congelados (lo dice `EVALUACION_DIFERIDA_FASE1.md` §"Decisión 5" y
  CLAUDE.md "cerrar consolida resultados … congelando la operación"). Observado —
  el endpoint de lectura ignora el snapshot y recalcula; el número mostrado
  depende del estado mutable de `StudentResponse`/`EvaluatorRecord` en el momento
  de la consulta.
- **Notas del auditor**: dos arreglos posibles y no excluyentes: (a) que
  `GET /results` y el export lean `ECOEResult` cuando el evento está en
  `cerrado`/`archivado` y solo recalculen en vivo antes; (b) cerrar el portillo
  de escritura (H-corr-2). `ECOEResult` no tiene columna de `mode` ni de
  `consolidated_at` explícito (solo `TimestampMixin`), habría que exponer
  `updated_at` como "fecha de consolidación".

### H-corr-2 · `/grading` no tiene gate de estado: se corrige después de `cerrado`
- **Rol / pantalla**: corrector, admin_ecoe · `/grading`
- **Severidad**: alta
- **Tipo**: bug / permiso
- **Evidencia**: `app/api/routes/grading.py:107-144` — `grade_response` no llama
  `ensure_submission_stage` ni comprueba `ecoe_event.status`. Contrasta con
  `routes/evaluator.py:269` y `routes/student_access` que sí gatean con
  `ensure_submission_stage`.
- **Reproducción**: paso 3 de H-corr-1 — `POST /api/grading/responses/{rid}`
  sobre un evento `cerrado` responde `200 {"graded": true, "score_obtained": 6}`.
- **Esperado vs. observado**: `FASE1.md` §Alcance "No incluye … Corrección
  después de `cerrado`". Observado: se permite sin restricción, en cualquier
  estado (incluido `borrador`/`archivado`).
- **Notas del auditor**: mínimo, bloquear `grade_response` (y ocultar acción en
  UI) cuando `status in {cerrado, archivado}`. Si se quiere permitir corrección
  tardía como caso operativo, entonces debe re-disparar `persist_results` para
  no dejar el consolidado stale — pero eso rompe la inmutabilidad, así que la
  decisión es de producto. El `AuditLog` sí registra la corrección
  (`grading.py:126-136`), eso está bien.

### H-corr-3 · Re-corrección silenciosa: `apply_manual_scores` sobrescribe un puntaje ya resuelto
- **Rol / pantalla**: corrector, admin_ecoe · `/grading`
- **Severidad**: alta
- **Tipo**: bug / dato
- **Evidencia**: `app/services/grading.py:97-148`. `pending` (línea 102-106)
  incluye **todas** las claves `kind == "manual"`, también las que ya tienen
  `earned` != None. `missing` (118-121) solo exige las que aún son `None`. Si
  todas están resueltas, se puede reenviar `scores` con valores nuevos y
  reescribe `score_obtained`, `graded_by_email`, `graded_at` sin aviso.
- **Reproducción**: `POST /grading/responses/{rid} {"scores":{"question_3": 2}}`
  y luego otra vez `{"scores":{"question_3": 3}}` → segunda gana, sin error.
- **Esperado vs. observado**: no hay decisión de diseño documentada. Podría ser
  deseado (corregir un error de tipeo) pero hoy es indistinguible de una
  manipulación; sin "primera nota vs. nota vigente", sin doble confirmación,
  sin bloqueo tras consolidar.
- **Notas del auditor**: combinado con H-corr-2 permite cambiar notas después
  del cierre. El `AuditLog` guarda cada `grade_student_response` con
  `score_obtained`, así que la evidencia forense existe, pero no hay UI ni
  endpoint que muestre el historial.

### H-corr-4 · La cola de corrección mezcla respuestas de pilotaje y de ejecución
- **Rol / pantalla**: corrector · `/grading`
- **Severidad**: media
- **Tipo**: fricción-UX / inconsistencia backend/UI
- **Evidencia**: `app/api/routes/grading.py:52-64` — `filters` solo acota por
  `ecoe_event_id` y `max_score is not None`. No filtra `StudentResponse.mode`.
  `compute_results` (`results.py:66-81`) sí filtra `mode == ejecucion`.
- **Esperado vs. observado**: el corrector ve en la misma lista respuestas del
  pilotaje (que no sumarán a resultados) y de la ejecución, distinguibles solo
  por el campo `mode` de cada fila. Corregir una respuesta de pilotaje es
  trabajo perdido silencioso (no entra al consolidado, sin feedback).
- **Notas del auditor**: la pantalla (`grading/page.tsx`) tiene filtro por
  estación pero no por modo, y no separa visualmente pilotaje/ejecución. Ídem
  el contador `pending_deferred_grading_stations` en `validation.py:217-235`:
  cuenta respuestas sin puntaje **sin filtrar `mode`**, así que una respuesta de
  pilotaje pendiente dispara la advertencia de cierre del evento real. (Ángulo
  nuevo relacionado con H-vivo-1: el conteo unfiltered-by-mode también aquí.)

### H-corr-5 · Fricción del corrector: sin cola "asignadas a mí", sin orden por prioridad, feedback pobre
- **Rol / pantalla**: corrector · `/grading`
- **Severidad**: media
- **Tipo**: fricción-UX
- **Evidencia**: `frontend/src/app/(app)/grading/page.tsx` (leído completo hasta
  ~línea 80 + estructura). `app/api/routes/grading.py:60-104`.
- **Observaciones**:
  - **Pasos para corregir una respuesta**: seleccionar ECOE (selector global de
    app-shell) → abrir `/grading` → (opcional) filtrar por estación → expandir
    la fila (`expandedId`) → escribir un número por pregunta → guardar. ~4-5
    interacciones por respuesta; sin atajo "siguiente pendiente", sin
    autoavance.
  - La lista viene ordenada por `submitted_at asc` (FIFO). No hay agrupación por
    estudiante ni por estación en el payload; el `corrector` multi-estación
    recibe todo junto.
  - `pending_count` es **global al evento** (línea 103-104), no respeta el
    `stationFilter` del cliente ni el scope del corrector se refleja en un "te
    quedan N". El front recalcula `pending`/`graded` sobre `visibleResponses`
    pero el header muestra el número del backend.
  - Feedback al enviar: `grade_response` devuelve `{graded, score_obtained,
    max_score}`. La UI muestra un `message` string. No confirma "esta estación
    del estudiante quedó cerrada" ni "quedan N respuestas tuyas".
  - No hay indicación de la **pauta/rúbrica** de referencia aunque `FASE1.md`
    §"Decisión 4" dice que si la estación tiene `assessment_tool_id` la pantalla
    "la muestra como referencia" — el endpoint no envía el `assessment_tool`
    (solo manda `questions` del formulario). Gap contra el diseño.
- **Notas del auditor**: para un uso real (un docente corrige 60 informes de 3
  estaciones) la ausencia de "siguiente" y de progreso personal es la fricción
  dominante.

### H-corr-6 · `corrector` sin estaciones asignadas: lista vacía silenciosa, sin explicación
- **Rol / pantalla**: corrector · `/grading`
- **Severidad**: baja
- **Tipo**: fricción-UX
- **Evidencia**: `app/api/routes/grading.py:41` — si no hay `StaffAssignment`
  `corrector`, `_corrector_station_scope` devuelve `set()` (vacío) y el endpoint
  retorna `{"responses": [], "pending_count": 0}` (líneas 57-58). Igual si el
  `station_ids` de la asignación apunta a estaciones inexistentes
  (`test_deferred_grading.py::test_corrector_cannot_grade_unassigned_station`).
- **Esperado vs. observado**: el corrector ve "no hay nada que corregir" cuando
  en realidad su asignación está mal armada. Sin distinción entre "todo
  corregido" y "no tienes estaciones".
- **Notas del auditor**: cosmético/UX; el backend está correcto en seguridad
  (los tests negativos de `test_deferred_grading.py` cubren scoping por evento y
  por estación, 403 fuera de asignación — verificado, todos verdes).

### Nota sobre el patrón sistémico (gating por rol global vs. rol de evento)
Revisado para `/grading` y `/results`:
- **`/grading`**: OK. `NAV_ITEMS` (`routes.ts:32`) y `Sidebar`
  (`sidebar.tsx:11-19`) filtran por `eventRoles`, no por rol global. El backend
  (`grading.py`) usa `ensure_event_access` + scope por `StaffAssignment`.
- **`/results`**: OK. `routes.ts:33` filtra por `eventRoles`; backend usa
  `ensure_event_access(*ADMIN_EVENT_ROLE_CODES)`.
- **`middleware.ts:71-77`**: solo gatea `/users` por rol global, y lo documenta
  explícitamente ("Other screens depend on the selected ECOE's effective
  roles"). No hay hallazgo de este patrón en mi alcance.

### Verificaciones que pasaron (sin hallazgo)
- **Idempotencia de `persist_results`**: verificado — `results.py:104` borra y
  reinserta; 3 llamadas seguidas dejan 1 fila por estudiante con los mismos
  valores. `UniqueConstraint(ecoe_event_id, student_id)` respetada.
- **El cierre congela la operación**: verificado — al pasar a `cerrado` los
  check-ins `confirmado` pasan a `cerrado` (`validation.py:460-468`); con la
  transición `en_ejecucion → cerrado` como única salida y
  `ensure_submission_stage` rechazando `cerrado`, no entran nuevos
  `EvaluatorRecord`/`StudentResponse`. (El agujero es `/grading`, H-corr-2.)
- **GET de resultados no escribe en BD**: verificado — dos `GET /results`
  seguidos devuelven idéntico JSON y `ECOEResult` sigue en 0 filas (nunca se
  consolida desde un GET). El problema de H-corr-1 es que el GET *recalcula*, no
  que *escriba*.
- **Scoping del corrector** (negativos de `test_deferred_grading.py`): evento A
  no ve evento B (403), estación fuera de `station_ids` (403), sin acceso a
  `/results` `/live` `/students` `/evaluator` `/dashboard`. Todos verdes.

---

## SECCIÓN B — Análisis de datos

### H-dato-1 · No hay nota ni resultado por estación; `StationResult` es un modelo muerto
- **Pantalla**: `/results`
- **Severidad**: alta
- **Tipo**: dato
- **Evidencia**:
  - `app/models/entities.py:510-517` — `class StationResult` (ecoe_event_id,
    station_id, student_id, obtained_score, max_score, percent_score) con
    `UniqueConstraint` e índice.
  - `grep -rn "StationResult" app/ tests/` → **solo la definición**. Nadie la
    escribe, nadie la lee.
  - `compute_results` (`results.py:42-99`) suma `EvaluatorRecord` +
    `StudentResponse` a nivel estudiante; el resultado no lleva `by_station`.
  - `station_traceability` (`results.py:262-293`) da counts (`checkins_count`,
    `evaluations_count`, `student_submissions_count`) pero **ningún puntaje**.
- **Impacto**: imposible responder "¿cómo le fue al estudiante X en la estación
  3?", "¿qué estación tuvo peor promedio?", "¿qué estación no discrimina?". El
  frontend `/results` solo muestra el consolidado plano y counts.
- **Notas del auditor**: los datos crudos existen (`EvaluatorRecord`,
  `StudentResponse` ambos con `station_id` y puntajes); falta la agregación y el
  endpoint. `persist_results` debería poblar `StationResult` en el cierre.

### H-dato-2 · Cero análisis psicométrico; el pilotaje no produce salida analítica
- **Pantalla**: `/results`, `/pilotage`
- **Severidad**: alta
- **Tipo**: dato
- **Evidencia**: `grep -niE "weight|discrimin|cronbach|alpha|fiabilidad|reliab|
  psicomet|difficulty|dificultad|percentil|borderline|standard.set"` sobre
  `app/` → 0 resultados relevantes. `compute_results:66-81` fija
  `mode == ejecucion`, así que las respuestas y evaluaciones del **pilotaje**
  no entran a ningún cálculo consultable.
- **Impacto**: el pilotaje sirve para validar estaciones (dificultad,
  discriminación, consistencia entre evaluadores) antes del examen real. Hoy la
  herramienta registra los datos del pilotaje pero no ofrece **ninguna** métrica
  a partir de ellos — `pilot_runs` solo cuenta corridas. La "validación de
  pilotaje" (`pilotaje_validado`) es un click humano sin respaldo cuantitativo.
- **Notas del auditor**: mínimo viable para gestión: media y DE por estación,
  histograma de notas, α de Cronbach entre estaciones, índice de
  discriminación (correlación estación-total). Para el pilotaje: lo mismo pero
  sobre `mode == pilotaje`.

### H-dato-3 · Consolidado por suma cruda: sin ponderación ni estándar por estación
- **Pantalla**: `/results`
- **Severidad**: alta
- **Tipo**: dato
- **Evidencia**: `results.py:84-89` — `total_score = eval_score + form_score`,
  `max_score = eval_max + form_max`, `percentage = total/max*100`. No hay campo
  de peso en `Station` (`grep weight|ponder` → nada). `compute_equivalent_grade`
  (`results.py:28-39`) aplica **un solo** `passing_reference_percent` al
  porcentaje agregado.
- **Impacto**:
  - Una estación con `max_score` alto domina la nota final; el diseñador no
    puede igualar el peso de las estaciones ni sobreponderar una crítica.
  - Solo hay estándar **compensatorio** (promedio global ≥ umbral). No se puede
    exigir estándar **conjuntivo** (aprobar ≥ N estaciones), que es habitual en
    ECOE de alto impacto.
  - `equivalent_grade` es lineal por tramos sobre el % global; no hay
    Angoff/borderline-regression ni nota por estación.
- **Notas del auditor**: decisión de producto, pero hoy no hay ni la
  infraestructura de datos (peso por estación, umbral por estación) ni el
  cálculo.

### H-dato-4 · Export Excel mínimo; el "Export PDF" de Resultados no son resultados
- **Pantalla**: `/results`
- **Severidad**: media
- **Tipo**: dato / fricción-UX
- **Evidencia**:
  - `results.py:355-361` — `export_results_excel`: `pd.DataFrame(data)` →
    1 hoja `consolidado` con las columnas de `compute_results` (student_id,
    student_name, ecoe_number, total_score, max_score, percentage,
    equivalent_grade).
  - `routes/operational.py:358-375` + `results.py:364-388` — el botón "Exportar
    PDF contingencia" (`results/page.tsx:82-88`) llama `export_contingency_pdf`,
    que imprime instrucciones de estación / lista de estaciones. **No** contiene
    puntajes ni notas. Etiqueta engañosa en la pantalla de Resultados.
- **Impacto**: para análisis externo (SPSS/R/planilla de acta) falta: desglose
  por estación, identidad del evaluador y del corrector por registro, timestamps,
  modo, metadatos del ECOE (curso, fecha, escuela, umbral), marca de
  contingencia (`by_contingency`), y una hoja de item-analysis.
- **Notas del auditor**: `export_results_excel` acepta `persist=True` pero el
  endpoint lo llama con `persist=False` siempre; el argumento está muerto en la
  ruta.

### H-dato-5 · Trazabilidad y completitud no distinguen "sin actividad real" por el conteo unfiltered-by-mode
- **Pantalla**: `/results`
- **Severidad**: media
- **Tipo**: dato
- **Evidencia**: `results.py:131-142` — `checkins`, `evaluator_records`,
  `student_responses` se cargan **sin filtrar `mode`**. `results.py:209-239` los
  cuenta para `completion_status`. Un estudiante con solo actividad de pilotaje
  puede quedar `completo`. (Es H-vivo-1; ángulo nuevo confirmado aquí: el mismo
  desfase alimenta `pending_deferred_gradings` por estudiante en
  `results.py:223-229` y el `pending_deferred_grading_stations` de
  `validation.py:217-235`, que se usa en la advertencia del **modal de
  cierre**.)
- **Impacto sobre notas/export**: `total_score`/`percentage`/`equivalent_grade`
  en cada fila de `student_traceability` vienen de `results_by_student`
  (`compute_results`, sí mode-filtrado) — así que la **nota** mostrada es
  correcta; lo inconsistente es el **estado** ("completo" con nota 0 y 0
  evaluaciones reales) y los contadores. La advertencia de cierre puede
  encenderse por pendientes de pilotaje.
- **Notas del auditor**: filtrar por `mode` en la carga o al menos en los
  cálculos de completitud y de pendientes. No re-file de H-vivo-1; anexar este
  ángulo (cierre + export) a ese hallazgo.

### H-dato-6 · `ECOEResult` no expone fecha de consolidación ni quién consolidó
- **Pantalla**: `/results`
- **Severidad**: baja
- **Tipo**: dato
- **Evidencia**: `entities.py:526-542` — `ECOEResult` solo tiene puntajes +
  `TimestampMixin`. `persist_results` (`results.py:102-116`) no registra actor.
  El `POST /results/{id}/consolidate` (`operational.py:336-344`) no escribe
  `AuditLog` (a diferencia de casi todo el resto de mutaciones del proyecto).
- **Impacto**: no se puede acreditar "estas notas fueron consolidadas el día X
  por Y", requisito típico de un acta de examen.
- **Notas del auditor**: agregar `AuditLog` en `consolidate_results` y en la
  rama de cierre; exponer `updated_at` de `ECOEResult` como "consolidado el".

---

## Apéndice — cómo se ejercitó

Tests scratch (borrados) sobre SQLite in-process:
- `test_persist_results_idempotent` — 3× `persist_results` → 1 fila estable. PASA.
- `test_get_results_does_not_mutate` — 2× `GET /results` idéntico, `ECOEResult`
  en 0. PASA.
- `test_grading_after_close_changes_results_and_leaves_consolidated_stale` —
  demuestra H-corr-1, H-corr-2: grade tras `cerrado` → 200; `GET /results` pasa
  de `(0,0)` a `(6,6)`; `ECOEResult` queda en `(0,0)`.

Suites revisadas (verdes en el repo): `test_grading.py`,
`test_deferred_grading.py` (incluye negativos de scoping del corrector),
`test_results.py`, `test_traceability_circuits.py`, `test_response_shapes.py`.
