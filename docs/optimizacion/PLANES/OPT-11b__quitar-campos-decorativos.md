# OPT-11b · Quitar (o derivar) `total_stations` / `total_students` decorativos

**Severidad: baja.** Origen: H-admin-ecoe-5. Follow-up de **OPT-11** (quick win
ya en `main` @ `b297df5`, `f7ee891`): OPT-11 relabeló los campos a "estimadas" en
el **form** pero no los tocó en el backend ni en la pantalla de detalle porque
"requeriría migración" (BACKLOG nota OPT-11).

## Problema

`ecoe_events.total_stations` y `ecoe_events.total_students` son campos que el
usuario ingresa al crear/editar un ECOE pero que **nadie calcula ni consume para
nada funcional**. Verificado en el árbol actual:

- `backend/app/services/validation.py:54` — `compute_ecoe_validation` cuenta las
  filas reales: `station_count = db.scalar(select(func.count(Station.id))…)`.
  **Nunca** lee `ecoe_event.total_stations` (grep en `backend/app/` confirma: los
  únicos usos son el schema, la columna, `duplicate_ecoe` y el seed).
- `frontend/src/components/ecoe-form.tsx:66-68` valida `total_stations >= 1`
  (mínimo cosmético); `:161-170` los inputs (ya relabelados "estimadas" con ayuda
  "…la validación usa el número real de estaciones construidas, no este valor").
- `frontend/src/app/(app)/ecoe/[id]/page.tsx:207,210` — la pantalla de **detalle**
  muestra `<DetailItem label="Total de estaciones" value={ecoe.total_stations} />`
  y `"Total de estudiantes"` **sin** el matiz "estimadas": junto a una lista real
  de 6 estaciones puede decir "Total de estaciones: 8". Esa es la
  falsa-expectativa que reporta H-admin-ecoe-5.

Consumidores completos (todos verificados):

| Archivo | Uso |
|---|---|
| `backend/app/schemas/common.py:51,54` | `ECOEEventBase` — campos requeridos (`Field(ge=1)` / `ge=0`); heredados por `ECOEEventCreate`, `ECOEEventUpdate`, `ECOEEventRead` |
| `backend/app/models/entities.py:116,119` | columnas `Integer`, `default=0` |
| `backend/alembic/versions/c7d8e9f00123_baseline_schema.py:56,59` | `nullable=False` en el baseline |
| `backend/app/api/routes/ecoe.py:306,309` | `duplicate_ecoe` copia `total_stations`, fija `total_students=0` |
| `backend/app/db/seed.py:123,126` | seed demo |
| `frontend/src/lib/types.ts:28,31` | tipo `ECOEEvent` |
| `frontend/src/components/ecoe-form.tsx:66-68,161-170,204,207,224,227` | validación, inputs, payload de submit, prefill de edición |
| `frontend/src/app/(app)/ecoe/page.tsx:19-20` | valores por defecto del form de alta |
| `frontend/src/app/(app)/ecoe/[id]/page.tsx:81-83,207,210` | prefill de edición + `DetailItem` de detalle |
| ~15 tests backend | pasan `total_stations=`/`total_students=` al **constructor ORM** `ECOEEvent(...)` |
| ~7 tests backend | los incluyen en el **body** del `POST /ecoe` (`test_api.py:21`, `test_permissions_matrix.py:65`, `test_state_machine_and_modes.py:81`, …) |

## Causa raíz

Campos de planificación que quedaron en el modelo desde el diseño inicial; la
validación de completitud migró a conteos reales de filas y estos nunca se
volvieron a usar. `compute_ecoe_validation` (`validation.py:47-...`) es la única
autoridad de "cuántas estaciones/estudiantes hay" y usa `func.count`.

## Decisión a proponer — (a) quitar vs (b) derivar

### Opción (b) — derivar de las filas reales (**recomendada**)

**Sin migración.** Los campos siguen en la respuesta de la API pero pasan a
reflejar el conteo real, no un valor ingresado.

- `backend/app/schemas/common.py`: **sacar** `total_stations` / `total_students`
  de `ECOEEventBase` → `ECOEEventCreate` / `ECOEEventUpdate` dejan de aceptarlos
  (Pydantic ignora las claves extra que sigan mandando los clientes viejos → sin
  romper). Moverlos a `ECOEEventRead` como campos normales.
- `backend/app/api/routes/ecoe.py`: helper `_with_counts(db, event)` que setea
  `event.total_stations = db.scalar(select(func.count(Station.id)).where(...))` y
  `event.total_students = db.scalar(select(func.count(Student.id)).where(Student.ecoe_event_id==id, Student.is_active.is_(True)))`
  **en memoria** (no commit) antes de devolver. Aplicar en los 6 handlers que
  devuelven `ECOEEventRead` (`ecoe.py:48,53,82,199,241,278`). Para
  `GET /ecoe` (lista) usar dos `GROUP BY` y un dict, no N+1.
