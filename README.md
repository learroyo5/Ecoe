# Proyecto Tecnologico ECOE

Plataforma web para planificacion, pilotaje, ejecucion y cierre de ECOE/OSCE en carreras de la salud.

**Version actual: v2** — CRUD completo del ECOE, constructor de estaciones con multimedia, panel en vivo con WebSocket, gestion de incidencias en tiempo real, y suite de tests.

## Punto de partida

Si vamos a retomar desarrollo sobre este repo, conviene leer en este orden:

1. `README.md`
2. `PROJECT_STATUS.md`
3. `NEXT_STEPS.md`
4. `datos_proyecto/README.md`

Eso deja claro:

- como levantar el stack
- cual es el estado real del proyecto
- cual es la prioridad de trabajo
- donde mirar operacion, credenciales y notas de producto

## Arquitectura

```text
ecoe/
├── backend/
│   ├── app/
│   │   ├── api/         # Routers REST + WebSocket
│   │   ├── core/        # Configuracion y seguridad
│   │   ├── db/          # Session, bootstrap y seeds
│   │   ├── models/      # SQLAlchemy ORM
│   │   ├── schemas/     # Validacion Pydantic
│   │   ├── services/    # Reglas de negocio y dependencias
│   │   └── utils/       # Archivos e importadores
│   ├── alembic/         # Migraciones de base de datos
│   ├── tests/           # Tests con pytest + fastapi.testclient
│   └── Dockerfile
├── frontend/
│   ├── src/app/         # App Router y pantallas (incluye /ecoe/[id])
│   ├── src/components/  # Shell, tablas, formularios, cards, media-preview
│   ├── src/hooks/       # Carga de datos
│   └── src/lib/         # API client, auth y tipos
└── docker-compose.yml
```

## Modulos incluidos

### Gestion del ECOE (v2)
- Formulario completo con validacion frontend, organizado en 3 secciones (Datos generales, Configuracion del circuito, Parametros de tiempo/evaluacion).
- `circuit_mode` como selector con 4 modos documentados.
- Transiciones de estado guiadas con botones de accion y modales de confirmacion (borrador → configuracion → pilotaje → publicado → ejecucion → cerrado → archivado).
- Vista de detalle `/ecoe/[id]` con 4 tabs: General, Estaciones, Participantes, Pilotajes.
- Duplicado de ECOE con opcion de copiar evaluadores y estaciones.

### Autenticacion y usuarios
- Autenticacion con JWT (cookie + Bearer) y control por rol.
- Panel de gestion de usuarios (`/users`) — solo administrador.
- Roles: `admin_ecoe`, `coeditor_docente`, `coordinador_operativo`, `evaluador`, `estudiante`, `cronometrador`.

### Estaciones
- Listado con cards, badges de estado, y boton de edicion por estacion.
- Constructor con 4 pasos guiados: origen, pedagogia, instrucciones, recursos.
- Asociacion de plantilla, instrumento de evaluacion y paciente simulado desde el constructor.
- Upload de multimedia con validacion por tipo, selector de audiencia, y preview inline (MediaPreview).

### Banco de plantillas, instrumentos y pacientes simulados

### Pilotaje separado de ejecucion real

### Panel en vivo (WebSocket)
- Cronometro central sincronizado en tiempo real via WebSocket (`/ws/live/{id}`).
- Controles: start, pause, resume, reset, next_transition.
- Gestion de incidencias: creacion rapida, resolucion, reapertura, con broadcast en tiempo real.
- Severidad: baja, media, alta, critica.

### Evaluador
- Identificacion de estudiante por numero ECOE.
- Render dinamico de instrumentos: checklist (toggle Si/No) y puntaje numerico.
- Bloqueo efectivo por tiempo: timer en rojo, campos deshabilitados al expirar.

### Estudiante
- Identificacion por numero ECOE.
- Formulario dinamico con 3 tipos de pregunta: seleccion unica, multiple, texto corto.
- Auto-guardado en localStorage y envio automatico al expirar el tiempo.
- Visualizacion de multimedia (imagen, video, audio, PDF).

### Resultados
- Consolidacion automatica, porcentaje, nota equivalente.
- Exportacion Excel y PDF de contingencia.

### Seeds demo
- 1 ECOE de ejemplo
- 5 estaciones
- 10 estudiantes
- 3 evaluadores/colaboradores
- 1 paciente simulado
- 1 pilotaje inicial

## Levantar con Docker

```bash
docker compose up --build
```

Servicios:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Docs API: `http://localhost:8000/docs`

Estado verificado en este servidor:

