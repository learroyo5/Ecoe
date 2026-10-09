# Plan — ECOE multiinstitucional (SaaS)

Fecha: 2026-10-09. Estado: **propuesto, pendiente de aprobación del usuario**. Nada implementado.

Origen: `docs/AUDITORIA_SAAS_MULTIINSTITUCIONAL_ECOE.md` (auditoría estática de Codex sobre la revisión `f11bb8d`). Este documento la contrasta con `main` actual (`0687a6a`, posterior a las correcciones PROC desplegadas el 2026-10-09) y la convierte en un plan ejecutable.

---

## 1. Veredicto sobre la auditoría

La auditoría es sólida y su recomendación central se sostiene: **aplicación compartida + una base PostgreSQL por institución**, sin reescribir el producto. El código la respalda: casi todo el dominio recibe una `Session` desde el llamador, así que el esquema académico puede vivir íntegro en cada base sin agregar `tenant_id` a las tablas.

Tres límites de la auditoría que conviene tener presentes:

- **No ejecutó nada.** Sus hallazgos de concurrencia (H03, H05) son deducidos del código, no reproducidos. Siguen siendo plausibles: no hay bloqueo ni índice único que los impida.
- **Es anterior a las correcciones PROC.** Un hallazgo quedó resuelto y varios cambiaron de forma (sección 2).
- **No vio la operación real.** Esta sesión sí confirmó parte de ella: el respaldo diario y la copia externa cifrada están corriendo; el servidor es único y también aloja otros proyectos.

## 2. Hallazgos contrastados con el código actual

| ID | Hallazgo | Estado hoy | Evidencia actual |
|---|---|---|---|
| H01 | No hay frontera institucional | **Vigente** | `db/session.py:10–11`: un `engine` y un `SessionLocal` globales; el JWT no lleva institución. |
| H02 | WebSocket y tickers indexados sólo por evento | **Vigente** | `services/websocket.py:30–31` (`dict[int, …]`) y `SessionLocal` global en el ticker y en el handshake (`operational.py:106`). |
| H03 | Check-in sin exclusión concurrente | **Vigente** (no reproducido) | `confirm_station_checkin` sigue sin `FOR UPDATE` ni índice único parcial. PROC-3 agregó reglas (otra estación, anulación) pero no serialización: dos confirmaciones simultáneas aún pueden dejar dos `confirmado`. |
| H04 | Consolidación manual tras el cierre | **Resuelto en lo principal** | `POST /results/{id}/consolidate` responde 409 con el evento cerrado (PROC-23). Queda una parte: la reapertura **borra** el acta en vez de versionarla (ver 3.b). |
| H05 | Reintentos y concurrencia de envíos/borradores | **Vigente** | `student/submit` y `kiosk/submit` hacen leer-luego-insertar sin capturar `IntegrityError` (500 en un choque); los borradores no tienen versión. |
| H06 | Sin separación operador central / admin institucional | **Vigente** | `admin_global` sigue siendo bypass universal dentro de la única base. |
| H07 | Almacenamiento sin namespace institucional | **Vigente** | Rutas absolutas en `MediaAsset.file_path`; `store_contingency_export` sigue sin usos (código muerto: eliminarlo). |
| H08 | Sockets sobreviven a la revocación | **Vigente** | El handshake autentica una vez; el bucle (`operational.py:147–149`) no revalida. |
| H09 | Respaldo/restauración no institucional ni ensayado | **Parcial** | Respaldo diario y copia externa cifrada **funcionan** (verificado en `offsite_cron.log`). Sigue faltando: multimedia en el respaldo, restauración ensayada, frecuencia mayor el día del examen. |
| H10 | Migraciones en el arranque, URL global | **Vigente** | Así se aplicaron las tres migraciones del 2026-10-09. Funciona con una base; no con varias. |
| H11 | Escalado horizontal | **Vigente, no urgente** | Un proceso backend; no se necesita broker mientras siga así. |
| H12 | Sin configuración ni alta institucional | **Vigente** | Configuración única por proceso (`core/config.py`). |
| H13 | Auditoría y ciclo de vida de datos | **Vigente y algo agravado** | PROC-14 agregó rastro de cambios de estructura, pero `delete_student` guarda nombre y RUT en el payload (ver 3.a). |
| H14 | Secretos y confianza en proxies | **Vigente** | El frontend recibe todo `backend/.env` (`docker-compose.yml:105`); `--forwarded-allow-ips "*"` en el Dockerfile. |
| H15 | `localStorage` sin institución ni usuario | **Vigente** | Claves `ecoe-event-id`, `kiosk-draft-<checkin_id>`, token de kiosco fijo. |
| H16 | Uploads leídos completos en memoria | **Vigente** | `operational.py:390`: `await file.read()` antes de validar tamaño. |
| H17 | Sin pruebas multiinstitucionales ni e2e en CI | **Vigente** | CI corre pytest sobre PostgreSQL y vitest/lint/build; no Playwright. |
| H18 | SSO, portabilidad, catálogo central | **Vigente, P3** | Sin cambios. |

