# Operación del día del examen (checklist)

Guía operativa para correr un ECOE real con esta plataforma servida desde
`ecoe.drnotus.cl` (Mac mini + nginx + Cloudflare/DNS). Imprimir y marcar.

## T-7 días

- [ ] ECOE en estado `publicado` con la pantalla **Validación** completamente en verde.
- [ ] Pilotaje realizado con las interfaces reales y **hallazgos registrados** en la pantalla Pilotaje.
- [ ] Estudiantes cargados y activos; números ECOE impresos/comunicados.
- [ ] Evaluadores creados como usuarios, asignados a su estación (una principal por persona) y con credenciales probadas por ellos mismos.
- [ ] Estaciones con formulario: puntajes y claves de respuesta definidos en el Constructor (lo que no tenga puntos NO suma a resultados).
- [ ] Prueba de red EN EL RECINTO: abrir `https://ecoe.drnotus.cl` desde el wifi real, correr una estación de prueba completa.
- [ ] Plan B de conectividad definido (hotspot 4G con los kioscos y el panel apuntando por ahí).
- [ ] **Congelamiento**: desde que el ECOE está `publicado` la plataforma bloquea estaciones, formularios, multimedia, tiempos, y borrar/renumerar estudiantes. Para cambiar algo hay que **despublicar**, corregir y volver a publicar.

## T-1 día

- [ ] `docker compose ps` en el servidor: todo `healthy`.
- [ ] Backup manual además del automático (la carpeta `backups/` es de root, por eso se escribe a través del contenedor de respaldos): `docker exec ecoe-db pg_dump -U ecoe ecoe | gzip | docker exec -i ecoe-db-backup sh -c "cat > /backups/pre-examen-$(date +%Y%m%d).sql.gz"`
- [ ] Ensayar la restauración del respaldo más reciente sin tocar producción: `./scripts/verify_backup.sh` (debe listar eventos, estudiantes y la versión de migración).
- [ ] PDF de contingencia impreso por estación (Resultados → Export PDF por estación): pautas en papel por si todo falla.
- [ ] Tablets de estación cargadas, con el navegador probado y bloqueo de pantalla desactivado.
- [ ] Definir quién es el **coordinador de contingencia** del día (usuario con rol coordinador): es la única persona que puede registrar envíos fuera de ventana.

## Día D — montaje (60–90 min antes)

- [ ] Panel en vivo abierto en el puesto de coordinación; **badge "Conectado"** en verde.
- [ ] **Vista proyector** activada en la pantalla del recinto (botón 🖥 en el panel en vivo).
- [ ] Por cada estación con formulario: en **Kioscos** (o Estaciones → Modo kiosco), generar el enlace y abrirlo en la tablet de ESA estación (el enlace es de un solo uso visible; si se pierde, generar otro — invalida el anterior). Verificar que cada tablet quede en "Esperando al siguiente estudiante" con el nombre de estación correcto.
- [ ] Cada evaluador logueado en su dispositivo, en la pantalla Evaluador, viendo su estación asignada.
- [ ] En el Panel en vivo, **«Estaciones en vivo» → Verificación previa: todo listo** (cada evaluador y cada tablet con señal). No iniciar con pendientes sin que el director lo decida.
- [ ] Estaciones **sin evaluador** (sólo formulario): definir quién de coordinación confirma el ingreso de cada estudiante en cada rotación.
- [ ] Transicionar el ECOE a **"Iniciar ejecución"** (los envíos SOLO se aceptan en ejecución o pilotaje — en `publicado` la plataforma los rechaza a propósito).

## Durante el examen

- **El cronómetro del panel en vivo es el reloj de todo el circuito** (OPT-20 F2). La ventana de envío de cada estación es *el fin de la fase actual del panel*, no "hora de check-in + tiempo de estación". Consecuencias operativas:
  - **El que entra tarde a una estación tiene menos tiempo**: su deadline es el de la rotación en curso, no un cronómetro propio que arranca al confirmarlo.
  - **Pausar CONGELA la ventana para todos**: mientras el panel está en pausa no se vence ninguna estación y los kioscos no autoenvían. Al **Reanudar**, la ventana sigue desde donde quedó. Ya no hace falta correr a registrar por contingencia a cada estudiante tras una pausa.
  - El que **entra después de reanudar** hereda el tiempo que reste de esa fase (menos tiempo), no la fase completa.
