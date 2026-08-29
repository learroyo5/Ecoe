# OPT-19 · Export Excel enriquecido (multi-hoja) + limpieza del `persist` muerto

**Severidad: media (capacidad ausente).** Origen: H-dato-4
(`docs/optimizacion/hallazgos/auditor-correccion-resultados__2026-08-28.md`
§Sección B). Fase 2 (`PLANES/FASE2_ANALISIS_DATOS__scoping.md` §OPT-19).
Depende de **OPT-16** (hoja `por_estacion`) y **OPT-18** (hoja `item_analysis`).
**Implementar último.**

## Problema

El export de Resultados es pobre para análisis externo (SPSS / R / acta de
examen):

- `export_results_excel` (`backend/app/services/results.py:562-573`) genera hoy
  **2 hojas**: `consolidado` (fila plana por estudiante) y `trazabilidad_envios`
  (indicador mínimo por respuesta, agregado en OPT-20 F4). Falta: desglose por
  estación, item analysis, metadatos del ECOE (curso, fecha, escuela, umbral,
  `passing_reference_percent`), identidad de evaluador/corrector por registro,
  timestamps, `mode`.
- `export_results_excel(db, ecoe_event_id, *, persist: bool = False)` acepta
  `persist=True` (que llama `persist_results` — una **escritura**), pero el
  endpoint `export_excel` (`operational.py:422-430`) siempre pasa `persist=False`.
  El parámetro está **muerto en la ruta** y su rama viva viola AGENTS.md
  ("Resultados sin mutación en endpoints GET"). Hay que quitarlo.

**Ya hecho, NO re-planificar**: el renombre del botón "Exportar PDF" → "Descargar
respaldo de contingencia (PDF)" + el texto aclaratorio en `/results` se aplicó en
el commit `e642abd` (lote de estabilización). Confirmado en
`frontend/src/app/(app)/results/page.tsx:95-109`.

## Causa raíz

`export_results_excel` nunca se amplió más allá de la fila plana de
`compute_results`. El `persist` es un resto de una idea vieja de "exportar y
consolidar en un paso" que quedó sin uso cuando la consolidación se movió al
cierre / a `POST /results/{id}/consolidate`.

## Decisión del usuario (2026-08-29) — ya tomada, no re-preguntar

Export Excel multi-hoja:
`consolidado` (actual) + `por_estacion` (OPT-16) + `item_analysis` (OPT-18) +
`trazabilidad_envios` (ya existe, OPT-20 F4) + `metadatos` del ECOE (curso,
fecha, escuela, umbral, `passing_reference_percent`).

Por registro en la hoja de trazabilidad: identidad de evaluador/corrector,
timestamps, `mode`, `submission_kind`, `by_contingency`.

El sub-fix de etiqueta ya está hecho (`e642abd`) — el `persist` muerto de la
ruta, si sigue, sí se limpia. Sin migración. Se implementa después de OPT-16 y
OPT-18.

## Cambio propuesto

### Backend — `app/services/results.py`

**1. `export_results_excel(db, ecoe_event_id) -> bytes`** — quitar el parámetro
`persist`. Siempre lee vía `read_results` / `read_station_results` (snapshot-aware,
OPT-1 / OPT-16). Escribe estas hojas con `pd.ExcelWriter(engine="openpyxl")`:

| Hoja | Fuente | Contenido |
|---|---|---|
| `metadatos` | `db.get(ECOEEvent, id)` + `read_results` | ECOE: nombre, curso, escuela, docente responsable, correo de contacto, fecha, `circuit_mode`, `station_time_minutes`, `transition_time_minutes`, `passing_reference_percent`, nº estudiantes activos, nº estaciones, `frozen` (sí/no), `consolidated_at`. Formato clave–valor (2 columnas). |
| `consolidado` | `read_results` | Igual que hoy (N ECOE, estudiante, puntaje, máximo, %, nota equivalente). Añadir `stations_counted` si OPT-17 lo expone. |
| `por_estacion` | `read_station_results` + `build_station_score_block` (OPT-16) | Formato largo: N ECOE · estudiante · estación (nº y nombre) · circuito · puntaje · máximo · %. Más un bloque agregado por estación (n, media %, DE %) — hoja aparte `por_estacion_resumen` o sección en la misma. |
| `item_analysis` | `build_psychometrics_block(mode="ejecucion")` (OPT-18) | Por criterio de pauta: estación · criterio · n · dificultad · punto-biserial · máximo. Más filas de nivel estación: α-contribución / discriminación estación-total. |
| `trazabilidad_envios` | `_submission_trace_rows` **ampliada** | Por respuesta/registro de la ejecución real (ver punto 2). |