- `backend/app/models/entities.py`: las columnas se **mantienen** (evita
  migración y el churn de ~15 tests que construyen `ECOEEvent(total_stations=1)`).
  Quedan como columnas escritas-pero-no-leídas; opcionalmente se puede refrescar
  su valor real en `create`/`update` para coherencia a nivel BD, pero no es
  necesario.
- `duplicate_ecoe` (`ecoe.py:306,309`): dejar de setearlos explícitamente (el
  `default=0` del modelo basta; `_with_counts` los corrige en la respuesta).
- `seed.py`: se pueden dejar (son inofensivos) o quitar.
- **Frontend**: `ecoe-form.tsx` — quitar los dos inputs (`:161-170`), su
  validación (`:66-68`), del payload de submit (`:204,207`) y del prefill
  (`:224,227`); `ecoe/page.tsx:19-20` — quitar de los defaults; `ecoe/[id]/page.tsx`
  — el prefill de edición (`:81-83`) y los `DetailItem` (`:207,210`) ahora
  muestran el conteo real que viene del backend (mantenerlos como
  "Estaciones" / "Estudiantes activos", sin "Total"). `types.ts` — sin cambios
  (siguen en `ECOEEvent`).
- **Tests**: los ~7 que asertan el valor en la **respuesta** de `POST /ecoe`
  (p. ej. esperando `total_stations == 4` inmediatamente tras crear, sin
  estaciones) pasan a esperar el conteo real (**0** recién creado). Ajuste
  mecánico. Los ~15 que sólo lo pasan al constructor ORM **no se tocan** (la
  columna sigue existiendo).

**Migración: NO.**

### Opción (a) — quitar del schema y de la BD

- Migración Alembic nueva (`down_revision = n4o5p6q7r8s9`): `op.drop_column`
  ×2 sobre `ecoe_events`. `downgrade` re-crea con `server_default="0"` +
  `nullable=False`. `batch_alter_table` para SQLite.
- Quitar de `ECOEEventBase`, del modelo, de `duplicate_ecoe`, del seed, de
  `types.ts`, de `ecoe-form.tsx`, `ecoe/page.tsx`, `ecoe/[id]/page.tsx`.
- **Churn de tests**: ~15 archivos que construyen `ECOEEvent(total_stations=1,
  total_students=1)` — hay que borrar esos kwargs. ~7 que los mandan en el body
  del POST — quitar. Es mecánico pero toca mucha superficie.
- La pantalla de detalle puede seguir mostrando un conteo real derivado (mismo
  helper que en (b)) o simplemente no mostrar la línea.

**Migración: SÍ** (`drop_column` ×2).

### Recomendación

**(b).** Elimina la falsa-expectativa (los `DetailItem` y todo lo demás muestran
el número real) sin migración y con el mínimo churn de tests. El único costo
frente a (a) es dejar dos columnas escritas-pero-no-leídas en `ecoe_events` —
cosmético, sin efecto funcional, y removibles después en una limpieza de schema
si el usuario lo quiere. (a) es el "estado final limpio" pero paga migración +
~22 archivos de test para borrar un concepto que (b) ya neutraliza.

## Cambio propuesto

Ver Opción (b) arriba. Resumen de archivos:

- Backend: `schemas/common.py` (mover 2 campos de `Base` a `Read`),
  `api/routes/ecoe.py` (`_with_counts` + 6 call-sites + lista con `GROUP BY`),
  `api/routes/ecoe.py::duplicate_ecoe` (no setear), `db/seed.py` (opcional).
- Frontend: `components/ecoe-form.tsx`, `app/(app)/ecoe/page.tsx`,
  `app/(app)/ecoe/[id]/page.tsx`.
- Migración: **no**.
- Máquina de estados: no se toca.

## Tests (incluye negativos — toca la forma del contrato de `/ecoe`)

`backend/tests/test_api.py` / `test_state_machine_and_modes.py` (ajustar) +
`backend/tests/test_ecoe_counts_opt11b.py` (nuevo):

- `test_create_ecoe_ignores_client_supplied_totals` — `POST /ecoe` con
  `total_stations: 99` en el body → la respuesta trae `total_stations == 0` (aún
  sin estaciones), no 99. (negativo: el cliente ya no controla el valor.)
- `test_ecoe_read_reflects_real_station_and_student_counts` — crear evento, 3
  estaciones, 5 estudiantes activos + 1 inactivo → `GET /ecoe/{id}` devuelve
  `total_stations == 3`, `total_students == 5`.
