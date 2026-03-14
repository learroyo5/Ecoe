# Next Steps

## Prioridad alta

1. Completar CRUD real de ECOE
- Formulario completo de datos generales.
- Cambio de estado guiado desde UI.
- Vista de detalle del ECOE activo.

2. Mejorar constructor de estaciones
- Edicion de estaciones existentes.
- Formularios por secciones con mejor UX.
- Asociacion real de multimedia.
- Asociacion real de instrumentos y paciente simulado.

3. Mejorar flujo operativo en vivo
- Sincronizacion real del cronometro entre clientes.
- Confirmacion visual por estacion activa.
- Mejora de panel de incidencias.

4. Robustecer evaluacion y respuestas
- Render dinamico de instrumentos.
- Render dinamico de formularios del estudiante.
- Bloqueo por tiempo de manera efectiva.

5. Persistencia y mantenimiento
- Agregar migraciones con Alembic.
- Separar mejor seeds demo de datos reales.
- Agregar pruebas backend basicas.

## Prioridad media

1. Multimedia
- Upload con validacion por tipo.
- Preview de imagen, audio, video y PDF.
- Definir si ve estudiante o evaluador.

2. Exportaciones
- Mejorar formato de Excel consolidado.
- PDF por estacion con formato imprimible real.
- hojas manuales de contingencia mejor estructuradas.

3. Seguridad operativa
- Logout real del lado cliente.
- expiracion de token mejor manejada.
- endurecer controles de permisos por ruta y accion.

4. UX/UI
- mejorar version tablet en formularios largos.
- reforzar feedback de guardado.
- filtros y buscadores en tablas.

## Prioridad baja

1. Observabilidad
- logs mas claros
- auditoria expandida

2. Infraestructura
- reverse proxy con Nginx
- HTTPS
- backups de PostgreSQL

## Sugerencia de orden de trabajo

### Iteracion 1

- CRUD completo del ECOE
- edicion de estaciones
- mejor validacion previa

### Iteracion 2

- instrumentos dinamicos
- formularios dinamicos del estudiante
- multimedia utilizable

### Iteracion 3

- tiempo real del panel central
- incidencias
- mejoras de exportacion

## Comandos utiles

Levantar:

```bash
docker compose up --build -d
```

Ver estado:

```bash
docker compose ps
```

Ver logs:

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

Apagar:

```bash
docker compose down
```

## Nota para futuras sesiones de Codex

Al retomar en otro servidor, pedir:

```text
Lee README.md, PROJECT_STATUS.md y NEXT_STEPS.md, revisa la estructura del repo y continuemos desde la prioridad alta.
```
