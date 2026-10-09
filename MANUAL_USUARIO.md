# Manual de usuario — Plataforma ECOE

> Última actualización: 2026-10-09. Para la lista de verificación del día del examen, ver `docs/OPERACION_DIA_EXAMEN.md`.

## Índice

1. [Cómo está organizada la plataforma](#1-cómo-está-organizada-la-plataforma)
2. [Acceso y roles](#2-acceso-y-roles)
3. [Datos del ECOE y su ciclo](#3-datos-del-ecoe-y-su-ciclo)
4. [Estaciones](#4-estaciones)
5. [Circuitos espejo](#5-circuitos-espejo)
6. [Estudiantes](#6-estudiantes)
7. [Equipo](#7-equipo)
8. [Validación, pilotaje y publicación](#8-validación-pilotaje-y-publicación)
9. [Día del examen](#9-día-del-examen)
10. [Cierre: corrección y resultados](#10-cierre-corrección-y-resultados)
11. [Biblioteca](#11-biblioteca)
12. [Flujo completo recomendado](#12-flujo-completo-recomendado)

---

## 1. Cómo está organizada la plataforma

La barra lateral sigue el ciclo del examen:

| Grupo | Pantallas | Para qué |
|---|---|---|
| — | **Inicio** | Fase actual del ECOE y el siguiente paso recomendado |
| **Este ECOE** | Datos del ECOE · Estaciones · Estudiantes · Equipo | Armar el examen |
| **Preparación** | Validación · Pilotaje · Publicación | Comprobar y ensayar antes del día |
| **Día del examen** | Panel en vivo · Kioscos · Contingencia · Vista de evaluador | Operar el examen |
| **Cierre** | Corrección · Resultados | Corregir, consolidar y exportar |
| **Biblioteca** | Banco de estaciones · Plantillas · Instrumentos · Pacientes simulados | Material reutilizable entre exámenes |
| **Institución** | Usuarios | Cuentas (sólo administración global) |

Cada persona ve sólo las pantallas de su rol.

Arriba de cada pantalla aparece el **ECOE activo** con su estado y fecha, y el selector **Cambiar de ECOE**. Todo lo que ves corresponde a ese evento. Si el ECOE está en ejecución, la plataforma pide confirmación antes de cambiar.

---

## 2. Acceso y roles

Ingresa con tu correo y contraseña en la dirección de tu institución (por ejemplo `https://app.ecoe.cl/login`).

**Primera vez.** Las cuentas no se crean con una contraseña entregada por otra persona: recibes un correo de invitación con un enlace de activación y defines tu propia contraseña. El enlace vence (72 horas por defecto); si venció, pide a la administración del ECOE que reinicie tu acceso.

| Rol | Qué puede hacer |
|---|---|
| **Administración global** | Crear ECOE, gestionar cuentas, delegar administradores de un ECOE. Acceso a todo |
| **Administración del ECOE** | Todo dentro de sus eventos: configurar, invitar al equipo, publicar, ejecutar, cerrar y reabrir |
| **Coeditor docente** | Diseñar estaciones, cargar estudiantes y equipo, validar, publicar, ver resultados |
| **Coordinación operativa** | Estudiantes, panel en vivo, kioscos, contingencia, confirmar ingresos en cualquier estación |
| **Cronometrador** | Panel en vivo |
| **Evaluador** | Su estación: confirmar estudiantes y registrar la pauta |
| **Corrector** | Corregir las respuestas abiertas de sus estaciones |
| **Estudiante** | Responder el formulario de la estación en que fue confirmado |

Una misma persona puede tener roles distintos en ECOE distintos.

---

## 3. Datos del ECOE y su ciclo

### Crear un ECOE

Sólo la administración global. En **Datos del ECOE**, botón **+ Nuevo ECOE**: datos generales (nombre, fecha, curso, escuela, docente responsable, correo), modo de circuito, minutos por estación, minutos de transición, pausa entre rondas y porcentaje de aprobación. Queda en **Borrador** y seleccionado.

Para repetir un examen con otro grupo usa **Duplicar ECOE**: copia las estaciones (incluidos los circuitos espejo) y, si quieres, los evaluadores. Nunca copia estudiantes.

### Pestañas

- **General**: edición de los datos.
- **Estaciones**, **Participantes**, **Pilotajes**: resumen con enlace a cada pantalla.

### Estado

La barra de estado muestra el estado actual y las acciones posibles:

```
Borrador → En configuración → Listo para pilotaje → En pilotaje
→ Pilotaje validado → Publicado → En ejecución → Cerrado → Archivado
```

Cada cambio pide confirmación y la plataforma comprueba que se cumplan las condiciones (por ejemplo, no deja publicar con bloqueos de validación). Se puede retroceder en casi todos los tramos antes de la ejecución.

**Qué se puede editar en cada etapa:**

| Etapa | Estructura (estaciones, pautas, formularios, tiempos, numeración) | Nómina y equipo |
|---|---|---|
| Hasta pilotaje validado | Editable | Editable |
| Publicado | **Bloqueada**. Para cambiarla: Despublicar | Editable |
| En ejecución | Bloqueada | Se puede agregar un estudiante rezagado y reasignar equipo |
| Cerrado / Archivado | Bloqueada | Bloqueada |

---

## 4. Estaciones

En **Estaciones** ves las estaciones agrupadas por circuito, con su tipo, tiempo, puntaje máximo y estado.

### Crear o editar

**+ Nueva estación** abre el Constructor, en cuatro pasos:

1. **Identidad**: nombre, tipo, circuito; se puede partir de una plantilla o del banco.
2. **Instrumento**: la pauta que usará el evaluador (lista de cotejo, rúbrica o escala), y el formulario del estudiante si la estación lo requiere. Las preguntas pueden ser de selección única, selección múltiple o texto corto; define los puntos y la respuesta correcta de cada una. Las de texto con puntaje requieren **corrección diferida**.
3. **Instrucciones**: previa al ingreso, dentro de la estación y guía para el evaluador.
4. **Recursos**: materiales, y archivos multimedia indicando para quién son (estudiante, evaluador o ambos).

Una estación debe poder puntuarse: necesita evaluador con pauta, o un formulario con puntos.

### Modo kiosco

Las estaciones con formulario o multimedia usan una tablet. Se vinculan desde **Kioscos** (ver sección 9).

### Borrar

Sólo antes de publicar. Una estación con registros no se borra.

---

## 5. Circuitos espejo

Úsalo cuando el mismo circuito se corre en paralelo, por ejemplo circuito A en un piso y circuito B en otro, para evaluar al doble de estudiantes por ronda.

**No crees las estaciones dos veces.**

1. Diseña todas las estaciones **una sola vez**, en un circuito (por ejemplo «Circuito A»).
2. En **Estaciones**, pulsa **Crear circuito espejo** y dale nombre («Circuito B»).
3. La plataforma crea las mismas estaciones con la misma pauta, formulario, puntaje e instrucciones, marcadas como **Espejo**.

Reglas:

- Una estación espejo **no se edita por separado**. Su botón dice **Editar la original**; lo que guardes en la original se copia solo a sus espejos.
- Lo que sí es propio de cada estación física: su **evaluador**, su **tablet** y su paciente simulado.
- La multimedia se sube una vez, en la original.
- Si agregas una estación al circuito original después de crear el espejo, usa **Sincronizar espejo**.
- **Eliminar circuito espejo** borra el circuito completo (no el original).
- Asigna cada estudiante a su circuito (campo *circuito*): rendirá sólo las estaciones de ese circuito.

La validación **bloquea** el pilotaje y la publicación si hay más de un circuito y no son copia exacta.

En Resultados, cada estación aparece una vez con todos los estudiantes y el promedio de cada circuito al lado.

---

## 6. Estudiantes

### Carga masiva

En **Estudiantes**, descarga la plantilla (Excel o CSV), complétala y súbela:

| Columna | Obligatoria | Descripción |
|---|---|---|
| nombre | Sí | |
| apellidos | Sí | |
| rut | Sí | Con guion y dígito verificador |
| correo | Sí | |
| grupo | No | Por defecto «Grupo 1» |
| circuito | No | Por defecto «Circuito A». En espejo, indica el de cada estudiante |

El **Número ECOE** se asigna solo (E001, E002…). Al terminar se informa cuántos se importaron y cuántos se omitieron por RUT duplicado o datos faltantes.

También hay alta manual, uno a uno.

### Acciones

- **Suspender / Reactivar**: un estudiante suspendido no cuenta en la nómina ni en los resultados. Úsalo para los ausentes. No se puede suspender a quien ya tiene registros mientras el ECOE está en ejecución.
- **Borrar**, **Reasignar Número ECOE** y **Limpiar duplicados por RUT**: sólo antes de publicar.

En modo kiosco los estudiantes no necesitan cuenta: se identifican por su Número ECOE ante el evaluador.

---

## 7. Equipo

En **Equipo** se ve la composición requerida (administración, coeditor, coordinación, cronometrador, evaluadores) y quién falta.

### Agregar a una persona

Escribe su correo. Si ya tiene cuenta, se la asigna al ECOE; si no, se crea pendiente y recibe una **invitación** para activarla. Elige el rol y, para un evaluador, su **estación principal** (puede asignarse después en la tabla). Un evaluador tiene una sola estación; un corrector puede tener varias.

También se puede importar el equipo desde Excel/CSV.

### Otras acciones

- **Reasignar** estación o rol desde la tabla.
- **Reiniciar acceso**: envía un nuevo enlace a quien no pudo activar o perdió su contraseña.
- **Borrar** una asignación.

En un ECOE en espejo, cada estación de cada circuito necesita su propio evaluador.

---

## 8. Validación, pilotaje y publicación

### Validación

Muestra, por estación y para el evento, qué falta para pilotear, publicar e iniciar. Los **bloqueos** impiden avanzar; las **advertencias** conviene resolverlas. Cada problema enlaza a la pantalla donde se corrige.

### Pilotaje

Con el ECOE **En pilotaje** se ensaya con las mismas pantallas del día del examen. Todo lo registrado queda marcado como pilotaje y **no entra a las notas**.

Recomendado: pilotear con el **Panel en vivo** y con transición, como se correrá el día real, y provocar a propósito un número mal tipeado, una tablet apagada y una pausa.

En **Pilotaje** se registran los ensayos y sus hallazgos, y se ve el análisis de las respuestas del ensayo. **Validar pilotaje** no se bloquea por ese análisis, pero lo advierte.

### Publicación

Deja el ECOE listo para el día: crea la sesión en vivo y **congela la estructura**. Si hay que corregir algo, **Despublicar**, corregir y volver a publicar.

---

## 9. Día del examen

### Kioscos

En **Kioscos** están todas las estaciones que necesitan tablet. **Generar todos los enlaces** crea uno por estación; abre cada enlace en la tablet de esa estación. Los enlaces se muestran una sola vez; generar uno nuevo invalida el anterior de esa estación.

### Panel en vivo

- **Cronómetro central**: es el reloj de todo el circuito. Iniciar, Pausar, Reanudar, Reiniciar y Sig. estación; los que no corresponden al momento aparecen deshabilitados.
- **Circuito automático** (se activa antes de iniciar): avanza solo estación → transición → siguiente estación, con pausa entre rondas para el cambio de estudiantes.
- **Pausar** congela el tiempo para todos; nadie pierde su ventana durante la pausa.
- **Finalizar la estación en curso**: cierra la fase antes de tiempo.
- **Vista proyector** y volumen del timbre.
- **Estaciones en vivo**: por estación, si el evaluador y la tablet están conectados, qué estudiante está confirmado y si ya hay evaluación y respuesta. Arriba, la **verificación previa**: debe decir «todo listo» antes de iniciar.
- **Incidencias**: registrar, resolver y reabrir.

Para empezar el examen real, en **Datos del ECOE** pasa el evento a **En ejecución**. El cronómetro parte limpio.

### Evaluador

1. Ingresa el **Número ECOE** del estudiante y confirma. Puede hacerlo durante la transición: el tiempo del estudiante es el de la estación que viene.
2. Verifica nombre y número.
3. Registra la pauta. Se guarda sola como borrador mientras la llenas.
4. **Guardar evaluación** y confirma. La pantalla queda lista para el siguiente.

Avisos que puede mostrar al confirmar:

- **Figura en otra estación en esta misma rotación** o **es de otro circuito**: casi siempre es un número mal tipeado. Corrige el número, o confirma sólo si el estudiante realmente está contigo.
- **Ya fue evaluado en esta estación**.

Si confirmaste a la persona equivocada: **No es este estudiante: anular ingreso** (sólo mientras no haya evaluación ni respuesta).

El evaluador tiene hasta el fin de la transición para terminar de registrar.

### Estudiante

En la tablet de la estación (kiosco) ve sus instrucciones, el material y el formulario apenas el evaluador lo confirma. Responde y pulsa **Enviar respuesta final**. Lo que escribe se guarda en el servidor mientras responde; si el tiempo termina, se envía lo que alcanzó a escribir.

En las estaciones **sin evaluador**, alguien de coordinación confirma el ingreso de cada estudiante desde **Vista de evaluador**.

### Contingencia

Para lo que se resolvió en papel o quedó mal registrado. Elige estación y Número ECOE:

- **Respuesta del estudiante**: transcribe el formulario. Reemplaza una respuesta que el servidor autoenvió en blanco; no reemplaza una que el estudiante envió por sí mismo.
- **Evaluación**: registra el puntaje de la pauta en papel, o **rectifica** una ya enviada indicando el motivo.

Todo queda en la auditoría. Sólo funciona con el ECOE en pilotaje o en ejecución: **hazlo antes de cerrar**.

---

## 10. Cierre: corrección y resultados

### Corrección

Los correctores ven las respuestas abiertas pendientes de sus estaciones, con la pauta de referencia, y asignan puntaje. Lo que no se corrige no suma a la nota.

### Cerrar el ECOE

En **Datos del ECOE**, **Cerrar ECOE**. Si algún estudiante tiene estaciones sin registro, el cierre **se detiene y los lista**. Opciones:

- Ingresar lo que falta por **Contingencia**.
- **Suspender** a quien estuvo ausente.
- **Cerrar de todas formas**: cada estación faltante cuenta **0**.

Al cerrar se consolida el **acta**, que ya no cambia.

Si después aparece algo sin ingresar, la administración del ECOE puede **Reabrir ejecución** indicando el motivo. El acta anterior queda archivada y visible en Resultados como «Actas anteriores». Un ECOE **archivado** ya no se reabre.

### Resultados

- **Notas**: puntaje, porcentaje y nota por estudiante, con estaciones rendidas sobre las esperadas. El porcentaje es el promedio del logro en cada estación (todas pesan igual).
- **Por estación**: promedio y dispersión; en espejo, el promedio de cada circuito.
- **Análisis**: confiabilidad del examen y comportamiento de cada estación y criterio.
- **Trazabilidad**: quién fue confirmado, evaluado y respondió; estudiantes completos y parciales.
- **Actividad**: secuencia de lo ocurrido.

**Exportar Excel** descarga todo en varias hojas. El **PDF de contingencia** es la hoja imprimible por estación para operar si falla la plataforma; no contiene resultados.

---

## 11. Biblioteca

Material que se reutiliza entre exámenes:

- **Banco de estaciones**: diseños completos que se pueden traer a un ECOE.
- **Plantillas**: estructuras base por tipo de estación.
- **Instrumentos**: pautas (listas de cotejo, rúbricas, escalas). Una pauta en uso por un ECOE en pilotaje o en una etapa posterior no se puede editar; se guarda como copia nueva.
- **Pacientes simulados**: personajes y guiones.

Se archivan en vez de borrarse y se pueden restaurar.

---

## 12. Flujo completo recomendado

**Configurar**
1. Crear el ECOE (o duplicar uno anterior) y pasarlo a *En configuración*.
2. Diseñar las estaciones en un circuito. Si es en espejo, **Crear circuito espejo**.
3. Cargar estudiantes (con su circuito) e invitar al equipo; asignar evaluador a cada estación.

**Preparar**
4. Revisar **Validación** hasta que no queden bloqueos.
5. Pilotear con el panel en vivo y registrar hallazgos; validar el pilotaje.
6. Publicar.

**Día del examen**
7. Generar enlaces en **Kioscos** y abrirlos en cada tablet.
8. Esperar la verificación previa «todo listo» en el Panel en vivo.
9. Pasar a *En ejecución* e iniciar el cronómetro.
10. Resolver lo que ocurra con Pausar, Incidencias y Contingencia.

**Cerrar**
11. Transcribir el papel por Contingencia y terminar la Corrección.
12. Revisar Trazabilidad; cerrar el ECOE.
13. Revisar Resultados y exportar el Excel.
14. Archivar cuando ya no se necesite reabrir.
