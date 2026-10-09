# Auditoría del proceso ECOE — coherencia, flujos, pérdida de información, zonas sin cubrir y seguridad (2026-10-09)

Solicitada por el usuario antes de sus pruebas. Alcance: backend (`backend/app`), modelo de datos (`models/entities.py`), y el frontend asociado, recorridos por las seis áreas del menú. Triage en `BACKLOG.md` (Grupo E, PROC-1…).

**Método.** Lectura de código + reproducción por API contra el stack desechable `docker-compose.e2e.yml` (PostgreSQL real con migraciones Alembic, evento demo en `en_ejecucion`). Cada hallazgo indica si está **verificado** (reproducido, con la respuesta HTTP observada) o es **por lectura** (deducido del código, sin reproducir). Nada se ejecutó contra producción.

**Profundidad por área.** Día del examen, Cierre y Este ECOE: revisión completa con reproducción. Preparación: completa por lectura, parcial por reproducción (no se recorrió un evento nuevo desde `borrador`). Biblioteca e Institución: revisión ligera por lectura (rutas, guardas y permisos); no se encontraron problemas graves pero no se probaron.

---

## Resumen

El núcleo está bien resuelto: máquina de estados con autoridad en backend, gate de envíos por etapa, separación pilotaje/ejecución, deadlines de servidor, snapshot al cierre, autorización por capas, tokens de kiosco con hash. Los problemas están en los **bordes del día del examen** y en la **falta de candados una vez que hay datos**:

1. Hay una secuencia natural de operación (confirmar al estudiante durante la transición) que le hace perder la estación. **PROC-1**
2. Los errores humanos típicos del día (número mal tipeado, tablet caída) no tienen vuelta atrás dentro de la plataforma. **PROC-2, PROC-3**
3. La clave de respuestas viaja al dispositivo del estudiante. **PROC-4**
4. Con el examen en curso, o ya cerrado, se puede seguir editando y borrando la estructura sobre la que se calculan las notas. **PROC-5, PROC-8**
5. La nota promedia sólo las estaciones con registro: una estación perdida no baja la nota y el cierre no lo advierte. **PROC-6**

---

## Día del examen

### PROC-1 · Confirmar al estudiante durante la transición le autoenvía la estación en blanco — **bloqueante · verificado**
- **Evidencia**: `utils/helpers.py::_live_phase_station_deadline` devuelve, en `transition`, el inicio de la transición como deadline del estudiante; en `round_pause` un instante pasado. `services/live_sweep.py` autoenvía todo check-in `confirmado` cuyo deadline + 30 s venció.
- **Reproducción**: `start` → `next_transition` → check-in de E002 en la estación 2 (con formulario) → esperar 36 s (la transición dura 120 s). Resultado: `blank_auto_submissions: 1`, el kiosco vuelve a "esperando" y el envío del estudiante responde `409 No hay un ingreso activo`. El borrador que el estudiante alcanzó a guardar se envía tal cual.
- **Impacto**: la transición es justamente el momento en que el estudiante llega a la puerta y el evaluador lo confirma. En estaciones con formulario pierde la estación antes de que empiece. Con circuito automático pasa lo mismo en la pausa entre rondas.
- **Esperado**: un check-in hecho en `transition`/`round_pause` pertenece a la **siguiente** fase de estación: su deadline es el fin de esa fase y el barrido no lo toca hasta entonces.

### PROC-2 · Una respuesta autoenviada en blanco no se puede reemplazar — **alta · verificado**
- **Evidencia**: `routes/contingency.py::submit_student_response_by_contingency` rechaza si ya existe `StudentResponse` (`400 Ya existe una respuesta registrada`), y el barrido crea una al vencer la fase aunque la tablet esté caída.
- **Impacto**: contradice `docs/OPERACION_DIA_EXAMEN.md` ("caída de red: seguir en papel y transcribir por contingencia"). En una estación con formulario, cuando el papel llega a coordinación la respuesta en blanco ya existe y bloquea la transcripción. Lo mismo vale para una evaluación del evaluador enviada con error: `evaluator/submit` y contingencia la declaran inmodificable y no existe ruta de rectificación.
- **Esperado**: contingencia debe poder **sustituir** una respuesta `submission_kind="auto"` (y rectificar una evaluación) dejando auditoría del valor anterior.

