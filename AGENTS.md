# AGENTS.md

Guia para agentes de codigo que trabajen en este repositorio ECOE.

## Proyecto

ECOE es una plataforma web para planificacion, pilotaje, ejecucion, evaluacion, resultados y cierre de ECOE/OSCE en carreras de la salud.

Stack principal:

- Backend: FastAPI, SQLAlchemy, Pydantic, Alembic, PostgreSQL.
- Frontend: Next.js, TypeScript, Tailwind CSS.
- Infraestructura local: Docker Compose con `frontend`, `backend` y `db`.

## Lectura inicial obligatoria

Antes de cambios estructurales o funcionales, leer:

1. `README.md`
2. `PROJECT_STATUS.md`
3. `NEXT_STEPS.md`
4. `datos_proyecto/README.md`, si aplica
5. Documentos relevantes en `docs/architecture/`

## Reglas de trabajo

- No leer ni exponer secretos de `backend/.env` o `datos_proyecto/credenciales_locales.md` salvo solicitud explicita y necesidad operacional clara.
- Mantener compatibilidad con Docker Compose.
- No agregar pantallas o cambios visibles cuando la tarea sea de estabilizacion backend.
- Para cambios de seguridad, permisos, datos o autenticacion, agregar tests negativos.
- Preferir cambios pequenos, verificables y con commits acotados.
- No revertir cambios del usuario sin permiso explicito.

## Verificacion recomendada

Backend:

```bash
cd backend
python3 -m pytest tests/test_api.py -v
```

Migraciones desde base limpia:

```bash
cd backend
DATABASE_URL=sqlite:////tmp/ecoe_alembic_check.db SECRET_KEY=test-secret ENVIRONMENT=test AUTO_SEED_DEMO=false alembic upgrade head
```

Frontend, solo si se modifica:

```bash
cd frontend
npm run lint
npm run build
```

## Prioridad arquitectonica actual

La prioridad P0 es estabilizacion institucional:

- Migraciones reproducibles.
- Configuracion segura por ambiente.
- Seeds demo fuera de produccion.
- Autorizacion por ECOE.
- WebSocket autenticado/autorizado.
- Media con scoping por ECOE y audiencia.
- Resultados sin mutacion en endpoints GET.
