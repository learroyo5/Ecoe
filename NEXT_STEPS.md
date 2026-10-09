# Next Steps

## Prioridad alta completada (v2)

1. ~~Completar CRUD real de ECOE~~ ✅
   - ~~Formulario completo de datos generales~~ → 3 secciones con validacion frontend
   - ~~Cambio de estado guiado desde UI~~ → StatusTransitionBar con modales de confirmacion
   - ~~Vista de detalle del ECOE activo~~ → `/ecoe/[id]` con 4 tabs

2. ~~Mejorar constructor de estaciones~~ ✅
   - ~~Edicion de estaciones existentes~~ → builder soporta carga y actualizacion completa
   - ~~Formularios por secciones con mejor UX~~ → constructor con 4 pasos guiados
   - ~~Asociacion real de multimedia~~ → upload con preview inline (MediaPreview)
   - ~~Asociacion real de instrumentos y paciente simulado~~ → selectores en el builder

3. ~~Mejorar flujo operativo en vivo~~ ✅
   - ~~Sincronizacion real del cronometro entre clientes~~ → WebSocket con broadcast
   - ~~Mejora de panel de incidencias~~ → creacion, resolucion, reapertura con WebSocket

4. ~~Robustecer evaluacion y respuestas~~ ✅
   - ~~Render dinamico de instrumentos~~ → checklist toggle + puntaje numerico
   - ~~Render dinamico de formularios del estudiante~~ → 3 tipos de pregunta
   - ~~Bloqueo por tiempo de manera efectiva~~ → timer rojo, campos deshabilitados al expirar

5. ~~Persistencia y mantenimiento~~ ✅
   - ~~Agregar migraciones con Alembic~~ → configurado con autogenerate
   - ~~Agregar pruebas backend basicas~~ → 23 tests pasando

---

## Completado en la estabilizacion pre-examen (julio 2026)

- ~~Aislar pilotaje de ejecucion (mode en duplicados y flags)~~ ✅
- ~~Maquina de estados backend + gate de envios por etapa~~ ✅
- ~~Deadlines autoritativos + registro por contingencia~~ ✅
- ~~Cierre que consolida y congela~~ ✅
- ~~Modo kiosco por estacion (tablets compartidas)~~ ✅
- ~~Formularios del estudiante puntuables + pantalla Correccion~~ ✅
- ~~Trazabilidad por circuito (modo espejo)~~ ✅
- ~~Pilotaje con hallazgos~~ ✅
- ~~Modales de confirmacion con resumen, semaforo de tiempo, indicador de borrador~~ ✅
- ~~Reconexion WS con indicador + vista proyector en panel en vivo~~ ✅
- ~~Filtros/buscadores en tablas de estudiantes y staff~~ ✅
- ~~E2E Playwright del flujo dorado + checklist del dia D~~ ✅

## Completado en agosto 2026

- ~~Evaluación diferida Fase 1~~ ✅ — rol `corrector`, capacidad de estación `requires_deferred_grading`, Validación y trazabilidad. Diseño en `docs/architecture/EVALUACION_DIFERIDA_FASE1.md`. Pendiente Fase 2 (ver abajo).
- ~~Unificar el alta de equipo en una sola pantalla (Evaluadores)~~ ✅
  - ~~Alta individual por correo: la cuenta existente manda su nombre, no se retipea~~ ✅
  - ~~Importacion masiva que crea cuentas `pending` con invitacion en vez de descartar filas~~ ✅
  - ~~Enlaces de activacion visibles al terminar el import, para repartirlos a mano~~ ✅
  - ~~Selector de estacion principal solo para el rol evaluador (en el resto no tenia efecto)~~ ✅

## Completado 2026-08-29 — pipeline de optimización + Fase 2 de análisis (desplegado)

Ciclo auditoría → triage → implementación sobre el flujo completo. Detalle en `PROJECT_STATUS.md` (sección "Pipeline de optimización + Fase 2") y `docs/optimizacion/BACKLOG.md`. Todo en `main`, desplegado (migración prod `j0e1f2a3b4c5 → o5p6q7r8s9t0`), CI verde, 394 backend + 78 frontend.

