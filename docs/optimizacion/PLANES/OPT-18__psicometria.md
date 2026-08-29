# OPT-18 · Analítica psicométrica (ejecución + pilotaje, con item analysis por criterio de pauta)

**Severidad: alta (capacidad ausente). El item más grande de la Fase 2 (L–XL).**
Origen: H-dato-2 (`docs/optimizacion/hallazgos/auditor-correccion-resultados__2026-08-28.md`
§Sección B). Fase 2 (`PLANES/FASE2_ANALISIS_DATOS__scoping.md` §OPT-18).
Depende de **OPT-16** (`compute_station_results` / matriz de %-por-estación).
**No** depende de OPT-17 (calcula su propia matriz de %-por-estación cruda).

## Problema

`grep -niE "weight|discrimin|cronbach|alpha|reliab|difficulty|borderline|point.?bis" backend/app/`
→ **0 resultados**. La app registra los datos crudos del examen y del pilotaje
(`EvaluatorRecord`, `StudentResponse`, sus `answers`/`grading` por ítem) pero **no
produce ninguna métrica** a partir de ellos:

- No hay media/DE/n por estación en ningún endpoint (más allá de conteos).
- No hay fiabilidad (α de Cronbach) ni discriminación estación-total.
- No hay índice de dificultad ni punto-biserial por criterio de pauta.
- `compute_results` fija `mode == ejecucion` (`results.py:67,87`), así que **los
  datos del pilotaje son inaccesibles vía Resultados**. `pilot_runs` sólo cuenta
  corridas. La transición `en_pilotaje → pilotaje_validado`
  (`validation.py:461-464`) es un click humano **sin respaldo cuantitativo** —
  justo la fase donde la psicometría aporta más valor.

## Causa raíz

Nunca se construyó la capa de analítica. Los insumos existen:

- **Estaciones con evaluador**: `EvaluatorRecord.answers` tiene forma
  `{"tool_id", "tool_name", "tool_type", "item_scores": {"<AssessmentItem.id>": score}}`
  (ver `frontend/src/app/(app)/evaluator/page.tsx:204-209,256-261`). Los ítems y
  su puntaje máximo están en `AssessmentTool.items` /
  `AssessmentItem.score_per_item` (`entities.py:244-259`), vía
  `Station.assessment_tool_id`.
- **Estaciones con formulario del estudiante**: `StudentResponse.grading` tiene
  forma `{"question_<n>": {"kind", "earned", "max", "answered"}}`
  (`services/grading.py:37-88`).
- **%-por-estación**: `compute_station_results` (OPT-16) ya da
  `(student_id, station_id, obtained, max, percent)` con los filtros correctos.

## Decisión del usuario (2026-08-29) — ya tomada, no re-preguntar

- **Suite completa con item analysis a nivel de criterio de pauta** (`AssessmentItem`),
  no sólo a nivel de estación. Explícitamente pedido.
- Métricas:
  - **Por estación**: media, DE, n, histograma de notas.
  - **Inter-estación**: α de Cronbach; discriminación estación-total
    (correlación de la estación contra el total-menos-esa-estación).
  - **Por criterio de pauta** (`AssessmentItem` para estaciones con evaluador;
    `question_<n>` para estaciones con formulario): índice de **dificultad** y
    **punto-biserial** (ítem vs. total de la estación, corregido).
- Corre sobre `mode == ejecucion` **y** `mode == pilotaje` (mismo módulo,
  parámetro `mode`).
- En `pilotaje_validado`: las métricas **advierten, no bloquean**. Umbrales con
  defaults sensatos (propuestos abajo), configurables después si hace falta.
- Endpoints de analítica nuevos; pantallas en `/results` y `/pilotage`; módulo de
  cálculo nuevo. **Sin migración obligatoria** (todo derivado). Cacheo: decisión
  registrada abajo (→ **no** cachear en F1–F3).
- Se puede dividir en sub-fases. Este plan lo hace: **F1 estación/evento**,
  **F2 item analysis por criterio**, **F3 integración con `pilotaje_validado`**.

## Definiciones estadísticas (para que la implementación no improvise)

Sea, para un `mode` dado y un evento, la matriz `P[estudiante][estación]` = % de
logro de esa estación (de `compute_station_results` filtrado por `mode`; sólo
estaciones con `max > 0`).

