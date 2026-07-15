# Next Steps

## Prioridad alta completada (v2)

1. ~~Completar CRUD real de ECOE~~ ✅
   - ~~Formulario completo de datos generales~~ → 3 secciones con validacion frontend
   - ~~Cambio de estado guiado desde UI~~ → StatusTransitionBar con modales de confirmacion
   - ~~Vista de detalle del ECOE activo~~ → `/ecoe/[id]` con 4 tabs

2. ~~Mejorar constructor de estaciones~~ ✅
   - ~~Edicion de estaciones existentes~~ → builder soporta carga y actualizacion completa
   - ~~Formularios por secciones con mejor UX~~ → constructor con 4 pasos guiados
   - ~~Asociacion real de multimedia~~ → upload con preview inline (MediaPreview)
   - ~~Asociacion real de instrumentos y paciente simulado~~ → selectores en el builder

3. ~~Mejorar flujo operativo en vivo~~ ✅
   - ~~Sincronizacion real del cronometro entre clientes~~ → WebSocket con broadcast
   - ~~Mejora de panel de incidencias~~ → creacion, resolucion, reapertura con WebSocket

4. ~~Robustecer evaluacion y respuestas~~ ✅
   - ~~Render dinamico de instrumentos~~ → checklist toggle + puntaje numerico
   - ~~Render dinamico de formularios del estudiante~~ → 3 tipos de pregunta
   - ~~Bloqueo por tiempo de manera efectiva~~ → timer rojo, campos deshabilitados al expirar

5. ~~Persistencia y mantenimiento~~ ✅
   - ~~Agregar migraciones con Alembic~~ → configurado con autogenerate
   - ~~Agregar pruebas backend basicas~~ → 23 tests pasando

---

## Prioridad actual (antes "Prioridad media")

1. Multimedia
   - Mejorar preview de audio y video con controles avanzados.
   - Definir si el material se muestra antes, durante o despues de la estacion.

2. Exportaciones
   - Mejorar formato de Excel consolidado con estadisticas por estacion.
   - PDF por estacion con formato imprimible real (membrete, tabla de puntajes).
   - Hojas manuales de contingencia mejor estructuradas.

3. Seguridad operativa
   - Logout real del lado cliente (invalidar token).
   - Expiracion de token mejor manejada (refresh token).
   - ~~Separar administrador global, administrador por ECOE y cerrar IDOR principales.~~ ✅
   - ~~Permitir que `admin_ecoe` incorpore usuarios mediante cuenta reutilizable o invitacion de activacion de un solo uso.~~ ✅
   - Integrar envio transaccional de invitaciones y un flujo seguro de reemision; hoy el enlace se comparte manualmente.
   - Ampliar auditoria y MFA para acciones institucionales sensibles.

4. UX/UI
   - Mejorar version tablet en formularios largos.
   - Reforzar feedback de guardado (toast animations).
   - Filtros y buscadores en tablas de datos.

5. Testing
   - Agregar tests de frontend (componentes, integracion).
   - Tests de integracion para flujos completos (crear ECOE → construir estacion → publicar → ejecutar).

## Prioridad media (antes "Prioridad baja")

1. Audio del cronometro
   - Reproducir sonido de aviso en transiciones de estacion.
   - Sonido configurable por ECOE.

2. Observabilidad
   - Logs mas claros y estructurados.
   - Auditoria expandida (quien hizo que, cuando, desde donde).

## Prioridad baja

1. Infraestructura
   - Backups automatizados de PostgreSQL.
   - Healthchecks y alertas mas visibles.
   - Procedimiento simple de rotacion de credenciales.

2. ACL avanzada
   - Permisos por unidad academica/centro para bancos institucionales compartidos.
   - Extender reglas por recurso mas alla de ECOE, estacion, audiencia y check-in ya implementados.

## Comandos utiles

Levantar:

```bash
docker compose up --build -d
```

Ver estado:

```bash
docker compose ps
```

Ver logs:

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

Apagar:

```bash
docker compose down
```

Tests:

```bash
cd backend
python3 -m pytest tests/test_api.py -v
```

Migraciones:

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "descripcion del cambio"
```

## Nota para futuras sesiones

Al retomar en otro servidor, pedir:

```text
Lee README.md, PROJECT_STATUS.md y NEXT_STEPS.md, revisa la estructura del repo
y continuemos desde la prioridad actual (multimedia, exportaciones, seguridad, UX).
```
