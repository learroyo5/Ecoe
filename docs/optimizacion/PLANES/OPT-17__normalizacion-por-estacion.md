# OPT-17 · Normalización por estación (promedio de %-de-logro, no razón de sumas)

**Severidad: alta (capacidad ausente / sesgo de cálculo).** Origen: H-dato-3
(`docs/optimizacion/hallazgos/auditor-correccion-resultados__2026-08-28.md` §Sección B).
Fase 2 (`PLANES/FASE2_ANALISIS_DATOS__scoping.md` §OPT-17). Depende de **OPT-16**
(`PLANES/OPT-16__resultado-por-estacion.md` — usa su `compute_station_results`).

## Problema

`compute_results` (`backend/app/services/results.py:94-110`) calcula la nota
agregada del estudiante como **razón de sumas crudas**:

```python
total_score = eval_score + form_score          # suma sobre TODAS las estaciones
max_score   = eval_max   + form_max
percentage  = total_score / max_score * 100
```

Consecuencia (H-dato-3): una estación con `max_score` alto **domina** la nota
final. Si la estación 1 vale 20 puntos y la estación 2 vale 5, la estación 1 pesa
4× en el porcentaje agregado y en la nota 1.0–7.0 (`compute_equivalent_grade`),
aunque psicométricamente ambas midan una competencia equivalente. El diseñador no
tiene forma de igualar el peso de las estaciones.

## Causa raíz

`backend/app/services/results.py:56-92` — las dos consultas agregadas
(`EvaluatorRecord`, `StudentResponse`) agrupan por `student_id` y suman
`score_obtained` / `max_score` sin normalizar por estación. `:97-99` combina esas
sumas directamente. No existe ningún paso de "porcentaje por estación" antes de
agregar. No hay campo de peso ni de umbral por estación en `Station`
(`grep -n "weight\|ponder\|umbral" backend/app/models/entities.py` → nada).

## Decisión metodológica del usuario (2026-08-29) — ya tomada, no re-preguntar

1. **Estándar COMPENSATORIO**, sin cambios de modelo: un solo umbral global
   (`passing_reference_percent`) sobre el desempeño agregado. **No** conjuntivo,
   **no** híbrido, **no** standard-setting (Angoff / borderline-regression).
2. **Todas las estaciones pesan igual.** La nota agregada pasa a ser el
   **promedio de los porcentajes de logro por estación**: cada estación se
   normaliza a 0–100 % contra su propio máximo, y el porcentaje del estudiante es
   la media aritmética de esos porcentajes.
3. **Nota final 1.0–7.0 sin cambio de método.** `compute_equivalent_grade` sigue
   mapeando el porcentaje (ahora el promedio de %-por-estación) contra
   `passing_reference_percent`. Esa función **no se toca**.
4. **Sin peso configurable, sin umbral por estación** en esta iteración. (Ver
   §"Umbral por estación" abajo: la auditoría del plan concluyó que **no** es
   trivial de sumar como opcional → queda fuera, follow-up OPT-17b.)
5. **Cambia el número consolidado** para eventos con estaciones de distinto
   máximo. Los eventos ya `cerrado`/`archivado` siguen sirviendo su snapshot
   `ECOEResult` viejo (patrón OPT-1); solo los eventos que se **consoliden desde
   OPT-17 en adelante** usan la fórmula nueva. Ver §"Impacto sobre eventos
   históricos".

## Cambio propuesto

### Backend — `app/services/results.py`

**1. `compute_results` se reescribe sobre `compute_station_results` (OPT-16).**

