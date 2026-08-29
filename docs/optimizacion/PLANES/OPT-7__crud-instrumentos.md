# OPT-7 · CRUD de instrumentos (`AssessmentTool`)

**Severidad: media.** Origen: H-admin-ecoe-4 (= H-admin-ecoe-OPT7-1).
Hallazgo de fundamento: `docs/optimizacion/hallazgos/auditor-admin-ecoe__OPT-7__2026-08-29.md`.

## Problema

El banco de instrumentos es de **solo creación**. `backend/app/api/routes/stations.py:78-105`
expone únicamente `GET /api/instruments` y `POST /api/instruments`; no hay `PUT`, `PATCH`,
`DELETE` ni `GET /{id}` (contraste: `StationBank` sí tiene `PUT` + `PATCH …/status`,
`stations.py:156-194`). Consecuencias verificadas:

- **No se puede corregir una errata de una pauta.** El único camino desde el Constructor
  (`frontend/src/app/(app)/stations/builder/instrument-step.tsx`,
  `stations/builder/page.tsx:369-388` — `saveInstrumentDraft` siempre hace
  `api.createInstrument`) es rehacer la pauta entera en modo "crear", lo que hace **POST de
  un `AssessmentTool` nuevo** y re-apunta la estación. La pauta vieja queda para siempre.
- **El banco se llena de huérfanas.** Cada ronda de revisión docente deja 1 tool muerto
  (+ sus `AssessmentItem`). Multiplicado por ~15-20 estaciones/ECOE y varios ECOE al año,
  el `<select>` de instrumentos —que **no filtra por evento**, `stations.py:81`
  `select(AssessmentTool)` sin `where`— se vuelve inusable.
- **El banco es institucional sin propietario ni noción de "en uso".** `AssessmentTool`
  (`backend/app/models/entities.py:214-224`) no tiene `ecoe_event_id`, `created_by` ni
  `archived`. Sin eso no hay de dónde agarrar ni la autorización de borrado ni el filtro de
  "qué puedo editar sin romper un examen".
- **Un borrado ingenuo rompe datos históricos.** `EvaluatorRecord.answers` es un JSON
  **indexado por `AssessmentItem.id`** (`frontend/src/app/(app)/evaluator/page.tsx:116,497`).
  Un update que borre+reinserte ítems (natural con `cascade="all, delete-orphan"`,
  `entities.py:222-224`) genera ids nuevos y deja colgadas las claves de todo
  `EvaluatorRecord` previo → se pierde el desglose criterio-a-criterio.

Contra `docs/architecture/P0_MATRIZ_PERMISOS.md:44,72` ("admin/coeditor pueden modificar").

## Causa raíz

- `backend/app/api/routes/stations.py:76-105` — router de `/instruments` sólo GET+POST.
- `backend/app/models/entities.py:214-224` — `AssessmentTool` sin `created_by`,
  `origin_event_id`, `archived`.
- `backend/app/models/entities.py:281,321` — `Station.assessment_tool_id` y
  `StationBank.assessment_tool_id` son FK nullable **sin `ondelete`** → en Postgres un
  hard-delete de un tool referenciado lanza `IntegrityError`.
- `backend/app/models/entities.py:227-240` — `AssessmentItem.tool_id` FK **sin `ondelete`**;
  la relación ORM sí cascadea (`delete-orphan`). `UniqueConstraint(tool_id, order_index)`.
- `frontend/src/app/(app)/stations/builder/instrument-step.tsx` — no existe un modo
  "editar esta pauta"; cargar una estación entra siempre en modo `existing`
  (`stations/builder/page.tsx:514-525`) y ni siquiera carga los ítems en el editor.
- `backend/app/api/routes/ecoe.py:315-348` — duplicar un ECOE **comparte** el mismo
  `assessment_tool_id` (no clona el tool): un tool puede estar referenciado por estaciones
  de varios eventos.

## Alcance de esta pasada

