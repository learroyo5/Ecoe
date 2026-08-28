# Hallazgos — auditor-admin-ecoe · 2026-08-28

Primera pasada, profundidad media-alta. Recorrido de un editor de evento desde
crear un ECOE hasta publicarlo: crear, configurar estaciones / instrumentos /
plantillas, asignar staff / permisos / invitaciones, y transiciones de estado
hasta `publicado`.

Método: API in-process con `TestClient` (fixtures de `backend/tests/conftest.py`,
SQLite) + lectura del frontend. Tests exploratorios `test_audit_admin_*` escritos
y borrados al terminar. No se levantó servidor ni Docker.

## Resumen

| Severidad | N.º |
|---|---|
| bloqueante | 0 |
| alta | 1 |
| media | 3 |
| baja | 3 |
| cosmético | 0 |

**Verificado OK (sin hallazgo):**
- El grafo `ALLOWED_STATUS_TRANSITIONS` (`backend/app/services/validation.py:383`)
  coincide **exactamente** con `STATUS_TRANSITIONS` de
  `frontend/src/components/ecoe-form.tsx:269`, incluidos todos los retrocesos
  (`en_configuracion→borrador`, `pilotaje_validado→en_pilotaje`,
  `publicado→pilotaje_validado`, `archivado→borrador`, etc.).
- La ruta feliz completa funciona íntegra vía API: crear ECOE → `en_configuracion`
  → crear estación + instrumento + asignar evaluador + cargar estudiante →
  `listo_para_pilotaje` → `en_pilotaje` → pilotaje estación + circuito →
  `pilotaje_validado` → `publicado` (HTTP 200 en cada paso).
- Los gates de escritura (`ensure_submission_stage`) rechazan correctamente
  check-ins / evaluaciones mientras el evento está `publicado` pero no
  `en_ejecucion` (409).

---

### H-admin-ecoe-1 · "Duplicar ECOE" es inaccesible desde la UI
- **Rol / pantalla**: admin_ecoe / admin_global · `/ecoe` y `/ecoe/[id]`
- **Severidad**: alta
- **Tipo**: inconsistencia backend/UI
- **Evidencia**:
  - `frontend/src/app/(app)/ecoe/page.tsx:150` —
    `disabled={!ecoeEvent || user?.role !== "admin_ecoe"}`
  - `frontend/src/app/(app)/ecoe/[id]/page.tsx:143-147` — el botón "Duplicar"
    solo hace `router.push('/ecoe?id=...')`, no abre el modal.
  - Backend `POST /api/ecoe/{id}/duplicate` responde 200 para admin_global y
    para admin de evento (test exploratorio: `DUPLICATE backend: 200 Copia audit`).
  - `docs/architecture/P0_MATRIZ_PERMISOS.md:37` — "Duplicar ECOE | Si" para
    `admin_ecoe`.
- **Reproducción**:
  1. Login admin_global, ir a `/ecoe`.
  2. El botón "Duplicar ECOE" aparece **deshabilitado** (el usuario tiene
     `role === "admin_global"`, no `"admin_ecoe"`).
  3. Ir a `/ecoe/{id}`, clic en "Duplicar" → navega a `/ecoe` y ahí el botón
     sigue deshabilitado. Callejón sin salida.
- **Esperado vs. observado**: se espera poder duplicar un ECOE (existe el
  endpoint, lo pide la matriz de permisos); observado: ningún rol real llega al
  modal de duplicación. Solo un usuario cuyo **rol global** sea literalmente
  `admin_ecoe` (inexistente en el seed) lo vería habilitado.
- **Notas del auditor** (hipótesis, no vinculante): el check debería seguir el
  patrón del resto de pantallas:
  `user?.role === "admin_global" || eventRoles.includes("admin_ecoe")`
  (ver `evaluators/page.tsx:14`, `instruments/page.tsx:14`). Y el botón de
  `/ecoe/[id]` debería abrir el modal, no redirigir.

---

