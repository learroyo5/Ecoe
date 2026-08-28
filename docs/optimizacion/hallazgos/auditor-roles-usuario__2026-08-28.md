# Hallazgos — auditor-roles-usuario · 2026-08-28

Primera pasada, profundidad media-alta. Acceso + autorización + journey de cada
rol: `admin_global`, editor de evento (`admin_ecoe` por `ECOEPermission`),
co-editor (`coeditor_docente`), `coordinador_operativo`, `cronometrador`,
`evaluador`, `corrector`, `estudiante`, `miembro`.

Método: API in-process con `TestClient` (fixtures de `backend/tests/conftest.py`,
SQLite) + lectura del frontend. Tests exploratorios `test_audit_roles_*` escritos
y borrados al terminar. No se levantó servidor ni Docker.

## Resumen

| Severidad | N.º |
|---|---|
| bloqueante | 0 |
| alta | 0 |
| media | 1 |
| baja | 3 |
| cosmético | 0 |

Hallazgos de seguridad (🔒): **0**.

**Verificado OK (sin hallazgo):**

- **Puerta gruesa vs. puerta fina**: *todos* los endpoints con alcance de evento
  combinan `require_roles(...)` (gruesa) con `ensure_event_access(...)` (fina).
  Se revisó ruta por ruta (`grep` sobre `app/api/routes/*.py`): no hay ningún
  endpoint operativo que quede solo con la puerta gruesa. Los recursos
  institucionales (`/users`, `/ecoe` POST, `/ecoe/{id}/admins`) usan
  `require_global_roles`, que ignora deliberadamente los grants por evento.
- **No hay fuga institucional→ECOE ni ECOE→institucional**: un `admin_ecoe`
  delegado por `ECOEPermission` recibe 403 en `/api/users` y en `POST /api/ecoe`
  (`test_only_global_admin_manages_users_and_delegates_event_admin`, verde). Un
  `ECOEPermission` nunca alcanza gestión de cuentas.
- **`require_roles` con `ECOEPermission`/`StaffAssignment` de otro evento**: pasa
  la puerta gruesa pero `ensure_event_access` del evento objetivo lo rechaza
  (patrón cross-event, cubierto por `test_authorization_regressions.py`).
- **Revocación**: `token_version` corta sesiones vivas al desactivar cuenta o
  cambiar contraseña, y reactivar NO resucita el token viejo
  (`test_auth_revocation.py`, verde). `activate_invitation` bumpea
  `token_version`, así que un reinicio de acceso invalida las sesiones previas.
- **Invitaciones**: token de un solo uso, solo se guarda su SHA-256, expira,
  reemitir invalida la anterior, cuenta `pending`/`suspended` no puede iniciar
  sesión ni tomar un token viejo (`test_event_member_invitations.py`,
  `test_event_access_reset.py`, verdes).
- **Delegación acotada**: `coeditor_docente`/`coordinador_operativo` solo pueden
  delegar `evaluador`/`corrector`/`cronometrador`
  (`ensure_staff_role_can_be_delegated`); intentar delegar
  `coeditor_docente`/`coordinador_operativo` da 403
  (`test_coordinator_cannot_delegate_content_or_coordinator_roles`, verde).
- **`corrector`**: `GET/POST /api/grading/*` es lo único que alcanza, y acotado a
  las estaciones de su `StaffAssignment` (`_corrector_station_scope`). NAV solo
  le muestra "Corrección"; `defaultRouteForRole("corrector") → /grading`.
- **`cronometrador`**: matriz y código coinciden (live HTTP/WS + incidencias;
  nada de estudiantes/estaciones/resultados).
- `python3 -m pytest tests/test_permissions_matrix.py tests/test_authorization_regressions.py tests/test_auth_revocation.py tests/test_event_member_invitations.py tests/test_event_access_reset.py` → **54 passed**.

---

### H-roles-usuario-1 · Las pantallas de estaciones expulsan por rol global, no por rol de evento
- **Rol / pantalla**: multi-rol (cuenta global `evaluador` que además es
  `coeditor_docente`/`admin_ecoe` en un evento) · `/stations`,
  `/stations/builder`, `/station-bank`
