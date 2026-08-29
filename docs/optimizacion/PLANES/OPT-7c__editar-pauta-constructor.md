# OPT-7c · Modo "editar esta pauta" en el Constructor de estaciones

**Severidad: baja–media.** Origen: OPT-7 §Decisión 5 (pendiente marcado
"invasivo" por el implementador — ver `PLANES/OPT-7__crud-instrumentos.md:307-310`).
Follow-up **solo frontend** de OPT-7 (ya en `main` @ `b297df5`).

## Problema

OPT-7 dio CRUD real a `AssessmentTool` en `/instruments` (`PATCH /api/instruments/{id}`
in-place por `AssessmentItem.id`, gate `EDIT_BLOCKING_STATUSES`). Pero el
**Constructor de estaciones sigue ensuciando el banco**: cuando el diseñador
quiere corregir una errata de la pauta desde el wizard, el único camino es
rehacerla en modo "crear" → **POST de una `AssessmentTool` nueva** + re-apuntar la
estación → la pauta vieja queda huérfona en el `<select>` de todos los eventos.

Verificado en el código actual:

- `frontend/src/app/(app)/stations/builder/shared.tsx:55` —
  `AssessmentMode = "existing" | "create"` (dos modos, no hay "editar").
- `frontend/src/app/(app)/stations/builder/page.tsx:369-388` —
  `saveInstrumentDraft` **siempre** hace `api.createInstrument` (POST), setea el
  id nuevo y vuelve a modo `"existing"`.
- `page.tsx:343-367` — `buildInstrumentPayload` arma `{name, tool_type,
  max_score, items[]}` **sin `id`** por ítem.
- `page.tsx:495-568` — `applyStationLikeData` (carga una estación en el wizard):
  `:525` `setAssessmentMode("existing")`, `:549` guarda
  `selectedAssessmentToolId`, `:550` `setInstrumentDraft(defaultInstrumentDraft)`
  → **nunca carga los ítems del tool referenciado en el editor**.
- `page.tsx:634-648` — efecto que en modo `"create"` recalcula `form.max_score`
  como suma de `score_per_item`.
- `page.tsx:842-851, 1068-1071` — los dos handlers de guardado de estación llaman
  `saveInstrumentDraft` sólo si `assessmentMode === "create"`.
- `instrument-step.tsx:120-145` — los dos botones de modo (`existing` / `create`);
  `:146` render condicional; `:176+` editor de pauta; `:186-195` "cancelar
  creación" → vuelve a `existing`.
- `instrument-step.tsx:64` — prop `saveInstrumentDraft: () => Promise<Record<string, unknown>>`.

Backend ya listo (OPT-7): `GET /api/instruments/{id}?ecoe_event_id=` devuelve el
tool serializado **con `items` (cada uno con su `id`)** y `reference_count`
(`stations.py:116-128`, `serialize_instrument`
`services/instruments.py:240-260`); `PATCH /api/instruments/{id}` opera in-place
preservando `AssessmentItem.id` y responde **409** si el tool lo usa un ECOE en
`en_pilotaje`/`publicado`/`en_ejecucion`/`cerrado`/`archivado`
(`services/instruments.py:110-129`). `api.instrument` / `api.updateInstrument` ya
existen en `frontend/src/lib/api.ts:302-307`.

## Causa raíz

Puramente de UI: el wizard nunca modeló "editar la pauta existente en sitio". Los
endpoints que lo permiten ya están; falta cablearlos.

## Cambio propuesto

**Solo frontend. Sin migración. Sin endpoints nuevos** (consume
`GET`/`PATCH /api/instruments/{id}`, ya existentes).

### 1 · `shared.tsx` — tercer modo

- `AssessmentMode = "existing" | "create" | "edit"` (`shared.tsx:55`).
- El snapshot builder (`shared.tsx:201-233`, usado para el diffing de cambios sin
  guardar) ya incluye `assessmentMode`, `selectedAssessmentToolId` e
  `instrumentDraft` — al agregar `"edit"` el snapshot lo captura sin cambios de
  forma. Verificar que `createBuilderSnapshot` serializa `instrumentDraft.items[].id`
  (agregar el campo si el tipo `InstrumentDraftItem` no lo tiene).

