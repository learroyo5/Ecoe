# Mini-auditoría — auditor-correccion-resultados · OPT-16 · 2026-08-29

Fundamento para el plan de **OPT-16 — resultado por estación (poblar `StationResult`)
+ desglose `by_station`** (hallazgo base H-dato-1). Rama auditada: `opt/fase2-analisis`
(desde `main` post-merge: OPT-1, OPT-2, OPT-3, OPT-4, OPT-5, OPT-7, OPT-8, OPT-15,
OPT-20 F1–F4). Modo: lectura de código + verificación in-process.

Responde las 7 preguntas del encargo.

---

## Resumen ejecutivo

| # | Pregunta | Veredicto |
|---|---|---|
| 1 | `StationResult` | Modelo **muerto** confirmado: 0 escritores, 0 lectores en backend y frontend. La tabla `station_results` **existe** en el baseline (`c7d8e9f00123_baseline_schema.py:409-425`), con `UniqueConstraint(ecoe_event_id, station_id, student_id)` e índice. **No hace falta migración.** |
| 2 | Agregación de `compute_results` | Suma `EvaluatorRecord` (mode=ejecucion, `is_draft=False`) + `StudentResponse` (mode=ejecucion, `score_obtained IS NOT NULL`), agrupado por `student_id` (colapsa estación). `max_score` = suma de los `max_score` de los propios registros, **no** de la config de la estación. |
| 3 | Forma de `by_station` | El frontend necesita: (a) nota del estudiante por estación (obtenido/máx/%) y (b) agregado por estación (n, media, DE). Encaja como una clave nueva `by_station` en el dict que ya devuelve `GET /results/{id}` (junto a `results` + `frozen` + `consolidated_at` + trazabilidad). Sin `response_model` Pydantic → es solo agregar la clave. |
| 4 | Interacción con OPT-1 | **Recomendado: congelar igual que `results`.** Poblar `StationResult` en `persist_results`; servir la nota por estación desde el snapshot cuando el evento está `cerrado`/`archivado` y hay filas; recalcular en vivo en cualquier otro caso. El agregado (media/DE/n) se deriva del conjunto servido → queda consistente automáticamente, no necesita almacenarse. |
| 5 | Interacción con OPT-20 F3/F4 | `by_station` debe aplicar **exactamente** los mismos filtros que `compute_results`: excluir `EvaluatorRecord.is_draft == True`; los `StudentResponse` autoenviados en blanco (`submission_kind == "auto"`, `answers == {}`) que ya tienen `score_obtained` (0/máx) **sí** entran (como en el consolidado). Los pendientes de corrección diferida (`score_obtained IS NULL`) **no** entran hasta que se corrijan. |
| 6 | `pilotaje` | **Estrictamente fuera de OPT-16.** `mode == ejecucion` únicamente. `station_results` no tiene columna `mode` y su constraint única colisionaría si se guardaran ambos modos. La analítica de pilotaje por estación es OPT-18 y debe resolverse por cálculo en vivo o con su propia decisión de schema. |
| 7 | Frontend | `results/page.tsx` es una pila plana de `<SectionCard>` en un `div.space-y-6`. Agregar una tarjeta "Resultados por estación" después de "Consolidado por estudiante" (línea 129) no toca el layout. `DataTable` ya envuelve en `overflow-x-auto` (`data-table.tsx:109`). |

---

## 1 · Estado de `StationResult`

### Definición del modelo — `backend/app/models/entities.py:586-599`

```python
class StationResult(Base, TimestampMixin):
    __tablename__ = "station_results"
    __table_args__ = (
        UniqueConstraint("ecoe_event_id", "station_id", "student_id",
                         name="uq_station_result_event_station_student"),
        Index("ix_station_results_event_student", "ecoe_event_id", "student_id"),
    )
    id: int
    ecoe_event_id: int  # FK ecoe_events.id
    station_id: int     # FK stations.id
    student_id: int     # FK students.id
    obtained_score: float   # NOT NULL
    max_score: float        # NOT NULL
    percent_score: float    # NOT NULL
    # + created_at / updated_at (TimestampMixin)
```

### La tabla existe en el schema actual — sin migración

