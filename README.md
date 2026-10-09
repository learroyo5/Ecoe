# Plataforma ECOE

Plataforma web para planificar, pilotear, ejecutar y cerrar ECOE/OSCE (exámenes clínicos objetivos estructurados) en carreras de la salud.

- Producción: `https://app.ecoe.cl` (también `https://ecoe.drnotus.cl`, mismo backend)
- Demostración: `https://demo.ecoe.cl` (misma versión, base de datos propia)
- Landing: `https://ecoe.cl`

## Por dónde empezar

Leer en este orden:

1. `README.md` (este archivo)
2. `PROJECT_STATUS.md` — qué está construido y qué límites tiene
3. `NEXT_STEPS.md` — qué sigue
4. `CLAUDE.md` — arquitectura y reglas que no son evidentes leyendo el código
5. `datos_proyecto/operacion_despliegue.md` — servidor, túnel, respaldos, demo

Para operar un examen: `docs/OPERACION_DIA_EXAMEN.md`. Para usar la plataforma: `MANUAL_USUARIO.md`.

## Stack

| Capa | Tecnología |
|---|---|
| Backend | FastAPI, SQLAlchemy 2, Pydantic, Alembic, PostgreSQL 16 |
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS |
| Tiempo real | WebSocket (cronómetro, timbre, incidencias) |
| Infraestructura | Docker Compose (`frontend`, `backend`, `db`, `db-backup`), túnel de Cloudflare |
| Pruebas | pytest (SQLite y PostgreSQL con migraciones), vitest, Playwright |

```text
backend/app/
├── api/routes/   # REST + WebSocket, un router por dominio
├── core/         # configuración (variables de entorno) y seguridad (JWT, hashing)
├── db/           # sesión, seed base y seed_demo (instancia de demostración)
├── models/       # entidades SQLAlchemy y enums
├── schemas/      # Pydantic
├── services/     # reglas de negocio: validación y estados, resultados, psicometría,
│                 #   cronómetro (live_cycle, live_sweep), espejos, candados por estado,
│                 #   presencia y tablero, kiosco, corrección, invitaciones
└── utils/        # reloj, gates de envío y deadlines, archivos, paginación
backend/alembic/  # migraciones (única forma de cambiar el esquema)
backend/tests/    # pytest

frontend/src/
├── app/(app)/    # pantallas autenticadas
├── app/kiosk/    # modo kiosco (tablet de estación, sin login)
├── components/   # shell, barra lateral, formularios, diálogos, tablero de estaciones
└── lib/          # cliente API, autenticación, rutas y permisos, WebSocket

scripts/          # deploy, demo, respaldos, e2e
docs/             # operación del día del examen, arquitectura, backlog y planes
```

## Qué hace

El ECOE sigue un ciclo con autoridad en el backend:

`borrador → en configuración → listo para pilotaje → en pilotaje → pilotaje validado → publicado → en ejecución → cerrado → archivado`

**Configurar**
- Datos del ECOE, tiempos y porcentaje de aprobación.
- Estaciones con el Constructor (identidad, pauta, instrucciones, recursos), o desde el banco.
- **Circuitos espejo**: se diseña un circuito y la plataforma crea su copia idéntica para otro piso o sala; las estaciones espejo no se editan por separado.
- Nómina de estudiantes (manual o Excel/CSV) y equipo (evaluadores, correctores, coordinación, cronometrador) con invitación por correo.
- Biblioteca reutilizable: banco de estaciones, plantillas, instrumentos y pacientes simulados.

**Preparar**
- Validación que bloquea pilotaje y publicación mientras falte algo.
- Pilotaje separado de la ejecución real: sus registros nunca entran a las notas.
- Desde la publicación, la estructura queda bloqueada; para cambiarla hay que despublicar.

