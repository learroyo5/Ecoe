# Proyecto Tecnologico ECOE

Primera version funcional de una plataforma web para planificacion, pilotaje, ejecucion y cierre de ECOE/OSCE en carreras de la salud.

## Arquitectura

```text
ecoe/
├── backend/
│   ├── app/
│   │   ├── api/         # Routers REST
│   │   ├── core/        # Configuracion y seguridad
│   │   ├── db/          # Session, bootstrap y seeds
│   │   ├── models/      # SQLAlchemy ORM
│   │   ├── schemas/     # Validacion Pydantic
│   │   ├── services/    # Reglas de negocio y dependencias
│   │   └── utils/       # Archivos e importadores
│   └── Dockerfile
├── frontend/
│   ├── src/app/         # App Router y pantallas
│   ├── src/components/  # Shell, tablas, formularios y cards
│   ├── src/hooks/       # Carga de datos
│   └── src/lib/         # API client, auth y tipos
└── docker-compose.yml
```

## Modulos incluidos

- Autenticacion con JWT y control basico por rol.
- Gestion de ECOE, estudiantes, evaluadores y estaciones.
- Banco de plantillas, instrumentos y pacientes simulados.
- Pilotaje separado de ejecucion real.
- Panel en vivo con cronometro central y acciones manuales.
- Interfaz del evaluador y del estudiante.
- Consolidacion de resultados y exportacion a Excel/PDF.
- Seeds demo con:
  - 1 ECOE
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

Acceso desde otro equipo en la red:

- UI: `http://IP_DEL_SERVIDOR:3000`
- API directa: `http://IP_DEL_SERVIDOR:8000`

El frontend ya viene configurado para consumir la API mediante proxy interno (`/backend/api`), por lo que al abrir la UI desde otra maquina no depende de `localhost` del cliente.

## Usuarios demo

- `creator@ecoe.cl` / `admin123`
- `coeditor@ecoe.cl` / `admin123`
- `eval1@ecoe.cl` / `admin123`
- `coord@ecoe.cl` / `admin123`
- `timer@ecoe.cl` / `admin123`

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
sudo ufw allow 3000/tcp
sudo ufw allow 8000/tcp
docker compose up --build -d
```

Luego accede desde `http://IP_DEL_SERVIDOR:3000`.

## Endpoints principales

- `POST /api/auth/login`
- `GET /api/dashboard/{ecoe_event_id}`
- `GET|POST /api/students`
- `GET|POST /api/staff`
- `GET|POST /api/stations`
- `GET|POST /api/templates`
- `GET|POST /api/instruments`
- `GET|POST /api/simulated-patients`
- `GET|POST /api/pilotage`
- `GET|POST /api/live/control`
- `POST /api/evaluator/submit`
- `POST /api/student/submit`
- `GET /api/results/{ecoe_event_id}`

## Verificacion realizada

- Backend validado con `fastapi.testclient` usando SQLite para smoke test.
- Frontend validado con `npm run lint` y `npm run build`.

## Decisiones de esta v1

- Persistencia simple con creacion automatica de tablas en startup.
- Multimedia y exportaciones almacenadas en volumen local del backend.
- Permisos por rol basicos y claros, sin ACL avanzada todavia.
- Cronometro preparado para control manual; la reproduccion de audio queda lista para extenderse en siguientes iteraciones.
