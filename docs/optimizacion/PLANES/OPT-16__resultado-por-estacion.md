# OPT-16 · Resultado por estación (poblar `StationResult`) + desglose `by_station`

**Severidad: alta (capacidad ausente).** Origen: H-dato-1
(`docs/optimizacion/hallazgos/auditor-correccion-resultados__2026-08-28.md` §Sección B).
Auditoría de fundamento: `docs/optimizacion/hallazgos/auditor-correccion-resultados__OPT-16__2026-08-29.md`.
Fase 2 · item ancla (`PLANES/FASE2_ANALISIS_DATOS__scoping.md` §OPT-16).

## Problema

Hoy no hay forma de responder "¿cómo le fue al estudiante X en la estación 3?" ni
"¿qué estación tuvo peor promedio?". `compute_results` colapsa todas las
estaciones en una sola nota por estudiante. El modelo `StationResult`
(`backend/app/models/entities.py:586-599`) y su tabla `station_results` existen
en el schema desde el baseline pero **nadie los escribe ni los lee** — modelo
muerto. `/results` solo muestra el consolidado plano y conteos por estación sin
puntaje (`station_traceability`).

Sin esto no hay ranking por estación, ni base para dificultad / discriminación
(OPT-18) ni para ponderación / estándar por estación (OPT-17).

## Causa raíz

- `app/services/results.py:57-92` — las dos consultas de agregación
  (`EvaluatorRecord`, `StudentResponse`) agrupan por `student_id`, colapsando la
  estación.
- `app/services/results.py:160-188` — `persist_results` escribe `ECOEResult`
  pero nunca `StationResult`.
- `app/api/routes/operational.py:399-408` — `get_results` devuelve
  `results` + `frozen` + `consolidated_at` + trazabilidad; no hay bloque
  `by_station`.
- `grep -rn "StationResult" backend/ frontend/` → solo la definición del modelo.

## Cambio propuesto

### Backend

**`app/services/results.py`**

1. `compute_station_results(db, ecoe_event_id) -> list[dict]` — nueva función.
   Reusa las **mismas dos consultas** de `compute_results`, cambiando
   `GROUP BY student_id` → `GROUP BY student_id, station_id`:
   - `EvaluatorRecord`: `mode == 'ejecucion'`, `is_draft == False`.
   - `StudentResponse`: `mode == 'ejecucion'`, `score_obtained IS NOT NULL`.
   - Combina por `(student_id, station_id)`:
     `obtained = eval_obtained + form_obtained`,
     `max = eval_max + form_max`,
     `percent = obtained / max * 100` (0 si `max == 0`).
   - **Solo emite filas para pares (estudiante, estación) con al menos una
     contribución** (no fila 0/0 para cada estudiante × cada estación —
     inflaría y confundiría en circuitos espejo).
   - Devuelve dicts: `student_id, station_id, obtained_score, max_score,
     percent_score`.
   - Invariante (test): `sum(by_station de un estudiante) == compute_results de
     ese estudiante`.

2. `persist_results` — tras poblar `ECOEResult`, poblar `StationResult` con el
   mismo patrón idempotente delete-then-insert:
   ```python
   db.query(StationResult).filter(StationResult.ecoe_event_id == ecoe_event_id).delete()
   for item in compute_station_results(db, ecoe_event_id):
       db.add(StationResult(ecoe_event_id=ecoe_event_id, **item))
   ```
   (reutilizar el `compute_station_results` ya calculado; no duplicar consulta).
   Sin `AuditLog` extra: el `AuditLog(action="consolidate_results")` de OPT-1 ya
   cubre la consolidación completa.

3. `read_station_results(db, ecoe_event_id) -> tuple[list[dict], bool]` — análoga
   a `read_results` (OPT-1). Si `ecoe_event.status ∈ {cerrado, archivado}` **y**
   hay filas `StationResult` → devuelve la nota por estación desde el snapshot,
   `frozen=True`. En cualquier otro caso → `compute_station_results` en vivo,
   `frozen=False`. Si el evento está cerrado pero **sin** filas (cierre previo a
   OPT-16) → cae a cálculo en vivo, sin romper.

4. `build_station_score_block(station_rows, stations) -> dict` — puro Python,
   sin BD. Toma la lista de notas por (estudiante, estación) + los `Station` del
   evento + el mapa de estudiantes y arma:
   ```jsonc
   {
     "stations": [
       {"station_id", "station_number", "station_name", "circuit_name",
        "n",                // nº de estudiantes con nota en la estación
        "mean_score", "sd_score",      // sobre obtained_score crudo
        "mean_max",
        "mean_percent", "sd_percent",  // sobre percent_score
        "min_percent", "max_percent"}
     ],
     "students": [          // formato largo
       {"student_id", "ecoe_number", "student_name",
        "station_id", "station_number", "station_name",
        "obtained_score", "max_score", "percent_score"}
     ]
   }
   ```
   - **DE**: `statistics.stdev` (muestral, n−1); `None` cuando `n < 2`.
     Agregado calculado sobre el conjunto servido (snapshot o vivo) → hereda la
     inmutabilidad de OPT-1 sin almacenarse.
   - Estaciones sin ninguna nota → fila con `n=0`, agregados `None`/`0`.