- ~~Resultados inmutables tras el cierre + AuditLog de consolidación~~ ✅
- ~~Aislamiento pilotaje/ejecución completo (`mode` en check-ins, trazabilidad, cola de corrección)~~ ✅
- ~~Gating de UI por rol de evento, no por rol global~~ ✅
- ~~OPT-20: cronómetro sincrónico único, deadline desde `LiveSession`, autoenvío server-side, borrador del evaluador, WebSocket para pantallas operativas, `expire_phase`~~ ✅
- ~~Resultado por estación + nota agregada = promedio de %-por-estación (compensatorio)~~ ✅
- ~~Psicometría (α Cronbach, discriminación, dificultad, punto-biserial) sobre ejecución y pilotaje + advertencias en `pilotaje_validado`~~ ✅ — **cubre "Exportaciones · estadísticas por estación" de Prioridad actual**
- ~~Export Excel multi-hoja con item analysis y metadatos~~ ✅
- ~~CRUD del banco institucional (instrumentos, plantillas, pacientes) + "editar pauta" en el Constructor~~ ✅
- ~~Cola personal del corrector + pauta de referencia + bulk-0 blancos + reasignar correctores~~ ✅ — **cubre parte de "Evaluación diferida Fase 2 · edición de estaciones del corrector"**

**Diferido (requiere cambio de contexto, no urgente):**
- OPT-14 — back-plane Redis para `LiveTimerManager` (solo con >1 worker / escalado horizontal).
- OPT-17b — umbral por estación / estándar conjuntivo (contradice el compensatorio elegido; sería su propio ciclo).

**Pendiente operativo:**
- Pilotar el cambio de deadline de OPT-20 (check-in tardío = menos tiempo, pausa congela para todos) antes de un examen real.
- Limpieza de ~24 ramas `opt/*` / `ops/*` locales ya mergeadas.
- 1 `evaluator_record` con `mode='ejecucion'` en el evento de pilotaje (dato viejo) — decidir si se corrige o se descarta con el resto del pilotaje.

## Completado 2026-08-18 — primera prueba funcional real

- Ensayo general con el equipo:
   - ~~Ensayo general con el equipo usando la app en `en_pilotaje`~~ → hecho: check-in, cronometro y evaluacion/kiosco de punta a punta en las 5 estaciones (1, 3 y 5 con evaluador real; 2 y 4 cubiertas por coordinacion). Pilotaje `circuito_completo` con hallazgos registrados (`pilot_run` id 3).
   - Bugs encontrados y corregidos durante la preparacion y el ensayo (quedaron en commits separados):
     - Editar una estacion publicada en el Constructor regresaba su estado a `incompleta`/`lista_para_pilotaje`, desincronizandola del resto.
     - Editar el timing del ECOE no resincronizaba la `LiveSession`: el cronometro en vivo seguia mostrando los minutos con los que se creo la sesion, no los configurados despues.
     - La pantalla Estaciones no distinguia cuales necesitan Modo kiosco (formulario de estudiante y/o multimedia).
     - `admin_ecoe`/`coordinador_operativo` no tenian forma de hacer check-in en una estacion sin evaluador asignado (pantalla Evaluador acotada a la estacion propia).
   - Invitaciones y reinicio de acceso ahora envian correo real (SMTP configurado); antes el enlace solo se mostraba una vez en pantalla.
   - Retro pendiente: definir evaluador fijo para las estaciones 2 y 4 (hoy las cubre coordinacion), y hacer la prueba de red formal en el recinto real antes del examen.
   - Ya corregido en el mismo ensayo: el reloj del kiosco seguia corriendo tras enviar (ahora se congela), y la pantalla dejaba visible la identidad/respuestas del estudiante anterior para quien llegara despues (ahora se reemplaza por una pantalla neutra hasta que el evaluador confirme al siguiente).

## Completado en octubre 2026 (desplegado)

