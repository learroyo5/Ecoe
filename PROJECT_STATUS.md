# Project Status

## Proyecto

- Nombre: `Proyecto Tecnologico ECOE`
- Objetivo: plataforma web para planificacion, pilotaje, ejecucion, contingencia y cierre de ECOE/OSCE para carreras de la salud.
- Estado actual: `v2 funcional`

## Estado general

La v2 del producto esta completa y ya paso su primer ensayo funcional real con el equipo (2026-08-18, ver seccion abajo): CRUD del ECOE con maquina de estados real en backend, constructor de estaciones con multimedia y formularios puntuables, panel en vivo con WebSocket con reconexion automatica y vista proyector, modo kiosco por estacion para tablets compartidas, correccion manual de respuestas, registro por contingencia, invitaciones/reinicio de acceso por correo real, y suite de tests (175 backend + 29 frontend + e2e Playwright del flujo dorado). El proyecto corre con Docker Compose en este servidor con salida publica por `nginx`.

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

## Arquitectura implementada

- Frontend:
  - Next.js con App Router
  - TypeScript
  - Tailwind CSS
  - layout con menu lateral y pantallas operativas
  - ruta dinamica `/ecoe/[id]` para vista de detalle
- Backend:
  - FastAPI
  - SQLAlchemy ORM
  - Pydantic
  - WebSocket para tiempo real
  - autenticacion JWT (cookie + Bearer) por rol
  - migraciones Alembic
  - tests con pytest + SQLite
- Base de datos:
  - PostgreSQL en Docker Compose
- Infraestructura:
  - `frontend`, `backend` y `db` separados en `docker-compose.yml`

## Modulos implementados

- Autenticacion:
  - login con JWT (cookie + Bearer)
  - sesion por token
  - proteccion por rol
  - panel institucional de usuarios (`admin_global`)
  - delegacion de `admin_ecoe` por evento
- Gestion ECOE:
  - listado con selector de ECOE activo
  - formulario completo en 3 secciones con validacion frontend
  - transiciones de estado guiadas con modales de confirmacion
  - duplicado con opcion de copiar evaluadores y estaciones
  - vista de detalle `/ecoe/[id]` con 4 tabs (General, Estaciones, Participantes, Pilotajes)
- Estudiantes:
  - alta manual
  - importacion CSV/Excel
  - listado con paginacion
- Evaluadores y colaboradores:
  - alta manual
  - importacion CSV/Excel
  - listado con paginacion
- Estaciones:
  - listado con cards y badges de estado
  - constructor con 4 pasos guiados
  - edicion de estaciones existentes
  - asociacion de plantilla, instrumento y paciente simulado
  - upload de multimedia con preview inline (MediaPreview)
- Banco de plantillas
- Banco de instrumentos
- Gestor de paciente simulado
- Pilotaje:
  - creacion
  - listado
  - archivado
  - separacion de datos de prueba
- Panel en vivo:
  - cronometro central sincronizado via WebSocket
  - start/pause/resume/reset/transition
  - broadcast de estado en tiempo real a todos los clientes
- Incidencias:
  - creacion rapida con severidad (baja/media/alta/critica)
  - resolucion y reapertura
  - broadcast en tiempo real via WebSocket
  - contadores de activas/resueltas
- Interfaz evaluador:
  - identificacion de estudiante
  - render dinamico de instrumentos (checklist + puntaje numerico)
  - bloqueo efectivo por tiempo (timer rojo, campos deshabilitados)
- Interfaz estudiante:
  - identificacion por numero ECOE
  - formulario dinamico (3 tipos de pregunta)
  - auto-guardado local y envio automatico al expirar el tiempo
  - visualizacion de multimedia
- Resultados:
  - consolidacion automatica
  - porcentaje
  - nota equivalente
  - exportacion Excel
  - exportacion PDF de contingencia

## Datos demo cargados

- 1 ECOE de ejemplo
- 5 estaciones
- 10 estudiantes
- 3 evaluadores/colaboradores
- 1 paciente simulado
- 1 pilotaje

## Verificaciones ya realizadas

- `npm run build`, `npm run lint` y `npm test` (29 tests frontend con vitest)
- 167 tests backend con `pytest`, verdes tanto en SQLite como en PostgreSQL real aplicando migraciones Alembic (lo que corre CI). Cubren health, auth, CRUD ECOE, estaciones, incidencias, paginacion, seguridad de archivos, matriz de permisos, maquina de estados, gate de envios, kiosco, correccion e invitaciones de equipo
- `docker compose up --build -d`
- acceso UI por red local
- acceso backend por healthcheck y endpoints autenticados
- verificacion local de `http://127.0.0.1:3000`
- verificacion local de `http://127.0.0.1:8000/health`
- verificacion publica de `https://ecoe.drnotus.cl`
- verificacion publica de `https://ecoe.drnotus.cl/api/health`
- dominios propios de producto en produccion desde 2026-08-25: `https://ecoe.cl` (landing), `https://app.ecoe.cl` (plataforma, mismo backend), `https://plataformaecoe.cl` (redirect a `ecoe.cl`) — detalle en `datos_proyecto/operacion_despliegue.md`