**`app/api/routes/operational.py`**

5. `get_results` — añadir la clave `by_station`:
   ```python
   results, frozen, consolidated_at = read_results(db, ecoe_event_id)
   station_rows, _ = read_station_results(db, ecoe_event_id)
   stations = db.scalars(select(Station).where(Station.ecoe_event_id == ecoe_event_id)...).all()
   return {
       "results": results,
       "frozen": frozen,
       "consolidated_at": ...,
       "by_station": build_station_score_block(db, station_rows, stations),
       **build_traceability_report(db, ecoe_event_id, consolidated_results=results),
   }
   ```
   Sin `response_model` → aditivo, sin cambio de contrato.

6. `consolidate_results` — añadir `by_station` al payload de retorno (calcularlo
   con las filas recién persistidas, análogo a lo que ya hace con `results`).

7. `export_excel` — **opcional, recomendado**: agregar una hoja
   `resultados_por_estacion` (formato largo: N ECOE, estudiante, estación,
   puntaje, máximo, %). Es barato y el analista externo lo pide (H-dato-4). El
   rediseño completo del export (hojas de item-analysis, metadatos, identidad de
   evaluador/corrector) sigue siendo **OPT-19**, que absorbe esta hoja. Si se
   prefiere no tocar el export en OPT-16, dejarlo para OPT-19 — marcar la
   decisión al usuario.

Sin endpoint nuevo. Sin permiso nuevo (misma `ensure_event_access(*ADMIN_EVENT_ROLE_CODES)`).

### Frontend

**`frontend/src/lib/types.ts`** — extender `ResultsResponse`:
```ts
export type StationScoreAggregate = {
  station_id: number; station_number: number; station_name: string;
  circuit_name: string; n: number;
  mean_score: number | null; sd_score: number | null; mean_max: number | null;
  mean_percent: number | null; sd_percent: number | null;
  min_percent: number | null; max_percent: number | null;
};
export type StudentStationScore = {
  student_id: number; ecoe_number: string; student_name: string;
  station_id: number; station_number: number; station_name: string;
  obtained_score: number; max_score: number; percent_score: number;
};
export type ResultsResponse = {
  results: ECOEResult[];
  frozen: boolean;
  consolidated_at: string | null;
  by_station: { stations: StationScoreAggregate[]; students: StudentStationScore[] };
} & TraceabilityReport;
```

**`frontend/src/app/(app)/results/page.tsx`** — nueva `<SectionCard title="Resultados
por estación">` insertada después de "Consolidado por estudiante" (tras la línea
129), antes de "Trazabilidad por estudiante":
- `DataTable` agregado: Estación · Nombre · n · Media % · DE % · Media pts · Máx.
- `DataTable` de nota por estudiante y estación (formato largo):
  N ECOE · Estudiante · Estación · Puntaje · Máximo · %.
  Opcional: `<select>` cliente de filtro por estación (patrón ya usado en
  `grading/page.tsx`).
- Sin chip propio de `frozen`: la tarjeta "Resultados y exportación" ya lo
  muestra. `DataTable` ya hace `overflow-x-auto`.

### Migración

**No.** `station_results` existe en `c7d8e9f00123_baseline_schema.py:409-425`
con la `UniqueConstraint(ecoe_event_id, station_id, student_id)` y el índice
`ix_station_results_event_student`. El modelo ORM coincide con la tabla;
autogenerate no produce diff.

> **Gate humano**: si al implementar se descubre que la tabla del baseline **no**
> coincide con el modelo (columna faltante, constraint distinta) → **parar** y
> escalar al usuario como decisión de schema. La auditoría verificó que coinciden.

### Máquina de estados

No se toca `ALLOWED_STATUS_TRANSITIONS`. `persist_results` ya se dispara en la
rama de cierre (`validation.py:556-562`); OPT-16 solo agrega qué escribe esa
función, no cuándo.

## Tests (incluye negativos — toca integridad de datos de resultados)

Archivo nuevo: `backend/tests/test_station_results_opt16.py`.

Positivos:
- `test_persist_results_populates_station_results` — cerrar un evento con
  registros en 2 estaciones → 1 fila `StationResult` por (estudiante, estación)
  con actividad; `obtained/max/percent` correctos.
- `test_station_results_sum_matches_consolidated` — para cada estudiante,
  `sum(StationResult.obtained_score) == ECOEResult.total_score` y
  `sum(max) == ECOEResult.max_score`.
