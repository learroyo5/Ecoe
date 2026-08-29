# OPT-7b · CRUD de `StationTemplate` y `SimulatedPatient`

**Severidad: baja.** Origen: H-admin-ecoe-4 §6 (mini-auditoría
`docs/optimizacion/hallazgos/auditor-admin-ecoe__OPT-7__2026-08-29.md`).
Follow-up directo de **OPT-7** (ya en `main` @ `b297df5`): reusa su
infraestructura (`created_by` / `origin_event_id` / `archived`, regla de
propiedad, comando de purga).

## Problema

Los otros dos bancos institucionales son de **solo creación**, igual que lo era
`AssessmentTool` antes de OPT-7:

- `backend/app/api/routes/stations.py:76-95` — `/templates` sólo `GET` + `POST`.
- `backend/app/api/routes/stations.py:293-312` — `/simulated-patients` sólo
  `GET` + `POST`.
- Contraste ya resuelto: `/instruments` tiene `GET/{id}` + `PATCH` + `DELETE`
  (soft) + `/restore` + `/purge` (`stations.py:116-288`).
- `frontend/src/lib/api.ts:294-299` — sólo `templates`, `createTemplate`,
  `simulatedPatients`, `createSimulatedPatient`. Sin `update*` / `archive*`.
- `frontend/src/app/(app)/templates/page.tsx` y `.../simulated-patient/page.tsx`
  son formulario de alta + `DataTable` de sólo lectura; no hay editar ni archivar.

Consecuencia: no se corrige una plantilla ni una ficha de paciente con un error,
y el banco se llena de registros muertos visibles en el `<select>` del
Constructor de **todos** los eventos (los `GET` no filtran por evento:
`select(StationTemplate)` / `select(SimulatedPatient)` sin `where`,
`stations.py:79,296`).

**Menos riesgo que OPT-7** (verificado en el hallazgo §6):

| | `AssessmentTool` (OPT-7) | `StationTemplate` | `SimulatedPatient` |
|---|---|---|---|
| Contenido leído en runtime | sí (`serialize_assessment_tool` en vivo) | **no** — `default_configuration` sólo se copia campo a campo al aplicar la plantilla en el Constructor (`stations/builder/page.tsx` `applyStationLikeData`) | **no** — no interviene en el cálculo de notas |
| Claves keyed por `id` en datos históricos | sí (`EvaluatorRecord.answers` por `AssessmentItem.id`) | **no** | **no** |
| Genera huérfanas de alto volumen | sí (el Constructor crea pautas) | bajo (sólo se crea desde `/templates`) | bajo (sólo desde `/simulated-patient`) |

→ No hace falta el gate `EDIT_BLOCKING_STATUSES` de OPT-7. Editar en sitio es
seguro incluso con el ECOE en ejecución (el cambio no llega a runtime). Basta
**UPDATE libre + soft-delete**.

## Causa raíz

- `backend/app/api/routes/stations.py:76-95, 293-312` — routers sin
  `PATCH`/`DELETE`/`GET-by-id`.
- `backend/app/models/entities.py:205-212` (`StationTemplate`) y `:262-271`
  (`SimulatedPatient`) — sin `created_by`, `origin_event_id`, `archived`.
- FKs de referencia **sin `ondelete`** (baseline
  `c7d8e9f00123_baseline_schema.py:149-150, 280-281`, anónimas):
  - `stations.template_id` → `station_templates.id`
    (`entities.py:299`)
  - `stations.simulated_patient_id` → `simulated_patients.id`
    (`entities.py:303`)
  - `station_bank.template_id` → `station_templates.id`
    (`entities.py:341`)
  - `station_bank.simulated_patient_id` → `simulated_patients.id`
    (`entities.py:345`)
  En Postgres (CI/prod) un hard-delete de un registro referenciado lanza
  `IntegrityError`; hoy no importa porque no hay DELETE.

## Alcance de esta pasada

CRUD completo de **`StationTemplate`** y **`SimulatedPatient`**, replicando el
patrón OPT-7 pero **sin gate de editabilidad** (decisión a confirmar — ver
§Decisiones). Sin versionado, sin copy-on-write.

## Cambio propuesto

### Migración (requiere aprobación explícita del usuario — ver §Decisiones)