**SOLO `AssessmentTool`.** `StationTemplate` y `SimulatedPatient` (mismo patrón
solo-creación, ver hallazgo §6) quedan como follow-up **OPT-7b** — su CRUD es casi trivial
(UPDATE libre + soft-delete), no comparten el riesgo de trazabilidad de `answers` por
`item.id` y no generan huérfanas de alto volumen (el Constructor no los crea).

## Cambio propuesto

### Migración (requiere aprobación explícita del usuario — ver §Decisiones)

Una revisión Alembic nueva, `down_revision = m3n4o5p6q7r8` (head actual de la rama
`opt/backlog-grupo-b`). Patrón idéntico a `k1f2a3b4c5d6_deferred_grading.py` para los
booleanos (`server_default` se conserva; SQLite no soporta `DROP DEFAULT`).

`assessment_tools`:
- `created_by` — `String(255)`, `nullable=True` (email del actor del POST; los históricos
  quedan `NULL`).
- `origin_event_id` — `Integer`, `ForeignKey("ecoe_events.id", ondelete="SET NULL")`,
  `nullable=True`.
- `archived` — `Boolean`, `nullable=False`, `server_default=sa.false()` (patrón
  `PilotRun.archived`, `entities.py:373`).
- Índice `ix_assessment_tools_archived` sobre `archived` (filtro por defecto del LIST).

FKs de referencia — añadir `ondelete` para que el soft-delete no sea la única opción segura
y para que el hard-delete falle limpio:
- `stations.assessment_tool_id` → `ondelete="SET NULL"` (recrear el constraint con nombre).
- `station_bank.assessment_tool_id` → `ondelete="SET NULL"`.
- `assessment_items.tool_id` → `ondelete="CASCADE"` (hoy sólo cascadea el ORM; alinear la BD).

> En SQLite el `ALTER` de FK no aplica; los tests SQLite ya recrean el schema con
> `create_all` desde los modelos, así que basta con actualizar `entities.py`. La migración
> usa `op.batch_alter_table` para que el `alembic upgrade` sobre SQLite (check de base
> limpia de AGENTS.md) no reviente. Verificar el up/down contra Postgres.

`entities.py`: agregar los tres campos a `AssessmentTool` y los `ondelete` a las tres FK.

### Backend

**`backend/app/services/instruments.py`** (nuevo módulo de reglas, análogo a
`services/grading.py`):

- `tool_reference_summary(db, tool_id) -> {station_ids, bank_ids, event_ids, event_statuses}`
  — un `SELECT Station.id, Station.ecoe_event_id, ECOEEvent.status … WHERE assessment_tool_id = tool_id`
  **UNION** el equivalente sobre `station_bank` (join a `station.ecoe_event` no aplica al
  banco, que es institucional: el banco cuenta como referencia "sin evento").
- `EDIT_BLOCKING_STATUSES = {en_pilotaje, publicado, en_ejecucion, cerrado, archivado}`
  (lista explícita del usuario; nótese que `en_pilotaje` bloquea aunque sea anterior a
  `pilotaje_validado` en el grafo — una vez que hay actividad de pilotaje registrada, los
  ids de ítem ya están referenciados por `EvaluatorRecord.answers`/`PilotRecord`).
- `ensure_tool_editable(db, tool)` — 409 si algún `event_status` de la referencia está en
  `EDIT_BLOCKING_STATUSES`. Una referencia sólo desde `station_bank` (sin evento) **no**
  bloquea.
- `apply_tool_patch(db, tool, payload)` — **update in-place por ítem, preservando `id`**:
  - campos de cabecera (`name`, `tool_type`, `free_observation`, `max_score`) → `setattr`.
  - `items`: cada item del payload lleva `id` opcional.
    - con `id` existente → `UPDATE` in-place (`label`, `score_per_item`, `order_index`).
    - sin `id` → `INSERT` nuevo `AssessmentItem`.
    - ids presentes en BD y ausentes del payload → `DELETE` explícito de ese ítem
      (`remove` de la colección; el `delete-orphan` lo borra).
  - **Nunca** `tool.items.clear()` + reinsert. Para evitar choques transitorios con
    `UniqueConstraint(tool_id, order_index)` durante la reordenación, aplicar en dos pasos
    dentro de la transacción: primero mover los `order_index` a un rango negativo temporal,
    luego asignar los definitivos (mismo truco que ya se usa para renumerar estaciones si
    aplica; si no, `db.flush()` entre borrados y updates).
