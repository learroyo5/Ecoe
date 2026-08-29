# OPT-15 · Cola del corrector (núcleo)

**Severidad: media.** Origen: H-corr-5, H-corr-6.
Hallazgo de fundamento: `docs/optimizacion/hallazgos/auditor-correccion-resultados__OPT-15__2026-08-29.md`.
Cierra el diseño de `docs/architecture/EVALUACION_DIFERIDA_FASE1.md` §Decisión 4.

## Problema

La corrección diferida (Fase 1, ya entregada) funciona pero es friccionada a escala —
un docente corrige decenas de informes de varias estaciones:

- **Cola FIFO plana, sin "siguiente pendiente" ni autoavance.** `GET /api/grading/{event}`
  ordena por `submitted_at ASC, id ASC` (`backend/app/api/routes/grading.py:79`); el
  cliente hace todo. Por respuesta: ~2 clics + N entradas numéricas + barrido visual + 1
  clic para abrir la siguiente. Tras cada guardado, `frontend/src/app/(app)/grading/page.tsx:204-210`
  **re-fetchea la lista entera** del evento (O(respuestas) por corrección).
- **`pending_count` es campo muerto.** El backend lo calcula y lo scopea al corrector
  (`grading.py:123`, `rows` ya filtrado por estación), pero la UI **no lo renderiza** en
  ninguna parte tras el rewrite de OPT-20 F4 (sólo aparece en tipos y en el stub de evento
  cerrado, `grading/page.tsx:60,63`). Los contadores visibles se recalculan en el cliente.
- **La pauta de referencia no llega.** `list_gradable_responses` adjunta sólo `questions`
  del `student_form_definition` (`grading.py:119-121`); **no** el `AssessmentTool` de la
  estación, pese a que FASE1 §Decisión 4 dice "si la estación tiene `assessment_tool_id`,
  la pantalla la muestra como referencia". El serializador ya existe
  (`app/utils/serializers.py::serialize_assessment_tool`, ya usado en
  `routes/evaluator.py:129,272`) — reutilización trivial.
- **Empty-state indistinguible (H-corr-6).** Un `corrector` sin `StaffAssignment` (o con
  `station_ids` vacío) recibe `{"responses": [], "pending_count": 0}`
  (`grading.py:73-74`) → la UI muestra "Nada que corregir" igual que si hubiera terminado.

**No es un bug de permisos**: los negativos de `backend/tests/test_deferred_grading.py`
están verdes (evento A no ve B; estación fuera de scope → 403).

## Causa raíz

- `backend/app/api/routes/grading.py:56-124` — `list_gradable_responses` devuelve una lista
  plana; no adjunta `assessment_tool`, no expone el `scope` del corrector, no desglosa
  pendientes por estación.
- `backend/app/api/routes/grading.py:165-170` — `grade_response` devuelve sólo
  `{graded, response_id, score_obtained, max_score}` → el cliente no tiene con qué evitar
  el refetch ni con qué mostrar progreso.
- `frontend/src/app/(app)/grading/page.tsx` — sin cola personal, sin autoavance, sin barra
  de progreso; `data.pending_count` sin uso; empty-state único (`:289-296`).

## Cambio propuesto

**Sin migración. Sin endpoints nuevos. El puntaje sigue en `StudentResponse.score_obtained`
(FASE1 §Decisión 3). `apply_manual_scores` sigue siendo número libre `[0, max]` por
pregunta (FASE1 §Decisión 4).** La pauta es **sólo referencia visual**, no puntuación por
ítem — eso es Fase 2.

### Backend — `backend/app/api/routes/grading.py`

`list_gradable_responses` extiende su respuesta:

1. **`assessment_tool` por fila** — cuando `station.assessment_tool_id` está poblado,
   `serialize_assessment_tool(db, station.assessment_tool_id)` (cachear por `station_id`
   dentro del request para no repetir el `SELECT`). `null` si la estación no tiene pauta.
2. **`scope`** (objeto, top-level de la respuesta):
   ```
   {
     "is_corrector": bool,          # el actor entra sólo como corrector
     "has_assignment": bool,        # existe StaffAssignment corrector con station_ids
     "assigned_station_ids": [int], # vacío para admin/coeditor (ven todo)
   }
   ```
   Todo se computa ya en `_corrector_station_scope` (`grading.py:40-53`); es exponerlo.
   `station_scope is None` → `is_corrector=False`. `station_scope == set()` →
   `is_corrector=True, has_assignment=False` (caso H-corr-6). Cuando
   `has_assignment=False`, seguir devolviendo `responses: []` pero **con** el objeto
   `scope` para que la UI distinga.