- Navegación y UX de la intranet (UX-1…7).
- Auditoría del proceso y sus correcciones (PROC-1…24): transición, clave de respuestas, anulación de ingresos, contingencia, candados por estado, cierre con completitud, reapertura, acta con identidad, tablero de estaciones.
- Fase 0 del plan multiinstitucional: ingreso activo único, envíos idempotentes, acta versionada, sockets con revocación, respaldo en vivo y restauración ensayada, e2e en CI.
- Circuitos espejo.
- Instancia `demo.ecoe.cl` y despliegue conjunto (`scripts/deploy.sh`).
- Audio del cronómetro (timbre) y respaldos automatizados, que figuraban como pendientes antiguos.

Estado por hallazgo: `docs/optimizacion/BACKLOG.md`.

## Prioridad actual

1. **Pruebas del usuario sobre el núcleo.** Recorrer de punta a punta, con el ECOE de prueba y el demo: configurar, crear circuito espejo, pilotear con el panel en vivo, ejecutar, contingencia, cerrar, reabrir. Todo depende de que esto funcione sin errores ni pérdida de datos.
   - El ECOE de prueba de producción tiene dos circuitos armados a mano: rehacerlo como espejo antes de publicarlo.

2. **Operación del día del examen que aún no cubre la plataforma**
   - Plan de rotación generado (quién parte en qué estación, por ronda y circuito) — COORD-3.
   - Reparto de estudiantes entre circuitos.
   - Identificación del estudiante en el kiosco para estaciones sin evaluador (PROC-12).

3. **Mínimo privilegio (F0.5)**: el frontend recibe todo `backend/.env` y `--forwarded-allow-ips` está abierto. Requiere revisar las variables reales con el usuario.

4. **Molde de institución**: parametrizar `docker-compose.demo.yml` (nombre, puertos, dominio), respaldo automático por instancia y marca por variable, para dar de alta una institución como una instancia más. Ver `docs/optimizacion/PLANES/SAAS__multiinstitucional.md`.

5. **Antes de un cliente real**: entorno de staging separado de producción, revisión de protección de datos (Ley 21.719 desde 2026-12-01), separación entre operador central y administrador institucional.

## Prioridad media

1. Evaluación diferida Fase 2 (diseño en `docs/architecture/EVALUACION_DIFERIDA_FASE1.md`, sección final)
   - Adjuntar entregables (PDF, foto, audio, video) por estudiante/estación para corregir estaciones sin formulario.
   - Puntuación estructurada contra los ítems de la pauta con comentario por ítem.
   - Edición de las estaciones de un corrector desde la tabla de Equipo (hoy sólo en el alta).
   - Opcional: doble corrección ciega e índice de acuerdo.

2. Pendientes menores de la auditoría de proceso: token de kiosco en la URL (PROC-18), duplicar ECOE comparte pautas con el original (PROC-20), número de orden en el borrador del evaluador.

3. Multimedia: controles avanzados de audio y video; definir si el material se muestra antes, durante o después de la estación.

4. Exportaciones: PDF por estación con formato imprimible (membrete, tabla de puntajes).

5. Pruebas: e2e de pausa, contingencia, corrección manual y circuito espejo; prueba de carga con muchas tablets.

## Prioridad baja

1. Observabilidad: logs estructurados, alertas, `readiness` por instancia.
2. Seguridad: MFA para acciones institucionales, SSO cuando un cliente lo pida.
3. ACL por unidad académica para los bancos compartidos.
4. Un solo proceso para varias instituciones (Fases 1–2 del plan), sólo si el número de instancias lo justifica.

## Comandos utiles

```bash
docker compose up --build -d          # levantar
docker compose ps                     # estado
docker compose logs -f backend        # logs
./scripts/deploy.sh                   # publicar en producción y demo
./scripts/demo_reset.sh               # recargar los ECOE de demo.ecoe.cl
./scripts/verify_backup.sh            # ensayar la restauración del último respaldo
./scripts/run_e2e.sh                  # flujo dorado en un stack desechable
```

Pruebas y migraciones: ver `README.md`.

## Nota para futuras sesiones

```text
Lee README.md, PROJECT_STATUS.md, NEXT_STEPS.md y CLAUDE.md, revisa WORKLOG.md
(última sesión) y continuemos desde la prioridad actual.
```
