# Hallazgos — auditor-operacion-vivo · 2026-08-28

Primera pasada, profundidad media-alta. Operación en vivo de punta a punta:
arranque de sesión al publicar, cronómetro central de servidor, rotaciones y
transiciones del timer, modo kiosko y rotación de token, gate de envíos por
etapa, contingencia / incidencias, y cierre (`persist_results` + cierre forzado
de check-ins). Foco: huecos donde datos de pilotaje contaminen resultados
reales o viceversa.

Método: lectura de código backend + frontend y ejercicio de la API / servicios
in-process con `TestClient` y `TestingSessionLocal` (fixtures de
`backend/tests/conftest.py`, SQLite). Tests exploratorios `test_audit_vivo_*`
escritos y borrados al terminar. No se levantó servidor, Docker ni navegador;
lo que requiere WS/navegador real queda marcado como "requiere confirmación
del usuario".

## Resumen

| Severidad | N.º |
|---|---|
| bloqueante | 0 |
| alta | 1 |
| media | 3 |
| baja | 4 |
| cosmético | 0 |

**Verificado OK (sin hallazgo):**
- **El cronómetro es autoridad de servidor para los envíos.** Las ventanas de
  envío se calculan siempre desde `checkin.confirmed_at + station_time` con
  `utcnow_naive()` (`helpers.py::checkin_submission_deadline` /
  `ensure_checkin_within_time`), nunca desde un timer de cliente. Un check-in
  con `confirmed_at` viejo da deadline en el pasado aunque el cliente mande
  otra cosa. `compute_remaining_seconds` deriva el restante de
  `phase_started_at` + reloj del servidor. `/live/control` no acepta ningún
  timestamp de cliente.
- **La pausa del cronómetro central NO extiende las ventanas de envío** — es el
  comportamiento documentado en `docs/OPERACION_DIA_EXAMEN.md` (se resuelve por
  contingencia). Ver H-vivo-3 por la fricción que genera.
- **Aislamiento pilotaje/ejecución en RESULTADOS y consolidado.**
  `compute_results` y `persist_results` filtran `mode == ejecucion`; las
  columnas `EvaluatorRecord` / `StudentResponse` tienen `UniqueConstraint`
  `(ecoe_event_id, station_id, student_id, mode)`, así que un registro de
  pilotaje ni bloquea ni suma al puntaje real. El gate `ensure_submission_stage`
  rechaza con 409 todo estado fuera de `en_pilotaje` / `en_ejecucion` y estampa
  el `mode` autoritativamente (el cliente no lo elige).
- **`EvaluatorSubmission` / `StudentResponseCreate`**: los routers excluyen
  `mode`, `max_score`, `by_contingency`, `checkin_id` del `model_dump`; el
  `max_score` sale de `resolve_station_max_score` y el puntaje del formulario de
  `apply_auto_grading`. El cliente no puede inyectar puntaje ni modo.
- **Cierre congela la operación.** `update_ecoe_status` a `cerrado` corre
  `persist_results(commit=False)` y cierra todos los check-ins `confirmado` en
  la misma transacción; después `ensure_submission_stage` rechaza todo (probado:
  POST `/evaluator/submit` da 409 tras cerrar).
- **Kiosko**: token con `secrets.token_urlsafe(32)`, solo SHA-256 en BD, emitir
  uno nuevo revoca los anteriores (`issue_kiosk_token`), `authenticate_kiosk_token`
  valida `revoked_at` y `expires_at`. El identity del que responde sale del
  check-in de la estación, no de una sesión de usuario. `/kiosk/submit` pasa por
  `ensure_submission_stage`.

---

