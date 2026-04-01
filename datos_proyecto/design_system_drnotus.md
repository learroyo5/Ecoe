# Design System DRNOTUS / UNEMSA

## Proposito
Base visual compartida para los productos DRNOTUS con una implementacion modular y mantenible. El tema activo actual del proyecto ECOE es `ecoe`, pero el sistema ya deja definidos los tokens principales para otros ecosistemas:

- `drnotus`
- `ecoe`
- `mna`
- `tumor`
- `unemsa`
- `clinico`

## Implementacion actual

Se implemento en [globals.css](/home/learroyo/Proyectos/Ecoe/frontend/src/app/globals.css) usando CSS variables globales y alias semanticos. El tema activo se inyecta desde [layout.tsx](/home/learroyo/Proyectos/Ecoe/frontend/src/app/layout.tsx) con `data-system="ecoe"`.

## Tokens globales

### Sistemas / marca
- `--brand-drnotus`
- `--brand-ecoe`
- `--brand-mna`
- `--brand-tumor`
- `--brand-unemsa`
- `--brand-clinico`

### Semanticos activos
- `--color-primary`
- `--color-primary-hover`
- `--color-primary-dark`
- `--color-bg-main`
- `--color-bg-soft`
- `--color-bg-card`
- `--color-bg-panel`
- `--color-border`
- `--color-border-strong`
- `--color-text-main`
- `--color-text-secondary`
- `--color-text-muted`
- `--color-success`
- `--color-warning`
- `--color-error`
- `--color-info`

### Tipografia
- `--font-display`
- `--font-body`
- escala `--font-size-xs` a `--font-size-3xl`

### Espaciado
- `--space-1` a `--space-10`

### Bordes y sombras
- `--radius-sm` a `--radius-xl`
- `--shadow-soft`
- `--shadow-card`
- `--shadow-focus`

## Componentes base reutilizables

### Superficies
- `.panel-card`
- `.clinical-panel`
- `.card-subtle`

### Acciones
- `.btn-primary`
- `.btn-secondary`
- `.btn-ghost`

### Estados
- `.pill`
- `.status-badge-success`
- `.status-badge-warning`
- `.status-badge-error`
- `.status-badge-info`

### Datos y evaluacion
- `.evaluation-table`

## Reglas UX

### 1. Color con proposito
- Azul primario para acciones principales, estructura y navegacion.
- Verde solo para confirmacion o exito.
- Amarillo solo para advertencias.
- Rojo solo para error, bloqueo o riesgo.
- Evitar usar color como decoracion sin significado funcional.

### 2. Feedback inmediato
- Todo guardado debe mostrar estado visible.
- Toda accion riesgosa debe usar color semantico y confirmacion.
- Tablas y badges deben permitir lectura rapida de estado.

### 3. Lenguaje centrado en rol
- Docente: lenguaje de construccion, validacion y diseno.
- Clinico/evaluador: lenguaje operativo, breve y seguro.
- Estudiante: solo la instruccion esencial, sin sobrecarga.

### 4. Menor carga cognitiva
- Mostrar primero lo indispensable.
- Usar bloques expandibles para complejidad progresiva.
- Mantener una jerarquia visual clara entre:
  - titulo
  - subtitulo
  - ayuda breve
  - detalle secundario

## Aplicacion inicial en ECOE

Ya se aplico a:
- shell general
- sidebar
- section cards
- stat cards
- formularios rapidos
- importadores
- tablas de datos
- dashboard
- resultados

## Siguiente iteracion recomendada

1. Llevar estos componentes a un directorio `components/ui/`.
2. Crear helpers de badges de estado por dominio.
3. Unificar feedback visual de guardado, warning y error.
4. Aplicar el mismo lenguaje a `pilotage`, `live`, `validation` y `publication`.