### PROC-3 · Un check-in equivocado no se puede anular y deja al estudiante en dos estaciones — **alta · verificado**
- **Evidencia**: `routes/evaluator.py::confirm_station_checkin` cierra los check-ins previos **de la estación**, no los del **estudiante**; no existe endpoint de anulación. No hay restricción en BD que impida dos `confirmado` del mismo estudiante.
- **Reproducción**: E001 confirmado en estación 4, luego (simulando un número mal tipeado) en estación 2 → ambos quedan `confirmado`; la pantalla del estudiante pasa a mostrar la estación 2 (contenido de otra estación); el kiosco de la 4 sigue mostrándolo. Al vencer la fase se crean **dos** respuestas en blanco. Cuando el estudiante llega de verdad a la estación 2: `409 student_already_evaluated` y el formulario ya está cerrado (ver PROC-2).
- **Esperado**: botón "anular ingreso" (mientras no haya envíos), y que confirmar a un estudiante cierre su check-in abierto en cualquier otra estación.

### PROC-9 · La sesión en vivo no parte limpia — **media · verificado en parte**
- **Verificado**: `Reanudar` sobre una sesión `ready` la deja `running` sin pasar por Iniciar; `Iniciar` tras `Sig. estación` deja `current_station_index = 2` (no vuelve a 1). El frontend ya deshabilita Reanudar fuera de pausa (UX-6), el backend lo sigue aceptando.
- **Por lectura**: `/live/control` crea la `LiveSession` en pilotaje; `update_ecoe_status` no la reinicia ni al publicar ni al entrar a `en_ejecucion`. Si el pilotaje terminó en estación 5, en `circuit_complete` o con circuito automático activo, la ejecución real hereda ese estado; con `circuit_complete` todo envío se rechaza hasta que alguien pulse Reiniciar.
- **Esperado**: reiniciar la sesión (estación 1, ronda 1, `ready`, modo automático apagado) en la transición a `en_ejecucion`.

### PROC-11 · Circuitos espejo, grupos y modo de circuito no gobiernan nada — **media · por lectura**
- **Evidencia**: `circuit_mode` y `total_groups` sólo se copian y se muestran. `services/live_cycle.py::station_slot_count` cuenta **todas** las estaciones del evento como un único circuito; `compute_total_rounds = ⌈estudiantes / estaciones⌉`. El check-in no compara `student.circuit_name` con `station.circuit_name`.
- **Impacto**: en un diseño espejo (A: estaciones 1–3, B: 4–6) el circuito automático calcula rondas de 6 fases en vez de 3. Un estudiante del circuito B puede confirmarse en una estación del A sin aviso. No existe plan de rotación (quién parte en qué estación en cada ronda).
- **Esperado**: decisión de diseño — o el circuito automático se declara válido sólo para circuito único, o las rondas se calculan por circuito; y el check-in advierte cuando el circuito no coincide.

### PROC-12 · Estaciones sin evaluador dependen de un check-in manual en cada rotación — **media · por lectura**
- **Evidencia**: el kiosco sólo muestra a un estudiante tras un check-in, y sólo evaluador asignado, coordinador o admin pueden confirmarlo. Las estaciones "sólo formulario" (demo: 4 y 6) no tienen evaluador.
- **Impacto**: alguien de coordinación debe confirmar a cada estudiante en cada rotación de cada estación sin evaluador. No está en el checklist del día.
- **Esperado**: definir quién lo hace (ver propuesta de coordinación) o permitir que el estudiante se identifique en el kiosco con su número ECOE.

### PROC-10 · El puntaje del evaluador lo calcula el navegador — **media · verificado**
- **Reproducción**: `POST /evaluator/submit` con todos los criterios "no cumplido" y `score_obtained: 20` → `200`, nota 7,0.
- **Impacto**: la nota y el desglose por criterio (item analysis del Excel) pueden no coincidir, por un error del cliente o una request armada a mano por un evaluador.
- **Esperado**: recalcular el puntaje en el servidor desde `answers` y la pauta; rechazar o registrar la discrepancia.

---

## Cierre