- **Frozen**: para eventos `cerrado`/`archivado`, `consolidado` y `por_estacion`
  salen del snapshot (`read_results` / `read_station_results` ya lo hacen).
  `item_analysis` y el resumen por estación se derivan del conjunto servido →
  inmutables si el conjunto lo es. `metadatos.frozen = "sí"`.
- **Robustez**: si OPT-18 no está mergeado aún al implementar OPT-19, la hoja
  `item_analysis` se genera vacía con encabezados y una nota
  ("Requiere el módulo de psicometría"). Idealmente OPT-19 va después de OPT-18 y
  la hoja es real.

**2. Ampliar `_submission_trace_rows` (`results.py:518-559`)** — hoy sólo cubre
`StudentResponse`. Ampliarla (o añadir `_evaluator_trace_rows`) para incluir
**ambos** orígenes de puntaje, una fila por registro:

Columnas: `n_ecoe`, `estudiante`, `estacion_numero`, `estacion_nombre`,
`circuito`, `tipo_registro` (`evaluador` | `formulario`), `mode`,
`submission_kind`, `by_contingency`, `en_blanco`, `score_obtained`, `max_score`,
`porcentaje`, `evaluador` (`EvaluatorRecord.evaluator_name`), `corrector`
(`StudentResponse.graded_by_email`), `enviado_at`
(`submitted_at` / `EvaluatorRecord.created_at`), `corregido_at`
(`StudentResponse.graded_at`), `actualizado_at` (`updated_at`).

- Filtro `mode == ejecucion` (como hoy). Considerar exponer también `pilotaje` en
  una hoja aparte `trazabilidad_pilotaje` — **decisión de implementación**
  (recomendado: sí, es barato y cierra H-dato-2/H-dato-5 desde el export).
- `is_draft == True` (evaluador): incluir con `submission_kind` marcado como
  borrador, o excluir. Recomendado: incluir con una columna `borrador` = sí/no,
  para que el analista vea qué quedó sin finalizar.

### Backend — `app/api/routes/operational.py`

**3. `export_excel`** (`:422-430`) — quitar el argumento `persist=False`:

```python
content = export_results_excel(db, ecoe_event_id)
```

Sin cambio de firma del endpoint, sin cambio de permiso
(`ensure_event_access(*ADMIN_EVENT_ROLE_CODES)`).

### Frontend

**`frontend/src/app/(app)/results/page.tsx`** — sólo copy: actualizar el texto
bajo los botones de export (`:104-109`) para listar las hojas nuevas del Excel
(consolidado, por estación, item analysis, trazabilidad, metadatos). Sin lógica,
sin pantalla nueva. El `<a href=".../export/excel">` ya existe.

### Migración

**No.** Todo derivado.

### Máquina de estados

No se toca.

## Tests (incluye negativos — export de datos de resultados)

Archivo nuevo: `backend/tests/test_export_excel_opt19.py` (abre el xlsx con
`openpyxl` / `pd.read_excel(sheet_name=None)`).

Positivos:
- `test_export_has_all_sheets` — nombres de hoja == {`metadatos`, `consolidado`,
  `por_estacion`, `item_analysis`, `trazabilidad_envios`} (+ opcionales).
- `test_export_metadatos_sheet` — curso, escuela, fecha, `passing_reference_percent`,
  nº estudiantes, `frozen`, `consolidated_at` presentes y correctos.
- `test_export_por_estacion_matches_read_station_results` — los valores de la
  hoja coinciden fila a fila con `read_station_results` / `build_station_score_block`.
- `test_export_trazabilidad_has_identity_columns` — por registro:
  `evaluador` (nombre), `corrector` (email), `enviado_at`, `corregido_at`,
  `mode`, `submission_kind`, `by_contingency`.
- `test_export_item_analysis_sheet` — estación con pauta de 3 criterios →
  3 filas con dificultad y punto-biserial (depende de OPT-18).

Negativos / integridad:
- `test_export_excel_does_not_mutate` — **clave**: llamar el endpoint 2 veces;
  `db.query(ECOEResult).count()` sin cambios; ningún `AuditLog(action=
  "consolidate_results")` nuevo. Prueba que el `persist` muerto se eliminó.
- `test_export_excel_requires_event_access` — `corrector` / `evaluador` /
  `estudiante` / usuario de otro evento → **403**.