### H-admin-ecoe-2 · Invitar evaluador sin estación: la UI lo ofrece, el endpoint lo rechaza
- **Rol / pantalla**: admin_ecoe · `/evaluators`
- **Severidad**: media
- **Tipo**: inconsistencia backend/UI · fricción-UX
- **Evidencia**:
  - `frontend/src/app/(app)/evaluators/page.tsx:349` —
    `<option value="">Sin estación asignada por ahora</option>`
  - `evaluators/page.tsx:356-359` y `:131` (ayuda de import) — "Los evaluadores
    quedan sin estación; se asigna después en la tabla de abajo."
  - `backend/app/services/invitations.py:54-64` — `_validated_assignment` con
    `require_evaluator_station=True` (default) lanza 400.
  - `backend/app/api/routes/invitations.py:40` — `invite_event_member` llama
    `assign_or_invite_member` **sin** pasar `require_evaluator_station=False`.
  - `backend/app/api/routes/staff.py:279` — el import masivo **sí** pasa
    `require_evaluator_station=False`.
  - Test exploratorio: `INVITE evaluador sin estacion: 400 {"detail":"El
    evaluador debe tener una estación principal asignada"}`.
- **Reproducción**: `/evaluators` → formulario → correo nuevo, rol Evaluador,
  estación "Sin estación asignada por ahora" → Guardar → error 400.
- **Esperado vs. observado**: la opción y el texto de ayuda prometen asignación
  diferida; el formulario la rechaza. El import del mismo rol en la misma
  pantalla sí la permite → dos caminos con reglas distintas y copy idéntico.
- **Notas del auditor**: o `invite_event_member` pasa
  `require_evaluator_station=False` (coherente con el import), o la UI quita la
  opción "Sin estación" y el texto para el alta individual.

---

### H-admin-ecoe-3 · Blocker fantasma "No existe una sesión en vivo" antes de publicar
- **Rol / pantalla**: admin_ecoe · `/publication` y `/validation`
- **Severidad**: media
- **Tipo**: inconsistencia backend/UI · fricción-UX
- **Evidencia**:
  - `backend/app/services/validation.py:328` — la lista `blockers` incluye
    incondicionalmente `"No existe una sesión en vivo creada para la ejecución
    real."` cuando `has_live_session == 0`.
  - La `LiveSession` **solo se crea al ejecutar la transición a `publicado`**
    (`validation.py:433-444`), nunca antes.
  - `can_publish` (`validation.py:278`) **no** depende de `has_live_session`, así
    que el botón Publicar sí se habilita.
  - `frontend/src/app/(app)/publication/page.tsx:52,93,96-106` — muestra
    "Listo para publicar" + botón habilitado **y** una caja roja de bloqueo al
    mismo tiempo.
  - Test exploratorio:
    `validation: {can_publish: True, blockers: ['No existe una sesión en vivo
    creada para la ejecución real.']}`.
- **Reproducción**: completar toda la configuración + un pilotaje, ir a
  `/publication` estando en `pilotaje_validado` → "Listo para publicar" con una
  alerta roja de bloqueo irresoluble.
- **Esperado vs. observado**: esperado — si `can_publish` es true no debería
  mostrarse ningún bloqueo; observado — un bloqueo permanente que el usuario no
  puede resolver y que no bloquea nada.
- **Notas del auditor**: la lista `blockers` mezcla prerequisitos de tres etapas
  (pilotaje, publicación, inicio de ejecución en vivo). El blocker de
  `has_live_session` pertenece a `can_start_live`, no a la vista de publicación.
  Separar `blockers` por etapa, o excluir el de sesión en vivo cuando el estado
  aún es `< publicado`.

---

### H-admin-ecoe-4 · Instrumentos / plantillas / pacientes son de solo creación (sin editar ni borrar)
- **Rol / pantalla**: admin_ecoe / coeditor_docente · `/instruments`, `/templates`,
  `/simulated-patient`, `/stations/builder`
- **Severidad**: media
- **Tipo**: fricción-UX · inconsistencia con especificación · dato
- **Evidencia**:
  - `backend/app/api/routes/stations.py:54-129` — `/templates`, `/instruments`,
    `/simulated-patients` exponen **solo GET y POST**. No hay PUT/PATCH/DELETE
    (contraste: `/station-bank` sí tiene PUT + PATCH).
  - `docs/architecture/P0_MATRIZ_PERMISOS.md:44,70` — "admin/coeditor pueden
    modificar" instrumentos/plantillas/pacientes.
  - `frontend/src/app/(app)/stations/builder/page.tsx:363-382` —
    `saveInstrumentDraft` siempre hace `api.createInstrument` (POST). Cada edición
    de una pauta genera una `AssessmentTool` nueva y re-apunta la estación.
  - Los bancos son institucionales (no tienen `ecoe_event_id`): las pautas
    huérfanas quedan visibles en el selector de instrumentos de **todos** los
    eventos, sin forma de eliminarlas.