Revisión Alembic nueva, `down_revision = n4o5p6q7r8s9` (head actual:
`n4o5p6q7r8s9_instrument_crud.py`). Mismo patrón que
`n4o5p6q7r8s9` (dialect-split: `batch_alter_table` en SQLite, recreación de FK
por nombre en Postgres; `server_default=sa.false()` que se conserva).

`station_templates` y `simulated_patients` (idénticas columnas nuevas en ambas):
- `created_by` — `String(255)`, `nullable=True`.
- `origin_event_id` — `Integer`, `ForeignKey("ecoe_events.id", ondelete="SET NULL")`,
  `nullable=True`.
- `archived` — `Boolean`, `nullable=False`, `server_default=sa.false()`.
- Índice `ix_station_templates_archived` / `ix_simulated_patients_archived`.

FKs de referencia (Postgres — nombres autogenerados del baseline, verificar en
`information_schema` como se hizo en `n4o5p6q7r8s9`):
- `stations_template_id_fkey` → `ondelete="SET NULL"`
- `station_bank_template_id_fkey` → `ondelete="SET NULL"`
- `stations_simulated_patient_id_fkey` → `ondelete="SET NULL"`
- `station_bank_simulated_patient_id_fkey` → `ondelete="SET NULL"`

`entities.py`: agregar los 3 campos a ambos modelos y `ondelete="SET NULL"` a las
4 FK.

> Verificar `alembic upgrade head` + `downgrade -1` + `upgrade head` desde base
> limpia en **SQLite y Postgres** (AGENTS.md; toca FKs → Postgres es obligatorio).

### Backend

**`backend/app/services/content_bank.py`** (nuevo módulo, o generalizar el
existente `services/instruments.py`): reglas compartidas para los tres bancos.

- `template_reference_summary(db, template_id)` / `patient_reference_summary(...)`
  — `SELECT` sobre `stations` **UNION** `station_bank` por la FK
  correspondiente; devuelve `{station_ids, bank_ids, event_ids, reference_count}`.
  (Análogo a `instruments.tool_reference_summary`, sin `event_statuses` porque no
  hay gate de estado.)
- `ensure_content_manage_permission(db, user, record, summary)` — **reusar la
  regla de propiedad de OPT-7** (`instruments.ensure_tool_manage_permission`,
  `services/instruments.py:134-183`): `admin_global` bypass; rol
  `admin_ecoe`/`coeditor_docente` en `origin_event_id`; regla de gracia para
  legados (`origin_event_id IS NULL`) sobre los eventos que hoy referencian el
  registro; si legado y 0 referencias → sólo `admin_global`.
  Refactor sugerido: extraer esa función a `content_bank.py` con `record` genérico
  (sólo necesita `.origin_event_id`) y que `instruments.py` la reexporte.
