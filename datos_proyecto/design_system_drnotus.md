# Design System DRNOTUS / UNEMSA

Actualizado el 2026-10-09 contra `frontend/src/app/globals.css` y los componentes en uso.

## Propósito

Base visual compartida para los productos DRNOTUS. El tema activo en ECOE es `ecoe`; el CSS define además los tokens de marca de `drnotus`, `mna`, `tumor`, `unemsa` y `clinico`.

## Implementación

- Tokens y clases base en [`globals.css`](../frontend/src/app/globals.css), como variables CSS y alias semánticos.
- El tema se activa en [`layout.tsx`](../frontend/src/app/layout.tsx) con `data-system="ecoe"`; cada `[data-system="…"]` redefine `--color-primary`, `--color-primary-hover` y `--color-primary-dark`.
- Tailwind CSS v4 para el resto (utilidades en los componentes).
- Tipografías: Bitter (títulos, `--font-display`) y Source Sans 3 (texto, `--font-body`).

## Tokens

- **Marca**: `--brand-drnotus`, `--brand-ecoe`, `--brand-mna`, `--brand-tumor`, `--brand-unemsa`, `--brand-clinico`.
- **Color semántico**: `--color-primary` (+ `-hover`, `-dark`), fondos `--color-bg-main|soft|card|panel`, bordes `--color-border|-strong`, texto `--color-text-main|secondary|muted|inverse`, estados `--color-success|warning|error|info` y sus variantes `-soft`.
- **Tipografía**: `--font-display`, `--font-body`, escala `--font-size-xs` a `--font-size-3xl`.
- **Espaciado**: `--space-1` a `--space-10`.
- **Bordes y sombras**: `--radius-sm` a `--radius-xl`, `--shadow-soft`, `--shadow-card`, `--shadow-focus`.

## Clases base

| Clase | Uso | Estado |
|---|---|---|
| `.panel-card` | Tarjeta principal de sección | En uso (vía `SectionCard`) |
| `.clinical-panel` | Panel interior dentro de una tarjeta | En uso |
| `.btn-primary`, `.btn-secondary` | Acción principal y secundaria | En uso |
| `.pill`, `.pill-ok`, `.pill-warn` | Etiqueta de estado en mayúsculas | En uso |
| `.status-badge` + `-success|-warning|-error|-info|-muted` | Estado en tablas | En uso |
| `.evaluation-table` | Tabla de pauta del evaluador | En uso |
| `.grid-auto` | Grilla de tarjetas de ancho automático | En uso |
| `.card-subtle`, `.btn-ghost`, `.pill-danger` | — | **Definidas pero sin uso**: retirarlas o empezar a usarlas |

## Componentes

En `frontend/src/components/` (no existe un directorio `ui/`):

- **Estructura**: `AppShell` (encabezado con título de la pantalla y barra «ECOE activo»), `Sidebar` (grupos por fase del ciclo, iconos, ítem activo por prefijo de ruta), `SectionCard`.
- **Datos**: `DataTable` (búsqueda, orden, paginación), `StationBoardPanel` (tablero de estaciones con puntos de estado).
- **Formularios**: `forms.tsx` (`QuickForm`, `FileImport`, `StatusNotice`), `ecoe-form.tsx` (campos del ECOE y barra de estado), `LoadingButton`.
- **Diálogos**: `ConfirmDialog` y `useConfirm()` (`confirm-provider.tsx`) para confirmar de forma imperativa: `if (!(await confirm("…"))) return;`.
- **Avisos**: `StructureLockNotice` (estructura bloqueada por el estado del ECOE), `toast.tsx` (`ErrorState`), `skeleton.tsx`.
- **Media**: `MediaPreview`.

## Patrones vigentes

- **Pestañas**: contenedor `rounded-2xl bg-slate-100 p-1` con botones `role="tab"`; la activa en blanco con sombra. Usado en Datos del ECOE y Resultados.
- **Estados del ECOE**: color por estado en `STATUS_COLORS` (`ecoe-form.tsx`) y texto en `lib/labels.ts`. Nunca mostrar el valor interno (`en_configuracion`).
- **Etiquetas**: todo valor de dominio pasa por `lib/labels.ts` (estado del ECOE, de estación, de sesión, tipo de estación, modo de circuito, rol).
- **Confirmaciones**: siempre el diálogo propio. El `confirm` nativo sólo queda en los avisos de «cambios sin guardar» del Constructor, que interceptan la navegación.
- **Bloqueos**: una acción no disponible se deshabilita y explica el motivo (texto junto al control o `title`), no desaparece sin más.
- **Avisos por severidad**: verde éxito, ámbar advertencia, rojo bloqueo o error, celeste informativo (por ejemplo, «estación espejo»).

## Reglas UX

1. **Color con propósito.** Azul para acciones principales, estructura y navegación; verde sólo confirmación; ámbar sólo advertencia; rojo sólo error, bloqueo o acción destructiva.
2. **Respuesta inmediata.** Todo guardado muestra su resultado; toda acción riesgosa pide confirmación con color semántico.
3. **Lenguaje según el rol.** Docente: construcción y validación. Evaluador: operativo, breve. Estudiante: sólo la instrucción esencial.
4. **Menor carga cognitiva.** Primero lo indispensable; lo demás en pestañas o bloques expandibles.
5. **Una voz.** Tuteo en toda la plataforma («confirma», «revisa»); sin voseo.
6. **Orientación.** Cada pantalla dice dónde está el usuario (título) y sobre qué ECOE trabaja (barra superior); Inicio dice qué sigue.

## Detalle técnico a recordar

`globals.css` define `a { color: inherit }` (y lo mismo para `p`, `span`, `li`…) **fuera de las capas de Tailwind**, así que le gana a las utilidades de color: `text-white` sobre un `<Link>` no surte efecto. Usar el modificador importante (`!text-white`) o poner el color en un contenedor. Así se corrigió el ítem activo de la barra lateral.

## Pendiente

1. Mover los componentes base a `components/ui/` si se van a compartir con otros productos.
2. Retirar las clases sin uso de la tabla anterior.
3. Revisión visual con cada rol y en tablet de las pantallas nuevas (Kioscos, Contingencia, tablero de estaciones, circuitos espejo).
4. Marca por institución (nombre y logo configurables) cuando haya más de una instancia.