- Rotación normal: el evaluador confirma por número ECOE → evalúa → el sistema se limpia para el siguiente. Se puede confirmar al estudiante **durante la transición**: su tiempo es el de la fase de estación que viene.
- **Número mal tipeado**: si el estudiante figura en otra estación en la misma rotación, o es de otro circuito, la plataforma avisa antes de confirmar. Si igual se confirmó al equivocado, usar **«No es este estudiante: anular ingreso»** (sólo mientras no haya evaluación ni respuesta). El evaluador tiene hasta el **fin de la fase de transición** para terminar de registrar (el semáforo pasa a ámbar/rojo).
- Kioscos: no requieren intervención; muestran al estudiante confirmado. El servidor autoenvía las respuestas al vencer la fase aunque la tablet esté bloqueada o sin conexión: lo que el estudiante alcanzó a escribir queda guardado en el servidor de forma continua. Una estación sin ninguna respuesta queda marcada como **"sin respuesta"** (suma 0, pero se distingue de un 0 real en la trazabilidad).
- **Buzzer / cortar una fase antes de tiempo**: la acción `expire_phase` del panel en vivo cierra las ventanas de esa fase y dispara el autoenvío **sin** avanzar el número de estación. Útil cuando una fase debe cerrarse ya pero la rotación aún no avanza.
- Incidencia que detiene el circuito: **Pausar** en el panel en vivo + registrar la incidencia. La pausa ya congela las ventanas (ver arriba); solo quedan para contingencia los casos de papel (caída de red) o un envío que se venció **antes** de alcanzar a pausar.
- Caída de red en una estación: seguir en papel (PDF de contingencia); transcribir después en la pantalla **Contingencia**, ANTES de cerrar el ECOE. Contingencia reemplaza la respuesta que el servidor autoenvió en blanco y permite **rectificar** una evaluación mal enviada (exige motivo; queda auditado).
- **Respaldo durante el examen**: mientras el ECOE está en ejecución el servidor guarda un volcado cada 5 minutos en `backups/live/` (se conservan los 36 más recientes). Ante una falla grave se restaura el último con `scripts/restore_db.sh`.
- Si el panel en vivo muestra "Reconectando" en rojo por más de un minuto: revisar red del puesto de coordinación; el cronómetro del servidor sigue corriendo y se resincroniza solo al volver.

## Cierre

- [ ] Verificar en **Corrección** que no queden respuestas pendientes de corrección manual (lo pendiente NO suma a resultados).
- [ ] Verificar en **Resultados** la trazabilidad: estudiantes "completos" vs "parciales" según su circuito; resolver faltantes por contingencia si corresponde.
- [ ] Transcribir todo el papel de contingencia ANTES de cerrar.
- [ ] Transicionar a **"Cerrar ECOE"**: consolida resultados y congela todos los envíos. Si hay estudiantes con estaciones sin registro, **el cierre se detiene y los lista**: resolverlos por Contingencia, suspender a los ausentes, o que el director fuerce el cierre (cada estación faltante cuenta 0).
- [ ] Si después del cierre aparece algo sin ingresar: la administración del ECOE puede **«Reabrir ejecución»** (exige motivo, queda auditado, invalida el acta hasta volver a cerrar). Un ECOE **archivado** ya no se reabre.
- [ ] Exportar Excel consolidado y respaldarlo fuera del servidor.
- [ ] Backup post-examen: mismo comando del T-1.

## Contactos y accesos del día

| Rol | Persona | Usuario |
|---|---|---|
| Admin global | ________ | ________ |
| Coordinador de contingencia | ________ | ________ |
| Cronometrador | ________ | ________ |
| Soporte técnico servidor | ________ | ________ |
