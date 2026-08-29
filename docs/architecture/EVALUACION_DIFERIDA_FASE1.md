# Evaluación diferida — Fase 1

Fecha: 2026-08-28

## Contexto: el vacío detectado

Hoy una estación solo tiene dos caminos reales de puntaje:

1. **Evaluador presencial** (`requires_evaluator = true`): alguien logueado hace
   check-in y llena el instrumento en la pantalla Evaluador durante la ventana de
   tiempo de la rotación. Produce `EvaluatorRecord` y suma directo al consolidado.
2. **Autocorrección** (`requires_student_form = true` con preguntas de alternativa
   y puntaje): `apply_auto_grading` puntúa al enviar.

Existe un tercer caso que **no está configurado como tal**: estaciones donde un
humano juzga el desempeño o la producción del estudiante, pero **no en tiempo real
en la estación** — corrige después, a partir del formulario que respondió el
estudiante (y, más adelante, de un video o un artefacto). Hoy eso solo ocurre como
efecto colateral de tener preguntas `short_text` con puntaje en el formulario, y se
resuelve en la pantalla Corrección (`/grading`).

Problemas concretos de ese estado:

- **No se puede designar quién corrige.** La ruta `/grading` la puede usar
  cualquier `admin_ecoe` / `coeditor_docente` del evento, sobre una lista plana de
  todas las respuestas. No hay asignación por estación ni cola "asignadas a mí".
- **No se puede delegar la corrección** a alguien que no sea admin/coeditor del
  ECOE. El rol `evaluador` no participa (y su `station_ids` solo tiene sentido para
  el camino presencial).
- **Validación no exige responsable.** Una estación con formulario de corrección
  manual aparece verde sin nadie asignado a corregirla. `can_publish` no lo mira.
- **Resultados y trazabilidad no distinguen "enviado" de "corregido".** Un
  estudiante puede figurar como `completo` con su estación escrita sin puntuar.
- **El instrumento (pauta) no se usa** en la corrección diferida: `apply_manual_scores`
  es entrada numérica libre por pregunta acotada a `[0, max]`.

## Objetivo de la Fase 1

Convertir la evaluación diferida en un **modo de estación de primera clase**, con
un **responsable asignable y delegable**, y hacer que Validación y Resultados lo
traten como tal. Sin rediseñar la pantalla Corrección ni cambiar dónde se guarda
el puntaje.

## Alcance

### Incluye

- Rol operativo nuevo `corrector` en `StaffAssignment`, delegable y **multi-estación**.
- Capacidad de estación `requires_deferred_grading` (flag explícito).
- Validación: bloqueos simétricos a `requires_evaluator` para el nuevo modo.
- `/grading` (API + pantalla) consciente del rol: un `corrector` ve y corrige solo
  sus estaciones asignadas.
- Trazabilidad: señal de "pendiente de corrección" por estudiante/estación.
- Semilla demo + tests (incluye negativos obligatorios por `AGENTS.md`).

### No incluye (queda para Fase 2)

- Adjuntar entregables (PDF, foto, audio, video) para corregir estaciones **sin
  formulario** — p. ej. revisión de un procedimiento grabado.
- Registro puntuable "en blanco" para estudiantes que solo hicieron check-in.
- Puntuación estructurada contra los ítems de la pauta / rúbrica multinivel,
  inter-rater, doble corrección ciega, comentarios por ítem.
- Mover el puntaje de la corrección diferida a `EvaluatorRecord`.
- Corrección después de `cerrado` (el cierre sigue consolidando y congelando).

## Decisiones de diseño

### 1. Rol nuevo `corrector`, no reutilizar `evaluador`

El rol `evaluador` tiene semántica fija en muchos puntos: una sola estación
principal (`normalize_station_ids` trunca a `[:1]`, `ensure_primary_station_assignment`),
presencial, con ventana de tiempo, aparece en `/evaluator` y en la lógica de
kiosco, y gatea `requires_evaluator` en Validación. Sobrecargarlo arriesga
regresiones en el día del examen.

`corrector` es un rol nuevo que **reusa el patrón `station_ids`** de `evaluador`
pero:

- admite **varias estaciones** (un docente corrige las 3 estaciones escritas);
- da acceso a `/grading`, no a `/evaluator`;
- no tiene ventana de tiempo ni check-in;
- es **delegable** por `coeditor_docente` / `coordinador_operativo` igual que
  `evaluador` y `cronometrador`.

La restricción `UniqueConstraint(ecoe_event_id, email)` de `StaffAssignment` se
mantiene: una persona tiene un rol por evento. Si alguien debe corregir y además
es coeditor, se le da `ECOEPermission` de coeditor + no necesita `corrector`
(coeditor ya entra a `/grading`).

### 2. Flag explícito `requires_deferred_grading`

En vez de deducir "necesita corrector" de "el formulario tiene una `short_text`
con puntaje", se agrega un switch explícito en el Constructor, junto a los otros
("Evaluador presencial", "Formulario del estudiante", …). Explícito porque es
configuración de integridad del examen y porque habilita la Fase 2 (corrección
diferida de estaciones sin formulario).

