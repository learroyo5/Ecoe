  # Auditoria estructural ECOE

  Fecha: 2026-06-29

  ## Resumen ejecutivo

  El proyecto ECOE esta en una v2 funcional y operable: tiene frontend Next.js, backend FastAPI, PostgreSQL via Docker Compose, autenticacion con JWT en cookie, control por roles, CRUD principal, constructor de estaciones, banco de instrumentos/plantillas/pacientes simulados, pilotaje, ejecucion en vivo con WebSocket, incidencias, evaluador, estudiante, resultados, exportaciones basicas y tests backend.

  La arquitectura actual ya supera una v1 inicial: hay separacion fisica frontend/backend/db, modelos de dominio reconocibles, scoping por ECOE en muchas rutas, validaciones de preparacion, trazabilidad calculada y una base de permisos por evento. Sin embargo, aun no esta lista como plataforma institucional escalable. Las brechas principales son: migraciones no reproducibles, autorizacion incompleta para recursos globales y WebSocket/media, modelo de instrumentos demasiado simple, resultados recalculados de forma destructiva, auditoria parcial, falta de historial/versionado, sincronizacion en vivo en memoria, ausencia de tests frontend/e2e/carga, y falta de capacidades analiticas longitudinales.

  La recomendacion central es no seguir agregando pantallas antes de estabilizar el nucleo: migraciones, permisos, auditoria, versionado de instrumentos/estaciones, modelo de sesiones de ejecucion/pilotaje y pipeline de resultados. Luego se puede crecer hacia analitica curricular, multi-cohorte, exportaciones institucionales y operacion robusta.

  ## Alcance revisado

  Se revisaron los documentos obligatorios:

  - `README.md`
  - `PROJECT_STATUS.md`
  - `NEXT_STEPS.md`
  - `datos_proyecto/README.md`

  Tambien se reviso la estructura del repositorio:

  - `backend/app/api/routes`
  - `backend/app/core`
  - `backend/app/db`
  - `backend/app/models`
  - `backend/app/schemas`
  - `backend/app/services`
  - `backend/app/utils`
  - `backend/alembic`
  - `backend/tests`
  - `frontend/src/app`
  - `frontend/src/components`
  - `frontend/src/hooks`
  - `frontend/src/lib`
  - `docker-compose.yml`
  - documentacion bajo `datos_proyecto`

  No se modifico codigo de aplicacion.

  ## Estado actual

  ### Lo que ya esta bien encaminado

  - Stack claro: FastAPI, SQLAlchemy, Pydantic, Next.js, Tailwind, PostgreSQL.
  - Separacion de contenedores `frontend`, `backend`, `db`.
  - Dominio ECOE visible en modelos: eventos, estaciones, estudiantes, equipo, instrumentos, pacientes simulados, pilotajes, sesiones en vivo, check-ins, respuestas, resultados, incidencias y auditoria.
  - Roles definidos: `admin_ecoe`, `coeditor_docente`, `coordinador_operativo`, `evaluador`, `estudiante`, `cronometrador`.
  - Scoping por evento implementado en muchas rutas mediante `ensure_event_access`.
  - Flujo operativo cubierto de punta a punta: planificacion, construccion, validacion, pilotaje, publicacion, ejecucion, evaluacion, resultados.
  - Uploads con allowlist de extensiones, limite de tamano y validacion parcial por firma.
  - Tests backend basicos para health, auth, CRUD ECOE, estaciones, incidencias, paginacion y uploads.
  - Documentacion operativa viva en README, PROJECT_STATUS, NEXT_STEPS y `datos_proyecto`.

  ### Lo que aun es fragil

  - La migracion inicial de Alembic no crea el esquema completo; `create_all` en startup actua como respaldo. Esto rompe reproducibilidad real.
  - El WebSocket `/ws/live/{ecoe_event_id}` acepta conexiones sin autenticacion ni autorizacion.
  - Media listing/download no valida acceso al ECOE asociado de la estacion/asset.
  - Los recursos globales como banco de estaciones, plantillas, instrumentos y pacientes simulados no tienen tenancy, versionado ni ownership institucional.
  - `schemas/common.py` concentra muchos DTOs y usa JSON flexible en instrumentos/formularios, lo que facilita iterar pero debilita contratos.
  - Resultados se recalculan y se reemplazan en cada lectura/exportacion (`persist_results` borra y recrea resultados).
  - Auditoria existe, pero se usa solo en algunas acciones criticas; no hay cobertura transversal ni actor/IP/user-agent/correlation id.
  - Sincronizacion en vivo depende de estado en memoria por proceso; no escala a multiples replicas.
  - No hay tests frontend, e2e, carga, concurrencia, permisos negativos por rol/recurso ni simulacion de ejecucion real.

  ## Mapa de arquitectura actual

  ```text
  Usuario
    |
    v
  Next.js frontend
    - App Router
    - paginas operativas por modulo
    - auth context con cookie session
    - API client centralizado
    - WebSocket desde /live
    |
    v
  FastAPI backend
    - rutas REST
    - WebSocket live
    - dependencias de auth/RBAC
    - servicios de dashboard, validacion, resultados
    - helpers de autorizacion, media y normalizacion
    |
    v
  PostgreSQL
    - modelos SQLAlchemy
    - Alembic parcialmente configurado
    |
    v
  Volumen local backend_storage
    - multimedia
    - exportaciones/contingencia potencial
  ```

  ### Backend

  - `main.py`: crea app, CORS, ejecuta Alembic en startup, cae a `Base.metadata.create_all`, ejecuta seeds.
  - `core/config.py`: settings, secretos, DB URL, CORS, storage.
  - `core/security.py`: PBKDF2, JWT HS256, expiracion configurable.
  - `services/dependencies.py`: usuario actual, roles globales, rate limiting en memoria.
  - `utils/helpers.py`: normalizacion, permisos por ECOE, media, serializacion, check-ins.
  - `services/validation.py`: readiness para pilotaje/publicacion/ejecucion y transiciones de estado.
  - `services/results.py`: consolidacion, trazabilidad calculada, Excel/PDF basicos.
  - `services/websocket.py`: manager en memoria para broadcast por ECOE.
  - `api/routes/*`: rutas agrupadas por auth, ECOE, estaciones/pilotaje, estudiantes, staff, evaluador, estudiante, operacional, usuarios.

  ### Frontend

  - `src/lib/api.ts`: cliente API centralizado.
  - `src/lib/auth.tsx`: contexto global de sesion, ECOE activo y dashboard.
  - `src/middleware.ts`: proteccion por cookie, sin autorizacion fina de rutas.
  - `src/app/(app)/*`: pantallas de dashboard, ECOE, estaciones, usuarios, pilotaje, live, evaluador, estudiante, resultados.
  - `src/components/*`: shell, tablas, formularios, cards, preview multimedia, toast.
  - `src/hooks/use-api.ts`: hook de carga simple.

  ### Infraestructura

  - `docker-compose.yml` levanta PostgreSQL, backend y frontend.
  - Puertos publicados solo en `127.0.0.1`, con salida publica prevista por nginx externo.
  - `.env` de backend y `datos_proyecto/credenciales_locales.md` estan ignorados por git.
  - No hay CI/CD, backups, healthchecks de aplicacion avanzados ni observabilidad centralizada en repo.

  ## Modulos existentes

  | Modulo | Estado | Observaciones |
  |---|---|---|
  | Autenticacion | Funcional | JWT en cookie HttpOnly, logout borra cookie, sin refresh token ni revocacion server-side. |
  | Usuarios | Funcional basico | CRUD admin, roles globales, sin MFA, sin politicas de password ni auditoria completa. |
  | ECOE | Funcional | CRUD, duplicado, estado guiado, permisos por evento para admin creador. |
  | Estudiantes | Funcional | Alta/importacion/paginacion/activar; sin constraints DB fuertes por ECOE. |
  | Staff | Funcional | Asignacion por ECOE, evaluador limitado a una estacion por helper. |
  | Estaciones | Funcional | Constructor rico, pero modelo grande y campos pedagogicos/operativos mezclados. |
  | Banco de estaciones | Funcional inicial | Sin versionado, ownership, aprobacion formal ni trazabilidad curricular. |
  | Instrumentos | Funcional inicial | Checklist/puntaje simple; sin rubricas avanzadas, dominios de competencia, versionado ni calibracion. |
  | Paciente simulado | Funcional inicial | Guion basico, sin agenda de entrenamiento/evaluacion del paciente simulado. |
  | Pilotaje | Separado parcialmente | `PilotRun/PilotRecord` marca prueba, pero los flujos de respuestas/evaluaciones comparten tablas con campo `mode`. |
  | Ejecucion en vivo | Funcional inicial | Timer manual y broadcast; sin autenticacion WS, sin reloj autoritativo robusto, sin multi-replica. |
  | Incidencias | Funcional | Crear/resolver/reabrir y broadcast; falta taxonomia, SLA y bitacora operacional completa. |
  | Evaluador | Funcional | Check-in, submit unico, bloqueo por tiempo en UI; falta firma/cierre/segunda evaluacion/revision. |
  | Estudiante | Funcional | Acceso por numero ECOE, autosave local, envio; falta sincronizacion robusta y recuperacion institucional. |
  | Resultados | Funcional inicial | Consolidado basico por evaluaciones, Excel/PDF simple; falta snapshot, reglas academicas y analitica. |
  | Trazabilidad | Parcial | Reporte calculado y `AuditLog` parcial; falta auditoria transversal append-only. |
  | Tests | Basicos | Backend API feliz; faltan permisos, e2e, frontend, carga, concurrencia y migraciones. |

  ## Modelo de dominio actual

  ### Entidades centrales

  - `ECOEEvent`: evento academico, estado, tiempos, configuracion general.
  - `Circuit`, `StudentGroup`: estructura operativa; poco usados en la logica actual.
  - `Student`: participante asociado a ECOE.
  - `StaffAssignment`: equipo operativo asociado a ECOE y estaciones.
  - `Station`: unidad de evaluacion con pedagogia, instrucciones, recursos, tiempos, estado.
  - `StationTemplate`, `StationBank`: reutilizacion de estructura de estaciones.
  - `AssessmentTool`, `AssessmentItem`: instrumentos de evaluacion simples.
  - `SimulatedPatient`: guion/personaje.
  - `MediaAsset`, `StationResource`: recursos asociados.
  - `PilotRun`, `PilotRecord`: pilotajes y evidencias de prueba.
  - `LiveSession`: estado operativo del timer.
  - `StationCheckIn`: confirmacion de estudiante en estacion.
  - `EvaluatorRecord`: evaluacion del evaluador.
  - `StudentResponse`: respuesta del estudiante.
  - `StationResult`, `ECOEResult`: resultados consolidados.
  - `Incident`: incidencia operacional.
  - `ContingencyExport`: exportaciones generadas.
  - `AuditLog`: auditoria parcial.
  - `Role`, `User`, `ECOEPermission`: identidad, roles y permiso de administracion por evento.

  ### Observaciones de dominio

  - La frontera entre diseno academico, ejecucion operacional y evaluacion sumativa esta en el mismo agregado `Station`.
  - `StationBank` duplica muchos campos de `Station`, lo que creara divergencia.
  - Los instrumentos no estan ligados a competencias, dominios, resultados de aprendizaje, blueprint curricular ni versiones.
  - `mode` distingue `pilotaje`/`ejecucion` en respuestas/evaluaciones, pero no hay una entidad fuerte de "sesion de ejecucion" que gobierne ciclo, participantes, estaciones, turnos y evidencia.
  - La trazabilidad es principalmente derivada; no hay un ledger de eventos de dominio completo.

  ## Principales acoplamientos

  1. Rutas con reglas de negocio: varios endpoints crean, validan, autorizan y persisten en una misma funcion.
  2. `schemas/common.py` como modulo concentrador: todos los contratos crecen en un solo archivo.
  3. `Station` como objeto grande: mezcla contenido pedagogico, logistica, multimedia, evaluacion y estado operativo.
  4. Frontend acoplado a endpoints y formas exactas del backend mediante `api.ts` y tipos manuales.
  5. Resultados acoplados a lectura/exportacion: consultar resultados modifica base de datos.
  6. WebSocket acoplado a memoria local del proceso: no hay broker ni persistencia de eventos live.
  7. Seeds acoplados al startup: si existe un usuario, se omite todo el seed; util para demo, debil para ambientes.
  8. Permisos mezclan rol global, `ECOEPermission`, `StaffAssignment` y `Student.email`; funciona, pero necesita formalizarse como politica.

  ## Deuda tecnica

  ### Alta prioridad

  - Reconstruir migraciones Alembic reales desde base limpia.
  - Separar migracion/seed del startup productivo.
  - Autenticacion/autorizacion de WebSocket.
  - Scoping de media por ECOE y audiencia.
  - Evitar mutaciones en `GET /results`.
  - Agregar constraints/indices DB: unicidad por ECOE para RUT, numero ECOE, staff email, station number; FK con cascade explicito.
  - Convertir JSON flexible de instrumentos/formularios en contratos versionados.
  - Tests negativos de permisos por rol y por ECOE.

  ### Media prioridad

  - Separar schemas por modulo.
  - Mover reglas de negocio de rutas a servicios/casos de uso.
  - Crear repositorios/query helpers para lecturas frecuentes.
  - Versionar Station/StationBank/AssessmentTool.
  - Crear `ExecutionSession`/`PilotSession` como agregado fuerte.
  - Formalizar lifecycle de ECOE y station con maquina de estados.

  ### Baja prioridad

  - Mejorar modularidad frontend por dominio.
  - Tipos generados desde OpenAPI.
  - Remplazar strings libres por enums/constantes compartidas.
  - Reducir duplicacion entre `Station` y `StationBank`.

  ## Riesgos de seguridad

  ### Criticos o altos

  - WebSocket sin autenticacion: cualquier cliente que conozca el ID podria conectarse a eventos live y recibir timer/incidencias.
  - Descarga/listado de media sin scoping de ECOE: `get_media_file(asset_id)` solo requiere usuario autenticado; falta comprobar que el usuario tenga acceso a la estacion/ECOE y a `target_viewer`.
  - JWT sin revocacion server-side: logout borra cookie, pero tokens existentes siguen validos hasta expirar.
  - `SECRET_KEY` puede quedar vacio en configuracion si no se define; se advierte, pero no falla en produccion.
  - Password hashing usa PBKDF2; aceptable si bien parametrizado, pero no es el preferido moderno frente a Argon2id.
  - Rate limiting en memoria: no sirve con multiples replicas ni reinicios; solo por IP.

  ### Medios

  - CORS depende de configuracion por string; debe cerrarse por ambiente.
  - Uploads aceptan formatos complejos (`docx`, `pptx`, `xlsx`, `svg`) sin antivirus/CDR/sandbox; riesgo para plataforma publica.
  - Validacion de magic bytes parcial; varios tipos permitidos no se validan por firma.
  - Cookies no declaran explicitamente `SameSite` por ambiente ni estrategia CSRF para mutaciones cookie-based.
  - No hay MFA para administradores ni acciones sensibles como exportar resultados.
  - No hay politica de password, rotacion, bloqueo progresivo por cuenta ni deteccion de stuffing.
  - Auditoria no cubre denegaciones, exports, cambios de usuarios/roles, descargas de evidencia ni acceso a resultados.

  ### Gestion de secretos

  - `backend/.env` y `datos_proyecto/credenciales_locales.md` estan ignorados por git, lo cual es correcto.
  - `docker-compose.yml` contiene credenciales dev por defecto (`ecoe/ecoe`) y debe quedar claramente limitado a local/demo.
  - Para produccion se requiere gestor de secretos o, al menos, procedimiento de rotacion y permisos de archivo.

  ## Riesgos de escalabilidad

  - WebSocket en memoria no funciona correctamente con multiples replicas de backend.
  - Timer no tiene reconciliacion autoritativa por timestamp; depende de broadcasts y estado persistido simple.
  - `compute_results` y `build_traceability_report` cargan listas completas en memoria; no escala a multiples cohortes/eventos grandes.
  - Exportaciones se generan sin colas ni cache; una exportacion pesada bloquea request.
  - Uploads guardan archivos locales en volumen; no hay object storage, CDN, antivirus ni lifecycle.
  - Falta paginacion/filtros en varios listados globales: estaciones, templates, instrumentos, banco.
  - No hay indices declarados en modelos/migraciones para queries por `ecoe_event_id`, `student_id`, `station_id`, `email`.
  - No hay estrategia multi-tenant institucional.

  ## Riesgos operativos para un ECOE real

  - Falta modo contingencia completo: impresion por estacion, captura offline, reingreso auditado, reconciliacion.
  - No hay cierre/firma de evaluacion por evaluador ni bloqueo institucional posterior con revision autorizada.
  - No hay control de doble evaluacion, evaluador suplente, ausencia, reemplazo de estudiante, anulacion de estacion o reintento.
  - Check-in cierra otros check-ins de la estacion, pero no modela rotaciones, turnos, circuitos espejo ni conflictos simultaneos.
  - La UI bloquea por tiempo, pero el backend no valida ventana temporal de envio.
  - El numero ECOE se usa como identificador operativo; falta estrategia antifraude y control de identidad local.
  - Incidencias no tienen workflow formal: responsable, severidad normalizada, impacto academico, resolucion validada.
  - Resultados pueden recalcularse despues de cambios sin snapshot firmado.
  - No hay bitacora operacional completa por segundo/minuto de ejecucion.
  - No hay runbook de dia de ECOE, backups pre-evento, restauracion, monitoreo, plan B de red/electricidad.

  ## Brechas respecto a plataforma institucional

  ### Planificacion, pilotaje y ejecucion

  - Existe separacion conceptual y algunos modelos, pero falta una separacion fuerte de contextos.
  - Pilotaje deberia tener sesiones, participantes de prueba, resultados excluidos, feedback estructurado y decision de aprobacion.
  - Ejecucion real deberia tener snapshot inmutable de estaciones, instrumentos, estudiantes, asignaciones y tiempos.

  ### Instrumentos

  - Falta versionado de instrumentos y criterios.
  - Falta relacion con competencias, subcompetencias, EPAs/resultados de aprendizaje, nivel esperado y ponderaciones.
  - Falta calibracion/inter-rater, comentarios por item, criterios de logro, rubricas multi-nivel.
  - Falta bloqueo del instrumento al publicar/ejecutar.

  ### Resultados

  - Falta modelo de intentos/snapshots/result sets.
  - Falta trazabilidad de formula de nota, ponderaciones, reglas de aprobacion, anulaciones y ajustes.
  - Falta analisis por estacion, item, competencia, evaluador, cohorte y periodo.
  - Falta exportacion institucional robusta y reproducible.

  ### Trazabilidad y auditoria

  - Falta auditoria transversal, append-only, con actor, rol, IP, user-agent, request id, accion, entidad, antes/despues y motivo.
  - Falta auditoria de acceso a datos sensibles y exportaciones.
  - Falta versionado de contenido academico.

  ### Permisos por rol

  - Hay RBAC global y scoping por evento parcial.
  - Falta matriz formal de permisos, ABAC/ReBAC por recurso, permisos por ECOE, estacion, instrumento y accion.
  - Falta separar roles institucionales de roles operativos por evento.

  ### Migraciones

  - Alembic no representa el schema completo.
  - Falta politica de migraciones revisadas, rollback, seed idempotente por ambiente y datos demo separados.

  ### Tests

  - Faltan frontend tests, e2e, pruebas de autorizacion negativa, pruebas de migraciones, pruebas de concurrencia live, pruebas de exportacion, pruebas de carga y simulaciones de dia de ECOE.

  ### Sincronizacion en vivo

  - Falta autenticacion WS, broker, persistencia de eventos, reconexion con replay, reloj autoritativo y tolerancia multi-dispositivo.

  ### Exportaciones

  - Existen Excel/PDF basicos, pero falta formato institucional, firmas, version del calculo, filtros, anonimizado, trazabilidad de descarga y colas.

  ### Analisis longitudinal de competencias

  - No existe todavia un modelo curricular longitudinal.
  - Faltan entidades como `Competency`, `Outcome`, `CurriculumMap`, `Cohort`, `Program`, `CourseOffering`, `AssessmentBlueprint`, `ItemCompetencyMapping`.
  - Faltan agregados historicos por estudiante/cohorte/competencia/periodo y normalizacion de instrumentos entre eventos.

  ## Recomendaciones priorizadas

  ### P0 - Estabilizar base institucional

  1. Reconstruir Alembic con migracion inicial completa y eliminar `create_all` de produccion.
  2. Hacer que backend falle si `SECRET_KEY` esta vacio en ambiente no dev.
  3. Autenticar y autorizar WebSocket por cookie/token y `ensure_event_access`.
  4. Scoping de media: validar acceso al asset por estacion/ECOE y audiencia.
  5. Convertir `GET /results` en lectura pura; mover persistencia a accion explicita de cierre/consolidacion.
  6. Agregar constraints e indices criticos.
  7. Crear matriz de permisos y tests negativos por rol/recurso.

  ### P1 - Separar contextos de negocio

  1. Crear agregados `PlanningECOE`, `PilotSession`, `ExecutionSession`, `ResultSet`.
  2. Crear snapshots inmutables al publicar: estaciones, instrumentos, asignaciones, estudiantes, tiempos.
  3. Versionar instrumentos, estaciones de banco y plantillas.
  4. Separar schemas por modulo y contratos de instrumentos/formularios.
  5. Mover reglas de negocio de rutas a servicios/casos de uso.

  ### P2 - Robustecer operacion real

  1. Event log operacional append-only.
  2. WebSocket con Redis Pub/Sub o broker equivalente.
  3. Backend valida ventanas de envio y estado de sesion.
  4. Modo contingencia completo con exportacion previa y reconciliacion posterior.
  5. Observabilidad: logs JSON, request id, metricas, alertas y dashboards.
  6. Backups automatizados y restore probado.

  ### P3 - Plataforma academica y analitica

  1. Modelo curricular: competencias, subcompetencias, outcomes, mapa curricular.
  2. Blueprint de ECOE por competencias y estaciones.
  3. Analisis longitudinal por estudiante, cohorte, curso, competencia, estacion, item y evaluador.
  4. Calibracion de evaluadores e indicadores psicometricos basicos.
  5. Exportaciones institucionales versionadas y anonimizado.

  ## Arquitectura objetivo propuesta

  ```text
  Frontend Next.js
    - modulos: planning, station-bank, pilotage, live, evaluator, student, results, analytics, admin
    - API client generado desde OpenAPI
    - e2e tests Playwright
    |
  API Gateway / FastAPI
    - auth/session
    - policy layer central
    - REST + WebSocket autenticado
    |
  Aplicacion por contextos
    - Identity & Access
    - ECOE Planning
    - Station & Instrument Authoring
    - Pilotage
    - Live Execution
    - Evaluation Capture
    - Results & Exports
    - Curriculum Analytics
    - Audit & Compliance
    |
  Persistencia
    - PostgreSQL normalizado
    - Alembic reproducible
    - audit/event tables append-only
    - object storage para media/exportaciones
    |
  Tiempo real y jobs
    - Redis Pub/Sub para WebSocket multi-replica
    - queue para exportaciones, recalculos, reportes
    |
  Operacion
    - backups, restore drills, logs estructurados, metricas, alertas
  ```

  ### Principios de la arquitectura objetivo

  - Publicar un ECOE crea un snapshot inmutable.
  - Pilotaje nunca contamina ejecucion real.
  - Resultados se calculan desde evidencia versionada y dejan un `ResultSet` firmado/logueado.
  - Cada acceso a datos sensibles y cada exportacion queda auditada.
  - La autorizacion se decide por politica central, no por convenciones dispersas.
  - El tiempo real es tolerante a reconexion, multiples replicas y clientes tardios.
  - Competencias e instrumentos son entidades de primera clase.

  ## Plan de refactorizacion por fases

  ### Fase 1 - Fundacion segura y reproducible

  Objetivo: que el sistema pueda instalarse, migrarse y proteger datos de forma confiable.

  - Crear migracion inicial completa.
  - Agregar indices/constraints.
  - Separar seed demo de startup productivo.
  - Endurecer `SECRET_KEY`, cookies, CORS y JWT.
  - Autenticar WebSocket.
  - Corregir permisos de media.
  - Tests: migracion desde cero, auth WS, media IDOR, permisos negativos.

  Criterio de salida: una instalacion limpia con `alembic upgrade head` crea todo el schema; ningun usuario autenticado puede ver media/eventos fuera de su ECOE.

  ### Fase 2 - Permisos, auditoria y lifecycle

  Objetivo: convertir RBAC simple en permisos institucionales auditables.

  - Definir matriz de permisos por accion/recurso.
  - Centralizar policy checks.
  - Extender `AuditLog` o crear `AuditEvent` append-only.
  - Auditar login/logout, denegaciones, usuarios, roles, ECOE, estaciones, instrumentos, exports, resultados.
  - Formalizar maquinas de estado para ECOE, estacion y sesion live.

  Criterio de salida: cada endpoint sensible tiene test allow/deny; las acciones criticas quedan auditadas con contexto.

  ### Fase 3 - Dominio academico versionado

  Objetivo: separar construccion academica de ejecucion real.

  - Versionar instrumentos y estaciones.
  - Crear snapshots de publicacion.
  - Crear `PilotSession` y `ExecutionSession`.
  - Separar registros de prueba, ejecucion real y contingencia.
  - Bloquear cambios a contenido publicado salvo nueva version.

  Criterio de salida: un ECOE ejecutado puede reproducir exactamente que instrumento/estacion uso cada estudiante.

  ### Fase 4 - Operacion en vivo robusta

  Objetivo: soportar dia de ECOE real con resiliencia.

  - Redis Pub/Sub para WebSocket.
  - Reloj autoritativo por timestamp y replay de estado.
  - Backend valida ventana temporal de check-in/envio.
  - Modo contingencia completo.
  - Observabilidad y runbooks.

  Criterio de salida: reconexion de clientes y reinicio de una replica no pierde el estado operacional ni habilita envios invalidos.

  ### Fase 5 - Resultados y exportaciones institucionales

  Objetivo: pasar de consolidado basico a evaluacion defendible.

  - Crear `ResultSet` versionado.
  - Calcular por estacion, item, competencia, evaluador, estudiante y cohorte.
  - Soportar anulaciones/ajustes con motivo y auditoria.
  - Exportaciones con formato institucional, firma/metadata y colas.
  - Tests de formulas y snapshots.

  Criterio de salida: cada reporte puede rastrearse a evidencia, version de instrumento y formula.

  ### Fase 6 - Analitica curricular longitudinal

  Objetivo: convertir ECOE en plataforma de mejora curricular.

  - Modelo de competencias/outcomes/mapa curricular.
  - Mapeo instrumento-item-competencia.
  - Analisis longitudinal por cohorte, estudiante, curso, periodo y competencia.
  - Dashboards de brechas y tendencias.
  - Exportes anonimizados para comites curriculares.

  Criterio de salida: la institucion puede responder que competencias mejoran/empeoran en el tiempo y en que estaciones/items aparece la evidencia.

  ## Decision recomendada de corto plazo

  Antes de agregar nuevas features visibles, conviene ejecutar una iteracion tecnica P0 de 1 a 2 semanas centrada en migraciones, permisos, WebSocket/media y resultados no destructivos. Esa inversion reduce riesgo operacional y evita que la plataforma crezca sobre una base que luego sera mas costosa de corregir.

  El proyecto tiene una buena base funcional. La oportunidad ahora es convertir esa base en un nucleo confiable: menos demo, mas evidencia, versionado, auditoria y reglas explicitas.
