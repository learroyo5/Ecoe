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

- ~~Evaluación diferida Fase 1~~ ✅ — rol `corrector`, capacidad de estación `requires_deferred_grading`, Validación y trazabilidad. Diseño en `docs/architecture/EVALUACION_DIFERIDA_FASE1.md`. Pendiente Fase 2 (ver abajo).
- ~~Unificar el alta de equipo en una sola pantalla (Evaluadores)~~ ✅
  - ~~Alta individual por correo: la cuenta existente manda su nombre, no se retipea~~ ✅
  - ~~Importacion masiva que crea cuentas `pending` con invitacion en vez de descartar filas~~ ✅
  - ~~Enlaces de activacion visibles al terminar el import, para repartirlos a mano~~ ✅
  - ~~Selector de estacion principal solo para el rol evaluador (en el resto no tenia efecto)~~ ✅

## Completado 2026-08-29 — pipeline de optimización + Fase 2 de análisis (desplegado)

Ciclo auditoría → triage → implementación sobre el flujo completo. Detalle en `PROJECT_STATUS.md` (sección "Pipeline de optimización + Fase 2") y `docs/optimizacion/BACKLOG.md`. Todo en `main`, desplegado (migración prod `j0e1f2a3b4c5 → o5p6q7r8s9t0`), CI verde, 394 backend + 78 frontend.

- ~~Resultados inmutables tras el cierre + AuditLog de consolidación~~ ✅
- ~~Aislamiento pilotaje/ejecución completo (`mode` en check-ins, trazabilidad, cola de corrección)~~ ✅
- ~~Gating de UI por rol de evento, no por rol global~~ ✅
- ~~OPT-20: cronómetro sincrónico único, deadline desde `LiveSession`, autoenvío server-side, borrador del evaluador, WebSocket para pantallas operativas, `expire_phase`~~ ✅
- ~~Resultado por estación + nota agregada = promedio de %-por-estación (compensatorio)~~ ✅
- ~~Psicometría (α Cronbach, discriminación, dificultad, punto-biserial) sobre ejecución y pilotaje + advertencias en `pilotaje_validado`~~ ✅ — **cubre "Exportaciones · estadísticas por estación" de Prioridad actual**
- ~~Export Excel multi-hoja con item analysis y metadatos~~ ✅
- ~~CRUD del banco institucional (instrumentos, plantillas, pacientes) + "editar pauta" en el Constructor~~ ✅
- ~~Cola personal del corrector + pauta de referencia + bulk-0 blancos + reasignar correctores~~ ✅ — **cubre parte de "Evaluación diferida Fase 2 · edición de estaciones del corrector"**

**Diferido (requiere cambio de contexto, no urgente):**
- OPT-14 — back-plane Redis para `LiveTimerManager` (solo con >1 worker / escalado horizontal).
- OPT-17b — umbral por estación / estándar conjuntivo (contradice el compensatorio elegido; sería su propio ciclo).

**Pendiente operativo:**
- Pilotar el cambio de deadline de OPT-20 (check-in tardío = menos tiempo, pausa congela para todos) antes de un examen real.
- Limpieza de ~24 ramas `opt/*` / `ops/*` locales ya mergeadas.
- 1 `evaluator_record` con `mode='ejecucion'` en el evento de pilotaje (dato viejo) — decidir si se corrige o se descarta con el resto del pilotaje.

## Prioridad actual

