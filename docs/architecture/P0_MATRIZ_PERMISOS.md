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
| `corrector` | Puntua las respuestas de las estaciones de evaluacion diferida que tiene asignadas dentro del ECOE (pantalla Correccion). No accede a configuracion, live, estudiantes ni resultados. Delegable por coeditor/coordinador; admite varias estaciones. |
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
| Estaciones | Si | Si | No | No | Via `/evaluator/context` [^ctx] | No |
| Instrumentos/plantillas/pacientes | Si | Si | Lectura | No | Via `/evaluator/context` [^ctx] | Via `/student/access` [^ctx] |
| Pilotaje | Si | Si | Crear/ver | No | No | No |
| Live HTTP control | Si | No | Si | Si | No | No |
| Live WebSocket | Si | No | Si | Si | No | No |
| Incidencias | Si | No | Si | Si | No | No |
| Evaluacion | Si | No | Si | No | Solo estacion asignada | No |
| Correccion diferida (`/grading`) | Si | Si | No | No | No | No |
| Respuesta estudiante | Si | No | Si | No | No | Solo su usuario/check-in |
| Resultados | Si | Si | Si | No | No | No |
| Consolidar resultados | Si | Si | Si | No | No | No |
| Media estudiante | Si | Si | Si | No | No | Solo estacion confirmada |
| Media evaluador | Si | Si | Si | No | Solo estacion asignada | No |

El `admin_global` hereda las capacidades de `admin_ecoe` sobre todos los eventos. Ademas, es el unico que puede listar/crear/modificar cuentas globales y conceder o revocar administradores por ECOE.

La columna `corrector` (omitida de la tabla por brevedad) solo tiene `Si` en "Listar/ver ECOE asignado" y en "Correccion diferida (`/grading`)", y ahi acotado a las estaciones de su `StaffAssignment`. Todo lo demas es `No`. Ver `docs/architecture/EVALUACION_DIFERIDA_FASE1.md`.

[^ctx]: `evaluador` y `estudiante` **no** tienen lectura directa de los bancos de estaciones, instrumentos, plantillas ni pacientes simulados: esos GET (`CONTENT_MANAGER_ROLES` en `app/api/routes/stations.py`) responden `403` para ellos. El contenido que necesitan para operar (guion de la estacion, formulario del estudiante, pauta del evaluador, multimedia de su audiencia) llega ya filtrado por `/api/evaluator/context/{ecoe_event_id}` y `/api/student/access`, resuelto a partir del check-in confirmado y de la asignacion de estacion, no de un permiso de lectura sobre el banco.

## Incorporacion de miembros por ECOE

1. El `admin_ecoe` busca por correo exacto; no puede enumerar el directorio institucional.
2. Si la identidad esta activa, el sistema crea o actualiza su `StaffAssignment` solo en ese ECOE.
3. Si no existe, se crea una identidad `miembro` pendiente y una invitacion de activacion con expiracion y uso unico. La contrasena la define el invitado.
4. El token original se muestra una vez y nunca se almacena: en base de datos queda unicamente su hash. Reemitir la invitacion invalida la anterior para ese evento.
5. Al activar una identidad se invalidan sus invitaciones pendientes y la cuenta queda disponible para asignaciones en otros ECOE.
6. Una cuenta suspendida requiere intervencion de `admin_global`; `admin_ecoe` no puede reactivarla. La carga masiva actual solo admite cuentas institucionales activas.

Los bancos de plantillas, instrumentos, pacientes simulados y estaciones son institucionales y reutilizables. Su consulta o mutacion exige indicar un ECOE de contexto: admin/coeditor pueden modificar; coordinador solo puede consultar.

Instrumentos (`AssessmentTool`, OPT-7): editar/archivar/restaurar una pauta exige, ademas del contexto de evento, ser `admin_global` **o** `admin_ecoe`/`coeditor_docente` del `origin_event_id` de la pauta. Para pautas legadas sin `origin_event_id`, basta ese rol en algun evento que hoy la referencia; si no tiene ninguna referencia, solo `admin_global`. Una pauta usada por una estacion de un ECOE en `en_pilotaje`/`publicado`/`en_ejecucion`/`cerrado`/`archivado` no se puede editar ni archivar (409): hay que duplicarla. El `DELETE` es soft (`archived`); el hard-delete (`.../purge`) es solo `admin_ecoe`/`admin_global` y solo con 0 referencias.

Plantillas y pacientes simulados (`StationTemplate` / `SimulatedPatient`, OPT-7b): misma regla de propiedad y gracia que los instrumentos (`admin_global` **o** rol en `origin_event_id`; para legados, rol en un evento que hoy los referencia; sin referencias, solo `admin_global`). `purge` sube el listón igual (`admin_ecoe`/`admin_global`, 0 referencias). **Diferencia con OPT-7**: no hay gate de estado — su contenido no se lee en runtime, así que el `PATCH` es UPDATE libre incluso con el ECOE en ejecución; el `DELETE` es soft (`archived`). Un registro archivado no se asigna a estaciones nuevas; las que ya lo usan siguen operativas.

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
- Coeditor y coordinador no pueden delegar roles privilegiados; solo evaluador, corrector o cronometrador.
- Un corrector del ECOE A no puede listar ni corregir respuestas del ECOE B, ni de una estacion fuera de su asignacion.
- Un administrador de ECOE no puede enumerar cuentas, invitar para otro ECOE ni asignar `admin_ecoe`.
- Una cuenta pendiente o suspendida no puede iniciar sesion.
- Una invitacion vencida, reutilizada o reemplazada no puede activar la cuenta.