### 2 · `page.tsx` — cargar los ítems del tool al abrir una estación

En `applyStationLikeData` (`page.tsx:495-568`), cuando
`station.assessment_tool_id` está poblado:

- disparar `api.instrument(eventId, Number(station.assessment_tool_id))` (async;
  hoy `applyStationLikeData` es síncrono → extraer la carga a un `useEffect` que
  observe `selectedAssessmentToolId`, o hacer `applyStationLikeData` async y
  await-earlo desde el efecto de `page.tsx:650-659`).
- guardar el tool cargado en estado nuevo `loadedTool` (con `items[].id`,
  `reference_count`).
- **no** cambiar el modo automáticamente: sigue entrando en `"existing"`
  (`:525`), pero ahora con los ítems disponibles para el modo `"edit"`.

### 3 · `instrument-step.tsx` — ofrecer "Editar esta pauta"

- Tercer botón de modo, **visible sólo si** `selectedAssessmentToolId` está
  seteado y hay `loadedTool`.
- "Editabilidad": el cliente no puede saber con certeza el estado de todos los
  ECOE que referencian el tool (el `GET/{id}` sólo trae `reference_count`, no los
  `event_statuses`). Estrategia:
  - `reference_count === 0` → seguro editable.
  - `reference_count > 0` → **optimista**: se ofrece "Editar"; si el `PATCH`
    devuelve **409**, se captura y se muestra el mensaje del backend
    ("…lo usa una estación de un ECOE en etapa avanzada… Duplica la pauta si
    necesitas una versión corregida") + se ofrece un botón "Crear copia" que
    cambia a modo `"create"` con los ítems ya precargados (POST + re-apuntar,
    flujo actual).
  > Mejora opcional fuera de alcance (backend, ~XS): que `GET /api/instruments/{id}`
  > devuelva `editable: bool` + `blocking_events: [...]` reusando
  > `ensure_tool_editable` sin lanzar. Deja el botón deshabilitado de entrada en
  > vez de fallar al guardar. Anotar como OPT-7d si el UX optimista molesta.
- Al entrar en `"edit"`: `setInstrumentDraft` con
  `{ name, tool_type, free_observation, items: loadedTool.items.map(i => ({ id: i.id, label, score_per_item: String(i.score_per_item) })) }`.
- El efecto de `max_score` (`page.tsx:634-648`) debe correr también en `"edit"`
  (cambiar `assessmentMode !== "create"` → `assessmentMode === "existing"` en el
  early-return, es decir: recalcular en `create` **y** `edit`).

### 4 · `page.tsx` — `saveInstrumentDraft` bifurca POST/PATCH

- `buildInstrumentPayload` (`page.tsx:343-367`): en modo `"edit"` incluye
  `id: item.id` para los ítems que lo tengan (los nuevos van sin `id`; el backend
  los da de alta). En `"create"` sigue ignorando `id`.
- `saveInstrumentDraft(mode)`:
  - `"edit"` → `api.updateInstrument(eventId, Number(selectedAssessmentToolId), payload)`
    (PATCH). No cambia `selectedAssessmentToolId` (sigue apuntando al mismo tool);
    refresca `loadedTool` y la lista `instruments` con la respuesta.
  - `"create"` → `api.createInstrument` (POST + re-apuntar), como hoy.
  - manejar el **409** (tool ya no editable) propagándolo para que
    `instrument-step` muestre el fallback "Crear copia".
- Los dos call-sites (`page.tsx:842-851`, `:1068-1071`): llamar
  `saveInstrumentDraft` cuando `assessmentMode === "create" || assessmentMode === "edit"`.

### 5 · Copy

- Botón: "Editar esta pauta" (modo `edit`) vs "Crear pauta nueva" (modo
  `create`).
- Aviso en modo `edit` cuando `reference_count > 1`: "Esta pauta la usan N
  estaciones/eventos; los cambios se aplican a todas."
- Mensaje de 409: usar el `detail` del backend + botón "Crear copia en su lugar".

## Tests (vitest — solo frontend)

`frontend/src/app/(app)/stations/builder/__tests__/` (extender el existente o
nuevo `instrument-edit.test.tsx`):

- `abrir una estación con assessment_tool_id carga los ítems del tool` — spy
  sobre `api.instrument`; el editor muestra los N ítems con sus labels.
- `modo "edit" hace PATCH, no POST` — spy sobre `api.updateInstrument` y
  `api.createInstrument`: al guardar en modo edit se llama update 1 vez, create 0.
- `modo "edit" preserva los id de ítem en el payload` — el body del PATCH lleva
  `items[].id` para los ítems precargados y sin `id` para los agregados.
- `409 al guardar en modo edit muestra el fallback "crear copia"` — mock del
  `api.updateInstrument` que rechaza con 409 → aparece el botón, y al pulsarlo se
  pasa a modo create con los ítems precargados.
- `modo "create" sigue haciendo POST + re-apuntar` (regresión).
- `reference_count === 0 habilita "Editar" directamente`.

Verificar que los tests de wizard existentes (diffing de cambios sin guardar,
`useNavigationGuard`) siguen verdes con `AssessmentMode` de 3 valores.

## Riesgos / alcance

- **El wizard es la zona más frágil del frontend** (1125 líneas en `page.tsx`,
  máquina de estados de pasos + snapshot diffing + navigation guard). El modo
  `"create"` **no se toca**; `"edit"` es aditivo y sólo aparece con un tool
  cargado y editable. El riesgo está en `applyStationLikeData` volviéndose async
  (hoy es `useCallback` síncrono, `page.tsx:495`) — mitigado moviendo la carga
  del tool a un `useEffect` dedicado que no bloquea el resto del `apply`.
- **UX optimista del 409**: si el usuario edita 10 minutos y al guardar recibe
  "no editable", pierde poco (los ítems quedan en el draft, el botón "Crear
  copia" los reusa) pero es fricción. La mejora backend (`editable` en el GET)
  la elimina — anotada como opcional.
- **`reference_count` cross-event**: editar afecta a todas las estaciones que
  apuntan al tool. Es el comportamiento correcto del banco compartido (el gate
  del backend ya impide tocar pautas de eventos avanzados); el aviso de copy lo
  hace explícito.
- Commit acotado: 1 corte (`shared.tsx` + `instrument-step.tsx` + `page.tsx` +
  tests). Sin backend, sin migración.

## Esfuerzo

**M** (≈2 días). Es "solo frontend" pero toca la máquina de estados del wizard:
`applyStationLikeData` async, tercer modo con render condicional, bifurcación
POST/PATCH en dos call-sites, manejo del 409, y tests de un componente grande.
El implementador de OPT-7 lo marcó "invasivo" con razón.

## Verificación

- [ ] `cd frontend && npm run lint && npm run build`
- [ ] `npx vitest run src/app/\(app\)/stations/builder`
- [ ] `./scripts/run_e2e.sh --grep "constructor"` si el flujo dorado cubre el
      wizard de pautas (requiere Docker; sobre el stack de ramas)

## Decisiones para el usuario

1. **UX del 409**: ¿optimista (ofrecer "Editar" siempre que `reference_count > 0`
   y manejar el 409 al guardar) — recomendado, frontend puro — o esperar la
   mejora backend `editable: bool` en `GET /api/instruments/{id}` (~XS extra, deja
   el botón deshabilitado de entrada)?
2. **Modo por defecto al abrir una estación con pauta**: seguir entrando en
   `"existing"` (recomendado; el usuario elige "Editar" explícitamente) o entrar
   directo en `"edit"` cuando el tool es editable.

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-29
- Aprobado por usuario: ⬜ pendiente