```python
def compute_results(db, ecoe_event_id) -> list[dict]:
    ecoe_event = db.get(ECOEEvent, ecoe_event_id)
    passing = ecoe_event.passing_reference_percent if ecoe_event else 60.0
    students = <activos, igual que hoy>
    station_rows = compute_station_results(db, ecoe_event_id)   # OPT-16
    by_student: dict[int, list[dict]] = defaultdict(list)
    for row in station_rows:
        by_student[row["student_id"]].append(row)
    results = []
    for student in students:
        rows = by_student.get(student.id, [])
        # Estaciones con máximo > 0: sólo esas pueden aportar un % de logro.
        scored = [r for r in rows if r["max_score"] and r["max_score"] > 0]
        raw_obtained = sum(r["obtained_score"] for r in rows)
        raw_max      = sum(r["max_score"] for r in rows)
        if scored:
            percentage = sum(r["percent_score"] for r in scored) / len(scored)
        else:
            percentage = 0.0
        grade = compute_equivalent_grade(percentage, passing)
        results.append({
            "student_id": student.id,
            "student_name": f"{student.name} {student.last_name}",
            "ecoe_number": student.ecoe_number,
            "total_score": round(raw_obtained, 2),   # suma cruda — informativa
            "max_score":   round(raw_max, 2),        # suma cruda — informativa
            "percentage":  round(percentage, 2),     # ← promedio de %-por-estación
            "equivalent_grade": round(grade, 2),
            "stations_counted": len(scored),         # nuevo, opcional (ver decisión #2)
        })
    return results
```

- **`total_score` / `max_score` se mantienen como suma cruda** de los registros
  del estudiante — siguen siendo el dato que el analista externo espera y lo que
  asertan varios tests hoy (`test_results_immutability.py`, `test_deferred_grading.py:256`).
  **Consecuencia visible a documentar**: a partir de OPT-17, para eventos con
  estaciones de distinto máximo, `percentage` deja de ser `total_score /
  max_score * 100`. Esto se explicita en la UI (subtítulo de la tabla) y en el
  export (OPT-19).
- **Filtro idéntico a hoy**: `compute_station_results` (OPT-16) ya aplica
  `mode == ejecucion`, `is_draft == False`, `score_obtained IS NOT NULL`. OPT-17
  no introduce filtros nuevos; sólo cambia cómo se combinan las filas.
- **Estación sin registro para el estudiante** (faltó / ausente): no genera fila
  → no entra a la media → **no penaliza** (igual que hoy: la suma cruda tampoco
  la contaba). OPT-17 no cambia el trato de las estaciones totalmente ausentes;
  eso es materia de trazabilidad / OPT-18.
- **Estación con fila pero `max == 0`**: se excluye de la media (no se puede
  calcular "% de logro" sobre 0). Entra igual a `total_score`/`max_score` crudos.
- **Estudiante sin ninguna estación puntuable**: `percentage = 0`,
  `equivalent_grade = compute_equivalent_grade(0, passing)` (= 1.0). Igual que hoy.

**2. `read_results` — sin cambios.** Ya sirve el snapshot `ECOEResult` cuando
`status ∈ {cerrado, archivado}` y hay filas (`results.py:124-157`); sólo recalcula
en vivo (`compute_results`) para eventos no cerrados o cerrados sin snapshot. La
fórmula nueva entra **sólo** por el camino de recálculo en vivo y por
`persist_results` en el próximo cierre.

**3. `persist_results` — sin cambios de código.** Llama `compute_results` (ya con
la fórmula nueva) y persiste `ECOEResult`. El snapshot que escribe a partir de
OPT-17 lleva el `percentage`/`equivalent_grade` nuevos.

**4. `build_traceability_report` — sin cambios.** Toma `total_score` /
`percentage` / `equivalent_grade` de `results_by_student` (`results.py:244-245,
365-367`); hereda la fórmula nueva automáticamente y de forma coherente.

**5. `compute_station_results` (OPT-16) — verificar orden de merge.** Este plan
**asume que OPT-16 ya está en `main`**. Si OPT-16 no expuso `compute_station_results`
como función reutilizable (sólo la usa dentro de `persist_results`), OPT-17 la
promueve a función de módulo. Coordinar con quien implemente OPT-16.

### Frontend

**`frontend/src/app/(app)/results/page.tsx`** — cambio mínimo de copy, sin lógica
nueva:
- Subtítulo de la `SectionCard` "Consolidado por estudiante": aclarar que
  `Porcentaje` es el **promedio del % de logro de cada estación** (normalizado a
  su propio máximo) y que `Puntaje`/`Máximo` son sumas crudas informativas.
- Opcional: columna "Estaciones" (`stations_counted`) para que se vea sobre
  cuántas estaciones se promedió.