**Día del examen**
- Panel en vivo: cronómetro central (manual o circuito automático por rondas), timbre, vista proyector, incidencias.
- Tablero de estaciones y verificación previa: qué evaluador y qué tablet están conectados y qué falta registrar.
- Evaluador: confirma al estudiante por número ECOE y registra la pauta; avisa si el número corresponde a otra estación u otro circuito; permite anular un ingreso equivocado.
- Kiosco: una tablet por estación con formulario o multimedia, sin login del estudiante.
- El servidor guarda borradores y cierra las ventanas vencidas aunque una tablet falle.
- Contingencia: transcribir lo resuelto en papel y rectificar registros, con auditoría.

**Cerrar**
- Corrección diferida de respuestas abiertas.
- El cierre exige que cada estudiante tenga todas sus estaciones, o que la dirección lo fuerce (las faltantes cuentan 0).
- Acta congelada con identidad y cobertura; reapertura controlada, con motivo, que archiva el acta anterior.
- Resultados por estudiante y por estación, análisis psicométrico, exportación a Excel.

## Levantar en local

```bash
cp backend/.env.example backend/.env      # completar SECRET_KEY y contraseñas
docker compose up --build
```

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000` (documentación en `/docs`)

Fuera de producción y con `AUTO_SEED_DEMO=true` se cargan cuentas y un ECOE de ejemplo. Las credenciales vigentes de cada entorno están en su archivo `.env`, nunca en este repositorio.

## Pruebas

Backend (desde `backend/`):

```bash
python3 -m pytest                      # SQLite, rápido
TEST_DATABASE_URL=postgresql+psycopg://ecoe:ecoe@localhost:5432/ecoe_test python3 -m pytest -q
```

La segunda forma aplica las migraciones Alembic sobre PostgreSQL y es la que corre CI; es la única que ejercita restricciones únicas, claves foráneas y concurrencia real. **Nunca apuntarla a una base con datos.**

Frontend (desde `frontend/`):

```bash
npm test          # vitest
npm run lint
npm run build
```

Flujo completo de punta a punta (stack desechable, puertos 13001/18001):

```bash
./scripts/run_e2e.sh
```

CI (`.github/workflows/ci.yml`) corre los tres: backend sobre PostgreSQL, frontend, y el flujo e2e.

## Migraciones

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "descripcion"
```

Cada backend aplica las migraciones pendientes sobre su propia base al arrancar.

## Despliegue

En el servidor:

```bash
./scripts/deploy.sh
```

Construye las imágenes una vez y actualiza producción y la instancia demo con ellas. Antes de un cambio con migraciones, respaldar producción (comando en el encabezado del script).

Otros scripts:

| Script | Uso |
|---|---|
| `scripts/demo_reset.sh` | Recarga los ECOE de muestra de `demo.ecoe.cl` (sólo toca la base demo) |
| `scripts/verify_backup.sh` | Ensaya la restauración del último respaldo en una base desechable |
| `scripts/restore_db.sh` | Restaura un respaldo sobre producción (pide confirmación) |
| `scripts/backup_loop.sh` | Lo usa el servicio `db-backup`: diario, y cada 5 min con un ECOE en ejecución |

Detalle de servidor, túnel y respaldos: `datos_proyecto/operacion_despliegue.md`.

## Documentación

| Documento | Contenido |
|---|---|
| `PROJECT_STATUS.md` | Estado, módulos, decisiones y límites |
| `NEXT_STEPS.md` | Pendientes priorizados |
| `MANUAL_USUARIO.md` | Uso de la plataforma por rol |
| `docs/OPERACION_DIA_EXAMEN.md` | Lista de verificación para correr un examen |
| `docs/architecture/` | Matriz de permisos y decisiones de fondo |
| `docs/optimizacion/BACKLOG.md` | Hallazgos de auditorías y su estado |
| `docs/optimizacion/PLANES/SAAS__multiinstitucional.md` | Plan multiinstitucional |
| `WORKLOG.md` | Bitácora por sesión |