## 3. Lo que agrego a la auditoría

a. **Mis propios registros de auditoría chocan con H13.** `audit_change` en `delete_student` guarda RUT y nombre. Hay que decidir si el rastro guarda identificadores o sólo el id interno y el número ECOE.

b. **La reapertura no conserva el acta anterior.** PROC-7 borra `ecoe_results`/`station_results` al reabrir. La auditoría recomienda versionar. Para un producto comercial, el acta reemplazada debe quedar guardada.

c. **El cierre forzado, los candados por estado y la contingencia** (PROC-2/5/6) responden parte de la fila "Evidencia académica" de la sección 13 de la auditoría: ya existe una política implementada de cuándo la nota es definitiva y cómo se rectifica.

d. **Un solo servidor para todo.** Producción, el entorno "de staging" (`ecoe.drnotus.cl`) y las pruebas comparten máquina, contenedores y base. `ecoe.drnotus.cl` y `app.ecoe.cl` son el mismo backend. Antes de una segunda institución real hace falta al menos un entorno de pruebas separado.

e. **El evento demo vive en la base de producción** (un evento, 10 estudiantes de prueba). Antes del primer cliente hay que decidir si esa base pasa a ser "la institución demo" o se vacía.

## 4. Decisiones que bloquean el diseño

La auditoría lista diez. Sólo cinco bloquean empezar; propongo un valor por defecto para cada una.

| # | Decisión | Propuesta | Qué condiciona |
|---|---|---|---|
| D1 | Cómo entra cada institución | **Un subdominio por institución** (`uchile.ecoe.cl`), verificado por Dr. Notus. Dominio propio del cliente, más adelante. | Resolución de institución, cookies, `localStorage`, enlaces de invitación. |
| D2 | Identidad de las personas | **Cuentas locales por institución.** La misma persona en dos instituciones tiene dos cuentas independientes. | JWT, login, invitaciones. Evita un directorio central de personas. |
| D3 | Dónde corre | **Seguir en el servidor actual para el piloto**, con un segundo entorno (staging) separado; migrar a infraestructura con IP fija antes de vender. | Fase 4 y el riesgo PROC-21. |
| D4 | Pérdida máxima tolerable el día del examen | **5 minutos** (respaldo incremental cada 5 min mientras hay un ECOE en ejecución). | Estrategia de respaldo (WAL/PITR vs. dumps frecuentes). |
| D5 | Acceso de soporte de Dr. Notus a datos de una institución | **Ninguno por defecto**; concesión temporal, con motivo, aprobada por la institución y auditada. | Plano de control y roles. |

Las otras cinco (volumen esperado, datos clínicos reales en multimedia, autonomía de configuración, modalidad dedicada/on-premise, responsables de operación) pueden responderse durante la Fase 1 sin frenar la Fase 0.

## 5. Plan por fases