- `test_export_frozen_event_uses_snapshot` — evento `cerrado`; mutar a mano un
  `StudentResponse.score_obtained` → la hoja `consolidado` y `por_estacion`
  siguen mostrando el snapshot, no el recálculo (espejo de
  `test_results_immutability.py:232`).
- `test_export_empty_event_no_crash` — evento sin estudiantes ni estaciones →
  xlsx válido con hojas vacías (encabezados), HTTP 200, sin excepción.
- `test_export_stations_without_tool_graceful` — estaciones sin `assessment_tool`
  ni formulario puntuable → `item_analysis` vacío/parcial, sin error.
- `test_export_pilotaje_not_in_execution_sheets` — registros `mode='pilotaje'`
  no aparecen en `consolidado` / `por_estacion` / `trazabilidad_envios`
  (sí en `trazabilidad_pilotaje` si se implementa).

Frontend: `results/page.tsx` test — el texto actualizado menciona las hojas
nuevas (test trivial, sólo si se quiere fijar el copy).

## Riesgos / alcance

- **Superficie**: una función reescrita (`export_results_excel`), una ampliada
  (`_submission_trace_rows`), un argumento eliminado en un endpoint, copy de UI.
  Sin migración, sin permisos nuevos, sin máquina de estados, sin contrato de
  request.
- **Dependencia de OPT-16 y OPT-18**: si alguno no está mergeado, la hoja
  correspondiente sale con encabezados y nota. Implementar **después** de ambos
  para que las 5 hojas sean reales.
- **Quitar `persist`**: revisar que ningún test ni llamador pase `persist=True`
  (`grep -rn "export_results_excel" backend/`). Hoy sólo lo llama el endpoint
  (con `persist=False`) — cambio seguro. El test negativo lo blinda.
- **Tamaño del archivo**: a escala del proyecto (cientos de filas) el xlsx sigue
  siendo pequeño; `openpyxl` maneja bien 5 hojas.
- **`graded_by_email == "auto"`** para autocorrección: mostrarlo tal cual en la
  columna `corrector` (es informativo: "corregido automáticamente").

## Verificación

- [x] `cd backend && python3 -m pytest` (SQLite) — **359 passed** (13 nuevos en
      `tests/test_export_opt19.py`; el archivo del plan se llamó
      `test_export_opt19.py`, no `test_export_excel_opt19.py`).
- [x] `TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q`
      — **359 passed**.
- [x] `DATABASE_URL=sqlite:////tmp/ecoe_opt19_check.db SECRET_KEY=test-secret ENVIRONMENT=test AUTO_SEED_DEMO=false alembic upgrade head`
      llega a head (`n4o5p6q7r8s9`) **sin revisión nueva** — OPT-19 es sin migración.
- [x] `cd frontend && npm run lint` (0 errores, 2 warnings preexistentes)
      `&& npm run build` (OK) `&& npx vitest run` — **61 passed**.
- [ ] Descarga manual del Excel de un evento demo cerrado — no corrida
      (restricción de sandbox de red en la sesión de implementación).
- [ ] `./scripts/run_e2e.sh --grep "results"` sobre el stack de ramas — pendiente
      global de Fase 2.

## Notas de implementación (2026-08-29)

- Rama `opt/OPT-19-export` desde `opt/OPT-18-psicometria` (`4c27779`). **Último de
  Fase 2**: con esto OPT-16..19 quedan `en-verificación` (falta e2e + merge).
- **`persist` eliminado** de `export_results_excel(db, ecoe_event_id) -> bytes`.
  `grep` confirmó que el único llamador real es el endpoint `export_excel`
  (`operational.py`), que pasaba `persist=False`; el re-export de
  `app/services/ecoe.py` no lo invoca. La rama `if persist: persist_results(...)`
  (una escritura en un GET) desapareció. Test negativo
  `test_export_excel_does_not_mutate` + `test_export_excel_signature_has_no_persist_param`.
- **Hojas del Excel, en orden**: `metadatos` · `consolidado` · `por_estacion` ·
  `item_analysis` · `trazabilidad_envios`. La hoja de OPT-16 se **renombró** de
  `resultados_por_estacion` a `por_estacion`.
- **`frozen`**: `consolidado` sale de `read_results` y `por_estacion` de
  `read_station_results` (ambos snapshot-aware): evento `cerrado`/`archivado` con
  snapshot → acta congelada. `item_analysis` y la trazabilidad se calculan
  **siempre en vivo** (derivados, no parte del acta).