- Baseline: `backend/alembic/versions/c7d8e9f00123_baseline_schema.py:409-425`
  crea `station_results` con las 7 columnas, la `UniqueConstraint`
  `uq_station_result_event_station_student` y el índice
  `ix_station_results_event_student`. El `downgrade` la borra (`:506-507`).
- `grep -rn "station_results" alembic/versions/` → **solo el baseline**. Ninguna
  migración posterior la altera.
- La forma del modelo ORM coincide byte a byte con la tabla del baseline
  (mismas columnas, mismo nombre de constraint, mismo índice). `alembic
  check` / autogenerate no produciría diff. **OPT-16 no necesita `alembic
  revision`.**

### Sin escritores ni lectores — modelo muerto confirmado

`grep -rn "StationResult\|station_results\|by_station\|byStation"
backend/app/ frontend/src/`:

- `backend/app/models/entities.py:586-590` — la definición.
- `backend/app/api/routes/grading.py` y `frontend/.../grading` — coincidencias de
  `pending_by_station`, que es de OPT-15 (cola del corrector) y **no** tiene
  relación con `StationResult`.
- Nada más. `StationResult` no se importa en `results.py`, `operational.py`,
  `validation.py`, ni en ningún test. No hay endpoint que lo lea. El frontend no
  tiene tipo ni vista.

`compute_results` (`results.py:50-110`) devuelve una lista de dicts a nivel
estudiante; no hay clave `by_station`. `build_traceability_report`
(`results.py:370-409`, bloque `station_traceability`) da **conteos** por estación
(`checkins_count`, `evaluations_count`, `student_submissions_count`,
`blank_auto_submissions`) pero **ningún puntaje**.

---

## 2 · Cómo agrega hoy `compute_results` a nivel estudiante

`backend/app/services/results.py:50-110`.

### Parte evaluador — `:57-74`

```sql
SELECT student_id, SUM(score_obtained), SUM(max_score)
FROM evaluator_records
WHERE ecoe_event_id = :id
  AND mode = 'ejecucion'
  AND is_draft = false          -- OPT-20 F3 (D3)
GROUP BY student_id
```

### Parte formulario del estudiante — `:77-92`

```sql
SELECT student_id, SUM(score_obtained), SUM(max_score)
FROM student_responses
WHERE ecoe_event_id = :id
  AND mode = 'ejecucion'
  AND score_obtained IS NOT NULL   -- pendientes de corrección diferida no entran
GROUP BY student_id
```

### Combinación — `:94-109`

Por cada `Student` activo (`is_active = true`):

```
total_score = eval_score + form_score
max_score   = eval_max   + form_max
percentage  = total_score / max_score * 100   (0 si max_score == 0)
equivalent_grade = compute_equivalent_grade(percentage, passing_reference_percent)
```

### De dónde sale `max_score`

**No de la configuración de la estación.** Sale de los `max_score` grabados en
cada `EvaluatorRecord` / `StudentResponse`. Consecuencia para OPT-16: el máximo
por estación se deriva de los propios registros de esa estación, no de
`Station.max_score` ni de `student_form_definition`. Un estudiante que no rindió
una estación (sin registro) simplemente no aparece en esa estación.

### Invariante aprovechable

`SUM(compute_station_results por estación de un estudiante) ==
compute_results de ese estudiante` — porque `by_station` reagrupa exactamente
las mismas filas con la misma clave de filtro, cambiando solo el `GROUP BY` de
`student_id` a `(student_id, station_id)`. Sirve de test de consistencia.

---

## 3 · Forma de datos para `by_station`

### Qué necesita el frontend

1. **Nota del estudiante por estación**: `obtained / max / percent` para cada par
   (estudiante, estación) con actividad. Formato largo (una fila por par) es lo
   más simple; el frontend puede pivotar a matriz estudiante×estación si quiere.
2. **Agregado por estación**: `n` (nº de estudiantes con nota en esa estación),
   `media` y `DE`. Útil además: `media %`, `min %`, `max %`, `media de máximo`.

### Dónde encaja en el payload

`GET /api/results/{id}` (`operational.py:399-408`) devuelve un **dict crudo sin
`response_model`**:

```python
return {
    "results": results,
    "frozen": frozen,
    "consolidated_at": ...,
    **build_traceability_report(db, ecoe_event_id, consolidated_results=results),
}
```

`by_station` entra como una clave más:

```python
by_station = {
    "stations": [   # agregado
        {"station_id", "station_number", "station_name", "circuit_name",
         "n", "mean_score", "sd_score", "mean_max",
         "mean_percent", "sd_percent", "min_percent", "max_percent"},
        ...
    ],
    "students": [   # formato largo, nota por (estudiante, estación)
        {"student_id", "ecoe_number", "student_name",
         "station_id", "station_number", "station_name",
         "obtained_score", "max_score", "percent_score"},
        ...
    ],
}
```

Sin `response_model` → agregar la clave no rompe contrato. `lib/types.ts` sí hay
que extenderlo (`ResultsResponse`).

---

## 4 · Interacción con OPT-1 (inmutabilidad)

OPT-1 dejó el patrón: `read_results` sirve el snapshot `ECOEResult` cuando
`status ∈ {cerrado, archivado}` **y** hay filas; si no, recalcula con
`compute_results`. `frozen` en el payload. El scoping doc de la Fase 2 pide
"respetar el patrón `frozen` de OPT-1".

**Recomendación: `StationResult` se congela igual que `ECOEResult`.**

- `persist_results` (`results.py:160-188`) — que ya se dispara en la rama de
  cierre (`validation.py:556-562`) y en `POST /results/{id}/consolidate`
  (`operational.py:411-419`) — **también** puebla `StationResult` con el mismo
  patrón delete-then-insert idempotente que usa para `ECOEResult`.
- Función de lectura análoga a `read_results` (p. ej. `read_station_results`):
  si `frozen` y hay filas `StationResult` → sirve la nota por estación desde el
  snapshot; si no → `compute_station_results` en vivo.
- **El agregado (media/DE/n) NO se almacena.** Se calcula en Python sobre el
  conjunto de notas por estación que se está sirviendo (snapshot o vivo). Como
  ese conjunto ya es inmutable cuando `frozen`, el agregado también lo es. Esto
  evita añadir columnas de agregado y evita el riesgo de que snapshot y agregado
  se desincronicen.

Motivo para congelar y no recalcular siempre: sin esto, editar una respuesta
después del cierre (aunque OPT-1 lo bloquea vía `grade_response` 409, quedan
rutas administrativas y reaperturas) movería la nota por estación mostrada como
oficial, exactamente el bug H-corr-1 que OPT-1 cerró para el consolidado.

Nota de coherencia: `build_traceability_report` hoy **siempre** recalcula en vivo
sus conteos aun con el evento cerrado (los `results` van por snapshot, la
trazabilidad no). `by_station` debe seguir el patrón de `results` (snapshot),
no el de la trazabilidad.

Riesgo espejo del de OPT-1: evento `cerrado` **sin** filas `StationResult`
(cerrado antes de OPT-16, o cierre a mano). `read_station_results` debe caer a
`compute_station_results` en vivo y el frontend no debe romperse.

---

## 5 · Interacción con OPT-20 F3/F4

`by_station` debe aplicar **los mismos filtros exactos que `compute_results`**:

| Caso | `compute_results` hoy | `by_station` debe |
|---|---|---|
| Borrador de evaluador (`EvaluatorRecord.is_draft == True`) | Excluido (`results.py:70`) | Excluir |
| Registro de evaluador finalizado (`is_draft == False`, cualquier `submission_kind`: `manual`/`contingency`/`draft_finalized`) | Incluido | Incluir |
| `StudentResponse` con `score_obtained IS NULL` (pendiente de corrección diferida) | Excluido (`results.py:88`) | Excluir (baja `n` de esa estación hasta que se corrija — consistente con el consolidado) |
| `StudentResponse` autoenviado en blanco (`submission_kind == "auto"`, `answers == {}`) con `score_obtained` resuelto = 0/máx | Incluido (suma 0) | Incluir (suma 0/máx; baja la media de la estación — es correcto) |
| `mode == pilotaje` | Excluido | Excluir |

Es decir: `by_station` reusa las **mismas dos consultas** de `compute_results`,
cambiando `GROUP BY student_id` → `GROUP BY student_id, station_id`. No hay que
razonar filtros nuevos; hay que no divergir.

`build_traceability_report` ya expone `blank_auto_submissions` por estación
(`station_traceability`), así que el frontend puede cruzar "media baja" con
"N autoenvíos en blanco" sin que OPT-16 agregue nada nuevo a ese bloque.