**`frontend/src/lib/types.ts`** — si se agrega `stations_counted`, añadirlo al
tipo `ECOEResult` del front (hoy en `ResultsResponse`). Si no, sin cambios.

Sin pantalla nueva, sin endpoint nuevo, sin permiso nuevo.

### Migración

**No.** Cálculo derivado. No se toca el schema. No se reescriben filas
`ECOEResult` existentes (los eventos cerrados conservan su snapshot).

> **Gate humano**: si durante la implementación se decide agregar
> `stations_counted` como columna persistida en `ecoe_results` (no recomendado —
> es derivable), eso pasa a requerir migración y aprobación explícita. El plan
> asume que `stations_counted` es sólo un campo del dict de respuesta, no de BD.

### Máquina de estados

No se toca `ALLOWED_STATUS_TRANSITIONS` ni `ecoe-form.tsx`. `persist_results` se
sigue disparando en la rama de cierre; OPT-17 sólo cambia qué número calcula.

## Impacto sobre eventos históricos

| Situación del evento | Qué sirve `/results` y el export | Efecto de OPT-17 |
|---|---|---|
| `cerrado` / `archivado` **con** snapshot `ECOEResult` | El snapshot congelado (`read_results`, `FROZEN_RESULT_STATUSES`, `results.py:125`) | **Ninguno.** Sigue mostrando la razón-de-sumas vieja tal como se consolidó. |
| `cerrado` **sin** snapshot (cierre previo a OPT-1, o cierre manual sin `persist_results`) | Recálculo en vivo (`compute_results`) | Pasa a mostrar la **fórmula nueva**. Caso raro; documentado. Si molesta, se puede consolidar el evento a mano una vez para congelarlo. |
| `publicado` / `en_ejecucion` (aún no cerrado) | Recálculo en vivo | `/results` muestra la fórmula nueva **de inmediato** tras el deploy. No es la nota oficial hasta el cierre; el chip `frozen=false` ya lo comunica. |
| Evento nuevo, se consolida tras OPT-17 | Snapshot con la fórmula nueva | Comportamiento deseado. |
| Evento `archivado → borrador` reabierto y re-cerrado | Snapshot re-escrito con la fórmula nueva | Esperado (una reapertura es una re-consolidación consciente). |

**Efecto sobre `equivalent_grade` (1.0–7.0)** en eventos que se consoliden con la
fórmula nueva y tengan estaciones de distinto máximo: los estudiantes fuertes en
la estación de máximo alto **bajan**; los fuertes en estaciones de máximo bajo
**suben**. Es la corrección buscada. Para eventos con **todas las estaciones del
mismo máximo**, `promedio(%) == razón de sumas` exactamente → **la nota no
cambia** (ver test `test_equal_max_stations_unchanged`).

**No hay backfill.** Ninguna rutina reescribe `ECOEResult` histórico. Si en algún
momento se quisiera re-expresar actas viejas con la fórmula nueva, sería una
operación explícita y aparte (gate humano) — fuera de OPT-17.

## Tests (incluye negativos — toca integridad de la nota consolidada)

Archivo: extender `backend/tests/test_results.py` + ajustar
`backend/tests/test_station_results_opt16.py`.

Positivos / comportamiento nuevo:
- `test_aggregate_is_mean_of_station_percents` — evento, 2 estaciones de máximo
  20 y 5; estudiante 20/20 y 0/5. Antes: 80 %. Ahora: `mean(100, 0) = 50` %.
  `total_score == 20`, `max_score == 25` (crudos, sin cambio).
- `test_equal_max_stations_unchanged` — 3 estaciones de máximo 10; cualquier
  combinación de puntajes → `percentage` idéntico a `sum(obtenido)/sum(máx)*100`.
  **Prueba que OPT-17 sólo mueve eventos con máximos heterogéneos.**
- `test_single_station_event_unchanged` — 1 estación → `mean` de un solo % ==
  razón de sumas. Cubre `test_grading.py:164` (`percentage == 100`).
- `test_missing_station_not_penalized` — estudiante con fila en 1 de 2 estaciones
  → `percentage` == % de esa estación, no la mitad. `stations_counted == 1`.