- **NO** `ensure_*_editable` con `EDIT_BLOCKING_STATUSES` (decisión #1).

**`backend/app/api/routes/stations.py`** — endpoints nuevos en los routers
existentes (`/templates`, `/simulated-patients`), gate idéntico al POST actual:

| Método | Ruta | Gate | Efecto |
|---|---|---|---|
| `GET` | `/api/templates/{id}` · `/api/simulated-patients/{id}` | `CONTENT_MANAGER_ROLES` + `ensure_event_access(*ADMIN_EVENT_ROLE_CODES)` | registro serializado o 404 |
| `PATCH` | `/api/templates/{id}` · `/api/simulated-patients/{id}` | `require_roles("admin_ecoe","coeditor_docente")` + `ensure_event_access(admin_ecoe, coeditor_docente)` + `ensure_content_manage_permission` | UPDATE **libre** de todos los campos (`setattr` por campo presente); `AuditLog` |
| `DELETE` | idem | idem | **soft**: `archived = True`. Idempotente. `AuditLog` |
| `POST` | `/api/templates/{id}/restore` · `.../simulated-patients/{id}/restore` | idem | `archived = False` |
| `DELETE` | `/api/templates/{id}/purge` · `.../simulated-patients/{id}/purge` | `require_roles("admin_ecoe")` (sin coeditor) o `admin_global` | **hard-delete**, sólo si `reference_summary.reference_count == 0` en `stations` **y** `station_bank`; si no → 409 |

- `GET /api/templates` y `GET /api/simulated-patients` ganan
  `include_archived: bool = False`; por defecto filtran `archived.is_(False)`.
- `POST` de ambos estampa `created_by = user.email` y
  `origin_event_id = ecoe_event_id` (el query param que ya se usa para el gate).
- `create_station` / `create_station_bank` / `update_station_bank`: extender
  `_reject_archived_tool` (`stations.py:62-72`) a un
  `_reject_archived_reference` que también rechace `template_id` /
  `simulated_patient_id` archivados al asignarlos a estaciones nuevas. Una
  estación que ya los usa sigue funcionando.
- `ecoe.py::duplicate_ecoe` (`ecoe.py:322-329`) ya comparte `template_id` /
  `simulated_patient_id` sin clonar — se mantiene; documentar en el docstring
  (igual que se hizo para `assessment_tool_id` en `ecoe.py:285-291`).

**`backend/app/schemas/common.py:212-233`**:
- `StationTemplateRead` / `SimulatedPatientRead` ganan
  `created_by: str | None`, `origin_event_id: int | None`, `archived: bool`,
  `reference_count: int` (calculado).
- `StationTemplatePatch` / `SimulatedPatientPatch` = todos los campos opcionales.

**`backend/scripts/purge_orphan_instruments.py`** — generalizar a
`purge_orphan_content.py` (o agregar `--kind templates|patients|instruments`)
reusando el criterio (0 referencias + `archived` opcional +
`--min-age-days` default 90). Sin el barrido de `EvaluatorRecord.answers` (no
aplica a estos dos modelos). Dry-run por defecto; el usuario decide si lo corre.

### Frontend

**`frontend/src/lib/api.ts`** (junto a `templates` / `simulatedPatients`):
- `template(eventId, id)` / `updateTemplate` / `archiveTemplate` /
  `restoreTemplate` / `purgeTemplate` + `templates(eventId, {includeArchived})`.
- Idem `simulatedPatient(...)` etc.

**`frontend/src/lib/types.ts`** — `StationTemplate` y `SimulatedPatient` (si
existen como tipos; hoy las páginas usan `Record<string, unknown>[]`) ganan
`created_by`, `origin_event_id`, `archived`, `reference_count`. Tipar de paso.

**`frontend/src/app/(app)/templates/page.tsx`** y
**`.../simulated-patient/page.tsx`** — pasar a CRUD real, mismo layout que
`instruments/page.tsx` (OPT-7):
- editar in-place (el `DataTable` gana columna de acciones: Editar / Archivar /
  Restaurar).
- toggle "Ver archivadas" (`?include_archived`).
- "Purgar" sólo visible para `admin_ecoe`/`admin_global` y sólo con
  `reference_count === 0`, con `ConfirmDialog` (patrón `instruments/page.tsx:48,
  354-363`).
- badge "En uso por N estación(es)" y "Archivada".
- respetar `canEditContent` como ya hace `templates/page.tsx:78-79`.

## Tests (incluye negativos — toca datos, permisos y migración)

`backend/tests/test_opt7b_content_bank_crud.py` (nuevo):

**Negativos obligatorios:**
- `test_archive_template_without_origin_permission_returns_403` — coeditor del
  evento B archiva una plantilla con `origin_event_id` = evento A (sin rol allí) → 403.
- `test_patch_patient_without_origin_permission_returns_403` — idem con
  `SimulatedPatient`.
- `test_purge_referenced_template_returns_409` — plantilla con ≥1 referencia en
  `stations` **o** `station_bank` → `DELETE …/purge` 409; sigue viva.
- `test_purge_requires_admin_ecoe_not_coeditor` — coeditor → 403 en `/purge`.
- `test_legacy_grace_rule` — registro `origin_event_id IS NULL` con 1 referencia:
  coeditor de ese evento archiva (200); coeditor de un evento sin relación → 403;
  legado con 0 referencias → sólo `admin_global`.
- `test_archived_template_not_selectable_for_new_station` — `create_station`
  rechaza `template_id` archivado; una estación que ya lo usa sigue operativa.
- `test_list_hides_archived_by_default` / `…_shows_with_include_archived` (ambos
  modelos).

**Positivos:**
- `test_patch_template_updates_all_fields_freely` — sin gate de estado: plantilla
  usada por una estación de un ECOE `en_ejecucion` → PATCH 200 (contraste
  deliberado con OPT-7, que devolvería 409).
- `test_soft_delete_then_restore` (ambos modelos).
- `test_create_stamps_created_by_and_origin_event`.
- `test_purge_orphan_command_dry_run_then_apply`.

**Migración:**
- `alembic upgrade head` + `downgrade -1` + `upgrade head` desde base limpia en
  SQLite **y** Postgres. Verificar `delete_rule = SET NULL` en las 4 FK; borrar un
  registro huérfano no rompe.

Frontend: `npm run lint && npm run build`; vitest de `templates` y
`simulated-patient` (archivar oculta de la lista; "Purgar" no aparece con
`reference_count > 0`; editar persiste).

## Riesgos / alcance

- **Sin gate de editabilidad** (a diferencia de OPT-7): si el usuario edita una
  plantilla mientras un ECOE está en ejecución, el cambio **no** afecta a las
  estaciones ya creadas (el Constructor copió `default_configuration` al aplicar
  la plantilla, no la lee en vivo). Confirmado en el hallazgo §6. Riesgo real:
  nulo para runtime; sólo cambia lo que verá el próximo diseñador que aplique la
  plantilla. Si el usuario prefiere paridad total con OPT-7, se agrega el gate
  (ver §Decisiones #1) — es una línea (`ensure_*_editable`).
- **Cross-event**: el banco es compartido; una edición afecta a lo que ve
  cualquier evento en el `<select>`. Igual que OPT-7; aceptable para plantillas.
- **Refactor de la regla de propiedad**: extraer
  `ensure_tool_manage_permission` a un módulo compartido puede tocar imports de
  `stations.py`. Corte de commit separado para el refactor puro (sin cambio de
  comportamiento) antes de agregar los endpoints nuevos.
- **Migración sobre 2 tablas + 4 FK**: mismo patrón ya probado en
  `n4o5p6q7r8s9`; el riesgo está en los nombres de FK de Postgres — verificar
  contra `information_schema` antes de escribir la revisión.

## Cortes de commit

1. **Refactor**: extraer la regla de propiedad + `reference_summary` genérico a
   `services/content_bank.py`; `instruments.py` la reexporta. Sin cambio de
   comportamiento; suite verde igual.
2. **Modelo + migración**: `created_by`/`origin_event_id`/`archived` ×2 tablas +
   `ondelete` en 4 FK + índices. Tests de migración (SQLite + Postgres).
3. **Backend CRUD**: endpoints PATCH/DELETE/restore/purge/GET-by-id ×2,
   `include_archived`, `created_by`/`origin_event_id` en el POST,
   `_reject_archived_reference`, `AuditLog`. Tests negativos + positivos.
4. **Frontend**: `api.ts`, `types.ts`, CRUD real en `/templates` y
   `/simulated-patient`. `lint` + `build` + vitest.
5. **Comando de purga** generalizado + doc. No se ejecuta.

## Esfuerzo

**S** (≈1–1,5 días). Menor que OPT-7: sin `apply_tool_patch` in-place (UPDATE
libre), sin barrido de `answers`, sin modo nuevo en el Constructor. El grueso es
migración (2 tablas, 4 FK) + duplicar el patrón de endpoints ×2 + dos pantallas
frontend análogas a `instruments/page.tsx`.

## Verificación

- [ ] `cd backend && python3 -m pytest`
- [ ] `TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q` (toca FKs/migración → **obligatorio**)
- [ ] `DATABASE_URL=sqlite:////tmp/ecoe_opt7b_check.db SECRET_KEY=test-secret ENVIRONMENT=test AUTO_SEED_DEMO=false alembic upgrade head` + `downgrade -1` + `upgrade head`
- [ ] mismo up/down/up contra Postgres desde base limpia; `delete_rule` verificado
- [ ] `cd frontend && npm run lint && npm run build && npx vitest run`

## Decisiones para el usuario

1. **¿Gate de editabilidad?** Recomendación: **NO** — UPDATE libre + soft-delete.
   El contenido no llega a runtime (verificado). Alternativa: replicar
   `EDIT_BLOCKING_STATUSES` de OPT-7 por paridad conceptual (cuesta ~1 función).
2. **¿`purge` = `admin_ecoe` o `admin_global`?** Recomendación: igual que OPT-7 —
   `admin_ecoe`/`admin_global`, sin coeditor.
3. **Migración**: 3 columnas ×2 tablas + `ondelete` en 4 FK. ¿OK de schema?
4. **Comando de purga**: ¿generalizar `purge_orphan_instruments.py` a los tres
   bancos, o script aparte? (recomendado: generalizar con `--kind`).

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-29
- Aprobado por usuario: ⬜ pendiente