### PROC-6 · Una estación sin registro no baja la nota y el cierre no avisa — **alta · verificado**
- **Evidencia**: `services/results.py::compute_results` promedia sólo las estaciones con registro (`stations_counted`).
- **Reproducción**: E007 con una sola estación evaluada (20/20) → `percentage 100`, nota `7,0`, `stations_counted 1`. Al cerrar con casi todos los estudiantes incompletos y dos autoenvíos en blanco, `validation` no entrega ninguna advertencia de cierre (sólo cubre corrección diferida y borradores de evaluador).
- **Impacto**: un estudiante que se salta una estación (o cuya evaluación se perdió) queda con mejor nota que uno que la rindió mal. La trazabilidad sí lo muestra como "parcial", pero es una pestaña aparte que nadie está obligado a mirar.
- **Esperado**: decisión del usuario — estación esperada sin registro = 0, o = bloqueo de cierre hasta resolverla. En ambos casos, el modal de cierre debe listar estudiantes incompletos por circuito.

### PROC-7 · El cierre es irreversible y la reactivación mezcla corridas — **alta · verificado**
- **Evidencia**: grafo `en_ejecucion → cerrado → archivado → borrador`. Contingencia tras el cierre: `409`.
- **Reproducción**: tras `archivado → borrador`, `/results` deja de estar congelado y sigue mostrando los registros de la corrida anterior (E007 100 %). Una segunda ejecución sumaría sobre ellos y chocaría con la restricción única (estudiante, estación, modo).
- **Impacto**: un cierre accidental, o papel que aparece después, no tiene solución dentro de la plataforma. "Reactivar" parece un reinicio pero conserva evaluaciones, respuestas y check-ins anteriores.
- **Esperado**: (a) reapertura controlada `cerrado → en_ejecucion` sólo para admin, auditada, que invalida el snapshot; (b) "Reactivar" o se elimina, o exige duplicar el evento.

### PROC-8 · El acta congelada no congela identidades ni estructura — **alta · verificado**
- **Reproducción con el ECOE `cerrado`**: renumerar estudiantes `200`; editar una estación (`max_score: 999`) `200`; cambiar nombre y % de aprobación del evento `200`. Con `en_ejecucion`: suspender a un estudiante lo hace desaparecer de `/results`.
- **Evidencia**: `ECOEResult`/`StationResult` guardan sólo `student_id`/`station_id`; nombre, RUT y número ECOE se leen en vivo.
- **Impacto**: después del cierre se puede alterar a quién corresponde cada fila del acta sin tocar el snapshot ni dejar rastro.
- **Esperado**: ver PROC-5 (candado por estado) y guardar nombre, RUT y número ECOE en el snapshot.

---

## Este ECOE

### PROC-5 · No hay candados por estado sobre la estructura — **alta · verificado**
- **Evidencia**: `routes/students.py`, `routes/stations.py`, `routes/staff.py` y `PUT /ecoe/{id}` no consultan el estado del evento. `services/instruments.py::ensure_tool_editable` sí lo hace para pautas, lo que deja la regla a medias.
- **Reproducción con el ECOE `en_ejecucion`**: cambiar el formulario y la clave de una estación `200`; renumerar estudiantes `200`; borrar un estudiante y una estación sin registros `200`; cambiar el tiempo por estación de 8 a 3 min con el cronómetro corriendo `200` (la sesión en vivo pasa a 180 s para las fases siguientes).
- **Impacto**: a mitad de examen, estudiantes de una misma estación pueden quedar evaluados con formularios, claves o tiempos distintos; renumerar cambia los números que los evaluadores están tipeando.
- **Esperado**: desde `publicado` la estructura queda de sólo lectura (estaciones, pautas, formularios, nómina, numeración, tiempos); en `en_ejecucion` sólo se permite alta de estudiante rezagado y reasignación de evaluador; en `cerrado`/`archivado`, nada.

### PROC-13 · Borrar con registros responde 500 — **media · verificado**
- **Reproducción**: `DELETE /students/{id}` o `/stations/{id}` con evaluaciones → `500` (`ForeignKeyViolation`). Los datos no se pierden (la restricción protege), pero el usuario ve un error técnico. En SQLite la restricción no actúa, así que los tests locales no lo detectan.
- **Esperado**: `409` con mensaje claro; suspender en vez de borrar.