- **Reproducción**: crear una pauta con un criterio mal escrito o con puntaje
  incorrecto → no hay endpoint para corregirla. En el builder, editar la pauta y
  volver a guardar → aparece una segunda pauta; la anterior permanece en el banco.
- **Esperado vs. observado**: esperado (según matriz) — poder modificar una
  pauta; observado — solo se puede crear otra. Acumulación de instrumentos
  muertos en el banco compartido.
- **Notas del auditor**: agregar `PUT/DELETE /instruments/{id}` (con guarda: no
  permitir borrar/mutar si ya hay `StudentResponse`/`EvaluatorRecord` que lo
  referencian en un evento cerrado). Alternativamente, versión copy-on-write
  explícita en el builder.

---

### H-admin-ecoe-5 · Campos `total_stations` / `total_students` son decorativos
- **Rol / pantalla**: admin_ecoe · `/ecoe` (formulario ECOE)
- **Severidad**: baja
- **Tipo**: fricción-UX · dato
- **Evidencia**:
  - `frontend/src/components/ecoe-form.tsx:168-178` — campos "Total de
    estaciones" (min 1) y "Total de estudiantes" presentados como configuración
    estructural, con validación de mínimos en `validateECOEPayload:71-74`.
  - `backend/app/services/validation.py` — `compute_ecoe_validation` usa
    **conteos reales de filas** (`station_count`, `students_count`), nunca
    `ecoe_event.total_stations` / `total_students`. Solo `total_groups` se
    verifica (`can_start_live`, `validation.py:288`).
- **Esperado vs. observado**: el usuario que pone "Total de estaciones = 8"
  espera que eso genere/limite estaciones o alimente la validación; no hace nada.
- **Notas del auditor**: renombrar a "estimado" con ayuda explícita, o
  eliminarlos y derivar de las filas reales.

---

### H-admin-ecoe-6 · Código muerto: selector de estado libre y `api.createStaff`
- **Rol / pantalla**: admin_ecoe · componentes ECOE
- **Severidad**: baja
- **Tipo**: fricción-UX (mantenibilidad)
- **Evidencia**:
  - `frontend/src/components/ecoe-form.tsx:98,199-212` — `ECOEFormFields` acepta
    `includeStatus` que renderiza un `<select>` con los 9 estados **sin guardas
    de transición**. `grep includeStatus` → nunca se pasa `true` en ninguna
    pantalla. Si alguna vez se activa, ofrece saltos que el backend rechazará.
  - `frontend/src/lib/api.ts:163` — `createStaff` (`POST /api/staff`) no lo llama
    ninguna pantalla; el alta de equipo va toda por `/event-members/invite`. El
    endpoint `create_staff` sigue expuesto y exige cuenta preexistente
    (`ensure_matching_operational_user`), a diferencia del camino real que sabe
    invitar.
- **Notas del auditor**: eliminar `includeStatus` y el `<select>` de estados;
  eliminar `api.createStaff` o el endpoint si no hay consumidor previsto.

---

### H-admin-ecoe-7 · `ecoe_event_id` como query param en creación de instrumentos/plantillas/pacientes
- **Rol / pantalla**: admin_ecoe · API `/instruments`, `/templates`,
  `/simulated-patients`
- **Severidad**: baja
- **Tipo**: inconsistencia backend/UI (forma de API)
- **Evidencia**:
  - `backend/app/api/routes/stations.py:60-64, 84-90, 116-121` — el POST recibe
    `ecoe_event_id: int` como **query param**, no en el body.
  - Todos los demás POST del dominio (`/stations`, `/staff`, `/students`,
    `/pilotage`, `/event-members/invite`) lo llevan **en el body**.
  - El frontend lo maneja bien (`api.ts:251` pasa `?ecoe_event_id=`), pero
    `ecoe_event_id` solo se usa para el gate de permiso y luego se descarta (el
    recurso creado es institucional, sin FK a evento).
- **Notas del auditor**: unificar a body para consistencia, o documentar por qué
  estos tres son distintos.
