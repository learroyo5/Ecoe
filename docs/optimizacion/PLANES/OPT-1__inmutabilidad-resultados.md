# OPT-1 · Inmutabilidad de resultados tras el cierre

**Severidad: bloqueante.** Origen: H-corr-1, H-corr-2, H-corr-3, H-dato-6.

## Problema

Después de pasar un ECOE a `cerrado`, los resultados que devuelve la app siguen siendo mutables:

1. **H-corr-1** — `GET /results/{id}` y `GET /results/{id}/export/excel` recalculan en vivo con
   `compute_results()`. `ECOEResult` (el snapshot que escribe el cierre) **nunca se lee**. Cualquier cambio
   posterior en `StudentResponse`/`EvaluatorRecord` altera el número mostrado como oficial.
2. **H-corr-2** — `POST /api/grading/responses/{id}` no tiene gate de estado: corregir una respuesta sobre un
   evento `cerrado` (o `archivado`, o `borrador`) responde 200.
3. **H-corr-3** — `apply_manual_scores` permite re-corregir una pregunta ya resuelta reenviando `scores`,
   sobrescribiendo `score_obtained`/`graded_by_email`/`graded_at` sin aviso ni historial visible.
4. **H-dato-6** — la consolidación (`POST /results/{id}/consolidate` y la rama de cierre) no escribe `AuditLog`
   y `ECOEResult` no expone quién/cuándo consolidó.

Test scratch del auditor (verificado): evento `cerrado` con `ECOEResult=(0,0)` → `POST grading` 200 →
`GET /results` pasa a `(6,6)`; `ECOEResult` sigue en `(0,0)` (stale).

## Causa raíz

- `app/api/routes/operational.py:325-333` (`get_results`) y `:347-355` (`export_excel`) llaman
  `compute_results()` / `export_results_excel(persist=False)` incondicionalmente.
- `grep -rn "ECOEResult"` → solo escritura en `app/services/results.py:104-113`.
- `app/api/routes/grading.py:107-144` (`grade_response`) no llama `ensure_submission_stage` ni mira
  `response.ecoe_event.status`.
- `app/services/grading.py:100-126` — `pending` = todas las claves `kind=="manual"`; `missing` solo las que
  siguen en `None`. Una respuesta totalmente resuelta admite `scores` nuevos.
- `app/api/routes/operational.py:336-344` (`consolidate_results`) — sin `AuditLog`.
- `app/services/validation.py:453-468` — la rama de cierre corre `persist_results(commit=False)` pero no
  registra actor.

## Cambio propuesto

