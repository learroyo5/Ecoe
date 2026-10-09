# Plan de pruebas de flujo ECOE

Actualizado el 2026-10-09 para la plataforma tal como está desplegada (navegación nueva, candados por estado, circuitos espejo, contingencia, cierre con completitud).

## Objetivo

Validar el núcleo de punta a punta antes de un examen real: que cada persona entienda qué hacer, que el sistema bloquee lo que está fuera de secuencia, y que **no se pierda ni se atribuya mal** ningún dato.

Las pruebas automáticas (545 backend, 143 frontend, flujo dorado e2e) cubren las reglas una a una. Este plan cubre lo que ellas no ven: personas reales, varias pantallas a la vez, tablets, red del recinto y errores humanos.

## Dónde probar

| Entorno | Para qué | Cuidado |
|---|---|---|
| `https://demo.ecoe.cl` | Recorrer pantallas con datos ya cargados (un ECOE en ejecución en espejo y otro cerrado) | Se puede recargar con `./scripts/demo_reset.sh` |
| `https://app.ecoe.cl` | Armar un ECOE desde cero, como se hará de verdad | Hoy tiene un ECOE de prueba con dos circuitos armados a mano: rehacerlo como espejo o crear uno nuevo |

Usar siempre datos ficticios.

## Roles a cubrir

Administración del ECOE, coeditor, coordinación operativa, cronometrador, evaluador (al menos dos, en estaciones distintas), corrector y estudiante. Cada ronda indica con qué rol se hace.

## Criterios de aprobación

Una prueba se aprueba si:

- la persona entiende qué hacer sin ayuda;
- el sistema impide lo que está fuera de secuencia y explica por qué;
- lo guardado sigue visible tras recargar la página o cambiar de pantalla;
- cada registro queda asociado al estudiante, estación y circuito correctos;
- un error humano típico tiene vuelta atrás dentro de la plataforma.

## Cómo registrar un hallazgo

Pantalla · rol · qué se esperaba · qué ocurrió · severidad (crítica, alta, media, baja). Adjuntar captura si se puede.

**Se corrige antes de dar por estable el núcleo** todo hallazgo que comprometa la identidad del estudiante, la asociación de respuestas, la secuencia de ejecución o cause pérdida de información.

---

## Ronda 1 — Configurar el ECOE y sus estaciones

Rol: administración global (crear) y administración del ECOE o coeditor (resto).

1. **Crear el ECOE** desde Datos del ECOE → «+ Nuevo ECOE». Queda en Borrador y seleccionado. Verificar que un usuario que no es administración global no ve ese botón.
2. **Pasar a En configuración** y revisar que Inicio muestre la fase y el siguiente paso.
3. **Crear una estación desde cero** en el Constructor: identidad, pauta (crear una nueva y también reutilizar una existente), instrucciones, recursos. Guardar, salir y volver: todo debe reaparecer.
4. **Estación con formulario**: preguntas de selección única y múltiple con puntos y respuesta correcta, y una de texto con puntos (corrección diferida).
5. **Estación con multimedia**: subir un archivo para el estudiante y otro para el evaluador.
6. **Crear una estación desde el banco** y verificar que copia el contenido.
7. **Salir del Constructor con cambios sin guardar**: debe advertir.
8. **Cambiar los tiempos del ECOE** (probar fracción de minuto) y verificar que las estaciones los reflejan.

Buscar: etiquetas poco claras, campos que se pierden al guardar, orden poco lógico.

## Ronda 2 — Circuito espejo

Rol: administración del ECOE o coeditor.

1. Con las estaciones ya diseñadas en «Circuito A», usar **Crear circuito espejo**. Deben aparecer las mismas estaciones en «Circuito B», marcadas «Espejo».
2. **Editar una estación original** (por ejemplo, la guía del evaluador) y comprobar que su espejo cambió igual.
3. **Intentar editar o borrar una estación espejo**: no debe ofrecerlo; el botón lleva a la original.
4. **Agregar una estación nueva al circuito A**: Validación y Estaciones deben avisar que al espejo le falta; **Sincronizar espejo** lo corrige.
5. **Eliminar el circuito espejo** y volver a crearlo.
6. Negativo: crear a mano una estación con circuito «Circuito C» sin usar el espejo → Validación debe bloquear pilotaje y publicación.

Buscar: cualquier forma de que 1A y 1B queden distintas.

## Ronda 3 — Estudiantes y equipo

Rol: administración del ECOE.

1. **Importar estudiantes** con la plantilla, indicando el circuito de cada uno. Reimportar el mismo archivo: no debe duplicar.
2. **Alta manual**, suspender, reactivar, renumerar, limpiar duplicados.
3. **Invitar al equipo**: una persona con cuenta existente y otra nueva (debe recibir correo y activar su cuenta definiendo su contraseña). Probar **Reiniciar acceso**.
4. **Asignar evaluador a cada estación de cada circuito**. Un evaluador debe quedar con una sola estación.
5. **Asignar un corrector** a la estación de corrección diferida (en espejo, a ambas).
6. Entrar como evaluador: debe llegar directo a su pantalla y ver sólo su estación.

Buscar: correlativos inconsistentes, asignaciones ambiguas, correos que no llegan.

## Ronda 4 — Validación, pilotaje y publicación

Rol: administración del ECOE o coeditor; coordinación para el ensayo.