- Docker expone solo a `127.0.0.1`
- la salida publica actual va por `nginx` del sistema
- dominio publicado: `https://ecoe.drnotus.cl`
- health backend publico: `https://ecoe.drnotus.cl/api/health`

Acceso desde otro equipo en la red:

- UI: `http://IP_DEL_SERVIDOR:3000`
- API directa: `http://IP_DEL_SERVIDOR:8000`

El frontend ya viene configurado para consumir la API mediante proxy interno (`/backend/api`), por lo que al abrir la UI desde otra maquina no depende de `localhost` del cliente.

## Credenciales

- Las credenciales activas del servidor actual no son las del README historico.
- Las claves locales vigentes estan en `backend/.env`.
- Referencia operativa: `datos_proyecto/credenciales_locales.md`
- Usuario demo: `admin@ecoe.cl`

## Variables de entorno

Frontend:

```bash
cp frontend/.env.example frontend/.env.local
```

Backend:

```bash
cp backend/.env.example backend/.env
```

## Ejecucion local sin Docker

Backend:

```bash
cd backend
python3 -m pip install --break-system-packages -r requirements.txt
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Si quieres exponerlo fuera de la red local en un servidor Ubuntu:

```bash
docker compose up --build -d
```

Para este proyecto, la recomendacion actual no es exponer Docker directo a internet. En este servidor la publicacion se hace con `nginx` como reverse proxy sobre `127.0.0.1`.

Referencia de despliegue:

- `datos_proyecto/operacion_despliegue.md`
- `datos_proyecto/ajuste_publico_ecoe.md`

## Tests

```bash
cd backend
python3 -m pytest tests/test_api.py -v
```

23 tests cubriendo: health, auth, CRUD ECOE, estaciones, incidencias (crear/resolver/reabrir), paginacion, y seguridad de archivos.

## Migraciones (Alembic)

```bash
cd backend
alembic upgrade head          # aplicar migraciones
alembic revision --autogenerate -m "descripcion"  # generar nueva migracion
```

## Endpoints principales

- `POST /api/auth/login`
- `GET /api/dashboard/{ecoe_event_id}`
- `GET|POST /api/ecoe` — `PUT /api/ecoe/{id}` — `POST /api/ecoe/{id}/duplicate`
- `GET|POST /api/students` — `PATCH /api/students/{id}/status` — `POST /api/students/import`
- `GET|POST /api/staff` — `PATCH /api/staff/{id}` — `POST /api/staff/import`
- `GET|POST|PUT /api/stations` — `PUT /api/stations/{id}`
- `GET|POST /api/templates`
- `GET|POST /api/instruments`
- `GET|POST /api/simulated-patients`
- `GET|POST /api/pilotage` — `POST /api/pilotage/{id}/archive`
- `GET|POST /api/live/control` — `WS /ws/live/{id}`
- `GET|POST /api/incidents` — `PATCH /api/incidents/{id}/resolve`
- `GET|POST|PATCH /api/users`
- `POST /api/evaluator/submit`
- `POST /api/student/submit`
- `GET /api/results/{ecoe_event_id}`
- `POST /api/media/upload` — `GET /api/media/{station_id}` — `DELETE /api/media/{id}`

## Verificacion realizada

- 23 tests backend con `pytest` + SQLite (todas las clases pasando).
- Frontend validado con `npm run build`.
- Stack verificado en ejecucion con `docker compose ps`.
- Frontend accesible en `/login`.
- Backend respondiendo `GET /health -> 200 OK`.
- Dominio publico `https://ecoe.drnotus.cl` accesible.

## Historial reciente de commits (evolucion v1 → v2)

| Commit | Que hizo |
|---|---|
| `88e25e4` | Rename `creador_ecoe` → `admin_ecoe`, duplicacion ECOE, CRUD usuarios |
| `af1a0fe` | Formulario ECOE con validacion + StatusTransitionBar guiado |
| `f48d85c` | Vista detalle ECOE con tabs |
| `040e64f` | Listado estaciones redisenado + MediaPreview |
| `038344c` | Gestion de incidencias con WebSocket |
| `cc8b2e2` | Bloqueo por tiempo, tests (23/23), Alembic, storage fix |

## Decisiones de esta version

- Persistencia con migraciones Alembic + creacion automatica en startup como respaldo.
- Multimedia y exportaciones almacenadas en volumen local del backend, ruta configurable via `STORAGE_PATH`.
- Permisos por rol simples y claros, sin ACL avanzada todavia.
- Cronometro manual y operativo, sincronizado entre clientes via WebSocket.
- Pilotaje y ejecucion real estan separados a nivel de modelo y registros.
- Incidencias gestionables en tiempo real con broadcast WebSocket.
