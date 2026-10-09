# Project Status

## Proyecto

- Nombre: `Proyecto Tecnologico ECOE`
- Objetivo: plataforma web para planificacion, pilotaje, ejecucion, contingencia y cierre de ECOE/OSCE para carreras de la salud.
- Estado actual: en pilotaje interno; núcleo endurecido en octubre 2026 (ver abajo). Todavía sin un examen real con estudiantes.

## Estado general

La v2 del producto esta completa y ya paso su primer ensayo funcional real con el equipo (2026-08-18, detalle en `NEXT_STEPS.md`): CRUD del ECOE con maquina de estados real en backend, constructor de estaciones con multimedia y formularios puntuables, panel en vivo con WebSocket con reconexion automatica y vista proyector, modo kiosco por estacion para tablets compartidas, correccion manual de respuestas, registro por contingencia, invitaciones/reinicio de acceso por correo real, y suite de tests (394 backend sobre SQLite y Postgres + 78 frontend + e2e Playwright del flujo dorado; CI verde). El proyecto corre con Docker Compose en este servidor con salida publica por `nginx`; ver la seccion "Pipeline de optimización + Fase 2" mas abajo para el estado actual.

### Estabilizacion pre-examen (fases 1-5, julio 2026)

- Aislamiento pilotaje/ejecucion: los registros del ensayo no bloquean ni contaminan la ejecucion real (duplicados y flags por `mode`).
- Maquina de estados del ciclo de vida en backend (mismo grafo que la UI) y gate de envios: check-ins/evaluaciones/respuestas solo en `en_pilotaje` o `en_ejecucion`.
- Deadlines autoritativos del servidor en las interfaces (el evaluador dispone del tiempo de transicion) y endpoints de contingencia auditados para envios fuera de ventana.
- Cierre que consolida resultados y congela la operacion.
- Modo kiosco: token por estacion (hasheado, revocable), la tablet muestra automaticamente al estudiante del check-in activo; carrera de rotacion cubierta.
- Formularios puntuables: autocorreccion de alternativas al enviar, correccion manual de texto (pantalla Correccion), resultados suman formularios corregidos.
- Trazabilidad por circuito (modo espejo ya no infla faltantes) y pilotaje con hallazgos.
- UX operativa: modales de confirmacion con resumen, semaforo de tiempo, indicador de borrador, reconexion WS visible, vista proyector, busqueda en tablas.
- E2E Playwright (`scripts/run_e2e.sh`) y checklist operativa (`docs/OPERACION_DIA_EXAMEN.md`).

### Evaluación diferida — Fase 1 (agosto 2026)

Vacío detectado: las estaciones sin evaluador presencial y sin autocorrección (el estudiante escribe, alguien puntúa después) no tenían responsable configurable. La corrección la hacía cualquier `admin_ecoe`/`coeditor_docente` sobre una lista plana, sin que Validación exigiera a nadie.

- Rol operativo nuevo `corrector`: `StaffAssignment` acotado a una o varias estaciones, delegable por coeditor/coordinador igual que `evaluador`/`cronometrador`. Solo entra a la pantalla Corrección y solo ve las respuestas de sus estaciones.
- Capacidad de estación `requires_deferred_grading` (switch en el Constructor). Exige el formulario del estudiante con al menos una pregunta de respuesta breve con puntaje y un corrector asignado; Validación lo bloquea y `can_publish` lo incluye.
- Trazabilidad: una respuesta enviada pero sin puntuar mantiene al estudiante en `parcial` (`pending_deferred_gradings`). Cerrar el ECOE con correcciones pendientes se advierte en el modal de cierre, no se bloquea.
- Demo: estación 6 "Informe de laboratorio" (corrección diferida) + cuenta `corrector@ecoe.cl`.
- Diseño y alcance: `docs/architecture/EVALUACION_DIFERIDA_FASE1.md`.

### Alta de equipo unificada (agosto 2026)

Incorporar gente a un ECOE obligaba a un rodeo: crear primero la cuenta institucional a mano en Usuarios y recien despues asignarla en Evaluadores, reescribiendo nombre y apellido (donde un tipeo creaba una identidad divergente para el mismo correo). La carga masiva exigia que todas las cuentas existieran de antemano y descartaba en silencio las filas sin cuenta.