- **Análisis por caso completo (listwise)** para α y discriminación estación-total:
  sólo estudiantes con % en **todas** las estaciones del circuito que rindieron.
  Reportar `n_complete` y `n_total`. (Item analysis por criterio usa todos los
  que tienen dato en ese ítem — pairwise.)
- **Media / DE por estación**: sobre `percent_score` de esa estación; DE muestral
  (`statistics.stdev`, n−1); `None` si n < 2. También media/DE del puntaje crudo.
- **Histograma de notas**: buckets de `equivalent_grade` (1.0–1.9, 2.0–2.9, …,
  7.0) o de tramos de 10 % — decidir en impl (recomendado: tramos de nota 1–7).
- **α de Cronbach** sobre `P` (estaciones = ítems):
  `α = k/(k−1) · (1 − Σ var(estación_j) / var(Σ_j estación_j))`, varianza
  poblacional, sobre los `n_complete`. `None` si k < 2 o `n_complete < 2` o
  varianza total 0.
- **Discriminación estación-total (corregida)**: para cada estación j,
  `r_j = pearson( P[:,j] , Σ_{m≠j} P[:,m] )` sobre `n_complete`. `None` si
  varianza 0 en cualquiera de los dos vectores.
- **Índice de dificultad de un criterio** (`p`): media de `earned / max` del
  criterio sobre los estudiantes con dato. Rango 0–1 (0 = nadie lo logra,
  1 = todos). Para ítems dicotómicos coincide con la proporción de acierto.
- **Punto-biserial de un criterio**: `pearson( earned_i , T_i − earned_i )`
  donde `T_i` = puntaje total de **esa estación** para el estudiante i
  (corrección ítem-resto). `None` si varianza 0 (p. ej. todos sacan el máximo).
- **Correlaciones**: implementar Pearson a mano o con `numpy.corrcoef` /
  `pandas.Series.corr`. **`scipy` no está en `requirements.txt`** — no usar
  `scipy.stats`. `numpy` está disponible transitivamente vía `pandas==2.3.2`;
  agregarlo explícito a `requirements.txt` (`numpy>=1.26`) para dejarlo claro.

## Umbrales por defecto (propuesta del plan — el usuario los revisa)

| Métrica | Umbral de advertencia | Texto sugerido |
|---|---|---|
| α de Cronbach | `< 0.6` | "Consistencia interna baja (α = X): las estaciones no miden un constructo común." |
| Discriminación estación-total | `r < 0.2` | "La estación N discrimina poco (r = X): su resultado casi no se relaciona con el desempeño global." |
| Discriminación estación-total | `r < 0` | "La estación N discrimina en sentido inverso (r = X): revisar pauta o dificultad." |
| Dificultad de criterio `p` | fuera de `[0.2, 0.9]` | "El criterio «…» es muy difícil / muy fácil (p = X)." |
| Punto-biserial de criterio | `< 0.2` | "El criterio «…» discrimina poco (r_pb = X)." |
| Punto-biserial de criterio | `< 0` | "El criterio «…» está invertido (r_pb = X): quienes rinden peor lo obtienen más." |
| n por estación | `< 10` | Nota de fiabilidad: "Métricas poco fiables con n < 10." (no es advertencia de calidad, es caveat de muestra) |

Constantes en `services/psychometrics.py` (`PSYCHO_THRESHOLDS = {...}`). **Sin
migración.** Si más adelante se quieren por evento → columna JSON en `ecoe_events`
→ migración → gate → follow-up, no en OPT-18.

## Cambio propuesto

### F1 — cálculo por estación + inter-estación + endpoint + pantallas (esfuerzo M–L)

**Backend nuevo: `app/services/psychometrics.py`**

- `station_percent_matrix(db, ecoe_event_id, mode) -> (matrix, students, stations)`
  — reusa `compute_station_results` parametrizado por `mode`. **Nota de
  coordinación con OPT-16**: `compute_station_results` hoy fija
  `mode == ejecucion`; OPT-18 necesita que acepte `mode` como parámetro
  (`mode: str = "ejecucion"`). Es un cambio aditivo de firma; hacerlo aquí y
  actualizar la llamada de `persist_results` (sigue pasando `"ejecucion"`).
