# Fase 2 · Capacidad de análisis de datos — documento de dimensionamiento

**No es un plan de implementación.** Es el encuadre de OPT-16, OPT-17, OPT-18 y OPT-19 para que el usuario
decida alcance, orden y definiciones metodológicas antes de que se redacten planes ejecutables.

Origen: `docs/optimizacion/hallazgos/auditor-correccion-resultados__2026-08-28.md` §Sección B (H-dato-1 a
H-dato-6). Todos confirmados por lectura de código.

## Por qué es una fase aparte

- Son **capacidades ausentes**, no regresiones ni bugs. La app registra los datos crudos; no los agrega ni los
  analiza.
- Están **explícitamente fuera del alcance P0** vigente (`P0_PLAN_CORE_INSTITUCIONAL.md` §"Fuera de alcance":
  "Analitica curricular longitudinal") y de `EVALUACION_DIFERIDA_FASE1.md`.
- Requieren **decisiones de producto y metodológicas** que no puede tomar un agente: modelo de estándar,
  ponderación, qué psicometría es requisito.
- Tienen **dependencias internas fuertes**: OPT-16 es el cimiento de los otros tres.

Recomendación del optimizador: cerrar primero el lote de estabilización (OPT-1..5, OPT-8). Luego abrir esta
fase con su propio ciclo auditor→plan→implementador.

## OPT-16 · Resultado por estación (poblar `StationResult`) — **item ancla, severidad alta**

- **Evidencia**: `app/models/entities.py:510-517` — `class StationResult` (ecoe_event_id, station_id,
  student_id, obtained_score, max_score, percent_score) con `UniqueConstraint` e índice. `grep StationResult`
  → **solo la definición**; nadie escribe ni lee. La tabla `station_results` **ya existe** en la migración
  baseline (`c7d8e9f00123_baseline_schema.py:409`) → **no requiere migración**. `compute_results`
  (`results.py:42-99`) agrega a nivel estudiante, sin `by_station`.
- **Alcance mínimo**: `persist_results` puebla `StationResult` (suma de `EvaluatorRecord` + `StudentResponse`
  por (estudiante, estación), `mode == ejecucion`). `read_results` / `/results` exponen un bloque `by_station`
  (nota del estudiante por estación) y un agregado por estación (media, DE, n). Frontend `/results`: tabla /
  vista por estación.
- **Esfuerzo**: M. Sin migración. Depende de OPT-1 (para saber si sirve snapshot o recálculo) — hacerlo
  **después** de OPT-1.
- **Decisión de producto**: ¿la nota por estación es informativa o entra en un estándar (ver OPT-17)?

## OPT-17 · Ponderación y estándar por estación — severidad alta

- **Evidencia**: `results.py:84-89` — `total_score = eval_score + form_score` (suma cruda). No hay campo de
  peso en `Station` (`grep weight|ponder` → nada). `compute_equivalent_grade` (`results.py:28-39`) aplica un
  solo `passing_reference_percent` al porcentaje agregado. Una estación de `max_score=20` pesa 3× una de
  `max_score=6`.
- **Alcance**: migración (peso por estación y/o umbral por estación en `stations`), normalización por estación
  en `compute_results`, y **elección de modelo de estándar**.
- **Esfuerzo**: L. **Requiere migración → gate humano.**
- **Decisiones metodológicas que debe fijar el usuario**:
  1. ¿Estándar **compensatorio** (media ponderada ≥ umbral, como hoy), **conjuntivo** (aprobar ≥ N de M
     estaciones), o **híbrido**?
  2. ¿Pesos configurables por estación, o todas las estaciones pesan igual (normalización a % por estación
     antes de promediar)?
  3. ¿La nota 1.0–7.0 se deriva del % global, o hay standard-setting (Angoff / borderline-regression)?
  4. ¿Umbral por estación además del global?

## OPT-18 · Analítica psicométrica (ejecución + pilotaje) — severidad alta, la más grande

- **Evidencia**: `grep -niE "weight|discrimin|cronbach|alpha|reliab|difficulty|borderline|standard.set"` sobre
  `app/` → 0 resultados. `compute_results:66-81` fija `mode == ejecucion`, así que los datos del **pilotaje**
  no entran a ningún cálculo consultable. `pilot_runs` solo cuenta corridas. `pilotaje_validado` es un click
  humano sin respaldo cuantitativo.
- **Alcance**: módulo de cálculo nuevo (media/DE por estación, histograma de notas, α de Cronbach
  inter-estación, índice de discriminación estación-total, punto-biserial por ítem/estación, índice de
  dificultad), endpoints de analítica, pantallas en `/results` y `/pilotage`, y correrlo también sobre
  `mode == pilotaje` para la validación de pilotaje.
- **Esfuerzo**: L–XL. Sin migración obligatoria (cálculo derivado), pero mucho backend + frontend + validación
  estadística.
- **Decisión del usuario**: ¿qué métricas son **requisito** para operar (bloquean/advierten en
  `pilotaje_validado`) y cuáles son **reportería deseable**? ¿Se necesita item analysis a nivel de criterio de
  pauta, o basta a nivel de estación?

## OPT-19 · Export enriquecido + renombrar "Export PDF" de Resultados — severidad media

- **Evidencia**: `results.py:355-361` — `export_results_excel` = 1 hoja `consolidado` con la fila plana por
  estudiante. `routes/operational.py:358-375` + `results.py:364-388` — el botón "Exportar PDF" de
  `results/page.tsx:82-88` llama `export_contingency_pdf`, que imprime **instrucciones de estación**, no
  resultados. Etiqueta engañosa. `export_results_excel` acepta `persist=True` pero el endpoint siempre pasa
  `persist=False` (argumento muerto en la ruta).
- **Sub-fix barato adelantable (≈XS)**: renombrar el botón de `/results` a "Exportar respaldo de contingencia
  (PDF)" o moverlo a la sección de contingencia; quitar el parámetro `persist` muerto de la ruta. Esto se
  puede meter en el lote de estabilización sin esperar a la Fase 2.
- **Export completo (M–L)**: hojas por estación, item analysis, metadatos del ECOE (curso, fecha, escuela,
  umbral), identidad de evaluador/corrector por registro, timestamps, `mode`, marca `by_contingency`. Depende
  de OPT-16 y OPT-18.

## H-dato-6 (fecha/actor de consolidación)

Ya está absorbido en **OPT-1** (AuditLog en consolidación + exponer `updated_at` como `consolidated_at`). No
se re-planifica aquí.

## Orden sugerido si el usuario prioriza esta fase

1. OPT-16 (ancla, sin migración) — después de OPT-1.
2. Sub-fix de etiqueta de OPT-19 (independiente, se puede adelantar).
3. Definición metodológica del usuario para OPT-17 y OPT-18.
4. OPT-18 (psicometría, empezando por pilotaje — es donde más valor aporta).
5. OPT-17 (ponderación/estándar — el de mayor riesgo, migración + método).
6. OPT-19 export completo.

## Estado de aprobación

- Documento de dimensionamiento propuesto por: optimizador — 2026-08-28
- El usuario debe decidir: (a) si esta fase se abre ahora o se difiere; (b) las 4 decisiones metodológicas de
  OPT-17 y las de OPT-18; (c) si el sub-fix de etiqueta de OPT-19 entra en el lote de estabilización.
- Aprobado por usuario: ⬜ pendiente