1. **Validación**: provocar un bloqueo (quitar el evaluador de una estación) y verificar que impide avanzar y enlaza a dónde se corrige.
2. **Pilotaje individual** de una estación. Luego **circuito completo** (debe exigir que exista antes un pilotaje individual).
3. **Ensayar con el Panel en vivo y con transición**, igual que el día real. Todo lo registrado debe quedar como pilotaje y **no aparecer en Resultados**.
4. Registrar hallazgos del pilotaje y **Validar pilotaje** (revisar las advertencias del análisis).
5. **Publicar**. Verificar que desde ese momento Estaciones, tiempos, y borrar/renumerar estudiantes quedan bloqueados, con el aviso correspondiente.
6. **Despublicar**, corregir algo y volver a publicar.

Buscar: estados que no cambian aunque la acción se complete, mensajes poco claros, algo editable que debería estar bloqueado.

## Ronda 5 — Día del examen (la más importante)

Hacerla con varias personas y dispositivos a la vez, en la red del recinto si es posible.

**Montaje**

1. En **Kioscos**, generar todos los enlaces y abrir cada uno en su tablet. Cada tablet debe quedar esperando con el nombre correcto de estación.
2. En el **Panel en vivo**, la sección «Estaciones en vivo» debe mostrar evaluadores y tablets conectados y la verificación previa en «todo listo». Apagar una tablet: debe pasar a «sin conexión» en menos de un minuto.
3. Pasar a **En ejecución**. El cronómetro debe partir limpio (estación 1), aunque el pilotaje haya terminado en otra.

**Rotación normal**

4. El evaluador confirma por Número ECOE (probar `7`, `007` y `E007`), evalúa y guarda. La pantalla queda lista para el siguiente.
5. En una estación con formulario, el estudiante responde en la tablet y envía.
6. **Confirmar al siguiente estudiante durante la transición**: no debe perder su estación ni su tiempo.
7. Correr al menos **dos rotaciones completas** y, si se usa, el **circuito automático** con su pausa entre rondas.
8. En espejo: operar los dos circuitos en paralelo.

**Errores a provocar a propósito**

9. **Número mal tipeado** de alguien que está en otra estación → debe avisar antes de confirmar.
10. **Estudiante del otro circuito** → debe avisar.
11. **Confirmar al equivocado y anular el ingreso**; confirmar luego al correcto.
12. **Reconfirmar al mismo estudiante** en su estación → no debe pasar nada malo.
13. **Doble toque en Enviar** y **reintento con mala red** → un solo registro, sin mensaje de error.
14. **Apagar una tablet a mitad de estación**: al terminar la fase, lo que el estudiante alcanzó a escribir debe quedar guardado.
15. **Pausar** en plena estación y reanudar; **pausar durante una transición** y reanudar (debe seguir siendo transición).
16. **Cortar el wifi** de una estación un par de minutos y volver.
17. **Suspender la cuenta de un evaluador** desde Usuarios: su pantalla debe dejar de recibir el cronómetro.
18. Intentar **editar una estación** con el examen corriendo → bloqueado.

**Contingencia**

19. Una estación «en papel»: transcribir la respuesta del estudiante por **Contingencia** (debe reemplazar el autoenvío en blanco).
20. **Rectificar** una evaluación mal enviada, con motivo.
21. Registrar y resolver una **incidencia**.

Buscar: respuestas asociadas al estudiante equivocado, registros duplicados o perdidos, cronómetros que no coinciden entre pantallas, problemas en tablet.

## Ronda 6 — Cierre y resultados

Rol: administración del ECOE; corrector.

1. **Corrección diferida**: el corrector puntúa las respuestas de texto.
2. **Cerrar con estudiantes incompletos**: debe detenerse y listarlos. Probar las tres salidas: contingencia, suspender al ausente, y cerrar de todas formas (las faltantes cuentan 0).
3. Tras cerrar: nada debe poder editarse ni registrarse.
4. **Resultados**:
   - *Notas*: estaciones rendidas sobre esperadas; comprobar a mano la nota de dos estudiantes.
   - *Por estación*: en espejo, una fila por estación con el promedio de cada circuito.
   - *Análisis*, *Trazabilidad* y *Actividad*.
5. **Exportar Excel** y revisar que cuadre con la pantalla.
6. **Reabrir ejecución** con motivo (sólo administración del ECOE; un coeditor no debe poder). Ingresar algo por contingencia, cerrar de nuevo y verificar que aparece «Actas anteriores».
7. **Archivar**: ya no debe ofrecer ninguna acción.

Buscar: diferencias entre lo ejecutado y lo registrado, exportaciones incompletas, notas que no se explican.

## Ronda 7 — Operación del servidor

Rol: quien administra el servidor.

1. `./scripts/verify_backup.sh` debe restaurar el último respaldo y listar el contenido.
2. Con un ECOE en ejecución, comprobar que aparecen volcados nuevos en `backups/live/` cada 5 minutos.
3. `./scripts/deploy.sh` actualiza producción y demo; ambos responden después.
4. `./scripts/demo_reset.sh` deja el demo recién cargado.

---

## Orden sugerido

1. Rondas 1 a 3 (configurar).
2. Ronda 4 (pilotaje), que ya ejercita buena parte de la 5.
3. Ronda 5 completa con el equipo, idealmente en el recinto.
4. Ronda 6.
5. Ronda 7 en cualquier momento.

Complementos: `MANUAL_USUARIO.md` (uso de cada pantalla) y `docs/OPERACION_DIA_EXAMEN.md` (lista de verificación del día).