- `station_stats(...)` → por estación: `n`, `mean_percent`, `sd_percent`,
  `mean_score`, `sd_score`, `grade_histogram`.
- `reliability(...)` → `{cronbach_alpha, n_complete, n_total,
  station_discrimination: [{station_id, r}]}`.
- `evaluate_thresholds(stats, reliability, items) -> list[warning dict]` —
  produce las advertencias contra `PSYCHO_THRESHOLDS`.
- `build_psychometrics_block(db, ecoe_event_id, mode) -> dict` — orquesta lo
  anterior + (en F2) el item analysis.

**Backend endpoint** — nuevo router `app/api/routes/analytics.py` (registrado en
`app/main.py` / `app/api/routes/__init__.py`):

```
GET /api/analytics/{ecoe_event_id}/psychometrics?mode=ejecucion|pilotaje
```

- `ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)` —
  misma puerta que `/results`. **No** accesible para `corrector` / `evaluador` /
  `estudiante`.
- `mode` validado contra `{"ejecucion", "pilotaje"}` (422 si otra cosa).
- **Frozen / live**: para `mode == ejecucion` y evento `cerrado`/`archivado`,
  usar `read_station_results` (snapshot-aware, OPT-16) como fuente; en cualquier
  otro caso, cálculo en vivo. Para `mode == pilotaje`, **siempre** en vivo (no
  hay snapshot de pilotaje). Las métricas se derivan del conjunto servido → si el
  conjunto es inmutable, las métricas también. No se persisten.
- Respuesta sin `response_model` estricto (dict) o con uno laxo → aditivo.

**Frontend F1**

- `frontend/src/lib/api.ts` — `api.psychometrics(eventId, mode)`.
- `frontend/src/lib/types.ts` — `PsychometricsResponse`.
- `frontend/src/app/(app)/results/page.tsx` — `SectionCard` "Psicometría
  (ejecución)": tabla por estación (n, media %, DE %, histograma mini) + bloque de
  fiabilidad (α, discriminación por estación) + lista de advertencias.
- `frontend/src/app/(app)/pilotage/page.tsx` — `SectionCard` "Psicometría del
  pilotaje" con `mode=pilotaje`: mismas métricas sobre los datos de pilotaje;
  este es el respaldo cuantitativo del paso `pilotaje_validado`.

### F2 — item analysis por criterio de pauta (esfuerzo M–L)

**`app/services/psychometrics.py`**

- `item_scores_by_station(db, ecoe_event_id, mode) -> dict[station_id, dict]`:
  - Estaciones con `assessment_tool_id`: leer `EvaluatorRecord` (`mode`,
    `is_draft == False`), extraer `answers["item_scores"]`. Resolver la clave
    contra `AssessmentItem.id` (y fallback a `order_index` — el front usa
    `String(item.id ?? item.order_index ?? index)`, `evaluator/page.tsx:116,497`,
    así que la clave puede no ser el id; documentar y manejar ambas). `max` del
    criterio = `AssessmentItem.score_per_item`.
  - Estaciones con formulario: leer `StudentResponse.grading` (`score_obtained
    IS NOT NULL`, `mode`), cada `question_<n>` con `max > 0` es un criterio;
    `earned` / `max` directos.
- `item_analysis(...)` → por criterio: `{station_id, criterion_key,
  criterion_label, n, difficulty, point_biserial, max}` + a nivel estación el
  vector de totales para la corrección ítem-resto.
- `build_psychometrics_block` incorpora `item_analysis` y sus advertencias.

**Limitaciones a documentar en el plan y en la UI**:
- El `score_obtained` del `EvaluatorRecord` es **provisto por el cliente**
  (acotado a `[0, max]`, `evaluator.py:459-463`); `item_scores` **no** se valida
  contra él en el backend. El item analysis del lado evaluador es **best-effort**
  y sólo cubre estaciones cuyo `assessment_tool` tiene ítems y cuyo evaluador
  usó la pauta estructurada (no el campo de puntaje libre).
- Estaciones sin `assessment_tool` y sin formulario puntuable → no aparecen en el
  item analysis (sólo en las métricas por estación de F1).

**Frontend F2**: extender la `SectionCard` de psicometría con una tabla por
criterio (estación · criterio · n · dificultad · punto-biserial), con resaltado
de los que caen fuera de umbral.