### H-vivo-1 · Registros de pilotaje contaminan la trazabilidad y el estado "completo" del cierre
- **Rol / pantalla**: coordinador / admin_ecoe · `/results` (trazabilidad por estudiante) — usado en el checklist de cierre
- **Severidad**: alta
- **Tipo**: dato · inconsistencia backend/UI (crossover pilotaje↔real)
- **Evidencia**: `backend/app/services/results.py::build_traceability_report`.
  `student_evaluations`, `student_form_responses`, `student_checkins` se arman
  **sin filtro de `mode`** (líneas ~205-215), a diferencia de `compute_results`
  que sí filtra `mode == ejecucion`. `StationCheckIn` **no tiene columna `mode`**
  (`entities.py:443`), así que un check-in de pilotaje es indistinguible de uno
  real. Test scratch: un estudiante creado con SÓLO registros `mode="pilotaje"`
  (check-ins + evaluator records + student responses en todas las estaciones de
  su circuito) y **cero actividad de ejecución** produce:
  `completion_status = "completo"`, `missing_evaluations = 0`,
  `missing_student_submissions = 0`; y en paralelo `compute_results` le da
  `total_score = 0`, `percentage = 0`, `equivalent_grade = 1.0`.
  `frontend/src/app/(app)/results/page.tsx:125` pinta ese `completion_status`
  como badge verde "completo".
- **Reproducción**: correr pilotaje con cuentas de estudiante reales sobre las
  interfaces reales (lo que pide `docs/OPERACION_DIA_EXAMEN.md` T-7). Un
  estudiante que pilotó pero **faltó** a la ejecución real aparece "completo" en
  la trazabilidad de cierre y con nota 1.0 en el consolidado.
- **Esperado vs. observado**: esperado — la trazabilidad de `/results` (que el
  checklist de cierre usa para "resolver faltantes por contingencia") debe
  contar sólo actividad `mode == ejecucion`. Observado — cuenta también
  pilotaje; `completion_status`, `missing_*`, `checkins_confirmed`,
  `evaluator_submissions`, y los contadores de `summary` (`confirmed_checkins`,
  `evaluator_submissions`, `student_submissions`) quedan inflados por el
  pilotaje. Las notas del consolidado NO se afectan (bien), pero la señal que
  guía las decisiones de contingencia del día del examen sí.
- **Notas del auditor**: hipótesis de causa: `build_traceability_report` se
  escribió antes o en paralelo al modelo de `mode` y no se le agregó el filtro.
  Arreglo probable: filtrar `EvaluatorRecord.mode == ejecucion` /
  `StudentResponse.mode == ejecucion` en las tres colecciones por-estudiante y
  por-estación, y stampar `mode` (o al menos excluir los check-ins de pilotaje)
  — lo que a su vez pide una columna `mode` en `StationCheckIn` o cerrar/marcar
  los check-ins de pilotaje al salir de `en_pilotaje` (ver H-vivo-4). Cambio de
  schema/dato → gate humano.

---

### H-vivo-2 · Blocker fantasma "No existe una sesión en vivo" en toda etapa previa a `publicado` (profundiza H-admin-3)
- **Rol / pantalla**: admin_ecoe / coeditor_docente · `/publication` y `/validation`
- **Severidad**: media
- **Tipo**: inconsistencia backend/UI · fricción-UX
- **Evidencia**: `backend/app/services/validation.py::compute_ecoe_validation`.
  El array genérico `blockers` **siempre** agrega
  `"No existe una sesión en vivo creada para la ejecución real."` cuando
  `has_live_session == 0`, sin condicionarlo al estado del ECOE. Pero la
  `LiveSession` sólo se crea **en la transición a `publicado`**
  (`update_ecoe_status`, rama `target_status == publicado`). Por lo tanto en
  `borrador … pilotaje_validado` `has_live_session` es siempre 0 y el blocker
  rojo se muestra siempre. `can_publish` NO depende de `has_live_session` (sólo
  `can_start_live` lo hace), así que el botón "Publicar" no está realmente
  bloqueado por esto. `frontend/src/app/(app)/publication/page.tsx:95` renderiza
  `data.blockers` como cajas rojas justo al lado del banner
  `data.can_publish ? "Listo para publicar" : …` (línea ~88) → señales
  contradictorias: "Listo para publicar" + caja roja "No existe sesión en vivo".
  Test scratch confirmó el blocker presente en estado `pilotaje_validado`.