**Regla de validez en Fase 1:** `requires_deferred_grading = true` exige
`requires_student_form = true` y al menos una pregunta de corrección manual con
puntaje. (En Fase 2 se relaja para permitir estaciones sin formulario.)

### 3. El puntaje sigue en `StudentResponse`

La corrección diferida sigue usando `apply_manual_scores` sobre `StudentResponse`.
No se mueve a `EvaluatorRecord`: evita colisiones con la constraint
`(ecoe_event_id, station_id, student_id, mode)`, evita tocar `compute_results` en
la parte del evaluador, y `compute_results` ya incorpora los `score_obtained`
resueltos del formulario.

### 4. Puntuación libre por pregunta (sin rúbrica) en Fase 1

`apply_manual_scores` se mantiene: número por pregunta manual, acotado a `[0, max]`.
Si la estación tiene una pauta asociada (`assessment_tool_id`), la pantalla la
muestra como referencia. La puntuación estructurada contra ítems es Fase 2.

### 5. La corrección ocurre antes de `cerrado`

`/grading` no gana gate de estado (sigue funcionando en cualquier estado del ECOE
salvo lo que ya impide el cierre). Pero **cerrar el ECOE con correcciones diferidas
pendientes muestra una advertencia explícita** en el modal de cierre (no bloquea:
el cierre operativo del día del examen manda). El texto sale de un contador nuevo
en la validación.

## Modelo de datos y migración

Una sola migración Alembic:

- `stations.requires_deferred_grading` — `Boolean`, `nullable=False`,
  `server_default = false`.
- `station_bank.requires_deferred_grading` — igual (para que el banco lo preserve).

`corrector` es un valor de string en `staff_assignments.role_code`; no requiere
cambio de schema.

Verificar la migración desde base limpia en SQLite y Postgres:

```bash
cd backend
DATABASE_URL=sqlite:////tmp/ecoe_alembic_check.db SECRET_KEY=test-secret ENVIRONMENT=test AUTO_SEED_DEMO=false alembic upgrade head
TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q
```

## Cambios backend (por archivo)

| Archivo | Cambio |
|---|---|
| `app/models/enums.py` | `RoleCode.corrector = "corrector"`. |
| `app/models/entities.py` | `requires_deferred_grading` en `Station` y `StationBank`. |
| `alembic/versions/*` | Revisión nueva con las dos columnas. |
| `app/schemas/common.py` | `requires_deferred_grading: bool = False` en `StationCreate` y `StationBankBase`. `ecoe.py` DTO de detalle expone el campo. |
| `app/services/authorization.py` | `corrector` en `STAFF_SCOPED_ROLE_CODES`; en `ensure_staff_role_can_be_delegated` / `ensure_staff_assignment_can_be_managed` sumar `corrector` al set de roles limitados delegables. |
| `app/utils/helpers.py` | `normalize_station_ids` deja de truncar cuando el rol lo permite: nueva firma `normalize_station_ids(raw, *, single=True)` o helper `normalize_multi_station_ids`. La ruta staff pasa `single=False` para `corrector`. |
| `app/api/routes/staff.py` | Aceptar `corrector`: exigir ≥1 estación (como `evaluador`), pero no truncar; validar que cada `station_id` pertenece al ECOE. |
| `app/api/routes/invitations.py` | Igual tratamiento de `station_ids` para invitaciones con rol `corrector`. |
| `app/services/validation.py` | Bloques nuevos (ver abajo) y agregado `deferred_grading_ready` en `can_publish`. Contador `pending_deferred_grading_stations`. |
| `app/api/routes/grading.py` | `GRADING_ROLES += (corrector,)`. Si los roles efectivos del actor en el evento son solo `{corrector}`, filtrar `responses` a las estaciones de su `StaffAssignment`. Igual en `grade_response` (403 si la respuesta es de una estación fuera de su asignación). |
| `app/services/results.py` | En `build_traceability_report`, `missing_deferred_gradings` por estudiante = respuestas de estaciones `requires_deferred_grading` con `score_obtained is None`. No cambia `compute_results`. |
| `app/db/seed.py` | Marcar una estación demo como `requires_deferred_grading` + agregar un `StaffAssignment` rol `corrector`. |

### Bloques nuevos en `compute_ecoe_validation`

Para cada estación con `requires_deferred_grading`:

- si no `requires_student_form` o `question_count` manual == 0 →
  `"Marca corrección diferida, pero no tiene preguntas de corrección manual con puntaje."`
- si ningún `StaffAssignment` rol `corrector` la cubre en `station_ids` →
  `"No tiene corrector asignado para la evaluación diferida."`

Agregados:

- `corrector_assignments_ready` (todas las estaciones diferidas cubiertas) →
  entra en `can_publish`.
- `pending_deferred_grading_stations`: nº de estaciones diferidas con respuestas
  `score_obtained is None`. Se usa para la advertencia del modal de cierre.

## Cambios frontend (por archivo)

