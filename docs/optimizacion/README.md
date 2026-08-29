# Pipeline de optimización por agentes

Objetivo: revisar la app y su flujo completo — acceso por rol → configuración → ejecución en vivo → corrección → análisis final de datos — detectando fricciones y convirtiéndolas en mejoras verificadas.

## Actores

| Agente | Tipo | Rol |
|---|---|---|
| `auditor-admin-ecoe` | auditor | Setup: crear/configurar ECOE, estaciones, instrumentos, staff, publicación |
| `auditor-operacion-vivo` | auditor | Pilotaje→ejecución: timer WS, rotaciones, kiosko, contingencia, incidencias |
| `auditor-roles-usuario` | auditor | Acceso y journey de estudiante, evaluador, corrector, co-editor |
| `auditor-correccion-resultados` | auditor | Grading vivo + diferido, cierre/consolidación, resultados, export/analítica |
| `optimizador` | triage | Evalúa causa · impacto · factibilidad; prioriza; redacta planes |
| `implementador` | ejecución | Ejecuta planes **aprobados**; tests con negativos; commit en rama |
| Claude (sesión principal) | orquestador | Bus de mensajes, mantiene estado, secuencia, verifica, presenta decisiones |

Los subagentes **no se comunican entre sí**. Todo pasa por el orquestador y por los archivos de este directorio.

## Flujo

```
auditoría → hallazgos/ → optimizador (triage) → BACKLOG.md
   → [APROBACIÓN DEL USUARIO] → PLANES/<id>.md → implementador → rama + tests verdes
   → verificación del orquestador → [MERGE/DEPLOY: USUARIO] → nueva auditoría
```

## Decisiones que toma el usuario (gate humano)

1. Prioridad del backlog.
2. Aprobar/rechazar cada plan antes de implementarlo.
3. Cualquier cambio de schema / migraciones / seguridad / permisos / datos.
4. Merge a `main` y deploy al servidor real.
5. Alcance y profundidad de cada pasada de auditoría.

## Modo de auditoría actual: código + API in-process

Los auditores recorren los journeys vía `TestClient`/pytest y leen el frontend para evaluar fricción de UX. **No** conducen navegador (no hay app corriendo en la sesión). Para confirmación visual, el usuario levanta el stack (`docker compose up` / `./scripts/run_e2e.sh`).

## Convención de hallazgo

Cada auditor escribe un archivo en `docs/optimizacion/hallazgos/<agente>__<AAAA-MM-DD>.md` con una entrada por hallazgo:

```
### H-<agente>-<n> · <título corto>
- **Rol / pantalla**: p. ej. evaluador · /evaluator
- **Severidad**: bloqueante | alta | media | baja | cosmético
- **Tipo**: bug | fricción-UX | inconsistencia backend/UI | permiso | rendimiento | dato
- **Evidencia**: archivo:línea, respuesta HTTP, o test que lo demuestra
- **Reproducción**: pasos mínimos (endpoint + payload, o clics)
- **Esperado vs. observado**:
- **Notas del auditor**: hipótesis de causa (no vinculante)
```

El `optimizador` consume estos archivos, no los edita; vuelca el triage en `BACKLOG.md`.
