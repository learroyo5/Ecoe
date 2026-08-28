# OPT-3 · Autorización de UI por rol de evento, no por rol global

**Severidad: alta.** Origen: H-admin-ecoe-1 (alta), H-roles-usuario-1 (media), H-roles-usuario-3 (baja).

## Problema

Varias pantallas comprueban `user?.role` (rol **global** del JWT) en vez de `eventRoles` (rol efectivo por
evento), contra el principio de `docs/architecture/P0_MATRIZ_PERMISOS.md:82` ("las restricciones usan roles
efectivos del ECOE, no el rol global"). El resto de la app ya usa `eventRoles`. Consecuencia: **funcionalidad
que el backend permite queda bloqueada en la UI**.

- **"Duplicar ECOE" inaccesible para todos** (`ecoe/page.tsx:150`):
  `disabled={!ecoeEvent || user?.role !== "admin_ecoe"}`. Ningún rol de cuenta del seed es literalmente
  `admin_ecoe` (el admin es `admin_global`; `admin_ecoe` solo existe como rol delegado por `ECOEPermission`).
  El endpoint `POST /api/ecoe/{id}/duplicate` responde 200 a `admin_global` y a un `admin_ecoe` delegado.
  Además `ecoe/[id]/page.tsx:143-147` — el botón "Duplicar" solo hace `router.push('/ecoe?id=...')`, nunca
  abre el modal → callejón sin salida.
- **Guards de `/stations*` expulsan por rol global** (`stations/page.tsx:74-79`,
  `stations/builder/page.tsx:613-616,697`, `station-bank/page.tsx:35-40`):
  `if (user?.role === "evaluador") router.replace("/evaluator")`. Una cuenta cuyo rol global es `evaluador`
  pero que es `coeditor_docente`/`admin_ecoe` en el evento es expulsada antes de renderizar; el backend habría
  aceptado la lectura/edición.
- **Aterrizaje post-login por rol global** (`login/page.tsx:64-70`, `middleware.ts:68-69`):
  una cuenta multi-rol siempre aterriza en `/evaluator` o `/student`. Recuperable (el sidebar usa
  `eventRoles`); baja prioridad.

## Causa raíz

Migración incompleta al patrón `eventRoles`. `frontend/src/components/sidebar.tsx:12-19`, `instruments/page.tsx:14`,
`templates/page.tsx:78`, `evaluators/page.tsx:14` ya usan `eventRoles`; estos guards quedaron rezagados.

## Cambio propuesto

- **Frontend únicamente.**
  - `ecoe/page.tsx`: `disabled={!ecoeEvent || !(user?.role === "admin_global" || eventRoles.includes("admin_ecoe"))}`.
  - `ecoe/[id]/page.tsx`: el botón "Duplicar" abre el modal de duplicación (mismo estado local que en
    `/ecoe`), no redirige. Si el modal solo vive en `/ecoe`, o bien se comparte el componente, o bien se
    mantiene la navegación pero llevando un query flag `?duplicate=1` que `/ecoe` interpreta para abrir el
    modal automáticamente.
  - `stations/page.tsx`, `stations/builder/page.tsx`, `station-bank/page.tsx`: reemplazar el check por
    ```ts
    const canEditStations =
      user?.role === "admin_global" ||
      eventRoles.some(r => r === "admin_ecoe" || r === "coeditor_docente");
    ```
    y redirigir/mostrar "acceso restringido" solo si `!canEditStations` **y** los `eventRoles` ya cargaron
    (evitar un flash de redirección mientras `eventRoles` es `undefined`).
  - (Opcional, H-roles-usuario-3) `login/page.tsx`: si tras elegir evento los `eventRoles` incluyen un rol de
    edición, aterrizar en `/dashboard` en vez de `/evaluator`. Requiere que el front conozca `eventRoles`
    antes de decidir — hoy ocurre después de elegir evento. **Se puede dejar fuera de este plan** si los
    guards de estaciones se corrigen (el usuario llega por el sidebar).
- **Backend**: sin cambios. `ensure_event_access` ya es la autoridad y ya acepta estas operaciones.
- **Migración**: no.
- **Máquina de estados**: no.

## Tests

No hay hueco de seguridad backend que cubrir con negativos (el backend ya valida correctamente). Aun así:

- `test_duplicate_ecoe_allowed_for_global_admin` — backend, confirma 200 para `admin_global` (si no existe ya
  en `test_permissions_matrix.py`).
- Frontend (vitest): `ecoe/page` habilita "Duplicar ECOE" cuando `user.role === "admin_global"`.
- Frontend (vitest): `stations/page` **no** redirige cuando `user.role === "evaluador"` pero
  `eventRoles` incluye `coeditor_docente`.
- e2e (`golden-flow`): el paso de duplicación como `admin_global` deja de estar bloqueado (si el flujo lo
  ejercita).

## Riesgos / alcance

- Riesgo de flash de contenido: hoy el guard redirige inmediatamente; con `eventRoles` hay un instante en que
  son `undefined`. Renderizar un spinner/estado neutro hasta que carguen.
- Cambiar el destino de aterrizaje (parte opcional) podría sorprender a usuarios mono-rol — por eso se
  recomienda dejarlo fuera salvo pedido explícito.
- Solo frontend, sin migración, sin cambio de API → commit acotado y reversible.

## Verificación

- [ ] `cd frontend && npm run lint && npm run build`
- [ ] `cd frontend && npm test`
- [ ] `cd backend && python3 -m pytest tests/test_permissions_matrix.py -v` (si se añade el test backend)
- [ ] Confirmación visual del usuario: `admin_global` puede duplicar un ECOE de punta a punta.

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-28
- Aprobado por usuario: ⬜ pendiente
