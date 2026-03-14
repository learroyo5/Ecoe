# Project Status

## Proyecto

- Nombre: `Proyecto Tecnologico ECOE`
- Objetivo: plataforma web para planificacion, pilotaje, ejecucion, contingencia y cierre de ECOE/OSCE para carreras de la salud.
- Estado actual: `v1 funcional inicial`

## Estado general

La base del producto ya fue construida y publicada en GitHub. El proyecto corre localmente con Docker Compose y queda preparado para continuar desarrollo incremental desde otro servidor Ubuntu.

## Arquitectura implementada

- Frontend:
  - Next.js con App Router
  - TypeScript
  - Tailwind CSS
  - layout con menu lateral y pantallas operativas
- Backend:
  - FastAPI
  - SQLAlchemy ORM
  - Pydantic
  - autenticacion JWT simple por rol
- Base de datos:
  - PostgreSQL en Docker Compose
- Infraestructura:
  - `frontend`, `backend` y `db` separados en `docker-compose.yml`

## Modulos implementados

- Autenticacion:
  - login
  - sesion basica por token
  - proteccion por rol
- Gestion ECOE:
  - listado
  - creacion
  - actualizacion
  - duplicado
  - validaciones de estado
- Estudiantes:
  - alta manual
  - importacion CSV/Excel
  - listado
- Evaluadores y colaboradores:
  - alta manual
  - importacion CSV/Excel
  - listado
- Estaciones:
  - listado
  - constructor base
  - configuracion pedagogica y operativa
- Banco de plantillas
- Banco de instrumentos
- Gestor de paciente simulado
- Pilotaje:
  - creacion
  - listado
  - archivado
  - separacion de datos de prueba
- Panel en vivo:
  - cronometro central
  - start/pause/resume/reset/transition
- Interfaz evaluador:
  - seleccion de estacion
  - identificacion estudiante
  - envio de evaluacion
- Interfaz estudiante:
  - identificacion
  - envio de formulario digital
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

- `npm run lint`
- `npm run build`
- smoke tests backend con `fastapi.testclient`
- `docker compose up --build -d`
- acceso UI por red local
- acceso backend por healthcheck y endpoints autenticados

## Decisiones importantes tomadas

- El frontend consume la API mediante proxy interno (`/backend/api`) para evitar romper acceso desde otras maquinas de la red.
- La persistencia se inicializa automaticamente en startup para acelerar la primera version.
- El control de permisos es por rol, simple y claro, sin ACL avanzada.
- El cronometro es manual y operativo, sin inicio automatico por hora.
- Pilotaje y ejecucion real estan separados a nivel de modelo y registros.

## Limites actuales de esta v1

- No hay editor avanzado de ECOE con formularios completos de todos los campos.
- No hay websocket o tiempo real verdadero para sincronizacion del cronometro.
- No hay reproduccion real de audio integrada; solo estructura preparada.
- No hay gestion robusta de archivos multimedia por tipo, preview y permisos finos.
- No hay migraciones Alembic; las tablas se crean automaticamente.
- No hay suite formal de tests automatizados.
- No hay despliegue con Nginx, dominio o HTTPS.

## Repo y continuidad

- Repo remoto: `git@github.com:learroyo5/Ecoe.git`
- Rama principal de trabajo: `main`
- Fuente de verdad del proyecto: este repositorio

## Recomendacion para continuar en otro servidor

1. Clonar repo desde GitHub.
2. Levantar con Docker Compose.
3. Leer este archivo y `NEXT_STEPS.md`.
4. Continuar por iteraciones pequenas con commit frecuente.