3. **`pending_by_station`** — `{ station_id: {station_number, station_name, pending, total} }`
   sobre las filas ya scopeadas (respeta el scope del corrector; el filtro de estación del
   cliente es post-fetch y no lo toca). `pending` = filas con `pending_questions`.
4. **`pending_count`** — se mantiene (ya scopeado); pasa a usarse en la UI (ver Frontend) o,
   si el usuario prefiere, se elimina. **Recomendación: mantenerlo y renderizarlo** como
   "N de M en tus estaciones" — es coherente con `pending_by_station` y no cuesta nada.
5. **Orden de la cola** — se mantiene `submitted_at ASC` FIFO (agrupar por estación /
   priorizar `by_contingency`/`draft_finalized` queda anotado como pulido menor, no entra
   en el núcleo).

`grade_response` extiende su retorno para **eliminar el refetch**:

```
{
  "graded": True,
  "response_id": ...,
  "score_obtained": ...,
  "max_score": ...,
  "next": { "response_id": ... } | None,   # próxima fila pendiente en el scope,
                                           # orden FIFO, tras la recién corregida
  "pending_remaining": int,                # pendientes que quedan en el scope del actor
}
```

`next` y `pending_remaining` se calculan con la misma query scopeada de
`list_gradable_responses` (filtrando `pending_manual_keys`). No hay endpoint nuevo:
`grade_response` ya tiene el `response.ecoe_event_id` y el `station_scope`
(`grading.py:143-149`).

> `GET /api/grading/{event}/next` **no** se agrega — queda como pulido opcional sólo si
> aparece un dispositivo "corrector de a una" o eventos muy grandes (hallazgo §5b).

### Frontend — `frontend/src/app/(app)/grading/page.tsx` + `lib/api.ts` + `lib/types.ts`

- **Tipos** (`types.ts`): `GradableResponse` gana `assessment_tool: AssessmentTool | null`;
  la respuesta de `gradingList` gana `scope` y `pending_by_station`; la de `gradeResponse`
  gana `next` y `pending_remaining`.
- **Panel de pauta de referencia**: bloque colapsable dentro de la fila expandida, junto a
  los inputs de las preguntas manuales, listando `assessment_tool.items`
  (`label` · `score_per_item`) + `free_observation`. Sólo lectura. Si
  `assessment_tool === null`, no se muestra.
- **Autoavance**: al guardar, en vez de `setExpandedId(null)` + `api.gradingList(eventId)`
  completo (`page.tsx:205-211`):
  - aplicar el resultado de `gradeResponse` sobre la fila local (mutar `score_obtained`,
    `grading`, `pending_questions` de esa fila en `data`);
  - si `next` no es `null`, `openResponse` de esa fila (scroll into view);
  - si `next` es `null`, cerrar y mostrar "No quedan pendientes en tus estaciones ✓".
- **Barra de progreso**: header con "X de Y corregidas en tus estaciones" a partir de
  `pending_by_station` (o `pending_count` + total), + chips por estación
  ("Estación 3: 4/12"). Para admin/coeditor (`scope.is_corrector === false`) el texto dice
  "en el evento".
- **`pending_count`**: re-renderizado como el número "M − pending" del header (opción
  preferida del usuario). Se elimina la rama de código que lo dejaba sin uso.
- **Empty-state diferenciado** (H-corr-6):
  - `scope.is_corrector && !scope.has_assignment` →
    *"No tenés estaciones asignadas para corregir. Pedile a un coordinador o al
    administrador del ECOE que te asigne estaciones de evaluación diferida."*
  - `has_assignment` y 0 respuestas en total → *"Todavía no hay respuestas para corregir en
    tus estaciones."*
  - `has_assignment` y todo corregido → *"Todo corregido ✓"* (el actual).
- Submit con Enter en los inputs de puntaje (barato, incluir).

## Tests (incluye negativos — el hallazgo es UX pero se toca la forma de la respuesta de un endpoint con scoping)

`backend/tests/test_deferred_grading.py` (extender) o `test_grading_queue_opt15.py` (nuevo):

**Negativos obligatorios (scope):**
- `test_corrector_response_rows_stay_within_scope` — corrector con `station_ids=[A]` y
  respuestas en A y B: `GET /api/grading/{event}` sólo trae filas de A; `assessment_tool`
  sólo de A.
- `test_pending_by_station_respects_corrector_scope` — `pending_by_station` **no** incluye
  la estación B; `pending_count` cuenta sólo A.
- `test_grade_response_next_stays_within_scope` — `next` devuelto por `grade_response`
  nunca apunta a una respuesta de una estación fuera del `station_ids` del corrector.