### PROC-14 · Ediciones y borrados de estructura sin auditoría — **media · por lectura**
- **Evidencia**: no se escribe `AuditLog` en alta/edición/borrado de estaciones, estudiantes, equipo, renumeración ni deduplicación. Sí en check-ins, envíos, transiciones y kiosco.
- **Impacto**: ante una discrepancia no se puede reconstruir quién cambió la nómina o una estación.

### PROC-15 · "+ Nuevo ECOE" visible para quien no puede crearlo — **baja · por lectura**
- **Evidencia**: `POST /ecoe` exige `admin_global`; el botón (UX-5) se muestra a todos y devolverá 403.

---

## Preparación

### PROC-16 · La validación no cubre todo lo que el día exige — **media · por lectura**
- `can_publish` no exige estudiantes activos (sólo `can_pilot`).
- Evaluador sin cuenta activa, o sin estación asignada, es advertencia y no bloqueo de publicación.
- No se verifica que el corrector tenga cuenta activa, ni que cada estudiante tenga circuito válido, ni que exista quien confirme en las estaciones sin evaluador (PROC-12).
- Una estación sin evaluador y sin formulario con puntos pasa la validación (`max_score > 0`) aunque nada pueda puntuarla.
- No hay verificación previa de dispositivos: nada indica qué estaciones tienen kiosco vinculado y vivo antes de iniciar.

### PROC-17 · El pilotaje no ensaya la ejecución real completa — **baja · por lectura**
- En pilotaje sin operador el deadline cae al reloj por check-in; con operador usa el reloj central. El comportamiento de PROC-1 sólo aparece cuando se pilotea con el panel en vivo y con transición, que es exactamente como se debe pilotear.

---

## Seguridad

### PROC-4 · La clave de respuestas llega al dispositivo del estudiante — **alta · verificado**
- **Reproducción**: `GET /kiosk/context` y `POST /student/access` devuelven `student_form_definition` completo, incluido `"correct_option": "SCA"` y los puntos por pregunta.
- **Impacto**: en modo estudiante (su propio equipo) la clave se lee en las herramientas del navegador. En kiosco el riesgo es menor pero existe.
- **Esperado**: servir al estudiante una versión sin `correct_option`/`correct_options`.

### Otros puntos revisados
- **Bien**: JWT con versión de token, argon2, rate limit de login, `SECRET_KEY` obligatoria en producción, CORS sin comodín, cookie `SameSite`, tokens de kiosco e invitaciones guardados como hash, permisos de multimedia por rol y estación, `GET /stations` negado al estudiante (verificado `403`).
- **PROC-18 · baja**: el enlace de kiosco lleva el token en la URL (queda en historial y logs del proxy) y dura 24 h.
- **PROC-19 · baja**: en modo estudiante los medios con destino "ambos" no se muestran (`student_access` filtra `== "estudiante"`), en kiosco sí (`in ("estudiante","ambos")`).

---

## Biblioteca e Institución (revisión ligera)

- Pautas, plantillas y pacientes: archivado en vez de borrado, purga protegida, edición de pautas bloqueada si las usa un evento en estados sensibles. Coherente.
- **PROC-20 · baja**: al duplicar un ECOE las estaciones comparten pauta, plantilla y paciente con el original (decisión OPT-7); no se copian correctores ni multimedia. La validación avisa lo segundo, no lo primero.
- Usuarios: sólo `admin_global`, con protección contra desactivar al último administrador e invalidación de tokens al suspender. Sin hallazgos.

---

## Infraestructura y datos

### PROC-21 · Punto único de falla el día del examen — **alta · por documentación**
- `datos_proyecto/operacion_despliegue.md`: servidor único en conexión residencial con IP pública dinámica detrás de Cloudflare; si la IP cambia durante el examen, el sitio cae hasta actualizar el registro DNS a mano.
- Respaldo de BD diario y copia externa cifrada funcionando (verificado en `offsite_cron.log`), pero la frecuencia diaria deja sin respaldo todo lo registrado durante el examen. El volumen de multimedia no está en el respaldo automático.
- Un solo proceso backend: un reinicio corta los WebSocket (se reconectan) y el timbre puntual; el reloj sobrevive porque vive en BD.

