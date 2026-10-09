export type RoleCode =
  | "admin_global"
  | "miembro"
  | "admin_ecoe"
  | "coeditor_docente"
  | "coordinador_operativo"
  | "evaluador"
  | "corrector"
  | "estudiante"
  | "cronometrador";

export type NavGroupKey = "evento" | "preparacion" | "examen" | "cierre" | "biblioteca" | "institucion";

// Grupos de la barra lateral, en el orden del ciclo del ECOE. Los bancos
// reutilizables (biblioteca) y lo institucional van al final: no son fases.
export const NAV_GROUPS: { key: NavGroupKey; label: string }[] = [
  { key: "evento", label: "Este ECOE" },
  { key: "preparacion", label: "Preparación" },
  { key: "examen", label: "Día del examen" },
  { key: "cierre", label: "Cierre" },
  { key: "biblioteca", label: "Biblioteca" },
  { key: "institucion", label: "Institución" },
];

export type NavItem = {
  label: string;
  href: string;
  allowedFor: RoleCode[];
  /** Grupo de la barra lateral; sin grupo va suelto arriba (Inicio). */
  group?: NavGroupKey;
  /** Trazo SVG (viewBox 24×24, sin relleno) del icono. */
  icon: string;
  /** Ruta con gating y título propios pero sin entrada en la barra lateral:
   *  se llega desde su pantalla padre (el item visible de prefijo más largo). */
  hidden?: boolean;
};

// Única fuente de verdad ruta→roles: la consumen el sidebar (visibilidad)
// y el gating de navegación. `allowedFor` es la autorización; `group`, `icon`
// y `hidden` son sólo presentación.
export const NAV_ITEMS: NavItem[] = [
  { label: "Inicio", href: "/dashboard", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"], icon: "M3 11l9-8 9 8M5 10v10h14V10" },
  { label: "Datos del ECOE", href: "/ecoe", group: "evento", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"], icon: "M6 3h9l4 4v14H6zM14 3v5h5M9 13h6M9 17h6" },
  { label: "Estaciones", href: "/stations", group: "evento", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"], icon: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" },
  { label: "Constructor de estaciones", href: "/stations/builder", group: "evento", hidden: true, allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente"], icon: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z" },
  { label: "Estudiantes", href: "/students", group: "evento", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"], icon: "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 6.5M18 14.5a6 6 0 0 1 3.5 5.5" },
  { label: "Equipo", href: "/evaluators", group: "evento", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"], icon: "M4 5h16v14H4zM9 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM6.5 16a2.5 2.5 0 0 1 5 0M14 10h4M14 14h4" },
  { label: "Validación", href: "/validation", group: "preparacion", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"], icon: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8.5 12.5l2.5 2.5 4.5-5" },
  { label: "Pilotaje", href: "/pilotage", group: "preparacion", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"], icon: "M9 3h6M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3M7.5 15h9" },
  { label: "Publicación", href: "/publication", group: "preparacion", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente"], icon: "M12 16V4M7 9l5-5 5 5M4 20h16" },
  { label: "Panel en vivo", href: "/live", group: "examen", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo", "cronometrador"], icon: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2" },
  { label: "Vista de evaluador", href: "/evaluator", group: "examen", allowedFor: ["evaluador", "admin_ecoe", "coordinador_operativo"], icon: "M9 4h6v3H9zM9 5H6v16h12V5h-3M9 12l2 2 4-4" },
  { label: "Estudiante", href: "/student", group: "examen", allowedFor: ["estudiante"], icon: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0" },
  { label: "Corrección", href: "/grading", group: "cierre", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "corrector"], icon: "M4 20h4L19 9l-4-4L4 16zM13 7l4 4" },
  { label: "Resultados", href: "/results", group: "cierre", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"], icon: "M4 20V10M10 20V4M16 20v-7M22 20H2" },
  { label: "Banco de estaciones", href: "/station-bank", group: "biblioteca", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"], icon: "M3 5h18v4H3zM5 9v10h14V9M10 13h4" },
  { label: "Plantillas", href: "/templates", group: "biblioteca", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"], icon: "M12 3l9 5-9 5-9-5zM3 13l9 5 9-5" },
  { label: "Instrumentos", href: "/instruments", group: "biblioteca", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"], icon: "M9 6h11M9 12h11M9 18h11M4 6l1 1 2-2M4 12l1 1 2-2M4 18l1 1 2-2" },
  { label: "Pacientes simulados", href: "/simulated-patient", group: "biblioteca", allowedFor: ["admin_global", "admin_ecoe", "coeditor_docente", "coordinador_operativo"], icon: "M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 10c0 5.5-7 10-7 10z" },
  { label: "Usuarios", href: "/users", group: "institucion", allowedFor: ["admin_global"], icon: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" },
];

export function defaultRouteForRole(role: string): string {
  switch (role) {
    case "evaluador":
      return "/evaluator";
    case "corrector":
      return "/grading";
    case "estudiante":
      return "/student";
    case "cronometrador":
      return "/live";
    default:
      return "/dashboard";
  }
}

/** Item de navegación más específico que cubre el pathname, o null. */
export function navItemForPath(pathname: string, items: NavItem[] = NAV_ITEMS): NavItem | null {
  let match: NavItem | null = null;
  for (const item of items) {
    if (pathname === item.href || pathname.startsWith(`${item.href}/`)) {
      if (!match || item.href.length > match.href.length) {
        match = item;
      }
    }
  }
  return match;
}

/**
 * Devuelve si la ruta está permitida para el rol, usando el item de
 * navegación más específico que cubra el pathname (p.ej. /ecoe/123 → /ecoe,
 * /stations/builder gana sobre /stations). Rutas sin item asociado se
 * permiten: el backend sigue siendo la autoridad final.
 */
export function isRouteAllowedForRole(pathname: string, role: string | string[]): boolean {
  const match = navItemForPath(pathname);
  if (!match) return true;
  const roles = Array.isArray(role) ? role : [role];
  return roles.some((item) => match?.allowedFor.includes(item as RoleCode));
}