- `test_equivalent_grade_fed_new_percentage` — `equivalent_grade ==
  compute_equivalent_grade(mean_percent, passing_reference_percent)`;
  `compute_equivalent_grade` sin tocar (los 6 tests de `test_results.py`
  existentes siguen verdes sin cambio).

Negativos / integridad:
- `test_station_with_zero_max_excluded_from_mean` — fila con `max_score == 0` no
  fuerza un 0 % en la media; sí entra a `max_score` crudo.
- `test_blank_auto_submission_counts_as_zero_percent` — `submission_kind='auto'`,
  `answers={}`, `score_obtained=0`, `max_score>0` → entra a la media como 0 %,
  baja el promedio (coherente con OPT-16 y con el consolidado viejo).
- `test_evaluator_draft_excluded_from_mean` — `EvaluatorRecord.is_draft=True` no
  aporta fila ni % (espejo de `compute_results` actual).
- `test_pending_deferred_grading_excluded_then_included` — `StudentResponse` con
  `score_obtained IS NULL` no entra; tras corregir, entra y mueve la media.
- `test_pilotaje_records_excluded` — `mode='pilotaje'` no aporta.
- `test_closed_event_keeps_old_snapshot_formula` — evento `cerrado` con snapshot
  cuyo `percentage` se guardó con la fórmula vieja; `GET /results` lo sirve tal
  cual; mutar un `StudentResponse.score_obtained` a mano no lo cambia (espejo de
  `test_results_immutability.py`). El valor servido **no** coincide con
  `compute_results` en vivo si el evento tiene máximos heterogéneos → confirma
  que el snapshot manda.
- `test_event_consolidated_after_opt17_persists_mean_formula` — `persist_results`
  sobre un evento fresco con máximos heterogéneos → `ECOEResult.percentage` es la
  media de %-por-estación, no la razón de sumas.
- `test_station_results_sum_still_matches_total_score` (ajuste del invariante de
  OPT-16) — el invariante de OPT-16 era `sum(by_station.percent…)`≠; se
  reescribe a: `sum(StationResult.obtained_score) == ECOEResult.total_score` y
  `sum(max) == ECOEResult.max_score` (las **sumas crudas** siguen cuadrando; el
  `percentage` ya no es una suma). **Cita consciente**: el test de OPT-16
  `test_station_results_sum_matches_consolidated` se adapta aquí.

Frontend: `frontend/src/app/(app)/results/__tests__/page.test.tsx` — el subtítulo
nuevo se renderiza; si se agrega la columna "Estaciones", aparece.

## Riesgos / alcance

- **Superficie acotada**: una función reescrita (`compute_results`), copy de UI,
  ajuste de tests. Sin migración, sin endpoint, sin permisos, sin máquina de
  estados.
- **Riesgo principal — expectativa de "porcentaje = puntaje/máximo"**: usuarios
  acostumbrados a verificar la aritmética a mano verán que ya no cuadra.
  Mitigación: copy explícito en `/results` y en el export (OPT-19), y esta
  sección en la doc de resultados.
- **Dependencia dura de OPT-16**: si `compute_station_results` no existe como
  función reutilizable tras OPT-16, este plan la crea — coordinar merge.
- **Tests de terceros**: `test_deferred_grading.py:256` y
  `test_results_immutability.py` asertan `total_score` (sumas crudas) → **no se
  rompen**. `test_grading.py:164` asierta `percentage == 100` en escenario de 1
  estación → **no se rompe**. Verificar en la corrida completa que no aparezca
  otro assert de `percentage` en escenario multi-estación heterogéneo; si
  aparece, ajustarlo con comentario citando esta decisión.
