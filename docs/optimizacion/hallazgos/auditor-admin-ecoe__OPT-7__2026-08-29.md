# Hallazgos — auditor-admin-ecoe · OPT-7 · 2026-08-29

Mini-auditoría acotada para fundamentar el plan de **OPT-7: CRUD de instrumentos /
plantillas / pacientes simulados**. Parte del hallazgo ya confirmado
**H-admin-ecoe-4** (los bancos institucionales son de solo creación).

Método: lectura de código backend (`backend/app/api/routes/stations.py`,
`models/entities.py`, `schemas/common.py`, `utils/helpers.py`, `utils/serializers.py`,
`services/results.py`, `services/authorization.py`) y frontend
(`frontend/src/app/(app)/stations/builder/*`, `instruments/page.tsx`,
`templates/page.tsx`, `simulated-patient/page.tsx`, `evaluator/page.tsx`,
`lib/api.ts`). No se levantó servidor ni Docker. No se escribieron tests scratch:
la evidencia estática es concluyente.

Rama: `opt/backlog-grupo-b`.

## Resumen

Esto no es un catálogo de bugs nuevos, es la base técnica de OPT-7. Un hallazgo
estructural (H-admin-ecoe-OPT7-1, ya conocido como H-admin-ecoe-4) y cinco
sub-observaciones que condicionan el diseño.

| Severidad | N.º |
|---|---|
| bloqueante | 0 |
| alta | 1 (estructural, = H-admin-ecoe-4) |
| media | 3 |
| baja | 2 |

Los 3 puntos que más condicionan el plan:

1. **`assessment_tool.answers` del evaluador se indexa por `AssessmentItem.id`**
   (`frontend/src/app/(app)/stations/builder/... ` → `evaluator/page.tsx:116,497`).
   Un UPDATE que borre y reinserte ítems (patrón natural con
   `cascade="all, delete-orphan"`) genera ids nuevos y deja colgadas las claves
   de todo `EvaluatorRecord` histórico. Cualquier UPDATE de instrumento tiene que
   preservar ids de ítem o hacer copy-on-write.
2. **Hoy ya se puede "editar" un instrumento en uso**, indirectamente: el
   constructor, en modo "create", hace POST de una pauta nueva y re-apunta la
   estación —incluso si el ECOE está `publicado`/`en_ejecucion`
   (`update_station` no valida estado del evento,
   `backend/app/api/routes/stations.py:233-274`)—. El riesgo de "tool en uso" no
   es nuevo de OPT-7; OPT-7 puede aprovecharse para cerrarlo.
3. **El banco es institucional sin noción de propietario ni de "en uso"**. No hay
   `ecoe_event_id`, `created_by` ni `archived` en `assessment_tools` /
   `station_templates` / `simulated_patients`. Sin eso, ni la autorización de
   borrado ni el filtro de "qué puedo editar sin romper un examen" tienen de
   dónde agarrarse.

---

## Respuestas a las 7 preguntas

### 1 · Inventario exacto de endpoints hoy

Todo vive en **`backend/app/api/routes/stations.py`** (router incluido con prefijo
`/api`, `app/main.py:79`). No hay routers `instruments.py` / `templates.py`
separados.

| Recurso | LIST | GET(id) | CREATE | UPDATE | DELETE |
|---|---|---|---|---|---|
| `AssessmentTool` / instrumento | `GET /api/instruments?ecoe_event_id=` (`stations.py:78`) | ❌ | `POST /api/instruments` (`stations.py:84`) | ❌ | ❌ |
| `StationTemplate` / plantilla | `GET /api/templates?ecoe_event_id=` (`stations.py:54`) | ❌ | `POST /api/templates` (`stations.py:60`) | ❌ | ❌ |
| `SimulatedPatient` / paciente simulado | `GET /api/simulated-patients?ecoe_event_id=` (`stations.py:110`) | ❌ | `POST /api/simulated-patients` (`stations.py:116`) | ❌ | ❌ |
| `StationBank` (para comparar) | `GET /api/station-bank` (`:134`) | ❌ | `POST /api/station-bank` (`:140`) | ✅ `PUT /api/station-bank/{id}` (`:156`) + `PATCH …/status` (`:177`) | ❌ |
| `Station` (para comparar) | `GET /api/stations/{ecoe_event_id}` (`:199`) | ❌ | `POST /api/stations` (`:205`) | ✅ `PUT /api/stations/{id}` (`:233`) | ✅ `DELETE /api/stations/{id}` (`:277`) |

