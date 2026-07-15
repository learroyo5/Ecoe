export type RoleCode =
  | "admin_global"
  | "miembro"
  | "admin_ecoe"
  | "coeditor_docente"
  | "coordinador_operativo"
  | "evaluador"
  | "estudiante"
  | "cronometrador";

// Única fuente de verdad ruta→roles: la consumen el sidebar (visibilidad)
// y el middleware (gating real de navegación).
export const NAV_ITEMS: { label: string; href: string; allowedFor: RoleCode[] }[] = [
  { label: "Dashboard", href: "/dashboard", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"] },
  { label: "ECOE", href: "/ecoe", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"] },
  { label: "Usuarios", href: "/users", allowedFor: ["admin_global"] },
  { label: "Estudiantes", href: "/students", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"] },
  { label: "Evaluadores", href: "/evaluators", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"] },
  { label: "Estaciones", href: "/stations", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"] },
  { label: "Banco de estaciones", href: "/station-bank", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"] },
  { label: "Constructor", href: "/stations/builder", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente"] },
  { label: "Plantillas", href: "/templates", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"] },
  { label: "Instrumentos", href: "/instruments", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"] },
  { label: "Paciente simulado", href: "/simulated-patient", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"] },
  { label: "Validacion", href: "/validation", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"] },
  { label: "Pilotaje", href: "/pilotage", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"] },
  { label: "Publicacion", href: "/publication", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente"] },
  { label: "Panel en vivo", href: "/live", allowedFor: ["admin_global", "admin_ecoe", "coordinador_operativo", "cronometrador"] },
  { label: "Evaluador", href: "/evaluator", allowedFor: ["evaluador"] },
  { label: "Estudiante", href: "/student", allowedFor: ["estudiante"] },
  { label: "Corrección", href: "/grading", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente"] },
  { label: "Resultados", href: "/results", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"] },
];

export function defaultRouteForRole(role: string): string {
  switch (role) {
    case "evaluador":
      return "/evaluator";
    case "estudiante":
      return "/student";
    case "cronometrador":
      return "/live";
    default:
      return "/dashboard";
  }
}

/**
 * Devuelve si la ruta está permitida para el rol, usando el item de
 * navegación más específico que cubra el pathname (p.ej. /ecoe/123 → /ecoe,
 * /stations/builder gana sobre /stations). Rutas sin item asociado se
 * permiten: el backend sigue siendo la autoridad final.
 */
export function isRouteAllowedForRole(pathname: string, role: string | string[]): boolean {
  let match: (typeof NAV_ITEMS)[number] | null = null;
  for (const item of NAV_ITEMS) {
    if (pathname === item.href || pathname.startsWith(`${item.href}/`)) {
      if (!match || item.href.length > match.href.length) {
        match = item;
      }
    }
  }
  if (!match) return true;
  const roles = Array.isArray(role) ? role : [role];
  return roles.some((item) => match?.allowedFor.includes(item as RoleCode));
}