- **`metadatos`** (clave–valor, 2 columnas `campo`/`valor`): nombre, curso,
  escuela/institución (`school_name`), docente responsable, correo de contacto,
  fecha, estado, modo de circuito, minutos por estación/transición,
  `passing_reference_percent`, nº de estudiantes activos, nº de estaciones,
  `frozen` (Sí/No), `consolidated_at`. No hay un campo "umbral" separado en el
  modelo → se omite (el `passing_reference_percent` es el único umbral).
- **`item_analysis`**: reusa `build_psychometrics_block(mode="ejecucion")` de
  OPT-18. Una fila por criterio: `estacion_numero`, `estacion`, `criterio`, `n`,
  `dificultad`, `punto_biserial`, `maximo`, `fuera_de_umbral` (Sí/No, contra las
  advertencias del bloque). Estaciones sin pauta estructurada ni formulario
  puntuable → sin filas (hoja con solo encabezados). Item analysis de pilotaje
  **no** entra al export (queda en pantalla vía OPT-18).
- **`trazabilidad_envios`** ampliada (`_submission_trace_rows`): una fila por
  cada `StudentResponse` (`tipo_registro="formulario"`) **y** cada
  `EvaluatorRecord` (`tipo_registro="evaluador"`) de `mode==ejecucion`. Columnas:
  `n_ecoe`, `estudiante`, `estacion_numero`, `estacion`, `circuito`,
  `tipo_registro`, `mode`, `submission_kind`, `origen` (etiqueta), `borrador`
  (Sí/No — los borradores de evaluador `is_draft=True` **se incluyen**),
  `en_blanco`, `by_contingency`, `score_obtained`, `max_score`, `porcentaje`,
  `evaluador` (`EvaluatorRecord.evaluator_name`), `corrector`
  (`StudentResponse.graded_by_email`; `"auto"` para autocorrección),
  `enviado_at` (`submitted_at` / `created_at`), `corregido_at` (`graded_at`),
  `actualizado_at` (`updated_at`). No hay campo de email en `EvaluatorRecord` →
  la identidad del evaluador es el nombre.
- **Decisiones de implementación abiertas del plan**: (1) hoja
  `trazabilidad_pilotaje` aparte → **no** se agregó (fuera del alcance explícito
  de la tarea, que fija exactamente 5 hojas); los `mode='pilotaje'` simplemente
  no aparecen. (2) borradores de evaluador → **incluidos** con columna
  `borrador`. (3) resumen agregado por estación → **no** como hoja aparte (el
  agregado ya vive en `/results` y en el endpoint de psicometría). (4)
  item analysis de pilotaje → **solo ejecución**. (5) `persist` eliminable →
  confirmado.
- **Tests existentes ajustados** (adaptación al Excel multi-hoja, sin debilitar
  la aserción): `test_results_immutability.py::test_export_excel_uses_snapshot_after_close`
  y `test_opt20_f4_submission_kind.py::test_export_excel_includes_submission_kind_column`
  ahora leen la hoja `consolidado` por nombre en vez de la primera hoja.

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-29
- **Decisiones metodológicas: Aprobado por usuario: ✅ 2026-08-29** (Excel
  multi-hoja: consolidado + por_estacion + item_analysis + trazabilidad_envios +
  metadatos; identidad/timestamps/mode/submission_kind/by_contingency por
  registro; limpiar el `persist` muerto; sin migración; implementar último).
- **Plan técnico y decisiones de implementación: ✅ 2026-08-29 — aprobado; decisiones de implementación = las recomendadas.**
- Implementado por: implementador — 2026-08-29 → `en-verificación` (rama
  `opt/OPT-19-export` desde `opt/OPT-18-psicometria`). **Cierra Fase 2 (OPT-16..19),
  toda `en-verificación`; falta e2e sobre el stack de ramas y merge.**
- Decisiones de implementación abiertas:
  1. ¿Hoja `trazabilidad_pilotaje` aparte para `mode='pilotaje'` (recomendado)?
  2. ¿Registros de evaluador en borrador (`is_draft=True`) en la trazabilidad,
     con columna `borrador` (recomendado), o excluidos?
  3. ¿Resumen agregado por estación como hoja `por_estacion_resumen` aparte o
     como bloque dentro de `por_estacion`?
  4. ¿`item_analysis` incluye también el `mode='pilotaje'` en otra hoja, o sólo
     ejecución (el pilotaje se ve en pantalla vía OPT-18)?
  5. Confirmar que se puede eliminar `persist` sin romper llamadores externos
     (grep dice que sólo lo usa el endpoint).