- `ensure_tool_manage_permission(db, user, tool, event_roles_by_event)` — regla de
  propiedad (ver §Autorización).

**`backend/app/api/routes/stations.py`** — endpoints nuevos en el mismo router de
`/instruments`:

| Método | Ruta | Gate | Efecto |
|---|---|---|---|
| `GET` | `/api/instruments/{id}` | `CONTENT_MANAGER_ROLES` + `ensure_event_access(ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)` | tool serializado (reusa `serialize_assessment_tool`) o 404 |
| `PATCH` | `/api/instruments/{id}` | `require_roles("admin_ecoe","coeditor_docente")` + propiedad | `ensure_tool_editable` → `apply_tool_patch`; 409 si evento avanzado, 403 si sin permiso de origen |
| `DELETE` | `/api/instruments/{id}` | ídem PATCH | **soft**: `tool.archived = True`. Idempotente. `AuditLog`. |
| `POST` | `/api/instruments/{id}/restore` | ídem | `archived = False` |
| `DELETE` | `/api/instruments/{id}/purge` | `require_roles("admin_ecoe")` (sin coeditor) o `admin_global` | **hard-delete**, sólo si `tool_reference_summary` da 0 referencias en `stations` **y** `station_bank`; si no → 409 |

- `GET /api/instruments` gana `include_archived: bool = False`; por defecto filtra
  `AssessmentTool.archived.is_(False)`.
- `POST /api/instruments` estampa `created_by = user.email` y
  `origin_event_id = ecoe_event_id` (el del query param que ya se usa para el gate).
- El `ecoe_event_id` de contexto para PATCH/DELETE/GET-by-id se pasa como **query param**
  (igual que el POST hoy, `stations.py:84`) — coherencia con OPT-12 (descartado: no se
  cambia la forma del contrato en esta zona).

**`backend/app/schemas/common.py`**:
- `AssessmentItemInput` gana `id: int | None = None`.
- `AssessmentToolCreate` gana `items: list[AssessmentItemInput]` (ya está) — el POST ignora
  cualquier `id` entrante.