- `test_ecoe_list_counts_are_not_n_plus_one` — 2 eventos con estaciones distintas
  → `GET /ecoe` devuelve los conteos correctos por evento (verifica el `GROUP BY`,
  no el lazy-load).
- `test_duplicate_ecoe_totals_reflect_copied_stations` — duplicar un ECOE con 4
  estaciones → la copia reporta `total_stations == 4`, `total_students == 0`.
- `test_validation_still_uses_row_counts` — regresión: `compute_ecoe_validation`
  no cambió (ya usa `func.count`).

Frontend: `npm run lint && npm run build` + vitest de `ecoe-form` (los inputs de
totales ya no se renderizan; el submit no manda esas claves) y de
`ecoe/[id]/page` (los `DetailItem` muestran el valor del backend).

## Riesgos / alcance

- **Contrato de `/ecoe`**: `ECOEEventCreate`/`Update` dejan de aceptar los campos.
  Pydantic **ignora** claves extra por defecto → clientes que sigan mandándolos
  no rompen (verificar que no haya `model_config = ConfigDict(extra="forbid")` en
  `ECOEEventBase` — hoy no lo hay).
- **Semántica de `total_students`**: ¿cuenta sólo `is_active` (recomendado, es lo
  que importa operativamente) o todos? Decidir (ver §Decisiones).
- **Lista `GET /ecoe`**: el `GROUP BY` agrega 2 queries agregadas al endpoint;
  trivial frente a la carga actual.
- **Columnas muertas** (opción b): quedan en `ecoe_events`. Documentar en el
  docstring del modelo que son legado y no autoritativas.
- Commit acotado: 1 corte backend (schema + helper + call-sites + tests), 1 corte
  frontend.

## Esfuerzo

- Opción (b): **S** (≈1 día). Sin migración; el grueso es el helper + 6
  call-sites + ajustar ~7 asserts de test + 3 archivos frontend.
- Opción (a): **S–M** (≈1,5–2 días). Migración + ~22 archivos de test.

## Verificación

- [x] `cd backend && python3 -m pytest` — 366 passed (SQLite)
- [x] `TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q` — 366 passed (Postgres, migraciones reales)
- [x] `alembic upgrade head` desde base limpia — OK, sin migración nueva (opción b)
- [x] `cd frontend && npm run lint && npm run build && npx vitest run` — lint sin errores, build OK, 61 vitest passed

## Decisiones para el usuario

1. **(a) quitar de la BD** vs **(b) derivar de las filas** — recomendación:
   **(b)** (sin migración, sin churn de tests, elimina la falsa-expectativa
   igual).
2. `total_students`: ¿sólo estudiantes `is_active` (recomendado) o todos?
3. Opción (b): ¿se dejan las columnas muertas en `ecoe_events` (recomendado, cero
   riesgo) o se agenda una limpieza de schema aparte?

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-29
- Aprobado por usuario: ✅ opción (b), `total_students` = sólo `is_active`, columnas legadas se conservan
- Implementado por: implementador — 2026-08-29 · rama `opt/OPT-11b-campos-derivados` · `en-verificación`

## Notas de implementación

- **Columnas ORM**: se conservan en `ecoe_events` (sin migración). Marcadas como
  legadas y no autoritativas en el docstring de `entities.py`. Se siguen
  escribiendo con su `default=0` y quedan huérfanas; ningún código las lee.
- **Schema**: `total_stations`/`total_students` salieron de `ECOEEventBase` →
  `ECOEEventCreate`/`ECOEEventUpdate` ya no los aceptan (Pydantic ignora las
  claves extra, sin `extra="forbid"`). Se agregaron a `ECOEEventRead` como
  campos derivados.
- **Handlers**: `_with_counts(db, event)` (detalle/create/update/timing/duplicate)
  y `_with_counts_bulk(db, events)` (lista, dos `GROUP BY`, sin N+1) en
  `api/routes/ecoe.py`. Asignan en memoria antes de serializar, sin `commit`.
- **`duplicate_ecoe`** y **`seed.py`**: dejan de setear los campos.
- **Tests existentes**: ninguno requirió cambios. Los ~15 que pasan
  `total_stations=` al constructor `ECOEEvent(...)` siguen válidos (la columna
  existe); los ~7 que lo mandan en el body de `POST`/`PUT` no rompen (Pydantic
  ignora extras) y no asertan sobre el valor de respuesta.
- **Test nuevo**: `backend/tests/test_ecoe_counts_opt11b.py` — 7 casos:
  contrato (create/update ignoran los totales del cliente), lectura refleja
  filas reales, estudiante inactivo no cuenta, agregar estación sube el conteo,
  lista por evento, `duplicate` reporta las estaciones copiadas y 0 estudiantes,
  regresión de `compute_ecoe_validation`.
