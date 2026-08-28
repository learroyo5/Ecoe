# OPT-5 · Alta individual de evaluador sin estación (coherencia UI/endpoint)

**Severidad: media.** Origen: H-admin-ecoe-2.

## Problema

En `/evaluators`, el formulario de alta individual ofrece la opción "Sin estación asignada por ahora" y un
texto de ayuda que promete asignación diferida ("se asigna después en la tabla de abajo"). Al guardar un
evaluador nuevo sin estación → **HTTP 400** "El evaluador debe tener una estación principal asignada". El
import masivo del **mismo rol en la misma pantalla** sí permite el alta sin estación → dos caminos con reglas
distintas y copy idéntico.

## Causa raíz

- `app/services/invitations.py:54-64` — `_validated_assignment` con `require_evaluator_station=True` (default)
  lanza 400 si el rol es `evaluador` y no hay `station_ids`.
- `app/api/routes/invitations.py:40` — `invite_event_member` llama `assign_or_invite_member` **sin** pasar
  `require_evaluator_station=False`.
- `app/api/routes/staff.py:279` — el import masivo **sí** pasa `require_evaluator_station=False`.

## Cambio propuesto

**Opción A (recomendada — coherente con el import):**

- **Backend** (`app/api/routes/invitations.py:40`): pasar `require_evaluator_station=False` a
  `assign_or_invite_member` en `invite_event_member`. El evaluador queda sin estación y se completa después en
  la tabla de asignaciones (que ya existe). La validación de "evaluador sin estación" pasa a ser una
  **advertencia de publicación** — revisar si `compute_ecoe_validation` ya la cubre vía `assignments_ready`
  (`validation.py:202-207`); si no, añadir un `warning` "Evaluadores sin estación principal asignada".

**Opción B (si se prefiere mantener la regla estricta):**

- **Frontend** (`frontend/src/app/(app)/evaluators/page.tsx:349,356-359`): quitar la opción
  `<option value="">Sin estación asignada por ahora</option>` y el texto de ayuda correspondiente para el alta
  individual; hacer el `select` de estación obligatorio. Dejar el import masivo como está (o alinearlo también).

- **Migración**: no.
- **Máquina de estados**: no.

## Tests (incluye negativos — toca invitaciones/permisos)

Para Opción A:
- `test_invite_evaluator_without_station_succeeds` — `POST /api/event-members/invite` rol `evaluador` sin
  `station_ids` → 200, `StaffAssignment` creado con `station_ids` vacío.
- `test_publication_warns_evaluator_without_station` — el ECOE con un evaluador sin estación marca el warning /
  `assignments_ready is False` y `can_publish` lo refleja.
- `test_invite_evaluator_with_invalid_station_still_rejected` (negativo) — estación inexistente o de otro
  evento → sigue dando 400/404.

Para Opción B:
- Frontend (vitest): el formulario individual no permite enviar sin estación.

## Riesgos / alcance

- Opción A relaja una validación de alta: hay que garantizar que la ausencia de estación se detecta en la
  compuerta de publicación (que ya cubre `assignments_ready`), para que no pase silenciosamente al día del
  examen.
- Commit acotado: 1 línea de backend + posible ajuste de warning, o unos pocos nodos de JSX.

## Verificación

- [ ] `cd backend && python3 -m pytest tests/test_event_member_invitations.py tests/test_validation*.py -v`
- [ ] `cd backend && python3 -m pytest`
- [ ] `cd frontend && npm run lint && npm run build` (si se toca frontend)

## Decisión pendiente del usuario

**¿Opción A (permitir alta sin estación, coherente con el import) u Opción B (exigir estación en el alta
individual)?** A es menos fricción y ya es el comportamiento del import; B es más estricta.

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-28
- Aprobado por usuario: ⬜ pendiente
