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

## T-1 día

- [ ] `docker compose ps` en el servidor: todo `healthy`.
- [ ] Backup manual además del automático: `docker exec ecoe-db pg_dump -U ecoe ecoe | gzip > backups/pre-examen-$(date +%Y%m%d).sql.gz`
- [ ] PDF de contingencia impreso por estación (Resultados → Export PDF por estación): pautas en papel por si todo falla.
- [ ] Tablets de estación cargadas, con el navegador probado y bloqueo de pantalla desactivado.
- [ ] Definir quién es el **coordinador de contingencia** del día (usuario con rol coordinador): es la única persona que puede registrar envíos fuera de ventana.

## Día D — montaje (60–90 min antes)

- [ ] Panel en vivo abierto en el puesto de coordinación; **badge "Conectado"** en verde.
- [ ] **Vista proyector** activada en la pantalla del recinto (botón 🖥 en el panel en vivo).
- [ ] Por cada estación con formulario: en **Estaciones → Modo kiosco**, generar el enlace y abrirlo en la tablet de ESA estación (el enlace es de un solo uso visible; si se pierde, generar otro — invalida el anterior). Verificar que cada tablet quede en "Esperando al siguiente estudiante" con el nombre de estación correcto.
- [ ] Cada evaluador logueado en su dispositivo, en la pantalla Evaluador, viendo su estación asignada.
- [ ] Transicionar el ECOE a **"Iniciar ejecución"** (los envíos SOLO se aceptan en ejecución o pilotaje — en `publicado` la plataforma los rechaza a propósito).

## Durante el examen

- Rotación normal: el evaluador confirma por número ECOE → evalúa → el sistema se limpia para el siguiente. El evaluador tiene **tiempo de estación + transición** para terminar de registrar (el semáforo pasa a ámbar/rojo).
- Kioscos: no requieren intervención; muestran al estudiante confirmado y se autoenvían al expirar el tiempo.
- Incidencia que detiene el circuito: **Pausar** en el panel en vivo + registrar la incidencia. OJO: la pausa NO extiende las ventanas de envío de la rotación en curso — si a alguien se le venció la ventana por la pausa, el coordinador registra ese caso por **contingencia** (queda auditado y marcado).
- Caída de red en una estación: seguir en papel (PDF de contingencia); transcribir después por contingencia, ANTES de cerrar el ECOE.
- Si el panel en vivo muestra "Reconectando" en rojo por más de un minuto: revisar red del puesto de coordinación; el cronómetro del servidor sigue corriendo y se resincroniza solo al volver.

## Cierre

- [ ] Verificar en **Corrección** que no queden respuestas pendientes de corrección manual (lo pendiente NO suma a resultados).
- [ ] Verificar en **Resultados** la trazabilidad: estudiantes "completos" vs "parciales" según su circuito; resolver faltantes por contingencia si corresponde.
- [ ] Transcribir todo el papel de contingencia ANTES de cerrar.
- [ ] Transicionar a **"Cerrar ECOE"**: consolida resultados y congela todos los envíos (después de esto no entra nada más).
- [ ] Exportar Excel consolidado y respaldarlo fuera del servidor.
- [ ] Backup post-examen: mismo comando del T-1.

## Contactos y accesos del día

| Rol | Persona | Usuario |
|---|---|---|
| Admin global | ________ | ________ |
| Coordinador de contingencia | ________ | ________ |
| Cronometrador | ________ | ________ |
| Soporte técnico servidor | ________ | ________ |