### F3 — integración con `pilotaje_validado` (esfuerzo M)

- **No** se toca `ALLOWED_STATUS_TRANSITIONS` ni `update_ecoe_status`. La
  transición `en_pilotaje → pilotaje_validado` **no se bloquea**.
- El **modal de validación de pilotaje** (`frontend/src/components/ecoe-form.tsx`
  + `frontend/src/app/(app)/pilotage/` / `validation/page.tsx`) hace un fetch
  extra a `GET /api/analytics/{id}/psychometrics?mode=pilotaje` y muestra las
  advertencias (α baja, estación que no discrimina, criterios fuera de rango)
  como **lista de advertencias no bloqueantes** junto a "Validar pilotaje".
- **No** agregar el cálculo psicométrico dentro de `compute_ecoe_validation`
  (`validation.py`) — corre en cada llamada de dashboard/validación y encarecería
  una ruta caliente. El modal hace su propio fetch cuando el usuario abre "Validar
  pilotaje". (Decisión de implementación: si se prefiere una sola llamada,
  exponer un `pilot_psychometrics_summary` calculado sólo cuando
  `status == en_pilotaje` — evaluar coste primero.)
- Opcional (recomendado, barato): `AuditLog(action="validate_pilot")` al pasar a
  `pilotaje_validado`, con un resumen de si había advertencias abiertas —
  trazabilidad de "se validó el pilotaje con α = X y N advertencias".

### Migración

**No** (F1, F2, F3 con umbrales por defecto). Sólo `requirements.txt`:
`numpy` explícito.

> **Gate humano** si el usuario decide: (a) umbrales configurables por evento
> (columna JSON en `ecoe_events`), o (b) cachear las métricas en una tabla
> `psychometrics_snapshot` escrita al cierre / a la validación de pilotaje.
> Ambas requieren migración y aprobación explícita. **Recomendación del plan: no
> hacer ninguna de las dos en OPT-18.**

### Máquina de estados

No se toca. F3 sólo agrega lectura en el modal.

## Tests (incluye negativos — endpoint nuevo que expone datos de resultados)

Archivo nuevo: `backend/tests/test_psychometrics.py`.

Positivos (dataset chico con valores calculados a mano en el test):
- `test_station_stats_mean_sd_n` — 3 estudiantes en 1 estación → media/DE/n
  correctos; DE `None` con n < 2.
- `test_cronbach_alpha_known_value` — matriz 5×3 fija → α calculado a mano
  (`pytest.approx`).
- `test_station_discrimination_corrected` — estación vs. total-menos-estación.
- `test_item_difficulty_and_point_biserial` — pauta de 3 criterios → `p` y
  `r_pb` por criterio, a mano.
- `test_item_analysis_student_form_station` — estación con formulario puntuable →
  dificultad por `question_<n>`.
- `test_psychometrics_over_pilotaje_mode` — `mode=pilotaje` sólo ve registros de
  pilotaje; los de ejecución no entran (y viceversa con `mode=ejecucion`).
- `test_pilot_validation_modal_gets_warnings` — evento en pilotaje con α baja →
  el endpoint `?mode=pilotaje` devuelve la advertencia esperada.

Negativos / integridad / permisos (AGENTS.md — endpoint nuevo, datos sensibles):
- `test_psychometrics_requires_event_access` — `corrector`, `evaluador`,
  `estudiante` y usuario de otro evento → **403**.
- `test_psychometrics_mode_param_rejects_garbage` — `?mode=foo` → 422.
- `test_psychometrics_excludes_evaluator_drafts` — `is_draft=True` no cuenta.
- `test_psychometrics_excludes_pending_deferred_grading` —
  `score_obtained IS NULL` no cuenta.
- `test_psychometrics_insufficient_data_no_500` — 1 estudiante / 1 estación →
  α, DE, discriminación = `None`; HTTP 200; sin excepción.
- `test_cronbach_none_with_fewer_than_two_stations`.
- `test_point_biserial_none_on_zero_variance_item` — criterio que todos logran al
  máximo → `r_pb = None`, sin división por cero.
- `test_pilot_psychometrics_do_not_block_transition` — `PUT /ecoe/{id}` a
  `pilotaje_validado` con métricas malas → **200**; el grafo de estados no cambió;
  la advertencia vive sólo en el payload de analítica.