---

## 6 · `pilotaje` — dónde está el límite

**OPT-16 es estrictamente `mode == ejecucion`.** Argumentos:

1. `station_results` **no tiene columna `mode`**. Su `UniqueConstraint` es
   `(ecoe_event_id, station_id, student_id)` — sin `mode`. Guardar ahí datos de
   pilotaje colisiona con los de ejecución para el mismo trío.
2. `compute_results`, `read_results` y `build_traceability_report` ya fijan
   `mode == ejecucion` en todo. OPT-16 debe ser paralelo, no introducir una
   asimetría.
3. La analítica de pilotaje por estación (media/DE/discriminación sobre
   `mode == pilotaje`) es el corazón de **OPT-18**, que la produce por cálculo
   en vivo (no persistido) o con su propia decisión de schema. El scoping doc ya
   lo asigna a OPT-18.

**Recomendación**: OPT-16 no toca pilotaje. Si OPT-18 luego quiere reusar la
función `compute_station_results`, que la parametrice por `mode` — pero esa es
una decisión de OPT-18, y su salida **no** va a `station_results`.

---

## 7 · Frontend — dónde va la vista por estación

`frontend/src/app/(app)/results/page.tsx` (leído completo, 284 líneas):

- Estructura: `<div className="space-y-6">` con 6 `<SectionCard>` apilados:
  "Resumen operativo" → "Resultados y exportación" → "Consolidado por estudiante"
  (línea 111-129) → "Trazabilidad por estudiante" → "Trazabilidad por estación"
  → "Actividad reciente".
- Cada tabla usa `<DataTable rows=... columns=... />`.
  `frontend/src/components/data-table.tsx:109` envuelve `<table>` en
  `<div className="overflow-x-auto">` → contenido ancho hace scroll dentro de su
  contenedor, no rompe el body.
- `data?.by_station` se leería igual que `data?.station_traceability`
  (línea 33).

**Ubicación propuesta**: nueva `<SectionCard title="Resultados por estación">`
entre "Consolidado por estudiante" (después de la línea 129) y "Trazabilidad por
estudiante". Contiene:

1. `DataTable` agregado: Estación | n | Media % | DE % | Media pts | Máx.
2. `DataTable` (o el mismo, en formato largo) con la nota por estudiante y
   estación: N ECOE | Estudiante | Estación | Puntaje | Máximo | %.
   Opcional: filtro por estación reutilizando el patrón `<select>` cliente que
   ya usa `grading/page.tsx`.

Sin cambios de layout, sin componentes nuevos, sin ruta nueva. Riesgo visual
nulo.

Chip `frozen`: la tarjeta "Resultados y exportación" ya muestra
"Resultados consolidados el {fecha}" (líneas 75-85) cuando `frozen`. La vista por
estación no necesita su propio chip; hereda el estado del payload.

---

## Verificación in-process realizada

- `grep` exhaustivo de `StationResult` / `station_results` / `by_station` sobre
  `backend/app/` y `frontend/src/` → confirmado 0 usos reales.
- `grep -rn "station_results" backend/alembic/versions/` → solo baseline.
- Lectura línea a línea de `compute_results`, `read_results`, `persist_results`,
  `build_traceability_report` (`results.py:36-507`), `get_results` /
  `consolidate_results` / `export_excel` (`operational.py:399-431`), la rama de
  cierre (`validation.py:556-573`) y `results/page.tsx` completo.
- Confirmado que `GET /results/{id}` no tiene `response_model` → agregar
  `by_station` es aditivo.

## Conclusión para el plan

OPT-16 es **mecánico**: sin migración, sin endpoint nuevo, sin permiso nuevo,
sin decisión de máquina de estados. La única sub-decisión metodológica menor
para el usuario: **qué DE reportar** (muestral n−1 con `None` para n<2, vs.
poblacional) y si el agregado se hace sobre `percent_score` (recomendado, las
estaciones tienen distinto máximo) o sobre puntaje crudo (se puede dar ambos).
La nota por estación es **informativa** en OPT-16 (FASE1 §Decisión 3:
`StudentResponse.score_obtained` / `EvaluatorRecord` siguen siendo la fuente de
verdad; `StationResult` es agregación derivada). Alimentar un estándar por
estación es OPT-17, aparte.