Hoy `Evaluadores` es el unico lugar necesario:

- El alta individual arranca por el correo. Si la cuenta existe, su nombre manda y se muestra en solo lectura; solo se piden nombre y apellidos cuando hay que crear la identidad.
- La importacion CSV/Excel usa la misma logica: crea cuentas `pending` con su invitacion en vez de omitir la fila, y devuelve los enlaces de activacion para repartirlos.
- Cada fila del import corre en un savepoint, asi una fila rechazada no descarta las ya validadas del mismo archivo.
- Crear identidades institucionales sigue siendo potestad de `admin_ecoe`: un `coeditor_docente` solo puede importar gente que ya tiene cuenta (cubierto con test negativo).
- El selector de estacion principal solo aparece para el rol `evaluador`. Para coeditor, coordinador y cronometrador el backend nunca lee `station_ids`, asi que la UI ofrecia una asignacion que se guardaba pero no tenia efecto ni se reflejaba en Validacion.

### Pipeline de optimización + Fase 2 de análisis (2026-08-29, desplegado)

Ciclo completo de auditoría → triage → implementación sobre el flujo entero (acceso por rol → configuración → ejecución en vivo → corrección → análisis). Estado y planes en `docs/optimizacion/` (proceso reutilizable con 6 subagentes en `.claude/agents/`). Todo en `main` y desplegado en el servidor; migración de producción `j0e1f2a3b4c5 → o5p6q7r8s9t0` (6 migraciones). Suite: **394 backend (SQLite + Postgres) + 78 frontend**, CI verde.

- **Estabilización (Grupo A):** los resultados ya no cambian tras el cierre (`/results` sirve el snapshot `ECOEResult`; corrección post-cierre prohibida con 409); aislamiento pilotaje/ejecución completo (columna `mode` en `station_checkins`, filtro en trazabilidad/cierre/cola de corrección); gating de UI por rol de **evento** y no por rol global; y fixes menores (blocker fantasma de sesión en vivo, evaluador sin estación, `/kiosk/submit` exige el check-in vigente, `/live/control` endurecido).
- **OPT-20 — cronómetro sincrónico único:** el `LiveSession` es la autoridad de tiempo para todas las estaciones; el deadline de envío se deriva de la fase (no de `confirmed_at + station_time`), así que el check-in tardío tiene menos tiempo y la pausa congela para todos. WebSocket ahora accesible a kiosko/evaluador/estudiante (token de kiosko por query param). Autoenvío autoritativo server-side al vencer la fase (`services/live_sweep.py`), con borrador server-side del formulario (`station_response_drafts`) y del registro del evaluador (`evaluator_records.is_draft`, se finaliza por contingencia). Acción `expire_phase` en el panel en vivo. "Sin respuesta" explícito por ítem (`answered`) y `submission_kind` (`manual`/`auto`/`contingency`/`draft_finalized`). **Requisito de despliegue ya cubierto:** headers `Upgrade`/`Connection` en `location /api/` de ambos bloques nginx.
- **Fase 2 — análisis de datos:** resultado por estación (`StationResult`, bloque `by_station` en `/results` con media/DE/n); la nota agregada pasa a ser el **promedio de los %-de-logro por estación** (estándar compensatorio, todas pesan igual — corrige que una estación de puntaje alto dominara); psicometría completa (`services/psychometrics.py`, `GET /api/analytics/{id}/psychometrics?mode=`): α de Cronbach, discriminación estación-total, dificultad y punto-biserial por criterio de pauta, sobre ejecución **y pilotaje**, con advertencias no bloqueantes en el modal "Validar pilotaje"; export Excel multi-hoja (metadatos + consolidado + por_estación + item_analysis + trazabilidad).
- **Banco institucional:** CRUD real para instrumentos (`AssessmentTool`), plantillas y pacientes simulados — antes solo se podían crear. Edición in-place preservando `AssessmentItem.id` (no rompe registros históricos), bloqueada si un ECOE que usa la pauta ya pasó de `pilotaje_validado`; soft-delete (`archived`); propiedad (`created_by`/`origin_event_id`) con regla de gracia para el legado; script de purga de huérfanas. El Constructor ahora ofrece "editar esta pauta" (PATCH) en vez de crear una copia nueva.
- **Corrección diferida:** cola personal del corrector con pauta de referencia visible, autoavance a "siguiente pendiente" y progreso por estación; botón "puntuar 0 los blancos" por estación; reasignar estaciones de un corrector desde la tabla Evaluadores.

