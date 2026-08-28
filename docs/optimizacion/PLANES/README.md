# Planes de optimización

Un archivo por mejora aprobada: `<ID-backlog>__<slug>.md`.

Plantilla:

```
# <ID> · <título>

## Problema
<qué fricción/bug resuelve, con evidencia del hallazgo>

## Causa raíz
<diagnóstico confirmado>

## Cambio propuesto
- Backend: <archivos, endpoints, servicios>
- Frontend: <pantallas, componentes>
- Migración: <sí/no — si sí, describir; requiere aprobación explícita del usuario>
- Máquina de estados: <si toca ALLOWED_STATUS_TRANSITIONS, actualizar también ecoe-form.tsx>

## Tests (obligatorio incluir negativos si toca seguridad/permisos/auth/datos)
- <test nuevo 1>
- <test nuevo 2>

## Riesgos / alcance
<qué podría romperse; por qué el commit es acotado>

## Verificación
- [ ] `cd backend && python3 -m pytest`
- [ ] contra Postgres si toca constraints/migraciones
- [ ] `cd frontend && npm run lint && npm run build` (si se tocó frontend)

## Estado de aprobación
- Propuesto por: optimizador — <fecha>
- Aprobado por usuario: ⬜ pendiente
```
