import { describe, expect, it } from "vitest";
import { NAV_GROUPS, NAV_ITEMS, defaultRouteForRole, isRouteAllowedForRole, navItemForPath } from "@/lib/routes";

describe("defaultRouteForRole", () => {
  it("sends evaluadores to /evaluator", () => {
    expect(defaultRouteForRole("evaluador")).toBe("/evaluator");
  });

  it("sends estudiantes to /student", () => {
    expect(defaultRouteForRole("estudiante")).toBe("/student");
  });

  it("sends cronometradores to /live", () => {
    expect(defaultRouteForRole("cronometrador")).toBe("/live");
  });

  it("defaults every other role to /dashboard", () => {
    expect(defaultRouteForRole("admin_ecoe")).toBe("/dashboard");
    expect(defaultRouteForRole("admin_global")).toBe("/dashboard");
    expect(defaultRouteForRole("coeditor_docente")).toBe("/dashboard");
    expect(defaultRouteForRole("unknown_role")).toBe("/dashboard");
  });
});

describe("isRouteAllowedForRole", () => {
  it("blocks estudiante/evaluador from admin-only routes", () => {
    expect(isRouteAllowedForRole("/users", "estudiante")).toBe(false);
    expect(isRouteAllowedForRole("/users", "evaluador")).toBe(false);
    expect(isRouteAllowedForRole("/users", "admin_ecoe")).toBe(false);
    expect(isRouteAllowedForRole("/users", "admin_global")).toBe(true);
  });

  it("blocks estudiante/evaluador from management routes hidden for them", () => {
    expect(isRouteAllowedForRole("/students", "estudiante")).toBe(false);
    expect(isRouteAllowedForRole("/students", "coeditor_docente")).toBe(true);
  });

  it("allows evaluador, admin_ecoe and coordinador_operativo on /evaluator (check-in fill-in for unassigned stations)", () => {
    expect(isRouteAllowedForRole("/evaluator", "evaluador")).toBe(true);
    expect(isRouteAllowedForRole("/evaluator", "admin_ecoe")).toBe(true);
    expect(isRouteAllowedForRole("/evaluator", "coordinador_operativo")).toBe(true);
    expect(isRouteAllowedForRole("/evaluator", "coeditor_docente")).toBe(false);
    expect(isRouteAllowedForRole("/evaluator", "estudiante")).toBe(false);
  });

  it("matches nested paths against the most specific configured prefix", () => {
    // /ecoe/123 should be governed by the /ecoe entry, not fall through as "allowed by default"
    expect(isRouteAllowedForRole("/ecoe/123", "estudiante")).toBe(false);
    expect(isRouteAllowedForRole("/ecoe/123", "admin_ecoe")).toBe(true);
  });

  it("prefers the longer/more specific prefix when two entries could match", () => {
    // /stations/builder has its own, stricter entry than /stations
    expect(isRouteAllowedForRole("/stations/builder", "evaluador")).toBe(false);
  });

  it("allows any role on routes with no matching nav entry (backend remains the authority)", () => {
    expect(isRouteAllowedForRole("/some-unlisted-route", "estudiante")).toBe(true);
  });

  it("uses effective ECOE roles when a user has different duties per event", () => {
    expect(isRouteAllowedForRole("/stations/builder", ["coeditor_docente"])).toBe(true);
    expect(isRouteAllowedForRole("/live", ["evaluador"])).toBe(false);
  });
});

describe("/kiosks", () => {
  it("sólo lo abren los roles que el backend deja emitir tokens de kiosco", () => {
    expect(isRouteAllowedForRole("/kiosks", "admin_ecoe")).toBe(true);
    expect(isRouteAllowedForRole("/kiosks", "coordinador_operativo")).toBe(true);
    expect(isRouteAllowedForRole("/kiosks", "admin_global")).toBe(true);
    expect(isRouteAllowedForRole("/kiosks", "coeditor_docente")).toBe(false);
    expect(isRouteAllowedForRole("/kiosks", "cronometrador")).toBe(false);
    expect(isRouteAllowedForRole("/kiosks", "evaluador")).toBe(false);
    expect(isRouteAllowedForRole("/kiosks", "estudiante")).toBe(false);
  });

  it("no captura la ruta pública /kiosk de las tablets", () => {
    expect(isRouteAllowedForRole("/kiosk", "estudiante")).toBe(true);
  });
});

describe("NAV_ITEMS (presentación)", () => {
  it("el Constructor sigue con gating propio aunque no tenga entrada en la barra lateral", () => {
    const builder = NAV_ITEMS.find((item) => item.href === "/stations/builder");
    expect(builder?.hidden).toBe(true);
    // Más estricto que /stations: el coordinador operativo no edita estaciones.
    expect(isRouteAllowedForRole("/stations/builder", "coordinador_operativo")).toBe(false);
    expect(isRouteAllowedForRole("/stations", "coordinador_operativo")).toBe(true);
  });

  it("todo item agrupado apunta a un grupo declarado", () => {
    const keys = new Set(NAV_GROUPS.map((group) => group.key));
    for (const item of NAV_ITEMS) {
      if (item.group) expect(keys.has(item.group)).toBe(true);
    }
  });

  it("navItemForPath acepta un subconjunto y devuelve el prefijo más largo", () => {
    const visible = NAV_ITEMS.filter((item) => !item.hidden);
    expect(navItemForPath("/stations/builder", visible)?.href).toBe("/stations");
    expect(navItemForPath("/stations/builder")?.href).toBe("/stations/builder");
    expect(navItemForPath("/no-existe")).toBeNull();
  });
});
