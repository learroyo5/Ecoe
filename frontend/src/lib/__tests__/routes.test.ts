import { describe, expect, it } from "vitest";
import { defaultRouteForRole, isRouteAllowedForRole } from "@/lib/routes";

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

  it("allows evaluador only on /evaluator, not on staff routes", () => {
    expect(isRouteAllowedForRole("/evaluator", "evaluador")).toBe(true);
    expect(isRouteAllowedForRole("/evaluator", "admin_ecoe")).toBe(false);
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