- **Severidad**: media
- **Tipo**: permiso · inconsistencia backend/UI
- **Evidencia**:
  - `frontend/src/app/(app)/stations/page.tsx:74-79` —
    `if (user?.role === "evaluador") { router.replace(...); }` y
    `if (user?.role === "evaluador") return null;`
  - `frontend/src/app/(app)/stations/builder/page.tsx:613-616` y `:697` — idéntico.
  - `frontend/src/app/(app)/station-bank/page.tsx:35-40` — idéntico.
  - Backend: para una cuenta con `User.role.code == "evaluador"` +
    `ECOEPermission(role_code="coeditor_docente")` en el evento,
    `GET /api/stations/{id}` → 200, `POST /api/stations` → 200,
    `PUT /api/stations/{id}` → 200 (test exploratorio
    `test_multirole_global_evaluator_can_manage_stations_via_backend`, verde;
    `/api/auth/me` devuelve `role: "evaluador"`).
  - `docs/architecture/P0_MATRIZ_PERMISOS.md:82` — "Las restricciones de
    evaluador/estudiante usan **roles efectivos del ECOE, no el rol global** de
    la cuenta." Estos guards violan ese principio.
  - Contraste: el `Sidebar` (`components/sidebar.tsx:12-19`) y las páginas de
    contenido (`instruments/page.tsx:14`, `templates/page.tsx:78`,
    `station-bank/page.tsx:22`) sí usan `eventRoles`. Solo estos tres guards de
    redirección quedaron con `user?.role`.
- **Reproducción**:
  1. Cuenta cuyo rol global es `evaluador`, con `ECOEPermission` o
     `StaffAssignment` de `coeditor_docente` en el ECOE seleccionado.
  2. Navegar a `/stations` o `/stations/builder` → `router.replace("/evaluator")`
     inmediato; la pantalla nunca se muestra.
  3. El backend habría aceptado cualquier lectura/edición de estaciones.
- **Esperado vs. observado**: esperado — el multi-rol (soportado explícitamente
  por `get_user_event_roles`) puede editar estaciones del evento donde es
  coeditor; observado — expulsado por su rol global antes de renderizar.
- **Notas del auditor** (hipótesis): reemplazar el check por el patrón ya usado
  en el resto de la app, p. ej.
  `const canEditStations = user?.role === "admin_global" || eventRoles.some(r => r === "admin_ecoe" || r === "coeditor_docente")`
  y redirigir solo si `!canEditStations`. Mismo patrón que H-admin-ecoe-1.

---

### H-roles-usuario-2 · La matriz promete "Lectura" de instrumentos/plantillas a evaluador y estudiante; el endpoint responde 403
- **Rol / pantalla**: evaluador, estudiante · `/api/templates`, `/api/instruments`,
  `/api/simulated-patients`, `/api/station-bank`
- **Severidad**: baja
- **Tipo**: dato (discrepancia matriz ↔ código)
- **Evidencia**:
  - `docs/architecture/P0_MATRIZ_PERMISOS.md:44` —
    `| Instrumentos/plantillas/pacientes | Si | Si | Lectura | No | Lectura | Lectura necesaria |`
    (columnas: Admin ECOE, Coeditor, Coordinador, Cronometrador, **Evaluador**,
    **Estudiante**).
  - `backend/app/api/routes/stations.py:50` —
    `CONTENT_MANAGER_ROLES = ("admin_ecoe", "coeditor_docente", "coordinador_operativo")`;
    los GET (`list_templates`, `list_instruments`, `list_patients`,
    `list_station_bank`) llaman
    `ensure_event_access(db, user, ecoe_event_id, *ADMIN_EVENT_ROLE_CODES)` →
    evaluador y estudiante reciben **403**.
  - El comentario `stations.py:46-49` lo hace a propósito: "Students/evaluators
    receive only what they need through `/student/access` and
    `/evaluator/context`."
- **Esperado vs. observado**: no es un bug de seguridad (el dato llega por los
  endpoints de contexto), pero la celda de la matriz induce a error: sugiere que
  el recurso genérico es legible por esos roles cuando no lo es.