**Falta para los tres bancos**: `PUT`/`PATCH` y `DELETE`. También falta `GET/{id}`
(menor: el frontend trabaja con la lista completa).

Frontend equivalente (`frontend/src/lib/api.ts:293-299`): solo
`createTemplate`, `createInstrument`, `simulatedPatients`, `createSimulatedPatient`.
No hay `update*`/`delete*` para ninguno. Las pantallas dedicadas
`/instruments`, `/templates`, `/simulated-patient` son lista + un botón de
"crear de prueba"; `instruments/page.tsx:29` lo admite ("todavía usa una acción
rápida de demostración").

### 2 · Modelo de datos y compartición

**`AssessmentTool` es 100% institucional (cross-event).**
`backend/app/models/entities.py:214-224`: no tiene `ecoe_event_id`, ni
`created_by`, ni `archived`/`is_active`. Ídem `StationTemplate` (`:204-211`) y
`SimulatedPatient` (`:243-252`).

- Los GET **no filtran por evento**: `db.scalars(select(AssessmentTool)).all()`
  (`stations.py:81`), `select(StationTemplate)` (`:57`),
  `select(SimulatedPatient)` (`:113`). El parámetro `ecoe_event_id` solo se usa
  para el gate de autorización (`ensure_event_access`), no para el scope de datos.
  → **Un coeditor del evento A ve, y en el dropdown del constructor puede elegir,
  toda pauta creada en cualquier evento B.** Esto es el ruido del banco compartido
  descrito en H-admin-ecoe-4.
- `Station` referencia el tool por FK nullable **`assessment_tool_id`**
  (`entities.py:281`), más `template_id` (`:280`) y `simulated_patient_id`
  (`:282`). `StationBank` tiene las mismas tres FK (`:320-322`).
- Las FK **no tienen `ondelete`** (`alembic/versions/c7d8e9f00123_baseline_schema.py:147-150,279-281`)
  → comportamiento por defecto `NO ACTION`/`RESTRICT`. En Postgres (lo que corre
  CI y prod) un hard-delete de un tool referenciado lanza `IntegrityError`. En
  SQLite local no se valida salvo `PRAGMA foreign_keys`.
- `AssessmentItem` → `assessment_tools.id` sin `ondelete`, pero la relación ORM
  tiene `cascade="all, delete-orphan"` (`entities.py:222-224`), así que
  `db.delete(tool)` arrastra sus ítems a nivel ORM.

**¿Qué pasa hoy si dos estaciones de eventos distintos apuntan al mismo tool?**
Nada, porque hoy las únicas operaciones son crear y referenciar (lectura). El
tool es un registro compartido inmutable: se serializa igual para ambos eventos
(`serialize_assessment_tool`, `utils/serializers.py:12`). El problema aparece
justo cuando OPT-7 agregue UPDATE/DELETE: una edición afectaría a los dos eventos,
un borrado rompería los dos. No hay forma de saber "quién usa este tool" sin un
`SELECT … WHERE assessment_tool_id = ?` sobre `stations` **y** `station_bank`.

### 3 · Flujo del constructor de pautas

`frontend/src/app/(app)/stations/builder/`:

- El paso instrumento (`instrument-step.tsx`) tiene dos modos:
  **`existing`** (`assessmentMode`) → un `<select>` de instrumentos existentes,
  guarda solo `selectedAssessmentToolId`, **no hace POST** (`instrument-step.tsx:146-162`);
  **`create`** → editor de pauta completo (`:176+`).
- Al guardar la estación (`page.tsx:832-846`), si `assessmentMode === "create"`
  se llama `saveInstrumentDraft()` → `api.createInstrument(...)` → **POST
  `/api/instruments`** (`page.tsx:369-388`). Tras el POST fuerza
  `setAssessmentMode("existing")` y selecciona el nuevo id (`:384-385`).
- **No existe un modo "editar esta pauta existente"**. Cargar una estación en el
  constructor siempre entra en modo `existing` con el `assessment_tool_id`
  guardado (`page.tsx:514-525`); los ítems de esa pauta ni siquiera se cargan en
  el editor. Para corregir una errata en un criterio, el único camino es: cambiar
  a modo `create`, **rehacer la pauta entera desde cero**, guardar → **POST de un
  `AssessmentTool` nuevo**, la estación queda apuntando al nuevo, el viejo queda
  en la tabla para siempre, visible en el dropdown de todos los eventos.
- El backend **nunca deduplica**: cada POST inserta
  (`stations.py:93-105`), aunque el `name`, los ítems y el `tool_type` sean
  idénticos a uno existente.

**Huérfanas de un flujo típico de edición**: 1 `AssessmentTool` huérfano
(+ sus N `AssessmentItem`) **por cada ronda de "necesito corregir la pauta"**. Un
ciclo realista de diseño de una estación con 3-4 pasadas de revisión docente deja
3-4 pautas muertas en el banco institucional. Multiplicado por ~15-20 estaciones
por ECOE y varios ECOE al año, el dropdown se vuelve inusable en una o dos
temporadas. Además, la pauta "buena" y las 3 "malas" tienen nombres casi
idénticos y no hay forma de distinguirlas ni de borrarlas.

Plantillas y pacientes simulados: el constructor **no los crea**, solo los
consume desde su propio dropdown (`page.tsx:68-69, 85`). Se crean únicamente
desde las pantallas dedicadas `/templates` y `/simulated-patient`
(`templates/page.tsx:125`, `simulated-patient/page.tsx:35`), también solo-POST.

### 4 · Impacto de agregar UPDATE

Depende del estado del ECOE que usa el tool y de **cómo** se implemente el UPDATE.

**Resultados ya consolidados (`cerrado`/`archivado`): NO se corrompen los números.**
- `EvaluatorRecord` guarda `score_obtained` y `max_score` **desnormalizados** como
  `Float` en el momento del submit (`entities.py:505-506`;
  `resolve_station_max_score` se evalúa al enviar, `evaluator.py:347,453` →
  `helpers.py:232-246`).
- El cierre escribe un snapshot `ECOEResult` y `read_results` lo devuelve
  congelado (`services/results.py:113-157`); `compute_results` suma los campos
  desnormalizados de `EvaluatorRecord`, **no** recalcula desde el tool
  (`results.py:57-98`).
- ⇒ editar el tool después del cierre no mueve ninguna nota ya consolidada.

**Pero sí se rompe la trazabilidad y la auditoría del examen:**
- `serialize_assessment_tool` lee los ítems **en vivo** (`serializers.py:12-27`).
  Cualquier vista histórica ("¿con qué criterios se evaluó a este alumno?") pasa a
  mostrar la versión editada, no la real.
- `EvaluatorRecord.answers` es un JSON **indexado por `AssessmentItem.id`**
  (`frontend/src/app/(app)/evaluator/page.tsx:116` y `:497`:
  `String(item.id ?? item.order_index ?? index)`). Si el UPDATE borra+reinserta
  ítems (natural con `delete-orphan`), los ids cambian y **las claves de
  `answers` de todos los registros previos quedan colgadas** → el desglose
  criterio-por-criterio de esos alumnos se pierde.

**ECOE `publicado` / `en_ejecucion`: riesgo real de inconsistencia entre alumnos.**
- Estaciones ya `publicada`, evaluadores recibiendo la pauta vía
  `/api/evaluator/context` en vivo (`evaluator.py:129,272`).
- `max_score` se recalcula por submit desde los ítems (`helpers.py:238-246`):
  editar los puntajes a mitad de rotación → alumnos de la mañana con un
  denominador y los de la tarde con otro, sin marca de que pasó.
- El constructor **ya permite este escenario hoy** por la vía indirecta de
  "crear + re-apuntar", porque `update_station` no valida el estado del evento
  (`stations.py:233-274`, solo evita recalcular el badge de la estación).

**Conclusión para el diseño**: un UPDATE plano ("reemplazá el tool") es
peligroso en dos frentes (mid-execution y trazabilidad histórica). Opciones, de
menos a más trabajo:
- **(a) Bloquear la edición si el tool está referenciado por una estación de un
  ECOE en estado ≠ `borrador`/`en_configuracion`.** Simple, seguro, pero
  frustrante: una vez piloteado no se toca ni una errata.
- **(b) Permitir edición libre solo mientras ninguna estación que lo use está en
  un evento > `pilotaje_validado`; PATCH a nivel de ítem preservando ids
  (`order_index`, `label`, `score_per_item`) sin borrar+reinsertar.** Cubre el
  99% de los casos reales (correcciones durante diseño y pilotaje).
- **(c) Copy-on-write / versionado**: al editar un tool "en uso por evento no
  borrador", se clona (`v2`) y se re-apunta solo la estación del evento en
  edición; los eventos históricos siguen con `v1`. Es lo correcto para trazabilidad
  total pero requiere `parent_tool_id` / `version` y decidir qué pasa con el banco
  (¿se listan las dos versiones?).

Recomendación no vinculante: **(b) para la Fase 1**, con la regla de "no editable
si lo usa una estación de un evento pasado `pilotaje_validado`", y dejar (c)
anotado como Fase 2 si aparece la necesidad de corregir pautas de exámenes ya
ejecutados.

### 5 · Impacto de agregar DELETE

- **Integridad referencial**: hay que chequear referencias en **`stations`
  Y `station_bank`** (ambas tienen `assessment_tool_id` / `template_id` /
  `simulated_patient_id`). Sin `ondelete` en las FK, un hard-delete de un tool
  referenciado revienta con `IntegrityError` en Postgres. Un hard-delete de un
  tool **no** referenciado sí funciona (ORM arrastra los `AssessmentItem` por
  `cascade delete-orphan`).
- **Soft vs hard**:
  - Hard-delete solo defendible para tools/plantillas/pacientes **con cero
    referencias** (huérfanas) y sin `EvaluatorRecord` histórico que dependa de
    sus ítems. Es lo que resuelve el problema de H-admin-ecoe-4 (limpiar el banco).
  - Soft-delete (`archived: bool` — ya hay precedente: `PilotRun.archived`
    `entities.py:373`, `User.is_active`, `Student.is_active`) para "sacar del
    dropdown sin romper nada". Es lo que hay que usar para cualquier tool que
    tenga referencias o historial. El GET de lista debería filtrar
    `archived == False` por defecto.
  - Patrón mixto recomendado: **DELETE = soft (`archived=true`) siempre; hard
    delete solo vía una acción explícita "purgar huérfanas" restringida a
    `admin_ecoe`/`admin_global` y solo sobre registros con 0 referencias.**
- **Quién puede borrar**: ver pregunta 7.

### 6 · Pacientes simulados y plantillas

**Mismo patrón exacto que instrumentos**, con matices:

| | `AssessmentTool` | `StationTemplate` | `SimulatedPatient` |
|---|---|---|---|
| Institucional (sin `ecoe_event_id`) | sí | sí | sí |
| Endpoints hoy | list + create | list + create | list + create |
| Referenciado por | `stations`, `station_bank` | `stations`, `station_bank` | `stations`, `station_bank` |
| Se crea desde el constructor | **sí** (modo `create`) | no (solo `/templates`) | no (solo `/simulated-patient`) |
| Genera huérfanas en el flujo de diseño | **sí, alto volumen** | bajo | bajo |
| Contenido sensible para trazabilidad | alto (`answers` por item.id, `max_score`) | bajo (`default_configuration` solo se copia al crear la estación, no se lee en vivo) | medio (guion que vio el paciente; no afecta notas) |

**Ninguno es por-evento y ninguno tiene CRUD completo.** El único recurso de banco
con UPDATE es `StationBank` (`PUT /api/station-bank/{id}`, `stations.py:156`) y
tampoco tiene DELETE. `StationTemplate.default_configuration` **solo se lee al
aplicar la plantilla en el constructor** (copia de campos, `page.tsx:130`), no en
runtime → editar una plantilla es de bajo riesgo (no toca estaciones ya creadas).
`SimulatedPatient` no interviene en el cálculo de notas → editarlo no corrompe
resultados; el único cuidado es no cambiarlo a mitad de ejecución.

⇒ La complejidad de OPT-7 está concentrada en `AssessmentTool`. Plantillas y
pacientes simulados pueden llevar un CRUD casi trivial (UPDATE libre + soft-delete).

### 7 · Autorización

**Lo que dice `P0_MATRIZ_PERMISOS.md`:**
- Fila "Instrumentos/plantillas/pacientes": Admin ECOE **Sí**, Coeditor **Sí**,
  Coordinador **Lectura**, resto vía contexto filtrado
  (`docs/architecture/P0_MATRIZ_PERMISOS.md:44`).
- "Los bancos … son institucionales y reutilizables. Su consulta o mutacion exige
  indicar un ECOE de contexto: **admin/coeditor pueden modificar; coordinador solo
  puede consultar**" (`P0_MATRIZ_PERMISOS.md:72`).
- `admin_global` hereda todo lo de `admin_ecoe` sobre todos los eventos (`:57`).

**Gate que aplica hoy a los POST** (y que OPT-7 debería replicar en UPDATE/DELETE):
`require_roles("admin_ecoe", "coeditor_docente")` + `ensure_event_access(db, user,
ecoe_event_id, RoleCode.admin_ecoe.value, RoleCode.coeditor_docente.value)`
(`stations.py:84-92`). Es decir: **NO** `require_global_roles`. El recurso es
institucional pero el gate es por-evento-de-contexto — coherente con la doctrina
de CLAUDE.md ("`ensure_event_access` para autorización fina por evento";
`require_global_roles` solo para recursos institucionales tipo gestión de
usuarios, que esto no es).

**Recomendación para UPDATE/DELETE:**
- **UPDATE**: mismo gate que el POST — `require_roles("admin_ecoe",
  "coeditor_docente")` + `ensure_event_access(..., ecoe_event_id de contexto,
  admin_ecoe, coeditor_docente)`. Coordinador queda fuera (solo lectura), como
  hoy.
- **DELETE (soft)**: igual, admin_ecoe + coeditor.
- **Hard-delete / purgar huérfanas**: subir el listón a `require_roles("admin_ecoe")`
  (sin coeditor) o incluso `admin_global`, porque es una acción destructiva sobre
  un recurso compartido y el "contexto de evento" es semánticamente débil aquí
  (el tool no pertenece al evento).
- **Problema de fondo sin resolver**: como el banco no tiene propietario, un
  coeditor del evento A puede editar/borrar (soft) una pauta que **solo** usa el
  evento B. El gate por-evento-de-contexto no protege contra eso. Mitigaciones
  posibles: (i) prohibir editar/borrar un tool si tiene referencias en un evento
  donde el actor **no** tiene acceso; (ii) agregar `created_by` / `origin_event_id`
  informativo y exigir que coincida o que el actor sea `admin_global`. Es una
  **decisión de diseño para el usuario**, no algo que el código actual resuelva.

---

## Decisiones de diseño que el usuario debe tomar para OPT-7

1. **Edición de un instrumento en uso** (la grande). Elegir entre:
   - **(a)** bloqueo total si lo usa una estación de un evento ≠ borrador/config;
   - **(b)** edición permitida hasta `pilotaje_validado`, PATCH por ítem
     preservando `AssessmentItem.id` (recomendada para Fase 1);
   - **(c)** copy-on-write con versionado (`parent_tool_id`/`version`) para poder
     corregir incluso pautas de exámenes cerrados sin tocar el histórico
     (Fase 2 si hace falta).
   Nota dura: cualquier opción que borre+reinserte ítems rompe el desglose
   criterio-a-criterio de `EvaluatorRecord` histórico (`answers` por `item.id`).

2. **Soft-delete vs hard-delete**:
   - propuesta: **DELETE siempre soft** (`archived: bool` nuevo en las 3 tablas,
     GET filtra `archived=False`); **hard-delete solo** como acción separada
     "purgar huérfanas" limitada a registros con 0 referencias en `stations` +
     `station_bank`.
   - decidir si "purgar huérfanas" es `admin_ecoe` o `admin_global`.

3. **Propiedad del banco institucional**: ¿se agrega `created_by` /
   `origin_event_id` (informativo o para autorización)? ¿O se acepta que cualquier
   admin/coeditor de cualquier evento pueda editar/archivar cualquier registro del
   banco? Sin esto, el gate por-evento no protege pautas de otros eventos.

4. **Alcance de la Fase 1**: ¿el CRUD completo para los 3 recursos, o solo
   `AssessmentTool` (que es donde está el dolor real) y plantillas/pacientes en
   una fase posterior con UPDATE libre + soft-delete trivial?

5. **Dedup en el POST de instrumentos**: ¿OPT-7 debería además evitar que el
   constructor cree una pauta nueva cuando el usuario en realidad quería editar la
   existente? (agregar un modo "editar esta pauta" en `instrument-step.tsx` que
   cargue los ítems y haga PATCH en vez de POST). Es la causa raíz de la
   acumulación de huérfanas; sin esto, el CRUD limpia el banco pero el constructor
   lo sigue ensuciando.

6. **Migración de datos**: al desplegar, ¿se hace una pasada de limpieza de las
   huérfanas ya existentes en prod (tools con 0 referencias), o se deja que el
   usuario las archive a mano desde la nueva UI?