## Decisiones importantes tomadas

- El frontend consume la API mediante proxy interno (`/backend/api`) para evitar romper acceso desde otras maquinas de la red.
- La persistencia usa migraciones Alembic + creacion automatica de tablas en startup como respaldo.
- El control combina autoridad institucional global con roles efectivos por ECOE.
- La incorporacion de equipos es descentralizada por evento: `admin_ecoe` puede reutilizar una cuenta activa o emitir una invitacion de activacion para una identidad nueva, sin acceso al directorio institucional completo ni a las contrasenas. Vale igual para el alta de a uno y para la importacion masiva.
- Las identidades son institucionales y unicas por correo; las funciones operativas se representan como asignaciones independientes por ECOE. La cuenta es duena de su nombre: un tipeo en el formulario de alta nunca crea una identidad divergente para el mismo correo.
- `station_ids` solo tiene significado funcional para el rol `evaluador`; el resto de los roles opera sobre el ECOE completo.
- El cronometro es manual y operativo, sincronizado entre clientes via WebSocket.
- Pilotaje y ejecucion real estan separados a nivel de modelo y registros.
- Las incidencias se transmiten en tiempo real via WebSocket.
- El storage path de multimedia es configurable via `STORAGE_PATH`.

## Limites actuales

- No hay reproduccion real de audio integrada en el cronometro; solo estructura preparada.
- Hay scoping por ECOE, estacion, audiencia y check-in; aun falta ACL institucional mas granular para bancos compartidos y otras unidades academicas.
- Las invitaciones nuevas se comparten manualmente; aun no hay envio por correo ni recuperacion automatica del enlace mostrado una vez. Con SMTP configurado, el import podria repartir las invitaciones solo y el panel de enlaces dejaria de ser necesario.
- Un evaluador solo admite una estacion principal a la vez: cubrir dos estaciones exige dos personas distintas.
- La pausa del cronometro central no extiende las ventanas de envio de la rotacion en curso; esos casos se resuelven por contingencia (documentado en docs/OPERACION_DIA_EXAMEN.md).
- La operacion publica depende de configuracion externa de `nginx`, router y Cloudflare, no solo del repo.

## Estado de la primera prueba funcional real (hecha, 2026-08-18)

El ECOE demo `ECOE Medicina Interna 2026` (id 1) sigue en `en_pilotaje`. El ensayo general con el equipo se corrio de punta a punta: check-in, cronometro y evaluacion/kiosco en las 5 estaciones (1, 3 y 5 con evaluador real logueado; 2 y 4 cubiertas por coordinacion operativa vía el nuevo selector de estacion). Pilotaje `circuito_completo` con hallazgos registrados (`pilot_run` id 3, ver pantalla Pilotaje).

Durante la preparacion y el ensayo se encontraron y corrigieron en vivo:

- `update_station` regresaba el estado de una estacion ya publicada a `incompleta`/`lista_para_pilotaje` al editarla, desincronizandola del resto (asi fue como la estacion 2 quedo en `lista_para_pilotaje`).
- `update_ecoe_timing` no resincronizaba la `LiveSession` existente: el cronometro en vivo seguia mostrando los minutos de cuando se creo la sesion (8 min), no los configurados despues en la pestana ECOE (5 min).
- La pantalla Estaciones no distinguia cuales necesitan Modo kiosco (formulario de estudiante y/o multimedia); ahora lo marca y deshabilita el boton en las que no aplica.
- `admin_ecoe`/`coordinador_operativo` no podian hacer check-in en una estacion sin evaluador asignado: la pantalla Evaluador solo mostraba la estacion propia del usuario. Ahora esos roles ven un selector con todas las estaciones del evento.
- Invitaciones y reinicio de acceso ahora envian correo real (SMTP configurado en `backend/.env`); antes el enlace de activacion solo se mostraba una vez en pantalla para repartir a mano.

Pendiente antes del examen real: asignar evaluador fijo a las estaciones 2 y 4 (hoy las cubre coordinacion en el ensayo), y hacer la prueba de red formal en el recinto real.

## Repo y continuidad

- Repo remoto: `git@github.com:learroyo5/Ecoe.git`
- Rama principal de trabajo: `main`
- Fuente de verdad del proyecto: este repositorio
- Ultimo commit: `4168e8c` — fix: mostrar el enlace Evaluador a admin_ecoe y coordinador_operativo

## Recomendacion para continuar en otro servidor

1. Clonar repo desde GitHub.
2. Levantar con Docker Compose.
3. Leer `README.md`, este archivo, `NEXT_STEPS.md` y `datos_proyecto/README.md`.
4. Ejecutar `alembic upgrade head` para asegurar que el schema este al dia.
5. Ejecutar `pytest` para verificar integridad. Contra PostgreSQL real (lo que corre CI): `TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q`, creando antes la base `ecoe_test` si no existe.
6. Continuar por iteraciones pequenas con commit frecuente.