- **Backend**
  - `app/services/results.py`: nueva función `read_results(db, ecoe_event_id)` que, si
    `ecoe_event.status in {cerrado, archivado}` **y** existe `ECOEResult` para el evento, devuelve el snapshot
    (`ECOEResult` → misma forma que `compute_results`, más `consolidated_at = updated_at`); en cualquier otro
    estado, recalcula en vivo con `compute_results`. Marcar en el payload `"frozen": true|false`.
  - `app/api/routes/operational.py`: `get_results` y `export_excel` usan `read_results` en lugar de
    `compute_results` directo. `build_traceability_report` recibe los resultados ya resueltos (ya acepta
    `consolidated_results=`).
  - `app/api/routes/grading.py::grade_response`: rechazar con **409** si
    `response.ecoe_event.status in {cerrado, archivado}` (mensaje: "El ECOE está cerrado; los resultados están
    consolidados"). Decisión de producto abierta (ver abajo): si se opta por permitir corrección tardía,
    entonces re-disparar `persist_results` dentro de la misma transacción — **no** es la opción recomendada.
  - `app/services/grading.py::apply_manual_scores`: `pending` = solo claves `kind=="manual"` con
    `earned is None`. Si `scores` trae una clave ya resuelta → **409** "La pregunta {k} ya tiene puntaje;
    usa el flujo de rectificación" (o 400 si se prefiere). Deja intacto el caso legítimo "resolver las que
    faltan".
  - `app/api/routes/operational.py::consolidate_results` y `app/services/validation.py` rama de cierre:
    escribir `AuditLog(action="consolidate_results", target_type="ECOEEvent", target_id=str(id),
    payload={"student_count": len(results)})` con el actor.
  - (Opcional, menor) exponer `ECOEResult.updated_at` como `consolidated_at` en el payload de `/results`.
- **Frontend**
  - `frontend/src/app/(app)/results/page.tsx`: si `frozen`, mostrar un chip "Resultados consolidados el
    {fecha}" y ocultar/deshabilitar cualquier acción de re-cálculo.
  - `frontend/src/app/(app)/grading/page.tsx`: si el ECOE está `cerrado`/`archivado`, ocultar el formulario de
    corrección y mostrar aviso "ECOE cerrado".
- **Migración**: **no**. `ecoe_results` ya existe (`c7d8e9f00123_baseline_schema.py:337`); `updated_at` viene
  de `TimestampMixin`.
- **Máquina de estados**: no se toca `ALLOWED_STATUS_TRANSITIONS`.

## Tests (incluye negativos — toca datos y permisos)

- `test_get_results_reads_snapshot_after_close` — evento `cerrado`, se muta una `StudentResponse` a mano;
  `GET /results` sigue devolviendo el valor consolidado, no el recalculado.
- `test_get_results_recalculates_before_close` — evento `en_ejecucion`, `GET /results` refleja cambios en vivo.
- `test_grade_response_rejected_after_close` (negativo) — `POST /api/grading/responses/{id}` sobre evento
  `cerrado` → 409. Ídem `archivado`.
- `test_grade_response_allowed_in_execution` — sigue funcionando en `en_ejecucion` / `en_pilotaje`.
- `test_apply_manual_scores_rejects_regrade_of_resolved_question` (negativo) — segunda llamada con una clave ya
  puntuada → 409/400; `score_obtained` original intacto.
- `test_apply_manual_scores_still_resolves_remaining` — resolver las pendientes cuando algunas ya están hechas
  sigue OK.
- `test_consolidate_writes_audit_log` — `POST /results/{id}/consolidate` y el cierre dejan un `AuditLog` con
  actor.
- `test_export_excel_uses_snapshot_after_close` — el Excel exportado tras el cierre coincide con `ECOEResult`.
- Frontend: test de que `/grading` oculta el formulario si `status === "cerrado"`.

## Riesgos / alcance

- El cambio de lectura (`read_results`) es el de mayor superficie: hay que asegurar que
  `build_traceability_report` reciba los mismos resultados que sirve el endpoint (ya soporta
  `consolidated_results=`, usarlo).
- Riesgo de que exista un evento `cerrado` **sin** `ECOEResult` (cierre anterior a que `persist_results`
  poblara la tabla, o cierre fallido): `read_results` debe caer a `compute_results` en ese caso y el frontend
  no debe romperse por `consolidated_at` nulo.
- El commit se mantiene acotado: un servicio nuevo + 3 endpoints tocados + 1 guard en un servicio. Sin
  migración, sin cambio de contrato de request.

## Verificación

- [x] `cd backend && python3 -m pytest` — 200 passed (incluye `tests/test_results_immutability.py`, 14 casos).
- [x] Migración desde base limpia: `DATABASE_URL=sqlite:////tmp/ecoe_alembic_check.db ... alembic upgrade head`
      llega a `k1f2a3b4c5d6` sin migración nueva (OPT-1 es sin migración).
- [ ] `TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q`
      (no toca constraints, pero se cambió lógica de resultados) — pendiente: sin Postgres en el entorno de implementación.
- [ ] `cd frontend && npm run lint && npm run build` — no aplica: OPT-1 se implementó **solo backend**
      (A/B/C/D). Los ajustes de UI del plan (chip "Resultados consolidados" en `/results`, aviso "ECOE cerrado"
      en `/grading`, test frontend) quedan como seguimiento; el backend ya es autoridad (409 + `frozen` en el payload).

## Decisión de producto pendiente (bloquea el detalle del plan)

**¿La corrección tardía después del cierre queda prohibida o permitida?**
- **Prohibida (recomendado)**: 409 en `grade_response`. Coincide con `EVALUACION_DIFERIDA_FASE1.md` §Alcance
  ("No incluye… Corrección después de `cerrado`") y con CLAUDE.md ("cerrar… congelando la operación"). Si hay
  que rectificar una nota, se reabre el evento por transición de estado (retroceso ya permitido en el grafo) o
  se hace por un procedimiento administrativo con `AuditLog`.
- **Permitida como caso operativo**: `grade_response` re-dispara `persist_results` para no dejar el consolidado
  stale. Rompe la promesa de inmutabilidad; solo si el usuario lo pide explícitamente.

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-28
- Aprobado por usuario: ✅ 2026-08-28 (parte del lote de estabilización Grupo A)
- **Decisión de producto**: corrección tardía tras `cerrado` queda **PROHIBIDA** — `grade_response` y `apply_manual_scores` devuelven 409 si `ecoe_event.status` es `cerrado`/`archivado`. `/results` y el export sirven el snapshot de `ECOEResult`; no recalculan en vivo cuando el evento está cerrado. Para corregir hay que reabrir explícitamente (retroceso de estado permitido por el grafo).
