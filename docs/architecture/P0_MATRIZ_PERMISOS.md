# P0 matriz inicial de permisos

Fecha: 2026-06-29

## Principios

- Denegar por defecto.
- Todo acceso operativo debe resolverse contra un ECOE concreto.
- Los roles globales no bastan para acceder a un ECOE: deben existir como creador/admin del evento, staff asignado o estudiante activo del evento.
- Los archivos multimedia se autorizan por asset -> estacion -> ECOE -> audiencia.
- Las lecturas GET no deben mutar resultados.
- La administracion institucional global se separa de la administracion de cada ECOE.
- La identidad institucional es unica por correo y se reutiliza; el rol operativo pertenece a la asignacion de cada ECOE.
- Un administrador de ECOE puede incorporar participantes a su evento sin obtener acceso al directorio global ni administrar credenciales.

## Roles

| Rol | Alcance P0 |
|---|---|
| `admin_global` | Administra cuentas institucionales, crea ECOE, ve todos los eventos y delega/revoca `admin_ecoe` por evento. |
| `admin_ecoe` | Administra solo ECOE donde tiene `ECOEPermission` e invita/asigna su equipo operativo. |
| `coeditor_docente` | Edita contenido y configuracion solo si esta en `StaffAssignment` del ECOE. |
| `coordinador_operativo` | Opera estudiantes, staff, live, incidencias y resultados si esta asignado al ECOE. |
| `cronometrador` | Controla panel en vivo si esta asignado al ECOE. |
| `evaluador` | Accede a su estacion asignada dentro del ECOE. |
| `estudiante` | Accede a su ECOE activo y a la estacion confirmada por check-in. |
| `miembro` | Identidad institucional neutra; no concede acceso por si sola y obtiene capacidades solo mediante asignaciones por ECOE. |

## Matriz por modulo

| Recurso/accion | Admin ECOE | Coeditor | Coordinador | Cronometrador | Evaluador | Estudiante |
|---|---:|---:|---:|---:|---:|---:|
| Listar/ver ECOE asignado | Si | Si | Si | Si | Si | Si |
| Crear ECOE | No; solo admin global | No | No | No | No | No |
| Editar ECOE | Si | Si | No | No | No | No |
| Duplicar ECOE | Si | No | No | No | No | No |
| Dashboard/validacion | Si | Si | Si | No | No | No |
| Estudiantes | Si | Si | Si | No | No | No |
| Staff | Si | Si | Si parcial | No | No | No |
| Buscar cuenta por correo exacto | Si | No | No | No | No | No |
| Invitar/asignar miembro al ECOE | Si | No | No | No | No | No |
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

El `admin_global` hereda las capacidades de `admin_ecoe` sobre todos los eventos. Ademas, es el unico que puede listar/crear/modificar cuentas globales y conceder o revocar administradores por ECOE.

## Incorporacion de miembros por ECOE

1. El `admin_ecoe` busca por correo exacto; no puede enumerar el directorio institucional.
2. Si la identidad esta activa, el sistema crea o actualiza su `StaffAssignment` solo en ese ECOE.
3. Si no existe, se crea una identidad `miembro` pendiente y una invitacion de activacion con expiracion y uso unico. La contrasena la define el invitado.
4. El token original se muestra una vez y nunca se almacena: en base de datos queda unicamente su hash. Reemitir la invitacion invalida la anterior para ese evento.
5. Al activar una identidad se invalidan sus invitaciones pendientes y la cuenta queda disponible para asignaciones en otros ECOE.
6. Una cuenta suspendida requiere intervencion de `admin_global`; `admin_ecoe` no puede reactivarla. La carga masiva actual solo admite cuentas institucionales activas.

Los bancos de plantillas, instrumentos, pacientes simulados y estaciones son institucionales y reutilizables. Su consulta o mutacion exige indicar un ECOE de contexto: admin/coeditor pueden modificar; coordinador solo puede consultar.

## Casos negativos obligatorios P0

- Usuario autenticado sin relacion con el ECOE recibe 403.
- Evaluador asignado a ECOE A no puede acceder a ECOE B.
- Estudiante no puede descargar media para evaluador ni media de una estacion sin check-in activo.
- WebSocket live rechaza conexiones sin token/cookie.
- WebSocket live rechaza token valido sin permiso operativo en el ECOE.
- GET de resultados no inserta, borra ni actualiza `ecoe_results`.
- Un admin de ECOE no puede gestionar cuentas institucionales ni crear otros ECOE.
- Un ID de estacion de otro ECOE se rechaza en updates, exports e incidencias.
- Las restricciones de evaluador/estudiante usan roles efectivos del ECOE, no el rol global de la cuenta.
- Coeditor y coordinador no pueden delegar roles privilegiados; solo evaluador o cronometrador.
- Un administrador de ECOE no puede enumerar cuentas, invitar para otro ECOE ni asignar `admin_ecoe`.
- Una cuenta pendiente o suspendida no puede iniciar sesion.
- Una invitacion vencida, reutilizada o reemplazada no puede activar la cuenta.