**Nota metodológica:** el cambio de fórmula de OPT-17 solo afecta eventos que se **consoliden desde ahora** y solo si tienen estaciones de puntaje máximo distinto; los ya `cerrado`/`archivado` conservan su snapshot. El cambio de deadline de OPT-20 (check-in tardío = menos tiempo) **debe pilotarse antes de un examen real**.

### Octubre 2026 — navegación, integridad del proceso y circuitos espejo (desplegado)

Cuatro bloques de trabajo, todos en `main` y en producción (detalle por sesión en `WORKLOG.md`, hallazgos en `docs/optimizacion/BACKLOG.md`):

- **Navegación y UX (UX-1…7):** barra lateral agrupada por fase del ciclo, encabezado con el estado del ECOE, Inicio con el siguiente paso, Datos del ECOE en una sola pantalla, Kioscos, Resultados con pestañas, textos y confirmaciones unificados.
- **Auditoría del proceso (PROC-1…24):** se corrigió la pérdida de la estación al confirmar durante la transición, la clave de respuestas que viajaba al estudiante, el check-in equivocado sin vuelta atrás y la contingencia que no podía reemplazar un autoenvío. Se agregaron candados por estado, cierre que exige completitud (o lo fuerza la dirección con 0), reapertura auditada, acta con identidad congelada, puntaje del evaluador validado contra la pauta, y el tablero de estaciones con verificación previa.
- **Fase 0 del plan multiinstitucional:** un solo ingreso activo por estación y por estudiante (garantizado por la base), envíos idempotentes, borradores ordenados, acta versionada, sockets que respetan la revocación, respaldo cada 5 minutos durante un examen y restauración ensayada.
- **Circuitos espejo:** se diseña un circuito y se genera su copia idéntica; resultados y psicometría por estación de diseño con desglose por circuito.

Además: instancia de demostración `demo.ecoe.cl` con base propia, y despliegue conjunto con `scripts/deploy.sh`.

## Arquitectura implementada

- Frontend: Next.js (App Router), TypeScript, Tailwind CSS. La API se consume por el mismo origen (`/api`, reescritura interna hacia el backend).
- Backend: FastAPI, SQLAlchemy, Pydantic, WebSocket, JWT (cookie + Bearer), migraciones Alembic.
- Base de datos: PostgreSQL 16. Alembic es la única forma de cambiar el esquema; cada backend migra su base al arrancar.
- Infraestructura: Docker Compose con `frontend`, `backend`, `db` y `db-backup`. Entrada desde internet por túnel de Cloudflare.
- Instancias: producción y demo corren las mismas imágenes con bases, archivos y secretos separados.

## Modulos implementados

- **Acceso y cuentas:** login, roles globales y por evento, invitaciones por correo con activación, suspensión con revocación de sesiones, panel institucional de usuarios.
- **Datos del ECOE:** edición, barra de estado con transiciones guiadas, duplicado (conserva circuitos espejo), creación (administración global).
- **Estaciones:** Constructor en 4 pasos, banco de estaciones, multimedia por audiencia, circuitos espejo (crear, sincronizar, eliminar).
- **Biblioteca:** plantillas, instrumentos (pautas) y pacientes simulados con edición, archivado y restauración.
- **Estudiantes y equipo:** alta manual e importación, numeración ECOE, asignación de evaluadores y correctores por estación.
- **Validación, pilotaje y publicación:** chequeos por estación y por evento, pilotaje con registros aislados y análisis, publicación que congela la estructura.
- **Panel en vivo:** cronómetro central manual o circuito automático por rondas, timbre, vista proyector, incidencias, tablero de estaciones con verificación previa, borradores de evaluador pendientes.
- **Operación de estación:** pantalla de evaluador (check-in, pauta, borrador en servidor), pantalla de estudiante, modo kiosco por estación.
- **Contingencia:** transcripción de respuestas y evaluaciones en papel, rectificación con motivo.
- **Corrección diferida:** cola por corrector con pauta de referencia.
- **Resultados:** nota por estación y agregada (promedio de porcentajes por estación), acta congelada al cierre con versiones anteriores, trazabilidad, análisis psicométrico, exportación a Excel y PDF de contingencia.

