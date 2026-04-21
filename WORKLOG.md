# Worklog

Guia corta para retomar trabajo sin reconstruir contexto desde cero.

## Flujo de sesion recomendado

1. Leer `README.md`.
2. Leer `PROJECT_STATUS.md`.
3. Leer `NEXT_STEPS.md`.
4. Leer `datos_proyecto/README.md`.
5. Revisar `git status --short`.
6. Confirmar que el stack responda con `docker compose ps`.

## Convencion de trabajo

- Mantener cambios pequenos y verificables.
- Antes de tocar UX o flujo, revisar primero backend y tipos ya existentes.
- Si una nota operativa contradice al codigo activo, manda el codigo y la configuracion vigente.
- Al cerrar una sesion, dejar este archivo actualizado con foco en contexto util, no en detalle historico.

## Ahora mismo

- El despliegue actual funciona localmente y por `https://ecoe.drnotus.cl`.
- Las credenciales vigentes del servidor actual estan en `backend/.env` y `datos_proyecto/credenciales_locales.md`.
- Primera prioridad activa: completar gestion real del ECOE desde frontend.

## Proximo paso sugerido

- Completar CRUD del ECOE con formulario general, creacion, duplicado y control de estado visible desde UI.