- **Notas del auditor**: corregir la matriz — marcar esas celdas como
  "Via /evaluator/context" y "Via /student/access" en vez de "Lectura" /
  "Lectura necesaria", o añadir una nota al pie como la que ya existe para
  `corrector` (línea 59).

---

### H-roles-usuario-3 · Redirección de aterrizaje por rol global ignora los roles de evento
- **Rol / pantalla**: multi-rol · `/login`, `/` (middleware)
- **Severidad**: baja
- **Tipo**: fricción-UX
- **Evidencia**:
  - `frontend/src/app/login/page.tsx:64-70` — tras login,
    `if (user.role === "evaluador") router.push("/evaluator")` y
    `if (user.role === "estudiante") router.push("/student")`, usando el rol
    global.
  - `frontend/src/middleware.ts:68-69` — `"/" → defaultRouteForRole(session.role)`
    (rol del JWT = rol global).
  - Una cuenta cuyo rol global es `evaluador` pero que es
    `coeditor_docente`/`coordinador_operativo` en su evento aterriza siempre en
    `/evaluator`, no en `/dashboard`.
- **Esperado vs. observado**: recuperable (el sidebar sí muestra los ítems de
  coeditor porque usa `eventRoles`), pero el usuario debe navegar a mano tras
  cada login. Para el caso mono-rol (el 99%) el comportamiento es correcto.
- **Notas del auditor**: baja prioridad; el arreglo real exige que el front
  conozca los `eventRoles` antes de decidir el aterrizaje, lo que hoy ocurre
  después de elegir el evento. Aceptable dejarlo si H-roles-usuario-1 se corrige.

---

### H-roles-usuario-4 · Miembro sin evento accesible ve un error genérico en vez de estado vacío
- **Rol / pantalla**: `miembro` / evaluador recién activado sin asignación activa
  · cualquier pantalla `(app)`
- **Severidad**: baja
- **Tipo**: fricción-UX
- **Evidencia**:
  - `frontend/src/lib/auth.tsx:40-44` — `eventId` arranca en `1` (o el último de
    `localStorage`).
  - `auth.tsx:61-64` — solo se corrige `eventId` si `list.length > 0`; si la
    lista viene vacía, `eventId` sigue en `1`.
  - `auth.tsx:74-92` — `loadECOEData` llama `api.ecoe(1)` → 403 →
    `setLoadError("No se pudo cargar el ECOE activo: ...")`.
  - `list_accessible_ecoe_events` (`services/authorization.py:127`) devuelve `[]`
    para una cuenta sin `ECOEPermission`/`StaffAssignment`/`Student`.
- **Reproducción**: activar una invitación cuyo `StaffAssignment` luego se
  elimina, o una cuenta `miembro` creada por `admin_global` sin asignarla a
  ningún evento → login → pantalla de error rojo en vez de "aún no tienes
  eventos asignados".
- **Esperado vs. observado**: esperado — estado vacío explicativo; observado —
  mensaje de error técnico. Caso borde (el flujo normal de invitación crea el
  `StaffAssignment` junto con la cuenta).
- **Notas del auditor**: en `loadECOEList`, si `list.length === 0` mostrar un
  empty-state dedicado y no intentar `loadECOEData`.

---

## Cruces con la pasada anterior (auditor-admin-ecoe)

- **H-admin-ecoe-1** ("Duplicar ECOE" inaccesible por `user?.role !== "admin_ecoe"`):
  **confirmado** desde el ángulo de roles. Ningún rol global del seed es
  literalmente `admin_ecoe` (`models/enums.py:7` lo define, pero
  `db/seed.py:74-80` no asigna ese código como rol de cuenta a nadie: el admin
  del seed es `admin_global`). El botón queda deshabilitado **para todos**,
  incluido `admin_global`. Backend `POST /api/ecoe/{id}/duplicate` responde 200
  para `admin_global` y para un `admin_ecoe` delegado por `ECOEPermission` (test
  exploratorio, verde). No re-fileado; se suma esta evidencia.
- **Patrón "gating por rol global"**: además de Duplicar, aparece en los tres
  guards de estaciones (H-roles-usuario-1) y en la redirección de login
  (H-roles-usuario-3). El resto de la app (sidebar, páginas de contenido,
  `/evaluators`) ya migró al patrón `eventRoles`.