- **Umbral por estación** (decisión #4): evaluado y **descartado para OPT-17**.
  Añadirlo como opcional exige (a) columna `passing_percent` nullable en
  `stations` → migración → gate; (b) UI en el Constructor; (c) lógica de
  agregación conjuntiva o de "flag por estación reprobada" que **contradice** el
  estándar compensatorio elegido. No es trivial. Queda como **OPT-17b** si el
  usuario lo pide.

## Verificación

- [x] `cd backend && python3 -m pytest` (SQLite) — **323 passed** (11 nuevos en
      `test_normalizacion_opt17.py`; `test_station_results_opt16.py::test_station_results_sum_matches_consolidated`
      reescrito citando OPT-17).
- [x] `TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q` — **323 passed**
- [x] Migración desde base limpia llega a head (`n4o5p6q7r8s9`) **sin revisión nueva**:
      `DATABASE_URL=sqlite:////tmp/ecoe_opt17_check.db SECRET_KEY=test-secret ENVIRONMENT=test AUTO_SEED_DEMO=false alembic upgrade head` — OPT-17 es sin migración.
- [x] `cd frontend && npm run lint` (0 errores, 2 warnings preexistentes) `&& npm run build` (OK) `&& npx vitest run` — **59 passed** (2 nuevos).
- [ ] Revisión manual: evento demo con 2 estaciones de distinto máximo →
      `/results` muestra el promedio de %-por-estación y el subtítulo aclaratorio.
- [ ] `./scripts/run_e2e.sh --grep "results"` sobre el stack de ramas — no corrido
      (restricción de sandbox de red en la sesión de implementación).

## Notas de implementación (2026-08-29)

- Rama `opt/OPT-17-normalizacion` desde `opt/OPT-16-station-results` (`adc7303`).
- `compute_results` reescrito sobre `compute_station_results` (OPT-16). Fórmula
  nueva de `percentage`:
  ```python
  rows = station_rows_by_student.get(student.id, [])
  scored = [r for r in rows if r["max_score"] and r["max_score"] > 0]
  percentage = (sum(r["percent_score"] for r in scored) / len(scored)) if scored else 0.0
  ```
  Estudiante sin ninguna estación puntuable → `percentage = 0.0` (no `None`),
  `equivalent_grade = 1.0` — idéntico al comportamiento anterior a OPT-17.
- `total_score` / `max_score` = suma cruda de `obtained_score` / `max_score` de
  **todas** las filas del estudiante (incluidas las de `max == 0`).
- `stations_counted = len(scored)` — sólo en `compute_results` (recálculo en
  vivo). El snapshot `ECOEResult` **no** lo persiste (sin columna, sin
  migración); `read_results` en la rama congelada devuelve las mismas 7 claves
  de antes. `test_results_immutability.py::test_read_results_helper_shapes_match`
  queda sin cambios (sigue verde).
- Frontend: columna "Estaciones" en "Consolidado por estudiante" + subtítulo
  reescrito (el % es promedio de %-por-estación; Puntaje/Máximo son sumas
  crudas). `ECOEResult.stations_counted?: number` (opcional) en `types.ts`.
- Tests de terceros verificados sin cambio: `test_grading.py:164`
  (`percentage == 100`, 1 estación), `test_deferred_grading.py:256`
  (`total_score`/`max_score` crudos), `test_results_immutability.py`
  (`total_score` crudo + shape congelado). Ningún assert de `percentage` en
  escenario multi-estación heterogéneo se rompió.
- CLAUDE.md: nueva sección "Consolidación de resultados y nota agregada".

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-29
- **Decisiones metodológicas: Aprobado por usuario: ✅ 2026-08-29** (estándar
  compensatorio; estaciones con peso igual = promedio de %-por-estación; nota
  1.0–7.0 sin cambio de método; sin peso/umbral por estación; sin migración;
  eventos cerrados conservan snapshot viejo).
- **Plan técnico y decisiones de implementación: ✅ 2026-08-29 — aprobado; decisiones de implementación = las recomendadas.**
- Implementado por: implementador — 2026-08-29 → `en-verificación` (rama `opt/OPT-17-normalizacion`).
- Decisiones de implementación abiertas:
  1. ¿`total_score` / `max_score` se mantienen como suma cruda (recomendado, no
     rompe tests ni el export) o se re-expresan como `mean%` / `100`?
  2. ¿Se agrega el campo `stations_counted` a la respuesta (recomendado, ayuda a
     leer la media) y a la tabla del front?
  3. Evento `cerrado` **sin** snapshot: ¿se deja caer a la fórmula nueva
     (recomendado, caso raro) o se agrega un guard que evite recalcular estados
     congelados sin snapshot?
  4. Orden de merge con OPT-16: confirmar que `compute_station_results` queda
     como función de módulo reutilizable.