- `AssessmentToolRead` gana `created_by: str | None`, `origin_event_id: int | None`,
  `archived: bool`, y `reference_count: int` (calculado, para que la UI muestre "en uso por
  N estaciones" y decida si ofrecer editar/purgar).
- Nuevo `AssessmentToolPatch` = mismos campos que `Create` sin exigir todos (todos
  opcionales salvo `items`, que si viene reemplaza la lista con la semántica in-place).

**`backend/app/api/routes/ecoe.py:315-348`** — al duplicar un ECOE, hoy se comparte el
`assessment_tool_id`. Se mantiene (decisión de no clonar el banco), pero el tool duplicado
seguirá con su `origin_event_id` original → la regla de propiedad sigue apuntando al evento
que lo creó, no a la copia. Documentar en el docstring de `duplicate_ecoe`.

**Constructor de pautas — `apply_tool_patch` desde el Constructor**: ver Frontend.

### Autorización (regla de propiedad — decisión del usuario #4)

`editar/archivar/restaurar` un tool exige **una** de:
1. `admin_global` (bypass universal, `authorization.py:64-68`).
2. El actor tiene rol `admin_ecoe` o `coeditor_docente` **en `tool.origin_event_id`**
   (vía `get_user_event_roles(db, user, tool.origin_event_id)`).
3. **Regla de gracia para tools históricos** (`origin_event_id IS NULL`): el actor tiene
   `admin_ecoe`/`coeditor_docente` en **al menos un** evento que actualmente referencia el
   tool (`tool_reference_summary(...).event_ids`). Si el tool histórico tiene 0 referencias
   → sólo `admin_global`.

Racional: la regla 3 le da a los mantenedores actuales un camino sin una arqueología de
datos en la migración, pero impide que un coeditor de un evento sin relación con la pauta
la toque. Un tool referenciado **sólo** desde `station_bank` (sin evento) y con
`origin_event_id NULL` → sólo `admin_global`.

`purge` (hard-delete): además de 0 referencias, `require_roles("admin_ecoe")` sin coeditor
(acción destructiva sobre recurso compartido; el "contexto de evento" es semánticamente
débil — el tool no pertenece al evento).

### Frontend

**`frontend/src/lib/api.ts`** (junto a `createInstrument`, `stations/builder` :291-300):
- `instrument(id)` → `GET /api/instruments/{id}?ecoe_event_id=`
- `updateInstrument(eventId, id, payload)` → `PATCH`
- `archiveInstrument(eventId, id)` / `restoreInstrument(eventId, id)`
- `purgeInstrument(eventId, id)` → `DELETE …/purge`
- `instruments(eventId, {includeArchived})`

**`frontend/src/lib/types.ts:100-113`** — `AssessmentTool` gana `created_by`,
`origin_event_id`, `archived`, `reference_count`.

**Constructor — `frontend/src/app/(app)/stations/builder/instrument-step.tsx` +
`.../page.tsx`**: agregar un tercer modo al paso instrumento: **"Editar esta pauta"**.
- Se ofrece sólo cuando la estación ya referencia un `assessment_tool_id` **y** el tool es
  editable (`reference_count`/estado del evento actual permite PATCH — la UI puede
  intentar el PATCH y tratar el 409 como "esta pauta ya no es editable, creá una copia").
- Al entrar, carga los ítems reales del tool (hoy `page.tsx:514-525` no lo hace) en el
  editor con sus `id`.
- Al guardar, `saveInstrumentDraft` hace **`api.updateInstrument`** (PATCH) en vez de POST
  cuando el modo es "editar". El modo "crear" sigue igual (POST + re-apuntar).
- Con esto el Constructor deja de ensuciar el banco: corregir una errata edita en sitio.

**`frontend/src/app/(app)/instruments/page.tsx`** (hoy lista + "acción de demostración",
`instruments/page.tsx:29`): pasar a CRUD real —
- editar (abre el editor de ítems o enlaza al Constructor),
- archivar / restaurar (toggle `?include_archived`),
- "Purgar" sólo visible para `admin_ecoe`/`admin_global` y sólo con `reference_count === 0`,
  con `ConfirmDialog`.
- badge "En uso por N estaciones" y "Archivada".

### Migración de datos — limpieza opt-in de huérfanas (decisión del usuario #6)

**No** se corre en `upgrade()`. Se agrega un comando:
`python -m app.scripts.purge_orphan_instruments` (nuevo, junto a otros scripts si existen;
si no, `backend/scripts/`).

- **Dry-run por defecto**: lista candidatos, no borra. `--commit` para ejecutar.
- Criterio de candidato:
  1. `archived == False` **o** `--include-archived`.
  2. 0 referencias en `stations` **y** `station_bank`.
  3. `created_at` anterior a `--min-age-days` (default **90**).
  4. Ninguno de los `AssessmentItem.id` del tool aparece como clave en
     `EvaluatorRecord.answers` de ningún registro (barrido defensivo — cubre el caso de un
     `EvaluatorRecord` histórico de una estación que **antes** apuntaba a ese tool). Es
     O(registros) pero es un one-shot.
- Emite un `AuditLog` por tool purgado.
- El usuario decide si correrlo y con qué `--min-age-days` tras revisar el dry-run.

## Tests (incluye negativos — toca datos, permisos y migración)

`backend/tests/test_instruments_crud.py` (nuevo):

**Negativos obligatorios:**
- `test_patch_tool_of_advanced_event_returns_409` — tool usado por una estación de un ECOE
  en `en_pilotaje` (y por separado: `publicado`, `en_ejecucion`, `cerrado`) → `PATCH` 409;
  el tool no cambia.
- `test_archive_tool_without_origin_permission_returns_403` — coeditor del evento B intenta
  archivar un tool con `origin_event_id` = evento A (donde no tiene rol) → 403.
- `test_purge_referenced_tool_returns_409` — `DELETE …/purge` sobre un tool con ≥1
  referencia en `stations` o en `station_bank` → 409; el tool sigue vivo.
- `test_purge_requires_admin_ecoe_not_coeditor` — coeditor → 403 en `/purge`.
- `test_patch_preserves_item_ids` — `PATCH` que edita el `label` del ítem 2 y agrega un
  ítem 4: el `id` de los ítems 1-3 **no cambia**; un `EvaluatorRecord.answers` previo
  keyed por esos ids sigue resolviendo. (regresión del riesgo central).
- `test_list_instruments_hides_archived_by_default` / `…_shows_with_include_archived`.
- `test_archived_tool_not_selectable_for_new_station` — el `<select>` / la validación de
  `create_station` rechaza (o al menos la UI no ofrece) un `assessment_tool_id` archivado;
  una estación que ya lo usa sigue funcionando (`GET /evaluator/context` lo serializa).
- `test_historical_tool_grace_rule` — tool `origin_event_id IS NULL` con 1 referencia:
  coeditor de ese evento **puede** archivar (200); coeditor de un evento sin relación → 403;
  tool histórico con 0 referencias → sólo `admin_global` (coeditor 403).

**Positivos:**
- `test_patch_tool_of_draft_event_ok` — evento en `en_configuracion` → PATCH 200.
- `test_soft_delete_then_restore`.
- `test_create_instrument_stamps_created_by_and_origin_event`.
- `test_purge_orphan_command_dry_run_lists_and_commit_deletes` (script).

**Migración:**
- `alembic upgrade head` + `downgrade -1` + `upgrade head` desde base limpia en SQLite y
  Postgres. Verificar que `ondelete="SET NULL"` en `stations.assessment_tool_id` funciona
  (borrar tool huérfano no rompe; con referencia, el hard-delete falla limpio).

Frontend: `npm run lint && npm run build`; test de la página `instruments` (archivar
oculta de la lista; "Purgar" no aparece con `reference_count > 0`).

## Riesgos / alcance

- **Cross-event**: el banco es compartido; una edición afecta a toda estación que apunte al
  tool. El gate de `EDIT_BLOCKING_STATUSES` lo acota a eventos aún en diseño/config, donde
  un cambio compartido es aceptable (y esperado). Documentar en el docstring del endpoint.
- **`UniqueConstraint(tool_id, order_index)`** durante la reordenación de ítems: mitigado
  con el paso de `order_index` temporales + `flush`. Cubierto por
  `test_patch_preserves_item_ids` con reordenación.
- **La regla de gracia (#3)** es una decisión de producto con incertidumbre: un coeditor de
  cualquier evento que use un tool histórico puede editarlo. Es intencional (mantenibilidad
  > aislamiento perfecto para el legado) pero conviene que el usuario lo confirme.
- El Constructor gana un modo nuevo: riesgo de regresión en el flujo de "crear pauta". El
  modo "crear" no se toca; el modo "editar" es aditivo y sólo aparece cuando hay tool
  editable.
- Commit acotado sugerido en 4 cortes (ver abajo).

## Cortes de commit

1. **Modelo + migración.** `created_by`/`origin_event_id`/`archived` + `ondelete` en las 3
   FK + índice. Tests de migración (SQLite + Postgres, up/down/up).
2. **Backend CRUD.** `services/instruments.py`, endpoints PATCH/DELETE/restore/purge/GET-by-id,
   schemas, `include_archived`, `created_by`/`origin_event_id` en el POST, `AuditLog`.
   Tests negativos + positivos.
3. **Frontend.** `api.ts`, `types.ts`, modo "editar pauta" en el Constructor, CRUD real en
   `/instruments`. `lint` + `build` + test de página.
4. **Comando de limpieza opt-in** + doc de operación. No se ejecuta; queda a decisión del
   usuario.

## Verificación

- [x] `cd backend && python3 -m pytest` — 289 passed (SQLite)
- [x] `TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q` — 289 passed (Postgres + migraciones Alembic)
- [x] `DATABASE_URL=sqlite:////tmp/ecoe_opt7_check.db … alembic upgrade head` + `downgrade -1` + `upgrade head` — OK
- [x] mismo up/down contra Postgres desde base limpia (toca FKs `ondelete`) — OK; `delete_rule` verificado (SET NULL / CASCADE)
- [x] `cd frontend && npm run lint && npm run build` — OK; `npx vitest run` 52 passed (9 archivos)
- [ ] `./scripts/run_e2e.sh` — no corrido (el Constructor de pautas no se tocó; ver pendiente)

### Estado de implementación (rama `opt/OPT-7-crud-instrumentos`)

- [x] Migración `n4o5p6q7r8s9` (down_revision `m3n4o5p6q7r8`) + modelo.
- [x] `services/instruments.py` + endpoints PATCH/DELETE/restore/purge/GET-by-id +
      `include_archived` en LIST + schemas + `created_by`/`origin_event_id` en el POST.
- [x] Frontend: `api.ts`, `types.ts`, CRUD real en `/instruments` + test de página.
- [x] `backend/scripts/purge_orphan_instruments.py` (dry-run por defecto, `--apply`,
      `--min-age-days 90`) + tests.
- [ ] **Pendiente**: modo "editar esta pauta" en el Constructor
      (`stations/builder/instrument-step.tsx` + `page.tsx`). Es aditivo; sin él el
      CRUD limpia el banco pero el Constructor sigue creando una pauta nueva al
      "corregir" desde ahí. No bloquea el cierre del hallazgo principal (H-admin-ecoe-4).

## Decisiones registradas (producto — ya tomadas por el usuario 2026-08-29)

1. **Edición de tool en uso**: editable mientras ningún ECOE que lo referencia (vía
   `Station` o `StationBank`→`Station`) haya pasado a
   `en_pilotaje`/`publicado`/`en_ejecucion`/`cerrado`/`archivado` → si no, 409.
   `PATCH /api/instruments/{id}` opera **por ítem preservando el `id`** (update in-place;
   add/remove explícitos); nunca borra+reinserta.
2. **Alcance**: sólo `AssessmentTool`. `StationTemplate` y `SimulatedPatient` → OPT-7b.
3. **DELETE**: soft siempre (`AssessmentTool.archived`). Hard-delete sólo vía
   `DELETE /api/instruments/{id}/purge`, restringido a `admin_ecoe`/`admin_global`, y sólo
   sobre tools con 0 referencias en `stations` y `station_bank`.
4. **Propiedad del banco**: `created_by` (email) + `origin_event_id` (FK nullable,
   `ondelete SET NULL`). Editar/archivar exige rol `admin_ecoe`/`coeditor_docente` en
   `origin_event_id` **o** `admin_global`. **Regla de gracia** para tools sin
   `origin_event_id`: la puede tocar quien sea `admin_ecoe`/`coeditor_docente` de algún
   evento que hoy referencia el tool; si el tool histórico tiene 0 referencias → sólo
   `admin_global`. — ✅ **confirmada e implementada** (`ensure_tool_manage_permission`,
   cubierta por `test_historical_tool_grace_rule`). `purge` sube el listón: sólo
   `admin_ecoe`/`admin_global` (sin coeditor).
5. **Constructor de pautas**: modo "editar esta pauta" que hace `PATCH` cuando la estación
   ya referencia un tool editable, en vez de `POST` + re-apuntar.
6. **Migración**: columnas nuevas en la migración; limpieza de huérfanas existentes como
   **comando opt-in** (`purge_orphan_instruments`, dry-run por defecto, criterio:
   0 referencias + `archived=false` + antigüedad ≥ `--min-age-days` (default 90) + ningún
   `AssessmentItem.id` usado en `EvaluatorRecord.answers`). El usuario decide si correrlo.

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-29
- **Aprobado por usuario: ✅ 2026-08-29** (decisiones de producto tomadas; el plan técnico
  —migración, regla de gracia #4, cortes de commit— lo revisa el usuario antes de
  implementar).
