# Base del Producto y Roadmap

Documento maestro de referencia para el proyecto `ECOE Digital`.

> Revisado el 2026-10-09. Las secciones 1 a 3 conservan la visión original. Desde la 4 se describe el estado real y se contrasta esa visión con las decisiones tomadas en octubre de 2026.

Su objetivo es reemplazar la dispersion de documentos fundacionales y dejar una sola base clara para:

- vision del producto
- arquitectura objetivo
- prioridad actual
- brecha entre la vision y el sistema real
- roadmap de avance

## 1. Vision del producto

`ECOE Digital` es una plataforma para disenar, pilotear, ejecutar, monitorear y cerrar ECOE/OSCE en carreras de la salud.

La vision original del producto contempla una arquitectura hibrida con tres piezas:

- `Studio`
  - nucleo web de autoria, gestion, publicacion, consolidacion y analisis
- `Runner`
  - nucleo local para pilotaje y ejecucion en red local, independiente de internet
- `Sync`
  - capa de intercambio entre Studio y Runner mediante paquetes, importacion y exportacion

## 2. Problema que resuelve

El producto busca reemplazar:

- pautas impresas
- cronometraje manual
- consolidacion tardia
- dispersion de informacion
- baja trazabilidad
- fragilidad operativa durante ECOE

## 3. Principios rectores

- el diseno del ECOE ocurre en entorno web
- la ejecucion debe poder operar con alta confiabilidad local
- la confiabilidad operacional prima sobre adornos
- debe existir separacion estricta entre borrador, pilotaje y ejecucion real
- la experiencia debe ser clara en notebook y tablet
- el sistema debe poder escalar a varias instituciones

## 4. Prioridad real actual

La prioridad sigue siendo la que se fijó al comienzo: **dejar muy sólido el núcleo antes de construir más arquitectura**. En palabras del propietario (2026-10-09): todo depende de que el núcleo funcione sin errores ni pérdida de datos, con flujos probados de punta a punta.

Lo inmediato:

1. Pruebas del propietario y su equipo sobre el núcleo (`plan_pruebas_flujo.md`).
2. Lo que el día del examen aún se organiza fuera de la plataforma: plan de rotación, reparto de estudiantes por circuito, estaciones sin evaluador.
3. Convertir la instancia demo en un molde para dar de alta instituciones.

Detalle y orden: `../NEXT_STEPS.md`.

## 5. Estado actual del sistema

Existe una plataforma unificada, en producción (`app.ecoe.cl`) y con una instancia de demostración (`demo.ecoe.cl`), que cubre el ciclo completo. No ha corrido todavía un examen real con estudiantes.

### Implementado

- **Cuentas y roles**: globales y por evento, invitación por correo, suspensión con revocación de sesiones.
- **Ciclo del ECOE** con máquina de estados en el servidor y candados: la estructura se congela al publicar; nada cambia tras el cierre salvo una reapertura explícita y auditada.
- **Estudiantes y equipo**: carga manual e importación, numeración, deduplicación, suspensión; evaluadores con estación principal, correctores con varias.
- **Constructor de estaciones**: estructura pedagógica, pautas, formulario del estudiante con autocorrección, multimedia por audiencia, paciente simulado, banco reutilizable.
- **Circuitos espejo**: se diseña un circuito y se genera su copia idéntica; análisis por estación de diseño.
- **Validación y pilotaje** con registros aislados de la ejecución real y análisis del ensayo.
- **Día del examen**: cronómetro central con autoridad en el servidor (manual o circuito automático por rondas), timbre, tablero de estaciones con verificación previa, incidencias, kiosco por estación, pantalla de evaluador con check-in y avisos de identidad.
- **Resguardo de datos**: borradores en el servidor, autoenvío al vencer la fase, envíos idempotentes, un solo ingreso activo garantizado por la base, respaldo cada 5 minutos durante un examen y restauración ensayada.
- **Contingencia**: transcripción del papel y rectificación con auditoría.
- **Cierre y resultados**: corrección diferida, cierre que exige completitud, acta congelada con versiones, trazabilidad, análisis psicométrico, exportación.

### Operativo pero parcial

- **Plan de rotación**: la plataforma calcula rondas, pero no genera quién parte en qué estación.
- **Estaciones sin evaluador**: requieren que coordinación confirme a cada estudiante.
- **Multimedia avanzada**: controles de reproducción y momento de exhibición.
- **Evaluación diferida de entregables** (procedimientos grabados, documentos): sólo diseñada.
- **Operación institucional**: sin SSO ni MFA, sin separación entre operador central y administrador de institución, un solo servidor para producción, demo y pruebas.

