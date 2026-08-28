# OPT-2 · Aislamiento pilotaje/ejecución en trazabilidad, cierre y cola de corrección

**Severidad: alta.** Origen: H-vivo-1 (alta), H-vivo-4 (baja), H-vivo-6 (baja), H-dato-5 (media), H-corr-4 (media).

## Problema

`compute_results` filtra `mode == ejecucion` y las notas del consolidado son correctas. Pero **el resto de la
maquinaria de cierre y corrección no filtra por `mode`**:

- **H-vivo-1** — `build_traceability_report` cuenta check-ins, evaluaciones y respuestas de pilotaje. Un
  estudiante que pilotó pero **faltó a la ejecución real** aparece `completion_status = "completo"`,
  `missing_evaluations = 0`, con nota 1.0 en el consolidado. `/results` lo pinta como badge verde. La
  trazabilidad de `/results` es lo que el checklist de cierre usa para "resolver faltantes por contingencia".
- **H-corr-4** — la cola de `/grading` (`grading.py:52-64`) mezcla respuestas de pilotaje y ejecución;
  corregir una de pilotaje es trabajo perdido silencioso. Y `pending_deferred_grading_station_numbers`
  (`validation.py:220-232`) cuenta respuestas de pilotaje sin puntuar → dispara la advertencia del modal de
  cierre del evento real.
- **H-vivo-6** — el `activity_log` hardcodea `"mode": "ejecucion"` en las entradas de check-in.
- **H-vivo-4** — la transición `publicado → en_ejecucion` no tiene efectos colaterales; los check-ins
  `confirmado` del pilotaje sobreviven y `evaluator_context`/`kiosk_context` pueden mostrar un estudiante viejo
  como "activo" hasta el primer check-in real de esa estación.

## Causa raíz

- `app/services/results.py:119-152` — `checkins`, `evaluator_records`, `student_responses` se cargan sin
  filtro de `mode`. Alimentan `completion_status`, `missing_*`, `summary` y `activity_log`.
- `app/services/results.py:303-313` — bucle de `activity_log` para check-ins: `"mode": "ejecucion"` literal.
- `app/api/routes/grading.py:52-59` — `filters` no incluye `StudentResponse.mode`.
- `app/services/validation.py:220-232` — la query de pendientes de corrección diferida no filtra `mode`.
- `app/services/validation.py::update_ecoe_status` — la rama `en_ejecucion` no existe como efecto colateral
  (solo `publicado` y `cerrado` lo tienen). Salir de `en_pilotaje` tampoco cierra check-ins.
- `app/models/entities.py:443-457` — `StationCheckIn` **no tiene columna `mode`**, así que un check-in de
  pilotaje es hoy indistinguible de uno real salvo por la fecha.

## Cambio propuesto

### Parte 1 — sin migración (hacer ya)

- **Backend**
  - `app/services/results.py::build_traceability_report`: filtrar `EvaluatorRecord.mode == ejecucion` y
    `StudentResponse.mode == ejecucion` en la carga de `evaluator_records` y `student_responses` (o al menos en
    todos los cálculos de completitud, contadores de `summary` y `activity_log`).
  - `app/services/validation.py` (query de `pending_deferred_grading_station_numbers`): añadir
    `StudentResponse.mode == SessionMode.ejecucion.value`.
  - `app/api/routes/grading.py::list_gradable_responses`: añadir `StudentResponse.mode == ejecucion` al
    `filters` (la corrección diferida solo aplica a la ejecución real). Confirmar que ninguna prueba dependa de
    ver pilotaje en la cola.
  - `app/services/validation.py::update_ecoe_status`: al entrar a `en_ejecucion` (y/o al salir de
    `en_pilotaje`), cerrar todos los `StationCheckIn` con `status == "confirmado"` del evento — mismo
    tratamiento que ya hace la rama de cierre. Resuelve H-vivo-4 y saca del conteo los check-ins de pilotaje
    residuales sin necesidad de columna `mode`.
