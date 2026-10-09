import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { Sidebar } from "@/components/sidebar";

let pathname = "/dashboard";
let user = { role: "admin_ecoe" };
let eventRoles: string[] = ["admin_ecoe"];

vi.mock("next/navigation", () => ({ usePathname: () => pathname }));
vi.mock("@/lib/auth", () => ({ useECOE: () => ({ user, eventRoles }) }));

beforeEach(() => {
  pathname = "/dashboard";
  user = { role: "admin_ecoe" };
  eventRoles = ["admin_ecoe"];
});

describe("Sidebar", () => {
  it("agrupa los items por fase del ciclo, en orden", () => {
    render(<Sidebar />);
    const groups = screen.getAllByRole("group").map((node) => node.getAttribute("aria-label"));
    expect(groups).toEqual(["Este ECOE", "Preparación", "Día del examen", "Cierre", "Biblioteca"]);
    const preparacion = within(screen.getByRole("group", { name: "Preparación" }));
    expect(preparacion.getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Validación",
      "Pilotaje",
      "Publicación",
    ]);
  });

  it("no ofrece el Constructor como entrada propia y marca Estaciones al estar en él", () => {
    pathname = "/stations/builder";
    render(<Sidebar />);
    expect(screen.queryByRole("link", { name: /Constructor/ })).toBeNull();
    expect(screen.getByRole("link", { name: "Estaciones" })).toHaveAttribute("aria-current", "page");
  });

  it("marca el item padre en una subruta", () => {
    pathname = "/ecoe/12";
    render(<Sidebar />);
    expect(screen.getByRole("link", { name: "Datos del ECOE" })).toHaveAttribute("aria-current", "page");
    expect(screen.getAllByRole("link").filter((link) => link.getAttribute("aria-current"))).toHaveLength(1);
  });

  it("oculta Institución y Usuarios a quien no es admin global", () => {
    render(<Sidebar />);
    expect(screen.queryByRole("group", { name: "Institución" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Usuarios" })).toBeNull();
  });

  it("muestra Usuarios al admin global", () => {
    user = { role: "admin_global" };
    eventRoles = [];
    render(<Sidebar />);
    expect(within(screen.getByRole("group", { name: "Institución" })).getByRole("link", { name: "Usuarios" })).toBeInTheDocument();
  });

  it("un corrector sólo ve Corrección", () => {
    user = { role: "miembro" };
    eventRoles = ["corrector"];
    render(<Sidebar />);
    expect(screen.getAllByRole("link").map((link) => link.textContent)).toEqual(["Corrección"]);
  });
});