## 6. Brecha respecto de la visión original

La visión describe tres piezas: `Studio` (autoría y análisis en la web), `Runner` (ejecución local, independiente de internet) y `Sync` (intercambio entre ambos).

- **`Studio`** está cubierto por la plataforma actual.
- **`Runner` y `Sync` no existen**: no hay ejecución local sin internet, ni paquetes de exportación e importación, ni manifiesto versionado, firma o licencia offline.

Hoy **el examen depende de internet en el recinto y del servidor**. Lo que se hizo para reducir ese riesgo no reemplaza a un `Runner`, lo mitiga:

- el reloj y los plazos viven en el servidor, no en cada navegador;
- lo que el estudiante y el evaluador escriben se guarda en el servidor mientras lo escriben;
- una tablet que se cae no pierde lo ya guardado, y el envío se cierra solo al terminar la fase;
- la contingencia permite seguir en papel y transcribir después;
- respaldo frecuente durante el examen.

Un corte de internet prolongado en el recinto sigue obligando a operar en papel.

## 7. Decisión abierta: `Runner` o instancias en línea

En octubre de 2026 el propietario definió el camino multiinstitucional: **un mismo núcleo con una base de datos independiente por institución**, cada una en su subdominio, con cuentas locales y cambios del núcleo que llegan a todas (plan en `../docs/optimizacion/PLANES/SAAS__multiinstitucional.md`; `demo.ecoe.cl` es la primera instancia de ese tipo).

Ese camino es **en línea**. No contradice la visión, pero tampoco avanza hacia el `Runner`. Queda por decidir cuál de estas dos direcciones se toma para la resiliencia del día del examen:

| Opción | Qué implica | Cuándo conviene |
|---|---|---|
| Mantener todo en línea | Exigir en cada recinto red probada y un respaldo (por ejemplo 4G), más el papel como último recurso | Si las instituciones tienen conectividad confiable; es lo más simple de operar y mantener |
| Instancia local en el recinto | Llevar la misma imagen a un equipo dentro de la red del recinto para el día del examen y sincronizar después. Es el `Runner` de la visión, y exige resolver el `Sync` | Si hay recintos sin internet confiable o instituciones que lo pidan como requisito |

Mientras no se decida, no se construye nada del `Runner`. Lo ya hecho (misma imagen para toda instancia, base independiente, respaldo y restauración por instancia) sirve a ambas opciones.

## 8. Diagnóstico actual

- **Núcleo funcional**: completo para el ciclo de un ECOE, incluido el caso en espejo. La auditoría de proceso de octubre encontró y corrigió fallas que habrían afectado un examen real (pérdida de la estación al confirmar durante la transición, clave de respuestas expuesta, errores de identidad sin vuelta atrás).
- **Evidencia**: pruebas automáticas amplias y un flujo de punta a punta, pero **ningún examen real** todavía. La confianza final sólo la dan las pruebas con personas, dispositivos y la red del recinto.
- **Producto comercial**: falta la operación institucional (aislamiento por institución en serie, soporte, protección de datos, staging).

## 9. Estrategia

1. **Consolidación** — en curso. Termina cuando el plan de pruebas se complete sin hallazgos críticos y se haya corrido un ECOE real o un ensayo general equivalente.
2. **Operación por institución** — convertir el demo en molde: alta de una institución como una instancia más, con su respaldo y su marca.
3. **Endurecimiento institucional** — auditoría de accesos, soporte con sesión temporal, protección de datos (Ley 21.719 desde 2026-12-01), staging separado.
4. **Resiliencia del recinto** — según la decisión de la sección 7.

El roadmap por sprints que tenía este documento quedó superado: lo que proponía (constructor, validaciones, pilotaje, panel en vivo, contingencia, resultados y trazabilidad) está hecho. El trabajo vigente se lleva en `../NEXT_STEPS.md` y `../docs/optimizacion/BACKLOG.md`.

## 10. Regla de decisión

Mientras las pruebas sigan mostrando fricciones o riesgos en la construcción y la operación de un examen, el esfuerzo principal va ahí. Arquitectura nueva (varias instituciones en un solo proceso, `Runner`) sólo cuando el núcleo esté probado con personas.

## 11. Conclusión

La dirección se mantiene: consolidar lo que existe, probarlo con el equipo y recién entonces ampliar. Lo que cambió respecto de la visión original es que la ampliación más cercana ya no es el `Runner`, sino atender a varias instituciones con el mismo núcleo; el `Runner` queda como una decisión abierta, no descartada.
