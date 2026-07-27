# Manual de Usuario — Plataforma ECOE

> Versión 2.0 · Última actualización: 2026-06-03

## Índice

1. [Introducción](#1-introducción)
2. [Acceso y roles](#2-acceso-y-roles)
3. [Gestión de usuarios](#3-gestión-de-usuarios)
4. [Crear y configurar un ECOE](#4-crear-y-configurar-un-ecoe)
5. [Construir estaciones](#5-construir-estaciones)
6. [Cargar estudiantes](#6-cargar-estudiantes)
7. [Asignar evaluadores y colaboradores](#7-asignar-evaluadores-y-colaboradores)
8. [Validación y publicación](#8-validación-y-publicación)
9. [Pilotaje](#9-pilotaje)
10. [Ejecución en vivo](#10-ejecución-en-vivo)
11. [Interfaz del evaluador](#11-interfaz-del-evaluador)
12. [Interfaz del estudiante](#12-interfaz-del-estudiante)
13. [Resultados y exportaciones](#13-resultados-y-exportaciones)
14. [Flujo completo recomendado](#14-flujo-completo-recomendado)

---

## 1. Introducción

La Plataforma ECOE permite planificar, ejecutar y cerrar Evaluaciones Clínicas Objetivas Estructuradas (ECOE/OSCE) para carreras de la salud. Cubre el ciclo completo: desde la creación del evento hasta la exportación de resultados.

### Pantallas principales

| Pantalla | ¿Quién la usa? | ¿Para qué? |
|---|---|---|
| Dashboard | Admin, Coeditor, Coordinador | Vista general del ECOE activo |
| ECOE | Admin, Coeditor | Crear, editar, duplicar y cambiar estado del ECOE |
| Estaciones | Admin, Coeditor | Listar y construir estaciones |
| Estudiantes | Admin, Coeditor, Coordinador | Cargar y gestionar estudiantes |
| Evaluadores | Admin, Coeditor | Asignar evaluadores y colaboradores |
| Banco de estaciones | Admin, Coeditor | Repositorio reusable de estaciones |
| Plantillas | Admin, Coeditor | Configuraciones base para estaciones |
| Instrumentos | Admin, Coeditor | Pautas de evaluación |
| Paciente simulado | Admin, Coeditor | Personajes para estaciones con actuación |
| Pilotaje | Admin, Coeditor, Coordinador | Ejecuciones de prueba |
| Validación | Admin, Coeditor | Verificar requisitos antes de publicar |
| Publicación | Admin | Publicar ECOE para ejecución real |
| Panel en vivo | Admin, Coordinador, Cronometrador | Control del cronómetro e incidencias |
| Evaluador | Evaluador | Evaluar estudiantes en su estación |
| Estudiante | Estudiante | Responder formulario de la estación |
| Resultados | Admin, Coeditor, Coordinador | Ver y exportar resultados |
| Usuarios | Admin | Gestionar cuentas de usuario |

---

## 2. Acceso y roles

### Inicio de sesión

Accede desde `https://ecoe.drnotus.cl/login` con tu correo y contraseña.

### Roles disponibles

| Rol | Permisos principales |
|---|---|
| **admin_ecoe** | Acceso completo: crear ECOE, gestionar usuarios, publicar, ver resultados |
| **coeditor_docente** | Colaborar en la construcción de estaciones, cargar estudiantes y evaluadores |
| **coordinador_operativo** | Gestionar estudiantes, pilotaje, panel en vivo e incidencias |
| **cronometrador** | Solo panel en vivo: controlar el cronómetro |
| **evaluador** | Solo interfaz del evaluador: evaluar estudiantes en su estación asignada |
| **estudiante** | Solo interfaz del estudiante: responder formulario de su estación |

### Seleccionar ECOE activo

En la barra lateral izquierda, bajo el nombre del ECOE, hay un selector **"Cambiar"** que permite elegir en qué ECOE estás trabajando. Todas las pantallas (Estudiantes, Estaciones, Evaluadores, etc.) muestran los datos del ECOE seleccionado.

---

## 3. Gestión de usuarios

> Solo disponible para el rol **admin_ecoe**.

### Crear un usuario

1. Ve a **Usuarios** en la barra lateral.
2. Completa el formulario: correo, nombre completo, contraseña y rol.
3. Haz clic en **Crear usuario**.

### Editar o desactivar un usuario

En la tabla de usuarios, usa los botones **Editar** para cambiar nombre, rol, contraseña, o activar/desactivar la cuenta.

> ⚠️ **Importante para evaluadores y colaboradores**: antes de importar evaluadores en la sección Evaluadores, cada persona debe tener una cuenta de usuario creada aquí con el mismo correo y rol.

---

## 4. Crear y configurar un ECOE

### Crear un ECOE nuevo

1. Ve a **ECOE** en la barra lateral.
2. En la sección **"Crear nuevo ECOE"** completa:
   - **Datos generales**: nombre, fecha, curso, escuela, docente responsable, correo de contacto.
   - **Configuración del circuito**: modo (paralelo en espejo, secuencial, independientes, mixto), total de estaciones, grupos y estudiantes.
   - **Parámetros de tiempo y evaluación**: minutos por estación, minutos de transición, porcentaje de aprobación.
3. Haz clic en **Crear nuevo ECOE**.

El nuevo ECOE aparecerá en estado **Borrador** y quedará seleccionado automáticamente.

### Editar un ECOE existente

1. Selecciona el ECOE en el selector de la barra lateral.
2. Modifica los campos en **Datos generales y estado**.
3. Haz clic en **Guardar ECOE**.

### Cambiar el estado del ECOE

El ECOE avanza por estados mediante botones de acción con confirmación:

```
Borrador → En configuración → Listo para pilotaje → En pilotaje
→ Pilotaje validado → Publicado → En ejecución → Cerrado → Archivado
```

Cada transición requiere confirmación. El sistema valida automáticamente las condiciones necesarias (por ejemplo, no permite publicar sin estaciones).

### Duplicar un ECOE

1. Haz clic en **Duplicar ECOE**.
2. Ingresa el nombre, fecha y elige si copiar también los evaluadores asignados.
3. Haz clic en **Crear copia**.

La estructura de estaciones siempre se copia. Los estudiantes nunca se copian (es un nuevo grupo).

### Ver detalle del ECOE

Haz clic en **"Ver detalle completo →"** en el panel de Evento activo para ver la vista completa con pestañas: General, Estaciones, Participantes, Pilotajes.

---

## 5. Construir estaciones

### Listado de estaciones

Ve a **Estaciones**. Verás las estaciones del ECOE activo en formato de tarjetas con su número, nombre, tipo, circuito, tiempo y estado. El subtítulo muestra cuántas estaciones hay configuradas.

### Crear una estación nueva

1. Haz clic en **"+ Nueva estación"**.
2. El constructor tiene 4 pasos guiados:
   - **Paso 1 — Origen y base**: elige crear desde cero, desde el banco, o desde plantilla. Define nombre, tipo y circuito.
   - **Paso 2 — Instrumento de evaluación**: selecciona una plantilla de referencia, un instrumento existente o crea uno nuevo (lista de cotejo, rúbrica simple, escala de puntaje). Asocia un paciente simulado si corresponde.
   - **Paso 3 — Instrucciones operativas**: define la instrucción previa, las instrucciones dentro de la estación y la guía para el evaluador.
   - **Paso 4 — Recursos y contingencia**: lista materiales, sube archivos multimedia (imagen, audio, video, PDF) y define el formulario del estudiante si la estación lo requiere.
3. Haz clic en **Guardar estación**.

### Editar una estación

Haz clic en **Editar** en la tarjeta de la estación. El constructor se abre con los datos precargados en modo "editando ECOE".

### Multimedia en estaciones

En el Paso 4, puedes subir archivos. Selecciona:
- **Visible para**: Estudiante, Evaluador, Paciente simulado o Coordinación.
- **Archivo**: arrastra o selecciona el archivo (imagen, audio, video, PDF, Word).
- Los archivos subidos muestran una previsualización inline.

---

## 6. Cargar estudiantes

> Los estudiantes **no necesitan cuenta de usuario** en el sistema. Se identifican por su Número ECOE en la interfaz del estudiante.

### Carga masiva desde Excel/CSV

1. Ve a **Estudiantes**.
2. Descarga la **plantilla Excel** (botón verde) o **plantilla CSV**.
3. Abre el archivo. La **pestaña "Estudiantes"** tiene los encabezados en la fila 1. La pestaña **"Instrucciones"** explica cómo usarla.
4. Completa una fila por cada estudiante:

   | Columna | Obligatorio | Descripción |
   |---|---|---|
   | nombre | ✅ | Nombre del estudiante |
   | apellidos | ✅ | Apellidos completos |
   | rut | ✅ | Con guion y dígito verificador (ej: 11111111-1) |
   | correo | ✅ | Email del estudiante |
   | numero_ecoe | ❌ | Se asigna automáticamente |
   | grupo | ❌ | Nombre del grupo (default: Grupo 1) |
   | circuito | ❌ | Nombre del circuito (default: Circuito A) |

5. Elimina las filas de ejemplo.
6. Guarda como `.xlsx` o `.csv` (UTF-8).
7. Arrastra el archivo al campo de importación o selecciónalo.
8. El sistema mostrará un resumen detallado: cuántos se importaron, cuántos se omitieron por RUT duplicado y cuántos por falta de datos.

### Alta manual

Completa el formulario de la derecha con nombre, apellidos, RUT, correo, grupo y circuito. El Número ECOE se asigna automáticamente.

### Acciones sobre estudiantes

- **Suspender / Reactivar**: cambia el estado del estudiante sin borrarlo.
- **Borrar**: elimina permanentemente al estudiante.
- **Reasignar Número ECOE**: renumera a todos los estudiantes en orden correlativo.
- **Limpiar duplicados por RUT**: elimina registros duplicados conservando el primero.

### Paginación

Si hay más de 50 estudiantes, la tabla muestra controles de paginación al final: **← Anterior | Siguiente →** con el total visible.

---

## 7. Asignar evaluadores y colaboradores

> ⚠️ **Paso previo obligatorio**: cada evaluador o colaborador debe tener una **cuenta de usuario** creada en la sección **Usuarios** con el mismo correo y rol. Si no, la importación los rechazará.

### Carga masiva desde Excel/CSV

1. Ve a **Evaluadores**.
2. Descarga la **plantilla Excel** o **plantilla CSV**.
3. Completa una fila por persona:

   | Columna | Obligatorio | Descripción |
   |---|---|---|
   | nombre | ✅ | Nombre de la persona |
   | apellidos | ✅ | Apellidos completos |
   | correo | ✅ | Debe coincidir con el usuario creado en Usuarios |
   | rol | ✅ | evaluador, coeditor_docente, coordinador_operativo, o cronometrador |

4. Arrastra el archivo al campo de importación.

### Alta manual

Completa el formulario de la derecha con nombre, apellidos, correo, rol y estación asignada. Haz clic en **Agregar al equipo**.

---

## 8. Validación y publicación

### Validación

Ve a **Validación**. El sistema revisa automáticamente si el ECOE cumple las condiciones para:
- **Pilotaje**: requiere estaciones completas y estudiantes cargados.
- **Publicación**: requiere pilotaje validado.
- **Ejecución en vivo**: requiere ECOE publicado.

La pantalla muestra checks ✅ y bloqueos ❌ con detalle de lo que falta.

### Publicar

Cuando el ECOE pasa la validación de publicación, ve a **Publicación** o usa el botón de estado en **ECOE** para cambiar a **Publicado**.

---

## 9. Pilotaje

El pilotaje permite hacer ejecuciones de prueba sin afectar los datos reales.

1. Ve a **Pilotaje**.
2. Haz clic en **Crear pilotaje**, asígnale un nombre y alcance.
3. Durante el pilotaje, el panel en vivo funciona igual que en ejecución real, pero los datos se marcan como prueba.
4. Al terminar, puedes **archivar** el pilotaje.

---

## 10. Ejecución en vivo

### Panel central

Ve a **Panel en vivo**. Verás:

- **Cronómetro central**: muestra el tiempo restante de la estación actual, sincronizado en tiempo real vía WebSocket.
- **Controles**: Iniciar, Pausar, Reanudar, Reiniciar, Siguiente estación.
- **Indicador de estado**: EN VIVO (verde), PAUSADO (amarillo), TRANSICIÓN (naranja).

Cuando el coordinador acciona un control, todos los clientes conectados (evaluadores, estudiantes) reciben la actualización instantáneamente.

### Incidencias

Durante la ejecución, puedes registrar incidencias:

1. Haz clic en **"+ Registrar incidencia"**.
2. Completa: título, detalle (opcional), severidad (baja/media/alta/crítica), y número de estación (opcional).
3. Haz clic en **Registrar incidencia**.

Las incidencias aparecen en tiempo real para todos los usuarios del panel. Cada incidencia se puede **Resolver** (✓) o **Reabrir**. Las incidencias activas se muestran primero, con color según severidad.

---

## 11. Interfaz del evaluador

> Para usar esta interfaz, el evaluador debe tener una cuenta de usuario con rol `evaluador` y estar asignado a una estación del ECOE activo.

1. El evaluador inicia sesión y es dirigido automáticamente a la interfaz del evaluador.
2. Ve su estación asignada y el **cronómetro visible** (solo lectura).
3. **Confirma al estudiante**: ingresa el Número ECOE del estudiante y haz clic en **Confirmar ingreso**.
4. Verifica nombre y número en el panel **"Estudiante confirmado"**.
5. **Evalúa**:
   - Si la estación tiene **lista de cotejo**: marca cada ítem como Cumplido/No cumplido.
   - Si la estación tiene **rúbrica o escala**: ingresa el puntaje por ítem.
   - Agrega una observación opcional.
6. Haz clic en **Guardar evaluación**. Confirma la acción.
7. La vista se limpia para recibir al siguiente estudiante.

> ⚠️ **Bloqueo por tiempo**: cuando el cronómetro llega a 0, el timer se pone en rojo y todos los campos se deshabilitan. Ya no se puede enviar la evaluación.

---

## 12. Interfaz del estudiante

> El estudiante no necesita cuenta de usuario. Se identifica con su **Número ECOE**.

1. El estudiante accede a la interfaz desde un dispositivo (tablet o computador).
2. Ingresa su **Número ECOE** y hace clic en **Verificar mi ingreso**.
3. Una vez que el evaluador confirma su ingreso, el estudiante ve:
   - **Instrucción previa** de la estación.
   - **Instrucciones dentro de la estación**.
   - **Material de apoyo** (imágenes, PDF, video, audio).
   - **Formulario del estudiante** con preguntas de la estación.
4. Responde las preguntas. Las respuestas se guardan automáticamente en el navegador.
5. Haz clic en **Enviar respuesta final** o espera a que el tiempo termine (se envía automáticamente).

### Tipos de pregunta del formulario

- **Selección única**: elige una opción de una lista desplegable.
- **Selección múltiple**: marca una o más opciones con checkboxes.
- **Texto corto**: escribe una respuesta breve.

---

## 13. Resultados y exportaciones

### Ver resultados

Ve a **Resultados**. Verás la tabla de resultados por estudiante con puntaje total, porcentaje y nota equivalente.

### Exportar

- **Excel**: haz clic en el botón de exportación Excel para descargar la planilla con todos los resultados.
- **PDF de contingencia**: genera un PDF imprimible por estación para respaldo físico.

---

## 14. Flujo completo recomendado

### Fase 1: Planificación

1. **Crear ECOE** → completar datos generales, circuito y parámetros.
2. **Crear usuarios** → dar de alta a evaluadores, coeditores, coordinadores y cronometradores con sus roles.
3. **Construir estaciones** → una por una, definiendo instrumentos, instrucciones y multimedia.

### Fase 2: Carga de participantes

4. **Cargar estudiantes** → desde Excel con la plantilla descargable.
5. **Asignar evaluadores** → desde Excel (requiere que ya tengan cuenta de usuario).

### Fase 3: Pilotaje

6. **Validar** → revisar que el ECOE cumpla condiciones para pilotaje.
7. **Iniciar pilotaje** → ejecutar prueba, registrar incidencias, ajustar.
8. **Validar pilotaje** → confirmar que todo funciona.

### Fase 4: Ejecución real

9. **Publicar ECOE** → visible para evaluadores y estudiantes.
10. **Iniciar ejecución** → panel en vivo, control de cronómetro, incidencias.
11. **Cerrar ECOE** → finalizar la ejecución.

### Fase 5: Cierre

12. **Ver resultados** → consolidación automática.
13. **Exportar** → Excel y PDF.
14. **Archivar ECOE** → el ECOE queda en modo solo lectura.

---

> 📝 Este manual se actualiza con cada funcionalidad nueva. Última versión siempre en el repositorio.