Convención de esfuerzo del backlog: XS < ½ día · S ~1 día · M 2–4 días · L 1–2 semanas · XL > 2 semanas. Cada fase termina con tests (negativos incluidos) en PostgreSQL y no se despliega sin aprobación.

### Fase 0 — Integridad con una sola institución (no depende de ninguna decisión)

Objetivo: cerrar lo que es un riesgo hoy, antes de multiplicarlo por N instituciones. Esfuerzo total: **M–L**.

| Tarea | Detalle | Archivos | Esfuerzo |
|---|---|---|---|
| F0.1 Check-in concurrente (H03) | Reproducir con dos transacciones reales en PostgreSQL. Serializar con `SELECT … FOR UPDATE` sobre la estación y agregar índice único parcial `(station_id) WHERE status='confirmado'` y `(ecoe_event_id, student_id) WHERE status='confirmado'` tras limpiar duplicados existentes. | `routes/evaluator.py`, migración | M · migración |
| F0.2 Envíos idempotentes (H05) | Un reintento de un envío ya guardado responde 200 con el registro existente en vez de 400/500; capturar `IntegrityError` en `student/submit`, `kiosk/submit`, `evaluator/submit` y contingencia. Versión monotónica en borradores para que uno tardío no pise a uno nuevo. | `routes/student_access.py`, `kiosk.py`, `evaluator.py`, `services/drafts.py` | M · migración (versión de borrador) |
| F0.3 Acta versionada (3.b, resto de H04) | Al reabrir, el acta anterior se archiva (tabla de versiones) en vez de borrarse; Resultados indica versión y fecha. | `services/validation.py`, `results.py`, migración | M · migración |
| F0.4 Sockets y revocación (H08) | Revalidar sesión y permisos cada N segundos en el WebSocket y cerrarlo si la cuenta fue suspendida o el token expiró. | `routes/operational.py`, `services/websocket.py` | S |
| F0.5 Mínimo privilegio (H14) | El frontend recibe sólo las variables que usa; `--forwarded-allow-ips` acotado a la red del proxy. | `docker-compose.yml`, `backend/Dockerfile` | S |
| F0.6 Uploads (H16) | Límite por streaming antes de leer a memoria; servir SVG y documentos como descarga. | `routes/operational.py`, `services/media.py` | S |
| F0.7 Auditoría sin datos personales de más (3.a, parte de H13) | Los payloads de `AuditLog` guardan ids y número ECOE, no RUT ni nombres; revisar los existentes. | `services/event_lock.py`, rutas | S |
| F0.8 Recuperación demostrada (H09) | Incluir el volumen multimedia en el respaldo automático; ensayar restauración completa (base + archivos) en un entorno aparte y dejar el procedimiento escrito; respaldo cada 5 min con un ECOE en ejecución (D4). | `docker-compose.yml`, `scripts/` | M · infraestructura |
| F0.9 CI | Agregar el flujo Playwright al CI; eliminar `store_contingency_export`. | `.github/workflows/ci.yml` | S |

Criterio de salida: dos confirmaciones simultáneas nunca dejan dos ingresos activos; un reintento nunca devuelve error ni duplica; una cuenta suspendida pierde su socket; restauración completa ensayada y cronometrada.

### Fase 1 — Institución y plano de control mínimo (requiere D1, D2, D5)

Objetivo: fijar el contrato de aislamiento antes de tocar las rutas. Esfuerzo: **L**.

- Base de control separada (`ecoe_control`) con `Institution`, `Domain`, `Deployment` (referencia al secreto de conexión, versión de esquema, estado) y operadores de Dr. Notus. Sin datos académicos.
- `TenantContext` inmutable: se resuelve desde el host contra la lista de dominios verificados; host desconocido o institución suspendida → rechazo, nunca caída a una base por defecto.
- Renombrar la semántica de `admin_global` a "administrador de la institución" en textos y documentación (el código de rol puede conservarse).
- La base actual se registra como primera institución (decidir 3.e: demo o vaciar).