| Archivo | Cambio |
|---|---|
| `src/lib/routes.ts` | `RoleCode` += `"corrector"`. `NAV_ITEMS`: `/grading` `allowedFor` += `"corrector"`. `defaultRouteForRole("corrector") → "/grading"`. |
| `src/components/app-shell.tsx` | Tratar `corrector` como operador de pantalla acotada (como `evaluador`): redirigir a `/grading`, ocultar el resto del menú. |
| `src/lib/types.ts` | `requires_deferred_grading: boolean` en los dos tipos de estación. |
| `src/app/(app)/stations/builder/shared.tsx` | `capabilityConfig` += entrada `requiresDeferredGrading` con su `requirement`. `StationCapabilities` + `defaultCapabilities`. |
| `src/app/(app)/stations/builder/page.tsx` | Cablear el switch: `requires_deferred_grading` en los dos payloads, precarga desde `station`/plantilla, y bloqueo de guardado si está activo sin pregunta manual con puntaje. |
| `src/app/(app)/stations/page.tsx` | Badge "Corrección diferida" en la card. |
| `src/app/(app)/evaluators/page.tsx` | Rol `corrector` en el selector; el selector de estaciones pasa a **multi-selección** cuando el rol es `corrector`. |
| `src/app/(app)/grading/page.tsx` | Filtro por estación; para un `corrector` la lista ya viene acotada por el backend. Encabezado indica "Evaluación diferida". |
| `src/app/(app)/validation/page.tsx` | Mostrar los bloqueos nuevos. |
| Modal de cierre del ECOE (`ecoe-form` / status bar) | Si `pending_deferred_grading_stations > 0`, línea de advertencia en el resumen de cierre. |

## Cortes de commit

1. **Modelo + migración + rol.** Enum `corrector`, columnas, schema, migración,
   `normalize_station_ids` multi, helpers de delegación. Tests de migración
   (SQLite + Postgres) y de que `corrector` es asignable/delegable.
2. **Validación.** Bloques nuevos + `can_publish` + contador de pendientes. Tests
   en `test_validation_warnings.py`.
3. **`/grading` consciente del rol.** Filtro por `station_ids`, 403 fuera de
   asignación, `corrector` en `GRADING_ROLES`. Tests negativos en
   `test_grading.py` y `test_permissions_matrix.py`.
4. **Frontend.** Switch del Constructor, `routes.ts`, selector multi-estación en
   Evaluadores, filtro en Corrección, badges, advertencia de cierre. `npm run
   build`, `lint`, `test`.
5. **Semilla + trazabilidad + docs.** Estación demo diferida + corrector demo,
   `missing_deferred_gradings` en trazabilidad, actualizar `PROJECT_STATUS.md`,
   `NEXT_STEPS.md` y `P0_MATRIZ_PERMISOS.md`.

## Verificación / tests

Negativos obligatorios (AGENTS.md — cambios de permisos/auth):

- `corrector` del ECOE A no puede listar ni corregir respuestas del ECOE B (403).
- `corrector` no puede corregir una respuesta de una estación fuera de su
  `station_ids` (403).
- `corrector` no puede entrar a `/stations` (escritura), `/evaluator`, `/live`,
  `/students`, `/results` (403 backend + gating de nav).
- `coeditor_docente` / `coordinador_operativo` **pueden** asignar rol `corrector`;
  no pueden asignar `admin_ecoe` (ya cubierto) — extender el test de delegación.
- Estación con `requires_deferred_grading` sin corrector → blocker y
  `can_publish = false`.
- Estación con `requires_deferred_grading` sin formulario / sin pregunta manual
  con puntaje → blocker.

Positivos:

- `corrector` asignado a estación X corrige una respuesta pendiente → entra al
  consolidado (`compute_results`).
- Trazabilidad: estudiante con respuesta enviada y sin puntuar figura con
  `missing_deferred_gradings = 1` y no como `completo`.
- Cerrar el ECOE con pendientes: el cierre procede y la respuesta a validación
  reporta `pending_deferred_grading_stations > 0`.

## Impacto en la matriz de permisos

Fila nueva en `P0_MATRIZ_PERMISOS.md`:

| Rol | Alcance |
|---|---|
| `corrector` | Corrige respuestas de las estaciones de evaluación diferida que tiene asignadas dentro del ECOE. Sin acceso a configuración, live, estudiantes ni resultados. |

`corrector` entra en `STAFF_SCOPED_ROLE_CODES` y en los roles delegables por
coeditor/coordinador. No es un rol global.

## Fase 2 (anotada, fuera de alcance aquí)

- Entregables adjuntos por estudiante/estación (reusar `MediaAsset` o tabla nueva
  `StationDeliverable`) para corregir estaciones sin formulario.
- Registro puntuable en blanco por check-in confirmado.
- Puntuación estructurada contra `assessment_tool.items` en la corrección diferida
  (mismo renderer que la pantalla Evaluador), con comentario por ítem.
- Opcional: doble corrección ciega e índice de acuerdo inter-rater.
