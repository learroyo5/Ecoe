# OPT-4 · Blocker fantasma "No existe sesión en vivo" antes de publicar

**Severidad: media.** Origen: H-admin-ecoe-3, H-vivo-2.

## Problema

En `/validation` y `/publication`, para cualquier ECOE aún no publicado, se muestra una caja roja de bloqueo
"No existe una sesión en vivo creada para la ejecución real." **al mismo tiempo** que el banner "Listo para
publicar" y el botón Publicar habilitado. Señales contradictorias; el bloqueo es irresoluble por el usuario y
en realidad no bloquea nada.

## Causa raíz

`app/services/validation.py:328` — el array genérico `blockers` agrega ese ítem siempre que
`has_live_session == 0`, **sin condicionarlo al estado del ECOE**. Pero la `LiveSession` solo se crea en la
transición a `publicado` (`validation.py:433-444`), así que en `borrador … pilotaje_validado` siempre es 0.
`can_publish` (`:278-282`) **no** depende de `has_live_session` — solo `can_start_live` (`:286-289`) lo hace.
`live_checks` ya incluye "Sesión en vivo creada" (`:358+`), de modo que el ítem en `blockers` es redundante.
`frontend/src/app/(app)/publication/page.tsx:95` renderiza `data.blockers` como cajas rojas junto al banner de
`data.can_publish`.

## Cambio propuesto

- **Backend** (`app/services/validation.py`): quitar la línea
  `None if has_live_session > 0 else "No existe una sesión en vivo creada para la ejecución real."`
  del array `blockers` (`:328`). Queda cubierto por `live_checks`. Alternativa equivalente: condicionarla a
  `ecoe_event.status in {ECOEStatus.publicado.value, ECOEStatus.en_ejecucion.value}`.
- **Frontend**: ninguno necesario. (Opcional: en `publication/page.tsx`, no renderizar la sección de blockers
  si `data.blockers` está vacío — probablemente ya lo hace.)
- **Migración**: no.
- **Máquina de estados**: no.

## Tests

- `test_validation_no_phantom_live_session_blocker_before_publish` — ECOE en `pilotaje_validado` con toda la
  configuración lista: `can_publish is True` **y** `blockers == []` (o no contiene el texto de sesión en vivo).
- `test_can_start_live_still_requires_live_session` — en `publicado` sin `LiveSession`, `can_start_live is False`
  y `live_checks` marca el ítem como no cumplido (regresión de que no se debilitó el gate real).

## Riesgos / alcance

- Mínimo. Un solo ítem de una lista. Verificar que ninguna prueba existente afirme la presencia de ese texto
  en `blockers` antes de publicar (`grep "sesión en vivo"` en `backend/tests/`).

## Verificación

- [ ] `cd backend && python3 -m pytest tests/test_validation*.py -v`
- [ ] `cd backend && python3 -m pytest`

## Estado de aprobación

- Propuesto por: optimizador — 2026-08-28
- Aprobado por usuario: ✅ 2026-08-28 (parte del lote de estabilización Grupo A)
