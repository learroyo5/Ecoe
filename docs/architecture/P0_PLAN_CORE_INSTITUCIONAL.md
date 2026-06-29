# P0 plan core institucional

Fecha: 2026-06-29

## Objetivo

Estabilizar el nucleo institucional del proyecto ECOE sin agregar funcionalidades visibles: reproducibilidad de base de datos, seguridad de configuracion, autorizacion de WebSocket/media, resultados no destructivos y pruebas negativas.

## Cortes de commit propuestos

### Commit 1 - Plan y migracion base reproducible

- Reemplazar/corregir la migracion inicial para que `alembic upgrade head` cree el esquema completo desde una base limpia.
- Agregar indices y constraints criticos por ECOE, estudiante, estacion, staff, resultados, media y auditoria.
- Mantener compatibilidad con SQLite para tests.

Verificacion:

- `cd backend && alembic upgrade head` sobre base limpia.
- Tests existentes siguen creando schema sin depender de `create_all` productivo.

### Commit 2 - Bootstrap seguro y seeds por ambiente

- Agregar `ENVIRONMENT` y `AUTO_SEED_DEMO` a configuracion.
- Hacer que el backend falle en produccion si `SECRET_KEY` esta vacio.
- Eliminar fallback productivo a `Base.metadata.create_all`; permitirlo solo en desarrollo/test si Alembic falla.
- Ejecutar seeds demo solo cuando el ambiente lo permita explicitamente.
- Revisar flags de cookie por ambiente.

Verificacion:

- Startup local sigue funcionando.
- Produccion sin `SECRET_KEY` falla temprano.

### Commit 3 - Autorizacion central para WebSocket y media

- Centralizar helpers para resolver usuario desde token/cookie en WebSocket.
- Autenticar `/ws/live/{ecoe_event_id}` y aplicar `ensure_event_access`.
- Validar media por asset -> station -> ECOE antes de listar/descargar/borrar.
- Aplicar audiencia: estudiante, evaluador, coordinador/cronometrador/admin/coeditor.

Verificacion:

- WebSocket sin token no conecta.
- Usuario sin acceso al ECOE no conecta.
- Estudiante no ve media de evaluador.

### Commit 4 - Resultados no destructivos y consolidacion explicita

- Hacer que `GET /results/{ecoe_event_id}` solo calcule/lea y no escriba.
- Mantener exportacion Excel/PDF operativa sin mutar por GET.
- Agregar `POST /results/{ecoe_event_id}/consolidate` como accion explicita para persistir resultados actuales.
- Dejar el modelo preparado para futuro `ResultSet` sin introducirlo todavia.

Verificacion:

- Conteo de `ecoe_results` no cambia al consultar GET.
- Consolidacion explicita persiste resultados.

### Commit 5 - Matriz de permisos y tests P0

- Crear matriz inicial de permisos en documentacion.
- Agregar tests negativos para:
  - usuario sin acceso a ECOE;
  - evaluador intentando acceder a otro ECOE;
  - estudiante intentando acceder a media no autorizada;
  - WebSocket sin token;
  - WebSocket con token sin permiso;
  - GET resultados no muta datos.

Verificacion:

- `cd backend && python3 -m pytest tests/test_api.py -v`
- Frontend build/lint solo si se modifica frontend.

## Fuera de alcance

- Nuevas pantallas o redisenos de UI.
- Analitica curricular longitudinal.
- Redis/broker para WebSocket multi-replica.
- MFA, refresh token o revocacion server-side completa.
- Modelo formal `ResultSet`.
