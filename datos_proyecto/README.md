# Datos del proyecto

Indice rapido para no perdernos entre documentos de apoyo.

## Que leer segun necesidad

- Estado del producto: `../PROJECT_STATUS.md`
- Prioridades de desarrollo: `../NEXT_STEPS.md`
- Operacion y despliegue del servidor actual: `operacion_despliegue.md`
- Credenciales locales del servidor actual: `credenciales_locales.md`
- Contexto de producto y roadmap largo: `base_producto_y_roadmap.md`
- Ajustes del despliegue publico por nginx (historico): `ajuste_publico_ecoe.md`
- Dominios propios, como se armaron en el servidor anterior (historico): `despliegue_dominios_ecoe.md`
- Fuente real del landing de `ecoe.cl` (copia exacta de lo desplegado): `ecoe-cl-landing.html`, `ecoe-cl-terminos.html`, `ecoe-cl-privacidad.html`
- Sistema visual y lenguaje de interfaz: `design_system_drnotus.md`
- Plan manual de pruebas de flujo (anterior al rediseno de octubre 2026): `plan_pruebas_flujo.md`
- Instancia demo, tunel de Cloudflare y respaldos: `operacion_despliegue.md`

## Convencion recomendada

- `README.md`: onboarding tecnico y como levantar el proyecto
- `PROJECT_STATUS.md`: estado actual real, sin wishlist
- `NEXT_STEPS.md`: backlog priorizado de trabajo
- `datos_proyecto/*`: notas operativas, producto y apoyo

## Nota

Algunas notas son historicas. Cuando haya contradiccion, tomar como fuente principal:

1. `backend/.env` para configuracion activa del servidor actual
2. `docker-compose.yml` para topologia local
3. `PROJECT_STATUS.md` para estado vigente