- **Frontend**: ninguno (la corrección es de datos servidos).
- **Migración**: no.
- **Máquina de estados**: se agrega un efecto colateral a la transición `→ en_ejecucion`; **no** cambia el
  grafo `ALLOWED_STATUS_TRANSITIONS`, así que `ecoe-form.tsx` no se toca. Documentar el nuevo efecto colateral
  en el docstring de `update_ecoe_status` y en CLAUDE.md (§"Máquina de estados").

### Parte 2 — con migración (requiere aprobación explícita del usuario)

- Agregar columna `mode` a `station_checkins` (`String(16)`, `nullable=False`, `server_default="ejecucion"`;
  backfill: todo lo existente queda `"ejecucion"` — aceptable, no hay datos de producción con pilotaje
  relevante).
- `confirm_station_checkin` estampa `mode = resolve_session_mode(ecoe_event)` (no-raising, ya existe en
  `helpers.py`).
- `activity_log` usa `checkin.mode` en vez del literal (cierra H-vivo-6 del todo).
- Es la solución completa y correcta; bajo riesgo técnico. Sin ella, H-vivo-6 queda parcialmente vivo (el
  `activity_log` de un evento con pilotaje + ejecución en la misma estación no distingue los check-ins), pero
  la Parte 1 ya elimina el impacto operativo grave (completitud y advertencias de cierre).

## Tests (incluye negativos — toca datos)

- `test_traceability_ignores_pilotage_activity` — estudiante con SOLO registros `mode="pilotaje"` →
  `completion_status = "sin actividad"`, `missing_* > 0`, contadores de `summary` en 0.
- `test_traceability_counts_execution_activity` — el mismo estudiante con actividad real → `"completo"`.
- `test_grading_queue_excludes_pilotage_responses` (negativo) — una respuesta `mode="pilotaje"` sin puntuar no
  aparece en `GET /api/grading/{id}` ni suma a `pending_count`.
- `test_close_warning_ignores_pilotage_pending_grading` — respuesta de pilotaje sin puntuar no enciende
  `pending_deferred_grading_station_numbers`.
- `test_entering_execution_closes_open_pilotage_checkins` — check-in `confirmado` de pilotaje queda `cerrado`
  tras `→ en_ejecucion`; `evaluator_context` no lo muestra como activo.
- (Parte 2) `test_checkin_mode_stamped_from_event_status` + migración verificada contra Postgres desde base
  limpia.

## Riesgos / alcance

- Cerrar check-ins al entrar a `en_ejecucion` podría afectar un test que hoy asume que un check-in de pilotaje
  sobrevive — revisar `test_state_machine_and_modes.py`, `test_traceability_circuits.py`.
- El filtro en la cola de `/grading` cambia lo que ve el corrector; confirmar que `test_deferred_grading.py` no
  dependa de respuestas de pilotaje visibles.
- Parte 1 es un commit acotado (filtros + un efecto colateral de transición). Parte 2 es un commit separado con
  su propia migración.

## Verificación

- [ ] `cd backend && python3 -m pytest`
- [ ] `TEST_DATABASE_URL=postgresql+psycopg://... python3 -m pytest -q` (obligatorio si se hace la Parte 2)
- [ ] `DATABASE_URL=sqlite:////tmp/ecoe_alembic_check.db ... alembic upgrade head` (Parte 2)
- [ ] frontend no se toca

## Decisión pendiente del usuario

**¿Se aprueba la Parte 2 (columna `mode` en `station_checkins`, con migración)?** Sin ella el arreglo es
funcionalmente suficiente para el día del examen pero H-vivo-6 queda parcialmente abierto.

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-28
- Aprobado por usuario: ✅ 2026-08-28 (parte del lote de estabilización Grupo A)
- **Decisión de schema**: se aprueba la **Parte 2** — columna `mode` en `station_checkins` con migración Alembic. Correr la suite contra Postgres antes de dar por buena la migración.
