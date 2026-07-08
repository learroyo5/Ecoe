export type RoleCode =
  | "admin_ecoe"
  | "coeditor_docente"
  | "coordinador_operativo"
  | "evaluador"
  | "estudiante"
  | "cronometrador";

// Única fuente de verdad ruta→roles: la consumen el sidebar (visibilidad)
// y el middleware (gating real de navegación).
export const NAV_ITEMS: { label: string; href: string; hiddenFor: RoleCode[] }[] = [
  { label: "Dashboard", href: "/dashboard", hiddenFor: ["evaluador", "estudiante"] },
  { label: "ECOE", href: "/ecoe", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Usuarios", href: "/users", hiddenFor: ["coeditor_docente", "coordinador_operativo", "evaluador", "estudiante", "cronometrador"] },
  { label: "Estudiantes", href: "/students", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Evaluadores", href: "/evaluators", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Estaciones", href: "/stations", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Banco de estaciones", href: "/station-bank", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Constructor", href: "/stations/builder", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Plantillas", href: "/templates", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Instrumentos", href: "/instruments", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Paciente simulado", href: "/simulated-patient", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Validacion", href: "/validation", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Pilotaje", href: "/pilotage", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Publicacion", href: "/publication", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Panel en vivo", href: "/live", hiddenFor: ["evaluador", "estudiante"] },
  { label: "Evaluador", href: "/evaluator", hiddenFor: ["admin_ecoe", "coeditor_docente", "coordinador_operativo", "cronometrador", "estudiante"] },
  { label: "Estudiante", href: "/student", hiddenFor: ["admin_ecoe", "coeditor_docente", "coordinador_operativo", "cronometrador", "evaluador"] },
  { label: "Resultados", href: "/results", hiddenFor: ["evaluador", "estudiante"] },
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
export function isRouteAllowedForRole(pathname: string, role: string): boolean {
  let match: (typeof NAV_ITEMS)[number] | null = null;
  for (const item of NAV_ITEMS) {
    if (pathname === item.href || pathname.startsWith(`${item.href}/`)) {
      if (!match || item.href.length > match.href.length) {
        match = item;
      }
    }
  }
  if (!match) return true;
  return !match.hiddenFor.includes(role as RoleCode);
}