- `test_by_station_block_in_results_payload` — `GET /results/{id}` incluye
  `by_station.stations` y `by_station.students`; `n`, `mean_percent`, `sd_percent`
  correctos para una estación con 3 estudiantes.
- `test_by_station_recalculates_before_close` — evento `en_ejecucion`,
  `GET /results` refleja una respuesta nueva en `by_station` en vivo.

Negativos / integridad:
- `test_by_station_excludes_evaluator_drafts` — un `EvaluatorRecord.is_draft=True`
  no entra a `StationResult` ni al agregado (espejo de `compute_results`).
- `test_by_station_excludes_pilotaje` — registros `mode='pilotaje'` no producen
  filas `StationResult` ni aparecen en `by_station`.
- `test_by_station_excludes_pending_deferred_grading` — `StudentResponse` con
  `score_obtained IS NULL` no entra; tras corregir, sí entra y baja/sube la
  media.
- `test_station_results_idempotent_on_reconsolidate` — `persist_results` ×3 →
  1 fila por (estudiante, estación), mismos valores; `UniqueConstraint`
  respetada.
- `test_by_station_frozen_snapshot_does_not_change_after_close` — evento
  `cerrado`; mutar a mano un `StudentResponse.score_obtained` → `GET /results`
  sigue devolviendo el `by_station` del snapshot, no el recalculado (espejo de
  `test_get_results_reads_snapshot_after_close` de OPT-1).
- `test_by_station_falls_back_to_live_when_closed_without_snapshot` — evento
  `cerrado` sin filas `StationResult` → `read_station_results` recalcula en vivo,
  sin error.
- `test_blank_auto_submission_counts_as_zero_in_station` — respuesta
  `submission_kind='auto'`, `answers={}`, `score_obtained=0` → entra como 0/máx,
  baja la media de la estación (espejo de `compute_results`).

Frontend: `frontend/src/app/(app)/results/__tests__/page.test.tsx` — la tarjeta
"Resultados por estación" renderiza el agregado y la nota por estudiante desde
`by_station`; no rompe cuando `by_station.stations` está vacío.

## Riesgos / alcance

- **Superficie acotada**: 3 funciones nuevas en `results.py` + 2 endpoints
  tocados (agregar una clave) + 2 archivos frontend. Sin migración, sin
  contrato de request, sin permisos, sin máquina de estados.
- **Riesgo de divergencia de filtros**: si `compute_station_results` no aplica
  exactamente los mismos `WHERE` que `compute_results`, el desglose no sumaría el
  consolidado. Mitigación: el test `test_station_results_sum_matches_consolidated`
  es bloqueante; idealmente factorizar los predicados de filtro en constantes
  compartidas.
- **Riesgo espejo de OPT-1**: evento cerrado sin snapshot → fallback a vivo
  (cubierto por test).
- **`persist_results` más pesado**: una consulta agregada extra + N inserts en
  el cierre. Irrelevante a la escala del proyecto (cientos de filas).
- **Decisión menor pendiente** (no bloquea la implementación): DE muestral con
  `None` para n<2 vs. poblacional; agregado sobre `percent_score` (recomendado)
  vs. puntaje crudo (el plan da ambos). Y si la hoja Excel `resultados_por_estacion`
  entra en OPT-16 o se difiere a OPT-19.

## Verificación

- [ ] `cd backend && python3 -m pytest` (SQLite) — incluye
      `tests/test_station_results_opt16.py`
- [ ] `TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q`
      (toca la `UniqueConstraint` de `station_results`, que SQLite no valida)
- [ ] Migración desde base limpia sin cambios:
      `DATABASE_URL=sqlite:////tmp/ecoe_alembic_check.db SECRET_KEY=test-secret ENVIRONMENT=test AUTO_SEED_DEMO=false alembic upgrade head`
      llega a head **sin revisión nueva** (OPT-16 es sin migración)
- [ ] `cd frontend && npm run lint && npm run build && npx vitest run`
- [ ] `./scripts/run_e2e.sh --grep "results"` sobre el stack de ramas (si aplica)

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-29
- Aprobado por usuario: ✅ 2026-08-29 — plan aprobado, decisiones de implementación = las recomendadas (DE muestral, agregado sobre percent_score, hoja Excel incluida, nota por estación informativa).
- Decisiones que el usuario debe revisar antes de implementar:
  1. **DE**: muestral (n−1, `None` si n<2) — recomendado — vs. poblacional.
  2. **Base del agregado**: `percent_score` (recomendado, estaciones con distinto
     máximo) vs. puntaje crudo. El plan entrega ambos; confirmar si sobra.
  3. **Hoja Excel `resultados_por_estacion`**: incluir en OPT-16 (barato) o
     diferir a OPT-19 (rediseño completo del export).
  4. Confirmar que la nota por estación es **informativa** en esta iteración
     (alimentar un estándar por estación = OPT-17).