1. ~~Primera prueba funcional real~~ ✅ (2026-08-18)
   - ~~Ensayo general con el equipo usando la app en `en_pilotaje`~~ → hecho: check-in, cronometro y evaluacion/kiosco de punta a punta en las 5 estaciones (1, 3 y 5 con evaluador real; 2 y 4 cubiertas por coordinacion). Pilotaje `circuito_completo` con hallazgos registrados (`pilot_run` id 3).
   - Bugs encontrados y corregidos durante la preparacion y el ensayo (quedaron en commits separados):
     - Editar una estacion publicada en el Constructor regresaba su estado a `incompleta`/`lista_para_pilotaje`, desincronizandola del resto.
     - Editar el timing del ECOE no resincronizaba la `LiveSession`: el cronometro en vivo seguia mostrando los minutos con los que se creo la sesion, no los configurados despues.
     - La pantalla Estaciones no distinguia cuales necesitan Modo kiosco (formulario de estudiante y/o multimedia).
     - `admin_ecoe`/`coordinador_operativo` no tenian forma de hacer check-in en una estacion sin evaluador asignado (pantalla Evaluador acotada a la estacion propia).
   - Invitaciones y reinicio de acceso ahora envian correo real (SMTP configurado); antes el enlace solo se mostraba una vez en pantalla.
   - Retro pendiente: definir evaluador fijo para las estaciones 2 y 4 (hoy las cubre coordinacion), y hacer la prueba de red formal en el recinto real antes del examen.
   - Ya corregido en el mismo ensayo: el reloj del kiosco seguia corriendo tras enviar (ahora se congela), y la pantalla dejaba visible la identidad/respuestas del estudiante anterior para quien llegara despues (ahora se reemplaza por una pantalla neutra hasta que el evaluador confirme al siguiente).

2. Evaluación diferida Fase 2 (diseño en `docs/architecture/EVALUACION_DIFERIDA_FASE1.md`, sección final)
   - Adjuntar entregables (PDF, foto, audio, video) por estudiante/estación para corregir estaciones **sin formulario** (p. ej. un procedimiento grabado).
   - Registro puntuable "en blanco" por check-in confirmado, para estaciones que se puntúan solo desde papel/observación.
   - Puntuación estructurada contra los ítems de la pauta (mismo renderer que la pantalla Evaluador) con comentario por ítem, en vez de número libre.
   - Edición de las estaciones de un corrector desde la tabla de Evaluadores (hoy solo en el alta).
   - Opcional: doble corrección ciega e índice de acuerdo inter-rater.

3. Rotacion autonoma en estaciones kiosco-solo sin evaluador (diseno, NO implementar aun)
   - Hoy el check-in de una estacion solo lo cierra un humano (el evaluador/coordinador confirma al siguiente estudiante por numero ECOE). En estaciones sin evaluador asignado (kiosco puro, ej. 2 y 4) eso exige que alguien este pendiente igual, lo que le quita el sentido a que sean "autonomas".
   - Opciones a evaluar mas adelante, no excluyentes:
     a. Auto-cierre por deadline: cuando pasa `submission_deadline` (o un margen corto despues), el backend cierra el check-in solo (job o chequeo perezoso en el poll del kiosco) y la tablet vuelve a esperar — pero sigue faltando quien confirme la identidad del siguiente.
     b. Auto-identificacion del estudiante en el kiosco: reusar el mismo patron de `/student` (login por numero ECOE) para que el propio estudiante se confirme al llegar, sin depender de que un evaluador lo haga por el — mismo nivel de confianza que ya existe en la interfaz Estudiante.
     c. Rotacion atada al circuito: si el panel en vivo ya sincroniza la estacion actual de cada grupo (`current_station_index`), la identidad podria resolverse por asignacion de grupo/circuito en vez de confirmacion manual por instancia.
   - Cualquier opcion debe mantener la misma garantia de privacidad ya corregida arriba (nunca mostrar al siguiente estudiante la identidad/respuestas del anterior).

4. Multimedia
   - Mejorar preview de audio y video con controles avanzados.
   - Definir si el material se muestra antes, durante o despues de la estacion.

5. Exportaciones
   - Mejorar formato de Excel consolidado con estadisticas por estacion.
   - PDF por estacion con formato imprimible real (membrete, tabla de puntajes).

6. Seguridad operativa
   - Logout real del lado cliente (invalidar token).
   - Expiracion de token mejor manejada (refresh token).
   - ~~Integrar envio transaccional de invitaciones~~ ✅ (2026-08-18): SMTP configurado en `backend/.env`, invitaciones e import masivo envian correo real; se agrego ademas reinicio de acceso para cuentas activas (admin_ecoe/coeditor_docente, sin requerir admin_global).
   - Ampliar auditoria y MFA para acciones institucionales sensibles.

7. Testing
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
