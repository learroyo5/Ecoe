# Base del Producto y Roadmap

Documento maestro de referencia para el proyecto `ECOE Digital`.

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

La prioridad inmediata del proyecto no es construir ya la arquitectura hibrida completa, sino dejar muy solido el nucleo funcional actual para un `piloto funcional del sistema`.

Decision actual:

- primero consolidar muy bien el sistema operativo actual
- despues separar y endurecer `Runner` como derivacion natural del nucleo ya probado

Esto implica que hoy la prioridad es:

1. constructor de estaciones
2. flujo evaluador
3. flujo estudiante
4. pilotaje
5. live panel
6. resultados
7. validaciones previas
8. multimedia y formularios

## 5. Estado actual del sistema

Hoy existe una plataforma unificada funcional que ya cubre gran parte del `Studio` y parte del runtime.

### Ya implementado con base util

- autenticacion y roles
- gestion de ECOE
- estudiantes:
  - carga manual
  - importacion
  - deduplicacion
  - suspension/reactivacion
  - correlativo ECOE
- evaluadores:
  - carga manual
  - importacion
  - deduplicacion
  - estacion principal asignada
- constructor de estaciones:
  - estructura pedagogica y operativa
  - instrumentos
  - formulario del estudiante
  - multimedia por estacion
  - paciente simulado
- pilotaje
- panel live
- evaluador:
  - check-in por numero ECOE
  - pauta dinamica
  - una sola evaluacion
  - vista optimizada para tablet
- estudiante:
  - verificacion por numero ECOE
  - formulario dinamico
  - multimedia visible
  - reloj
  - autosave y autoenvio
- resultados y exportaciones

### Implementado de forma operativa pero aun parcial

- multimedia avanzada
- validacion previa
- robustez de estados
- contingencia
- trazabilidad
- experiencia de publicacion

## 6. Principal brecha respecto de la vision original

La mayor diferencia con la base fundacional no esta en las pantallas actuales, sino en la arquitectura.

### Lo que aun no existe

- `Runner` separado
- `Sync` separado
- paquete Studio -> Runner
- paquete Runner -> Studio
- manifest versionado
- hash y firma
- licenciamiento offline
- importacion/exportacion formal de publicaciones y resultados

## 7. Diagnostico actual

### Respecto al piloto funcional del sistema actual

Estamos bien encaminados.

El proyecto ya tiene una base suficientemente real para:

- construir estaciones
- asignar evaluadores
- confirmar estudiantes
- ejecutar respuestas y evaluaciones
- usar multimedia
- pilotear flujo operativo

### Respecto al producto hibrido completo

Todavia hay una distancia importante.

La vision completa de `Studio + Runner + Sync` todavia no esta materializada como arquitectura.

## 8. Estrategia recomendada

### Etapa 1: consolidacion del nucleo actual

Objetivo:

- convertir el sistema actual en una plataforma muy estable para piloto real

Focos:

- pulir constructor de estaciones
- cerrar mejor formularios y pautas
- pulir multimedia
- endurecer check-in y runtime
- mejorar pilotaje y live
- mejorar resultados y estados
- validar mejor antes de publicar o ejecutar

### Etapa 2: separacion arquitectonica

Objetivo:

- desprender `Runner` a partir de un nucleo ya funcional y probado

Focos:

- contrato de paquete
- exportador Studio
- importador Runner
- exportador de resultados local
- importador de retorno en Studio

### Etapa 3: endurecimiento institucional

Objetivo:

- llevar el producto hacia una version defendible institucionalmente

Focos:

- versionado
- firma
- hash
- licencia
- auditoria
- trazabilidad

## 9. Roadmap de trabajo sugerido

### Sprint 1

- terminar pulido del constructor de estaciones
- ordenar mejor plantillas, instrumentos y formularios
- cerrar UX multimedia
- fortalecer validaciones previas

### Sprint 2

- endurecer pilotaje
- endurecer panel live
- mejorar estados operativos
- reforzar contingencia y persistencia

### Sprint 3

- mejorar resultados y trazabilidad
- revisar checklist de publicacion interna
- preparar especificacion del paquete Studio -> Runner

### Sprint 4

- primer exportador de paquete
- primer importador local
- esqueleto real de `Runner`

## 10. Regla de decision

Mientras el piloto funcional actual siga mostrando fricciones visibles en construccion y operacion, el esfuerzo principal debe ir ahi.

La arquitectura hibrida completa no se abandona, pero se posterga hasta tener un nucleo operativo realmente pulido y confiable.

## 11. Conclusion

La direccion correcta hoy es esta:

- consolidar el producto que ya existe
- probarlo
- pulirlo
- y luego separar `Runner` sobre una base ya validada

Eso permite avanzar con sentido practico, sin traicionar la vision original del proyecto.