- `test_grading_scope_object_for_corrector_without_assignment` — corrector sin
  `StaffAssignment`: respuesta `{responses: [], scope: {is_corrector: true,
  has_assignment: false, assigned_station_ids: []}}` (no un 200 indistinguible).
- `test_corrector_event_a_cannot_read_grading_event_b` — se mantiene verde (regresión).

**Positivos:**
- `test_grading_row_includes_serialized_assessment_tool` — estación con
  `assessment_tool_id` poblado + 2 `AssessmentItem` → la fila trae
  `assessment_tool.items` con 2 entradas; estación sin pauta → `assessment_tool: null`.
- `test_grade_response_returns_next_and_pending_remaining` — con 3 pendientes, corregir una
  → `{next: {response_id: <2ª>}, pending_remaining: 2}`; corregir la última →
  `{next: null, pending_remaining: 0}`.
- `test_admin_sees_full_scope_object` — admin/coeditor →
  `scope.is_corrector === false`, `pending_by_station` cubre todas las estaciones del
  evento.
- `apply_manual_scores` **sin cambios** — los tests existentes de `[0, max]` y de
  re-corrección 409 siguen verdes (confirmar que no se tocó).

Frontend: `npm run lint && npm run build` + vitest de la página `grading`:
- autoavance abre la fila `next` sin refetch (spy sobre `api.gradingList` — se llama 1 vez
  al montar, 0 veces por guardado);
- empty-state "sin estaciones asignadas" cuando `scope.has_assignment === false`;
- panel de pauta visible sólo con `assessment_tool` no nulo.

## Riesgos / alcance

- **Forma de respuesta de `grade_response` y `list_gradable_responses` cambia** (campos
  aditivos). Revisar que `test_deferred_grading.py` y cualquier consumidor no rompan por
  claves nuevas (aditivo → bajo riesgo).
- El `serialize_assessment_tool` por fila añade un `SELECT` por estación distinta; mitigado
  con caché por `station_id` dentro del request. La cola es de decenas–bajos cientos de
  filas (escala declarada).
- El autoavance del cliente cambia el comportamiento observable de `/grading` (deja de
  recargar). Cubierto por el vitest de "0 refetch por guardado".
- Commit acotado: 1 corte backend (respuesta extendida + `next`/`pending_remaining`),
  1 corte frontend (panel de pauta + autoavance + progreso + empty-states).
- **Sin migración, sin máquina de estados, sin permisos nuevos** — el scoping ya existe.

## Fuera de este plan → **OPT-15b** (anotado en BACKLOG)

- Bulk "puntuar 0 las respuestas en blanco de esta estación" (apoyado en
  `submission_kind == "auto"` + `answered == false`, ya disponibles tras OPT-20 F4).
- Extender la columna "Reasignar" de `frontend/src/app/(app)/evaluators/page.tsx:537-604`
  a `role_code === "corrector"` (hoy corta con "No aplica" para todo `!== "evaluador"`;
  `api.updateStaff` ya lo soporta, sólo falta la UI).
- Puntuación estructurada real contra `assessment_tool.items` + comentario por ítem
  (Fase 2). Si algún día se agrega detalle por ítem, va **dentro** del JSON `grading`
  (patrón OPT-20 F4 con `answered`), nunca en un store paralelo — así OPT-16/OPT-18 pueden
  leerlo sin conflicto.

## Verificación

- [ ] `cd backend && python3 -m pytest`
- [ ] `TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q`
- [ ] `cd frontend && npm run lint && npm run build && npx vitest run`
- [ ] `./scripts/run_e2e.sh --grep "grading"` si el flujo dorado cubre corrección diferida

## Decisiones registradas (producto — ya tomadas por el usuario 2026-08-29)

- Sin endpoints nuevos; extender `GET /api/grading/{event}` con `assessment_tool` por fila,
  `scope`, `pending_by_station`.
- Pauta = sólo referencia visual. `apply_manual_scores` sin cambios (número libre `[0,max]`).
  Puntaje en `StudentResponse.score_obtained`. Cualquier detalle por ítem futuro va dentro
  del JSON `grading`.
- Cola/siguiente/progreso en el cliente; `grade_response` devuelve `{next, pending_remaining}`
  para dejar de refetchear la lista entera.
- `pending_count`: re-renderizarlo como "N de M en tus estaciones" (preferido sobre
  borrarlo).
- Empty-state del corrector sin estaciones (H-corr-6): mensaje diferenciado. Incluido (XS).
- Bulk-0 y "Reasignar" para correctores → OPT-15b, fuera de este plan.

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-29
- **Aprobado por usuario: ✅ 2026-08-29** (decisiones de producto tomadas; el plan técnico
  lo revisa el usuario antes de implementar).