---

## Propuesta de coordinación de personas y dispositivos

La plataforma hoy asume que la coordinación ocurre fuera de ella. Propuesta en dos capas.

### A. Lo que puede hacerse ya, sin código

1. **Roles del día, una persona por rol, con suplente nombrado**
   - *Director del examen*: única persona que cambia el estado del ECOE (Iniciar ejecución, Cerrar).
   - *Cronometrador*: único que toca el Panel en vivo. Nadie más inicia, pausa ni avanza.
   - *Coordinador de contingencia*: único que registra por contingencia y resuelve incidencias.
   - *Anfitrión de circuito* (uno por circuito): mueve a los estudiantes y confirma el ingreso en las estaciones sin evaluador.
   - *Soporte técnico*: red, tablets y servidor; no opera el examen.
2. **Regla de oro mientras no se corrija PROC-1**: el evaluador confirma al estudiante **después** de que suena el inicio de estación, nunca durante la transición.
3. **Regla de congelamiento**: desde que el ECOE queda `publicado` nadie edita estaciones, nómina ni tiempos. Cualquier cambio pasa por el director y obliga a repetir la verificación previa.
4. **Mapa de dispositivos impreso**: una fila por estación con evaluador, dispositivo del evaluador, tablet de kiosco (etiquetada con el número de estación), y repuesto. Una fila aparte para proyector, panel de coordinación y equipo de contingencia.
5. **Plan de rotación impreso**: por ronda y circuito, qué número ECOE parte en qué estación. Hoy la plataforma no lo genera.
6. **Ensayo general obligatorio** con el panel en vivo, transición real, todos los dispositivos y la red del recinto, incluyendo a propósito: un número mal tipeado, una tablet apagada a mitad de estación, una pausa y un corte de wifi.
7. **Red**: wifi del recinto probado + hotspot 4G de respaldo ya emparejado en el panel y en al menos una tablet; el día del examen alguien vigila el acceso al servidor desde fuera del recinto.
8. **Papel**: PDF de contingencia impreso por estación, y una hoja de "incidencias de coordinación" numerada para que todo lo que se resuelva a mano quede anotado con hora, estación y número ECOE antes de transcribirlo.
9. **Antes de cerrar**: revisión conjunta director + coordinador de la pestaña Trazabilidad hasta que no queden "parciales" sin explicación, y respaldo manual de la BD inmediatamente antes y después del cierre.

### B. Lo que conviene construir

1. **Verificación previa ("pre-vuelo") en el Panel en vivo**: por estación, evaluador conectado, kiosco vinculado y con señal reciente, cronometrador conectado; todo en verde antes de habilitar Iniciar. Los kioscos y evaluadores ya consultan al servidor cada pocos segundos: basta registrar la última señal.
2. **Tablero de estaciones en vivo**: por estación, estudiante confirmado, si ya hay evaluación y respuesta, y alerta cuando una fase termina sin registro. Convierte la trazabilidad de "revisión posterior" en "aviso durante".
3. **Plan de rotación generado por la plataforma** a partir de nómina, circuito y número de estaciones; el check-in avisa cuando el estudiante no es el esperado en esa estación y ronda (resuelve PROC-3 y PROC-11 en el origen).
4. **Anular ingreso y sustituir autoenvío** (PROC-2, PROC-3) con auditoría.
5. **Candado por estado** (PROC-5) y **modal de cierre con incompletos** (PROC-6).
6. **Respaldo automático cada pocos minutos mientras el ECOE está `en_ejecucion`**, y uno forzado en la transición a `cerrado`.

---

## Orden sugerido de corrección

1. PROC-1 (bloqueante) y PROC-4 (seguridad): acotados, solo backend, con tests.
2. PROC-2 y PROC-3: contingencia y anulación; requieren decidir reglas de auditoría.
3. PROC-5 y PROC-8: candado por estado y snapshot con identidad (migración).
4. PROC-6 y PROC-7: requieren decisión del usuario sobre la regla de nota y la reapertura.
5. PROC-9, PROC-10, PROC-13, PROC-14: endurecimiento.
6. Coordinación B.1 y B.2 (pre-vuelo y tablero), luego B.3.