- **Reproducción**: abrir `/publication` o `/validación` en cualquier ECOE que
  aún no se ha publicado.
- **Esperado vs. observado**: esperado — antes de publicar no debería alarmar
  por algo que la propia publicación crea. Observado — blocker rojo permanente
  hasta publicar, contradiciendo el estado "Listo para publicar".
- **Notas del auditor**: mover ese ítem de `blockers` a `live_checks`
  únicamente, o condicionarlo a `ecoe_event.status in {publicado, en_ejecucion}`.
  Los `live_checks` ya tienen "Sesión en vivo creada" — el blocker en el array
  genérico es redundante.

---

### H-vivo-3 · Evaluador y kiosko no reciben el broadcast del panel en vivo: sus cronómetros siguen corriendo (y auto-envían) durante una pausa coordinada
- **Rol / pantalla**: evaluador · `/evaluator` ; kiosko · `/kiosk`
- **Severidad**: media
- **Tipo**: fricción-UX · inconsistencia operativa
- **Evidencia**: `frontend/src/app/(app)/evaluator/page.tsx` deriva su cuenta
  regresiva de `confirmedAt + timerDurationSeconds` con un offset de reloj de
  servidor (líneas ~61-137); **no abre ningún WebSocket** (`resolveLiveWsUrl`
  sólo se usa en `/live`). `frontend/src/app/kiosk/page.tsx` cuenta contra
  `current.submission_deadline` y **auto-envía** al expirar
  (`autoSubmitAttemptedRef`, líneas ~208-224). Ninguna de las dos pantallas
  conoce el estado `paused` del `LiveTimerManager`. `docs/OPERACION_DIA_EXAMEN.md`
  ya lo asume ("la pausa NO extiende las ventanas … el coordinador registra ese
  caso por contingencia").
- **Reproducción**: coordinador pulsa "Pausar" en `/live` por una incidencia que
  detiene el circuito. Los kioscos de la rotación en curso siguen contando y al
  llegar a 0 auto-envían formularios incompletos; los evaluadores ven su
  semáforo pasar a rojo sin ninguna señal de que hay pausa.
- **Esperado vs. observado**: esperado — al pausar el circuito, las pantallas
  operativas deberían al menos indicar "pausa en curso" y frenar el auto-envío.
  Observado — cero visibilidad; se traduce en una tanda de entradas manuales por
  contingencia por cada pausa (una por estudiante del circuito), justo bajo
  presión.
- **Notas del auditor**: no es un bug de datos (el servidor sigue siendo
  autoridad y la contingencia queda auditada), es carga operativa. Opciones:
  suscribir `/evaluator` y `/kiosk` al mismo WS del evento y, en `paused`,
  ocultar el botón de envío + suspender el auto-submit del kiosko; o que la
  pausa extienda explícitamente las ventanas de los check-ins abiertos de esa
  rotación (cambio de semántica — gate humano). Confirmación visual del
  comportamiento WS real: requiere confirmación del usuario.

---

### H-vivo-4 · `publicado → en_ejecucion` no limpia check-ins `confirmado` que quedaron abiertos del pilotaje
- **Rol / pantalla**: evaluador / kiosko · arranque del día del examen
- **Severidad**: baja
- **Tipo**: bug · higiene de estado
- **Evidencia**: `backend/app/services/validation.py::update_ecoe_status`. Las
  ramas `publicado` (crea `LiveSession`, pasa estaciones a `publicada`) y
  `cerrado` (`persist_results` + cierra check-ins) tienen efectos colaterales;
  la rama `en_ejecucion` **no tiene ninguno**. Salir de `en_pilotaje`
  (`en_pilotaje → pilotaje_validado`) tampoco cierra los check-ins. Un check-in
  `status="confirmado"` creado durante el pilotaje sigue `confirmado`
  indefinidamente. `evaluator_context` y `kiosk_context` consultan
  `status == "confirmado"` ordenado por `confirmed_at desc` y mostrarían ese
  estudiante viejo como "activo" hasta el primer check-in real de la estación
  (el `confirm_station_checkin` sí cierra los `confirmado` previos de esa
  estación, así que se auto-cura al primer uso).
- **Reproducción**: pilotar una estación confirmando un ingreso y no enviar;
  avanzar el ECOE hasta `en_ejecucion`; abrir `/evaluator` o la tablet de kiosko
  de esa estación antes del primer check-in real.
- **Esperado vs. observado**: esperado — al arrancar la ejecución real, ninguna
  rotación de pilotaje sobrevive. Observado — el evaluador/kiosko puede ver un
  estudiante de pilotaje como confirmado; su `submission_deadline` está en el
  pasado, así que un envío se rechaza por ventana (contenido), pero la pantalla
  confunde. También suma a H-vivo-1 (esos check-ins cuentan en la trazabilidad).
- **Notas del auditor**: cerrar todos los check-ins `confirmado` del evento al
  entrar a `en_ejecucion` (y/o al salir de `en_pilotaje`), igual que hace el
  cierre.

---

### H-vivo-5 · `/kiosk/submit` acepta cualquier `checkin_id` de la estación, no sólo el check-in activo
- **Rol / pantalla**: kiosko · `/kiosk/submit`
- **Severidad**: baja
- **Tipo**: permiso · integridad de dato
- **Evidencia**: `backend/app/api/routes/kiosk.py::kiosk_submit`. Hace
  `checkin = db.get(StationCheckIn, payload.checkin_id)` y sólo valida
  `checkin.station_id == kiosk.station_id`. No exige que sea el check-in
  `confirmado` vigente. Con un token de kiosko válido para la estación X, una
  request armada a mano puede enviar respuestas atribuidas a **cualquier
  estudiante que haya tenido un check-in en X** cuya ventana de tiempo siga
  abierta (p. ej. el estudiante inmediatamente anterior durante el solapamiento
  de la transición), mientras ese estudiante aún no tenga respuesta registrada
  (el chequeo de duplicado por `mode` cubre el caso común de que ya envió).
- **Reproducción**: token de kiosko de estación X; `POST /api/kiosk/submit` con
  el `checkin_id` del estudiante anterior (visible en un `/kiosk/context`
  previo) dentro de su ventana.
- **Esperado vs. observado**: esperado — el kiosko sólo puede responder por el
  estudiante del check-in activo confirmado. Observado — puede responder por un
  check-in anterior ya `cerrado` pero dentro de ventana. El comentario en el
  código ("identity is fixed by the check-in row, so nothing can be submitted
  on someone else's behalf") subestima este borde.
- **Notas del auditor**: exigir que `payload.checkin_id` coincida con el
  check-in `confirmado` más reciente de la estación (o al menos que su
  `confirmed_at` sea el máximo). Riesgo real bajo: requiere request manual desde
  un dispositivo ya confiable y ventana estrecha.

---

### H-vivo-6 · El `activity_log` de trazabilidad etiqueta todos los check-ins como `mode: "ejecucion"`
- **Rol / pantalla**: coordinador · `/results` (bitácora de actividad)
- **Severidad**: baja
- **Tipo**: dato
- **Evidencia**: `backend/app/services/results.py::build_traceability_report`,
  bucle de `activity_log`: las entradas de tipo `checkin` fijan
  `"mode": "ejecucion"` literalmente, sin mirar el estado en que se creó el
  check-in (las de `evaluacion` y `respuesta_estudiante` sí usan `record.mode` /
  `response.mode`). Combinado con que `StationCheckIn` no tiene `mode`, los
  check-ins de pilotaje aparecen en la bitácora como si fueran de ejecución.
- **Reproducción**: pilotar una estación y abrir la bitácora de `/results`.
- **Esperado vs. observado**: esperado — un ingreso de pilotaje se distingue en
  la bitácora. Observado — se muestra como `ejecucion`.
- **Notas del auditor**: mismo origen que H-vivo-1; se resuelve junto con el
  marcado de `mode` en check-ins.

---

### H-vivo-7 · `LiveTimerManager` es un singleton en memoria: sin difusión entre procesos si el backend escala a >1 worker
- **Rol / pantalla**: infra · panel en vivo
- **Severidad**: baja (latente; no aplica al despliegue actual)
- **Tipo**: rendimiento · arquitectura
- **Evidencia**: `backend/app/services/websocket.py` — `live_timer` es una
  instancia de módulo. `backend/Dockerfile` arranca `uvicorn app.main:app` sin
  `--workers`, así que hoy hay un solo proceso y funciona. Si en algún momento
  se agrega `--workers N`, `gunicorn -w`, o réplicas, un `/live/control`
  atendido por el worker A sólo hace broadcast a los clientes WS conectados a A;
  los demás paneles quedan desincronizados hasta su resync REST periódico.
- **Reproducción**: n/a en esta sesión (no se levantan servidores).
- **Esperado vs. observado**: n/a — nota de diseño para tener presente antes de
  escalar horizontalmente. Requeriría un back-plane (Redis pub/sub o similar).

---

### H-vivo-8 · `/live/control` sin gate de etapa y frágil si el evento no existe; controles del timer sin límites ni confirmación de "Iniciar"
- **Rol / pantalla**: coordinador / cronometrador · `/live`
- **Severidad**: baja / cosmético
- **Tipo**: bug menor · fricción-UX
- **Evidencia**: `backend/app/api/routes/operational.py::control_timer`.
  (a) Si no hay `LiveSession`, hace `ecoe_event = db.get(ECOEEvent, id)` y usa
  `ecoe_event.station_time_minutes` sin comprobar `None` → 500 con un id
  inválido. (b) No exige que el ECOE esté en `en_ejecucion` para operar el
  cronómetro (aceptable, pero permite "correr" el timer en `publicado` /
  pilotaje). (c) `action == "next_transition"` incrementa
  `current_station_index` sin tope contra el número real de estaciones;
  `action == "start"` resetea `remaining_seconds` al total y no tiene diálogo de
  confirmación en el frontend (`/live/page.tsx` sólo confirma `reset`), así que
  un click accidental en "Iniciar" a mitad de estación reinicia el reloj para
  todos los paneles.
- **Reproducción**: en `/live`, pulsar "Iniciar" con una estación en curso.
- **Esperado vs. observado**: esperado — "Iniciar" a mitad de rotación debería
  pedir confirmación como "Reiniciar". Observado — reinicia el reloj sin
  preguntar.
- **Notas del auditor**: guardas menores; agrupar (b)+(c) es opcional, (a) es un
  `if not ecoe_event: raise 404`.

---

## Notas sueltas (sin hallazgo formal)

- **Gating por rol GLOBAL vs rol de EVENTO en el frontend** (patrón que la
  orquestación pidió vigilar): el `Sidebar` (`components/sidebar.tsx`) y
  `AppShell` usan `eventRoles` (rol por evento), no `user.role`, así que la
  visibilidad de "Panel en vivo" / "Pilotaje" / "Publicación" es correcta. Las
  páginas `/live`, `/pilotage`, `/publication` **no tienen guarda de rol propia**
  (renderizan y dependen del 403 del backend en cada llamada API) — consistente
  con "el backend es la autoridad", no es el bug global-vs-evento. `middleware.ts`
  sólo gatea `/users`. No se encontró el antipatrón de "chequear `user.role` en
  vez de `eventRoles`" en estas tres pantallas.
- **Pérdida de respuesta del kiosko en el borde exacto**: si el auto-envío del
  kiosko llega tras `deadline + 30s` de gracia (reloj de la tablet atrasado), el
  servidor responde 400 y las respuestas del alumno quedan sólo en el
  `localStorage` de esa tablet (draft por `draftKey`). Recuperable manualmente
  desde el dispositivo vía contingencia, pero frágil. Baja probabilidad.
- **`IncidentCreate.severity`** no valida el valor contra un enum; una request
  a mano puede grabar cualquier string. Cosmético.