## Datos demo

- El seed base (`app/db/seed.py`, sólo fuera de producción) crea cuentas por rol y un ECOE de ejemplo.
- La instancia `demo.ecoe.cl` usa `app/db/seed_demo.py`: «ECOE Medicina Interna 2026» en ejecución y en espejo (4 estaciones × 2 circuitos, primera ronda registrada) y «ECOE Cirugía 2026» cerrado con acta (12 estudiantes × 5 estaciones). Se recarga con `scripts/demo_reset.sh`.
- La base de producción todavía contiene el ECOE de prueba del equipo, en pilotaje.

## Verificaciones (2026-10-09)

- Backend: 545 tests con pytest, verdes en SQLite y en PostgreSQL aplicando las migraciones (lo que corre CI). Incluye una prueba de concurrencia real de check-in.
- Frontend: 143 tests con vitest, lint sin errores, build de producción.
- Flujo dorado e2e (Playwright) 5 de 5 sobre el stack desechable; agregado al CI.
- Restauración del respaldo ensayada con `scripts/verify_backup.sh`.
- `https://app.ecoe.cl`, `https://ecoe.drnotus.cl` y `https://demo.ecoe.cl` verificados por HTTP tras cada despliegue.

Lo que **no** está verificado: un ECOE real con estudiantes, carga con muchas tablets simultáneas, y la revisión visual de todas las pantallas con cada rol.

## Decisiones importantes tomadas

- El backend es la autoridad: máquina de estados, deadlines, puntajes y permisos se resuelven en el servidor.
- Identidades únicas por correo dentro de una instalación; las funciones se asignan por ECOE.
- Pilotaje y ejecución real están separados por modo en cada registro.
- La nota agregada es el promedio de los porcentajes por estación; el estándar es compensatorio con un umbral global.
- Desde la publicación la estructura no se edita; con el ECOE cerrado no cambia nada salvo una reapertura explícita.
- Una estación sin registro no se ignora: bloquea el cierre o cuenta 0 si se fuerza.
- En espejo, la estación de diseño es la unidad de análisis; las estaciones espejo no se diseñan por separado.
- Multiinstitución: mismo núcleo con una base independiente por institución. Hoy, una instancia por institución con las mismas imágenes (ver `docs/optimizacion/PLANES/SAAS__multiinstitucional.md`).

## Limites actuales

- No hay plan de rotación generado: quién parte en qué estación se organiza fuera de la plataforma.
- Repartir estudiantes entre circuitos es manual (campo circuito o columna del Excel).
- Las estaciones sin evaluador necesitan que coordinación confirme a cada estudiante; el estudiante no puede identificarse solo en el kiosco.
- Un evaluador tiene una sola estación principal.
- Un solo proceso backend: el cronómetro en vivo no está preparado para varios procesos.
- Producción, demo y pruebas comparten el mismo servidor físico.
- El frontend recibe todas las variables del backend y los proxies de confianza no están acotados (pendiente F0.5).
- Sin SSO, sin MFA y sin separación entre operador central y administrador de institución.
- Cumplimiento de protección de datos (Ley 21.719, vigente desde 2026-12-01) sin revisar.

## Repo y continuidad

- Repo remoto: `git@github.com:learroyo5/Ecoe.git`, rama `main`.
- Bitácora por sesión: `WORKLOG.md`. Backlog y planes: `docs/optimizacion/`.

## Para continuar en otro servidor

1. Clonar el repo y crear `backend/.env` a partir de `backend/.env.example`.
2. `docker compose up --build -d` (las migraciones corren al arrancar).
3. Leer `README.md`, este archivo, `NEXT_STEPS.md` y `CLAUDE.md`.
4. Correr las pruebas (ver README). Para PostgreSQL, usar una base vacía dedicada a tests.