Criterio de salida: matriz de autoridades (central / institucional / evento) aprobada; host desconocido, duplicado o suspendido rechazado con test.

### Fase 2 — Aislamiento efectivo (el corazón del trabajo)

Objetivo: que ningún camino llegue a la base sin contexto institucional. Esfuerzo: **XL**.

- **Sesiones** (H01): registro acotado de engines/pools por institución; `get_db` depende de `TenantContext`. Eliminar todo uso de `SessionLocal` global fuera de ese registro (hoy: handshake WS, ticker, seed, lifespan).
- **Autenticación** (H01): el JWT lleva la institución; cada solicitud exige que coincida con la del host. Login, activación, invitaciones y kiosco resuelven la base por dominio.
- **WebSocket y ticker** (H02): claves `(institución, evento)`; el ticker abre su sesión con el contexto capturado.
- **Archivos** (H07): prefijo opaco por institución y rutas relativas; migración de las rutas absolutas existentes.
- **Navegador** (H15): claves de `localStorage` con institución, usuario y evento; limpieza al cerrar sesión.
- **Migraciones** (H10): migrador explícito fuera del arranque, que recorre las instituciones del registro con bloqueo por base y credencial de DDL separada de la de ejecución.
- **Pruebas A/B**: suite PostgreSQL con dos instituciones que comparten ids y correos; token de A en dominio de B, admin de A contra recursos de B, dos sockets con `event_id=1`, invitación y kiosco de A usados en B.

Criterio de salida: A y B con los mismos ids y correos operan un ECOE simultáneo sin cruzar cuentas, permisos, archivos, reloj ni reportes; la credencial de A no puede conectarse a la base de B.

### Fase 3 — Alta de una institución sin tocar código

Esfuerzo: **L**. Trabajo idempotente que crea base, rol y almacenamiento, migra, inserta roles mínimos (nunca datos demo) y emite la invitación del administrador; suspensión y reactivación; configuración local (nombre, logo, carreras, sedes, parámetros de nota). Reintento tras fallo en cada paso, con test.

### Fase 4 — Operación de la flota

Esfuerzo: **L–XL**, depende de D3. Migración canaria por institución; respaldo y restauración por institución con catálogo; `readiness` por institución además del `health` global; métricas y alertas; entorno de staging separado de producción. Broker de mensajes sólo si se pasa a más de un proceso backend.

### Fase 5 — Dos instituciones ficticias bajo carga

Esfuerzo: **M–L**. Prueba de carga con el tamaño real de un ECOE (pico de envíos al timbre, autoguardado, exportación), con el ticker real activo; restauración de A mientras B rinde.

### Fase 6 — Piloto real

Requiere revisión jurídica (Ley 21.719 entra en vigencia el 2026-12-01), contrato de tratamiento de datos, responsables de operación el día del examen y ensayo en el recinto.

## 6. Qué no haría

- **`tenant_id` en una base compartida.** Obligaría a revisar cada consulta del producto y un filtro olvidado mezcla instituciones.
- **Microservicios, colas o broker ahora.** Con un solo proceso backend no resuelven ningún problema existente.
- **SSO antes del primer cliente que lo pida** (H18).
- **Vender la plataforma como multiinstitucional antes de terminar la Fase 2.** Hoy una segunda institución real compartiría base, usuarios y bancos con la primera.

## 7. Orden recomendado

1. **Fase 0 completa ahora.** No depende de decisiones, mejora el producto para las pruebas que ya vienen y es requisito de todo lo demás.
2. En paralelo, responder D1–D5.
3. Fases 1 y 2 juntas, en una rama larga con la suite A/B creciendo desde el primer día.
4. Fases 3 a 6 según el calendario comercial.

Si aparece un primer cliente antes de terminar la Fase 2, el puente seguro es una **instancia dedicada** (otro Compose, otra base, otro dominio, misma imagen): es operación manual, pero aísla de verdad.