- `test_psychometrics_frozen_event_uses_snapshot` — evento `cerrado`; mutar a
  mano un `StudentResponse.score_obtained` → `?mode=ejecucion` sigue calculando
  sobre el snapshot `StationResult`, no sobre la mutación (espejo de OPT-1/OPT-16).

Frontend: tests de `results/page.tsx` y `pilotage/page.tsx` — los paneles
renderizan con métricas presentes y **degradan** (sin romper) con
`cronbach_alpha: null`, listas vacías, `mode` sin datos.

## Riesgos / alcance

- **El item más grande de la fase.** Mitigación: 3 sub-fases entregables e
  independientes (F1 ya es útil sola; F2 agrega profundidad; F3 conecta el
  workflow). Cada una con su corte de commit y su verificación.
- **Calidad estadística**: las fórmulas son estándar pero fáciles de equivocar
  (varianza n vs n−1, corrección ítem-resto, casos degenerados). Mitigación:
  tests con valores calculados a mano; documentar cada fórmula (arriba); revisar
  contra un caso conocido en R/planilla antes de cerrar.
- **`item_scores` no autoritativo** (lado evaluador): el item analysis es
  best-effort. Documentado en UI ("basado en la pauta estructurada; las
  estaciones con puntaje libre no aparecen").
- **Clave de `item_scores`** puede ser `id` u `order_index` según cómo se guardó
  el registro. Resolver ambas; test de las dos formas.
- **Coste en rutas calientes**: evitado al mantener el cálculo fuera de
  `compute_ecoe_validation` y en un endpoint aparte que el front pide bajo
  demanda.
- **`mode == pilotaje` y circuitos espejo**: la matriz por caso completo puede
  quedar con `n_complete` bajo si el pilotaje sólo cubrió algunas estaciones.
  Reportar `n_complete`/`n_total` y caveat de muestra; no fallar.
- **Sin migración** → riesgo de regresión de schema nulo.

## Verificación

- [ ] `cd backend && python3 -m pytest` (SQLite) — incluye `test_psychometrics.py`.
- [ ] `TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q`
- [ ] `DATABASE_URL=sqlite:////tmp/ecoe_alembic_check.db SECRET_KEY=test-secret ENVIRONMENT=test AUTO_SEED_DEMO=false alembic upgrade head`
      llega a head **sin revisión nueva**.
- [ ] `cd frontend && npm run lint && npm run build && npx vitest run`
- [ ] Validación cruzada: exportar la matriz de %-por-estación de un evento demo,
      recalcular α y discriminación en R/planilla, comparar con el endpoint.
- [ ] `./scripts/run_e2e.sh --grep "pilotaje|results"` sobre el stack de ramas
      (si aplica).

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-29
- **Decisiones metodológicas: Aprobado por usuario: ✅ 2026-08-29** (suite
  completa; item analysis a nivel de criterio de pauta; corre sobre ejecución y
  pilotaje; en `pilotaje_validado` advierte y no bloquea; endpoints + pantallas
  nuevas; módulo de cálculo nuevo; sin migración obligatoria; dividido en
  sub-fases).
- **Plan técnico, umbrales por defecto y decisiones de implementación: ✅
  2026-08-29 — aprobado; decisiones de implementación = las recomendadas
  (incluida la tabla de umbrales por defecto propuesta).**
- Decisiones de implementación abiertas:
  1. **Umbrales por defecto**: confirmar la tabla propuesta (α<0.6,
     discriminación<0.2, dificultad fuera de [0.2, 0.9], punto-biserial<0.2).
  2. **Histograma**: por tramo de nota 1.0–7.0 (recomendado) o por decil de %.
  3. **Casos completos**: listwise para α/discriminación (recomendado) vs.
     pairwise.
  4. **F3**: fetch separado desde el modal (recomendado) vs. campo dentro de
     `compute_ecoe_validation`.
  5. **`AuditLog` de `validate_pilot`** con resumen de advertencias: ¿se agrega?
  6. **Cacheo**: el plan recomienda **no** cachear. Confirmar.
  7. `numpy` explícito en `requirements.txt` vs. usar sólo `pandas`.
  8. ¿Router nuevo `routes/analytics.py` o los endpoints van en `operational.py`?
