/**
 * Gating de UI por rol EFECTIVO de evento (`eventRoles`), no por el rol
 * global del JWT. Ver docs/architecture/P0_MATRIZ_PERMISOS.md: "las
 * restricciones usan roles efectivos del ECOE, no el rol global".
 *
 * `admin_global` es el único bypass universal. El backend
 * (`ensure_event_access`) sigue siendo la autoridad final; estos helpers
 * solo evitan ofrecer/bloquear en la UI lo que el backend ya decide.
 */

/** Roles de evento que pueden ENTRAR al área de gestión de estaciones
 *  (lectura). Espeja el GET de `/api/stations/{id}` y `/api/station-bank`
 *  (`ADMIN_EVENT_ROLE_CODES` en el backend). */
export const STATION_AREA_EVENT_ROLES = [
  "admin_ecoe",
  "coeditor_docente",
  "coordinador_operativo",
] as const;

/** Roles de evento que pueden EDITAR estaciones / contenido de banco.
 *  Espeja `require_roles("admin_ecoe", "coeditor_docente")` en las rutas
 *  de mutación de estaciones. */
export const STATION_EDITOR_EVENT_ROLES = ["admin_ecoe", "coeditor_docente"] as const;

function hasAnyEventRole(eventRoles: readonly string[], allowed: readonly string[]): boolean {
  return eventRoles.some((role) => allowed.includes(role));
}

/** ¿Puede esta cuenta ver el área de gestión de estaciones para el evento activo? */
export function canAccessStationArea(
  globalRole: string | null | undefined,
  eventRoles: readonly string[],
): boolean {
  return globalRole === "admin_global" || hasAnyEventRole(eventRoles, STATION_AREA_EVENT_ROLES);
}

/** ¿Puede esta cuenta editar estaciones / contenido de banco para el evento activo? */
export function canEditStations(
  globalRole: string | null | undefined,
  eventRoles: readonly string[],
): boolean {
  return globalRole === "admin_global" || hasAnyEventRole(eventRoles, STATION_EDITOR_EVENT_ROLES);
}

/** ¿Puede esta cuenta duplicar el ECOE activo? `admin_global` o `admin_ecoe` del evento. */
export function canDuplicateEcoe(
  globalRole: string | null | undefined,
  eventRoles: readonly string[],
): boolean {
  return globalRole === "admin_global" || eventRoles.includes("admin_ecoe");
}
