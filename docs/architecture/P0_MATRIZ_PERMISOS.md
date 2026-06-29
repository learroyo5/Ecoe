# P0 matriz inicial de permisos

Fecha: 2026-06-29

## Principios

- Denegar por defecto.
- Todo acceso operativo debe resolverse contra un ECOE concreto.
- Los roles globales no bastan para acceder a un ECOE: deben existir como creador/admin del evento, staff asignado o estudiante activo del evento.
- Los archivos multimedia se autorizan por asset -> estacion -> ECOE -> audiencia.
- Las lecturas GET no deben mutar resultados.

## Roles

| Rol | Alcance P0 |
|---|---|
| `admin_ecoe` | Administra solo ECOE donde tiene `ECOEPermission`. |
| `coeditor_docente` | Edita contenido y configuracion solo si esta en `StaffAssignment` del ECOE. |
| `coordinador_operativo` | Opera estudiantes, staff, live, incidencias y resultados si esta asignado al ECOE. |
| `cronometrador` | Controla panel en vivo si esta asignado al ECOE. |
| `evaluador` | Accede a su estacion asignada dentro del ECOE. |
| `estudiante` | Accede a su ECOE activo y a la estacion confirmada por check-in. |

## Matriz por modulo

| Recurso/accion | Admin | Coeditor | Coordinador | Cronometrador | Evaluador | Estudiante |
|---|---:|---:|---:|---:|---:|---:|
| Listar/ver ECOE asignado | Si | Si | Si | Si | Si | Si |
| Crear ECOE | Si | No | No | No | No | No |
| Editar ECOE | Si | Si | No | No | No | No |
| Duplicar ECOE | Si | No | No | No | No | No |
| Dashboard/validacion | Si | Si | Si | No | No | No |
| Estudiantes | Si | Si | Si | No | No | No |
| Staff | Si | Si | Si parcial | No | No | No |
| Estaciones | Si | Si | No | No | Lectura asignada via evaluador | No |
| Instrumentos/plantillas/pacientes | Si | Si | Lectura | No | Lectura | Lectura necesaria |
| Pilotaje | Si | Si | Crear/ver | No | No | No |
| Live HTTP control | Si | No | Si | Si | No | No |
| Live WebSocket | Si | No | Si | Si | No | No |
| Incidencias | Si | No | Si | Si | No | No |
| Evaluacion | Si | No | Si | No | Solo estacion asignada | No |
| Respuesta estudiante | Si | No | Si | No | No | Solo su usuario/check-in |
| Resultados | Si | Si | Si | No | No | No |
| Consolidar resultados | Si | Si | Si | No | No | No |
| Media estudiante | Si | Si | Si | No | No | Solo estacion confirmada |
| Media evaluador | Si | Si | Si | No | Solo estacion asignada | No |

## Casos negativos obligatorios P0

- Usuario autenticado sin relacion con el ECOE recibe 403.
- Evaluador asignado a ECOE A no puede acceder a ECOE B.
- Estudiante no puede descargar media para evaluador ni media de una estacion sin check-in activo.
- WebSocket live rechaza conexiones sin token/cookie.
- WebSocket live rechaza token valido sin permiso operativo en el ECOE.
- GET de resultados no inserta, borra ni actualiza `ecoe_results`.
