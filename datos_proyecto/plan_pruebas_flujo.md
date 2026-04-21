# Plan de Pruebas de Flujo ECOE

## Objetivo

Validar el piloto funcional del sistema actual de ECOE de punta a punta, detectando quiebres de flujo, ambiguedades operativas, validaciones faltantes y necesidades de pulido UX antes de una fase de uso mas amplia.

Este plan prioriza:

- seguridad operativa
- claridad de uso
- consistencia entre roles
- trazabilidad
- capacidad real de ejecucion

## Alcance de esta ronda

Se prueba el sistema actual centralizado, no la arquitectura hibrida futura.

Se consideran estos roles:

- creador ECOE
- coordinador operativo
- evaluador
- estudiante

## Preparacion previa

Antes de iniciar una ronda de pruebas, confirmar:

1. el stack esta arriba
2. existe un ECOE activo de prueba
3. hay estudiantes cargados y numerados
4. hay evaluadores cargados y asignados
5. hay al menos:
   - una estacion con pauta de evaluacion
   - una estacion con formulario del estudiante
   - una estacion con multimedia
   - una estacion con paciente simulado, si aplica

## Criterios globales de aprobacion

Una prueba se considera aprobada si:

- el usuario entiende que hacer sin asistencia adicional
- el sistema bloquea acciones fuera de secuencia
- los datos guardados quedan visibles y trazables despues
- no se pierde informacion por recarga o navegacion accidental
- el resultado final queda asociado al estudiante, estacion y contexto correctos

## Ronda 1. Constructor de estaciones

### Objetivo

Confirmar que la pantalla principal de construccion permite crear estaciones completas, reutilizables y coherentes.

### Casos de prueba

1. Crear estacion nueva desde cero
   - definir origen
   - definir identidad pedagogica
   - definir instrucciones
   - crear pauta o asociar pauta existente
   - crear formulario del estudiante si aplica
   - cargar multimedia si aplica
   - guardar

2. Crear estacion desde banco
   - abrir banco
   - seleccionar una estacion base
   - revisar que copie contenido esperado
   - ajustar sin perder integridad
   - guardar en ECOE

3. Editar estacion existente
   - abrir desde listado
   - modificar campos clave
   - guardar
   - verificar que los cambios reaparezcan correctamente

4. Validar tiempos globales del ECOE
   - cambiar tiempo de estacion
   - usar fraccion de minuto
   - verificar sincronizacion con estaciones

### Hallazgos a buscar

- etiquetas poco claras
- duplicidad conceptual entre campos
- faltan botones de guardado intermedio
- orden poco logico
- componentes que desaparecen o se cierran sin confirmacion

## Ronda 2. Datos base y asignaciones

### Objetivo

Confirmar que estudiantes y evaluadores quedan bien cargados, sin duplicados y listos para uso real.

### Casos de prueba

1. Cargar estudiantes por archivo
   - usar plantilla
   - verificar correlativos
   - reimportar archivo
   - confirmar no duplicacion por RUT

2. Gestionar estudiantes
   - suspender
   - reactivar
   - borrar con confirmacion
   - renumerar

3. Cargar evaluadores por archivo
   - usar plantilla
   - reimportar archivo
   - confirmar no duplicacion por correo

4. Asignar evaluador principal a estacion
   - revisar una sola estacion principal por evaluador
   - confirmar que el evaluador luego vea solo su estacion

### Hallazgos a buscar

- datos duplicados
- correlativos inconsistentes
- estados visualmente poco claros
- asignaciones ambiguas o multiples

## Ronda 3. Validacion, pilotaje y publicacion

### Objetivo

Confirmar que el sistema no deja avanzar a etapas superiores sin completar los requisitos.

### Casos de prueba

1. Revisar validacion
   - identificar blockers
   - identificar warnings
   - verificar detalle por estacion

2. Pilotear una estacion
   - elegir una estacion lista
   - crear pilotaje individual
   - revisar que quede registrado

3. Intentar pilotear circuito completo sin prerrequisito
   - debe bloquearse si no hubo pilotaje individual previo

4. Pilotear circuito completo
   - hacerlo cuando ya exista pilotaje individual
   - revisar registro correcto

5. Publicar ECOE
   - verificar que solo se habilite cuando corresponde
   - revisar cambio de estado
   - revisar creacion de sesion en vivo

### Hallazgos a buscar

- validaciones incompletas
- errores de secuencia
- estados que no cambian aunque la accion se complete
- mensajes poco claros

## Ronda 4. Flujo operativo evaluador-estudiante

### Objetivo

Confirmar que el flujo real de estacion evita errores de identidad y de asociacion de respuestas.

### Casos de prueba

1. Ingreso del evaluador
   - debe entrar directo a su vista
   - no debe ver gestion avanzada

2. Confirmacion de estudiante por Numero ECOE
   - probar ingreso con y sin ceros a la izquierda
   - verificar que aparezcan numero y nombre

3. Vista estudiante
   - debe activarse solo despues de confirmacion
   - debe mostrar instrucciones dentro de la estacion
   - debe mostrar multimedia y formulario si aplican

4. Envio del estudiante
   - una sola respuesta
   - limpieza posterior del formulario
   - retorno a estado inicial

5. Envio del evaluador
   - una sola evaluacion
   - confirmacion previa
   - retorno a identificacion de siguiente estudiante

### Hallazgos a buscar

- respuestas asociadas al estudiante equivocado
- posibilidad de reenviar o sobreescribir
- cronometro inconsistente
- fallas en tablet o pantallas estrechas

## Ronda 5. Live, resultados y trazabilidad

### Objetivo

Confirmar que la operacion queda visible y auditable despues de ejecutarse.

### Casos de prueba

1. Revisar panel live
   - iniciar
   - pausar
   - reanudar
   - transicionar
   - resetear

2. Revisar resultados
   - puntajes por estudiante
   - maximos y porcentajes
   - exportacion

3. Revisar trazabilidad
   - check-ins
   - evaluaciones
   - respuestas del estudiante
   - actividad reciente
   - trazabilidad por estacion

### Hallazgos a buscar

- diferencias entre lo ejecutado y lo registrado
- estaciones sin evidencia visible
- estudiantes con registros incompletos
- exportaciones incompletas o inconsistentes

## Prioridad para esta semana

Orden sugerido de trabajo:

1. constructor de estaciones
2. asignaciones y datos base
3. validacion, pilotaje y publicacion
4. flujo evaluador-estudiante
5. live, resultados y trazabilidad

## Como registrar hallazgos

Cada hallazgo deberia anotar al menos:

- modulo o pantalla
- rol usado
- que se esperaba
- que ocurrio realmente
- severidad:
  - critica
  - alta
  - media
  - baja

## Regla de decision

Si un hallazgo compromete:

- identidad del estudiante
- asociacion correcta de respuestas
- secuencia de ejecucion
- perdida de informacion

entonces debe corregirse antes de dar por estable el piloto funcional.
