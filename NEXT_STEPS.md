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

## Completado en la estabilizacion pre-examen (julio 2026)

- ~~Aislar pilotaje de ejecucion (mode en duplicados y flags)~~ ✅
- ~~Maquina de estados backend + gate de envios por etapa~~ ✅
- ~~Deadlines autoritativos + registro por contingencia~~ ✅
- ~~Cierre que consolida y congela~~ ✅
- ~~Modo kiosco por estacion (tablets compartidas)~~ ✅
- ~~Formularios del estudiante puntuables + pantalla Correccion~~ ✅
- ~~Trazabilidad por circuito (modo espejo)~~ ✅
- ~~Pilotaje con hallazgos~~ ✅
- ~~Modales de confirmacion con resumen, semaforo de tiempo, indicador de borrador~~ ✅
- ~~Reconexion WS con indicador + vista proyector en panel en vivo~~ ✅
- ~~Filtros/buscadores en tablas de estudiantes y staff~~ ✅
- ~~E2E Playwright del flujo dorado + checklist del dia D~~ ✅

## Completado en agosto 2026

- ~~Unificar el alta de equipo en una sola pantalla (Evaluadores)~~ ✅
  - ~~Alta individual por correo: la cuenta existente manda su nombre, no se retipea~~ ✅
  - ~~Importacion masiva que crea cuentas `pending` con invitacion en vez de descartar filas~~ ✅
  - ~~Enlaces de activacion visibles al terminar el import, para repartirlos a mano~~ ✅
  - ~~Selector de estacion principal solo para el rol evaluador (en el resto no tenia efecto)~~ ✅

## Prioridad actual

1. Primera prueba funcional real — PENDIENTE, bloqueada por preparacion del evento
   - Ensayo general con el equipo usando la app en `en_pilotaje` (guiarse por docs/OPERACION_DIA_EXAMEN.md).
   - Antes de convocar al equipo, cerrar estos pendientes en el ECOE demo (id 1):
     - Asignar un evaluador a la estacion 5 "Consejeria y cierre" (hoy solo estan cubiertas la 1 y la 3).
     - Homologar el estado de la estacion 2 "Interpretacion ECG", que quedo en `lista_para_pilotaje` mientras las otras cuatro estan `publicada`.
     - Confirmar en el Constructor que el formulario de la estacion 4 "Plan diagnostico" tenga puntajes y claves; hoy no tiene instrumento asociado y no sumaria a resultados.
     - Correr la pasada completa por las 5 estaciones y registrar hallazgos (hoy hay un solo registro en `pilot_records`).
   - Retro post-ensayo y ajustes.

2. Multimedia
   - Mejorar preview de audio y video con controles avanzados.
   - Definir si el material se muestra antes, durante o despues de la estacion.

3. Exportaciones
   - Mejorar formato de Excel consolidado con estadisticas por estacion.
   - PDF por estacion con formato imprimible real (membrete, tabla de puntajes).

4. Seguridad operativa
   - Logout real del lado cliente (invalidar token).
   - Expiracion de token mejor manejada (refresh token).
   - Integrar envio transaccional de invitaciones (SMTP en `core/config.py`, plantillas, decidir sincrono o en background) y un flujo seguro de reemision. Hoy los enlaces se reparten a mano, uno por uno o desde el panel que deja el import masivo; con correo configurado ese panel deja de ser necesario.
   - Ampliar auditoria y MFA para acciones institucionales sensibles.

5. Testing
   - Tests de frontend de componentes clave (kiosco, evaluador).
   - Ampliar el e2e: pausa/contingencia y correccion manual en UI.

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
python3 -m pytest -q
```

Los mismos tests contra PostgreSQL real con migraciones Alembic (lo que corre CI):

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q
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
y continuemos desde la prioridad actual: preparar el ECOE para la primera prueba
funcional real (ver los pendientes listados en Prioridad actual).
```
