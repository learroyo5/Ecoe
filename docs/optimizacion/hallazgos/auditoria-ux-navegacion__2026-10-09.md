# Auditoría UX de la intranet — navegación, barra lateral y flujos (2026-10-09)

Modo: lectura del frontend (`frontend/src`), sin navegador. Alcance: shell autenticado (`components/app-shell.tsx`, `components/sidebar.tsx`, `lib/routes.ts`) y pantallas de gestión bajo `app/(app)/`. Solicitada por el usuario; el triage está en `BACKLOG.md` (Grupo D, UX-1..UX-7).

Diagnóstico de fondo: el ECOE sigue un ciclo claro (configurar → pilotar → publicar → ejecutar → cerrar) pero la navegación lo presenta como 19 enlaces planos del mismo peso.

### H-ux-1 · Barra lateral plana, sin grupos ni orden de flujo
- **Rol / pantalla**: gestión · `components/sidebar.tsx`, `lib/routes.ts::NAV_ITEMS`
- **Severidad**: alta · **Tipo**: fricción-UX
- **Evidencia**: 19 ítems en una sola lista; "Usuarios" (institucional) entre "ECOE" y "Estudiantes"; "Constructor" separado de "Estaciones" por el banco; bancos reutilizables y fases del evento sin distinguir.

### H-ux-2 · Barra lateral más alta que la pantalla, sin scroll propio
- **Severidad**: alta · **Tipo**: bug de layout
- **Evidencia**: `sidebar.tsx` usa `lg:h-fit lg:sticky lg:top-4 overflow-y-auto` sin `max-height`: el `overflow` nunca actúa y en pantallas < ~1000 px de alto los últimos ítems (Corrección, Resultados) sólo aparecen al llegar al final de la página.

### H-ux-3 · Ítem activo por ruta exacta
- **Severidad**: media · **Tipo**: fricción-UX
- **Evidencia**: `const active = pathname === href` → en `/ecoe/123` no se marca nada.

### H-ux-4 · Título de página constante
- **Severidad**: media · **Tipo**: fricción-UX
- **Evidencia**: `app/(app)/layout.tsx` pasa siempre `title="Operación académica del ECOE"`; el título real vive en la primera `SectionCard`.

### H-ux-5 · Selector de ECOE sin estado, duplicado y sin protección en vivo
- **Severidad**: media · **Tipo**: fricción-UX / riesgo operativo
- **Evidencia**: `app-shell.tsx` rotula "ECOE en edición" en todas las pantallas y no muestra el estado; `/ecoe` repite el selector ("Selección"); el layout de gestión permite cambiar de ECOE con el evento `en_ejecucion` (el layout de operador sí lo bloquea).

### H-ux-6 · El inicio no orienta
- **Severidad**: media · **Tipo**: fricción-UX
- **Evidencia**: `dashboard/page.tsx` muestra contadores y estados, sin siguiente paso ni enlaces; tiempo restante en segundos crudos.

### H-ux-7 · Gestión del ECOE repartida y mezclada
- **Severidad**: media · **Tipo**: fricción-UX
- **Evidencia**: `/ecoe` mezcla editar + cambiar estado + crear (formulario siempre abierto); `/ecoe/[id]` muestra lo mismo en solo-lectura con un botón "Editar en Gestión" que devuelve a `/ecoe`; publicar existe en la barra de estado y en `/publication` con confirmaciones distintas.

### H-ux-8 · Enlaces de kiosco uno a uno
- **Severidad**: media · **Tipo**: fricción-UX (día del examen)
- **Evidencia**: `stations/page.tsx` — botón por fila, enlace visible una sola vez.

### H-ux-9 · Controles del panel en vivo siempre todos visibles
- **Severidad**: baja · **Tipo**: fricción-UX
- **Evidencia**: `live/page.tsx` renderiza Iniciar/Pausar/Reanudar/Reiniciar/Siguiente sin deshabilitar los que no aplican al estado.

### H-ux-10 · Resultados en una sola página larga
- **Severidad**: baja · **Tipo**: fricción-UX
- **Evidencia**: `results/page.tsx` — siete `SectionCard` seguidas sin pestañas.

### H-ux-11 · Inconsistencias de texto y confirmación
- **Severidad**: baja · **Tipo**: cosmético
- **Evidencia**: estados crudos (`en_configuracion`) en `/ecoe`, `/publication`, `/ecoe/[id]`; `window.confirm` en Estudiantes, Evaluadores, Estaciones, Publicación junto a `ConfirmDialog` en otras; voseo ("tenés", "Pedile") junto a tuteo; tildes faltantes ("Gestion", "Nomina").
