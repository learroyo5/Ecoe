import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import DashboardPage from "../page";
import { api } from "@/lib/api";

let eventRoles: string[] = ["admin_ecoe"];

vi.mock("@/lib/api", () => ({ api: { dashboard: vi.fn() } }));
vi.mock("@/lib/auth", () => ({
  useECOE: () => ({ authenticated: true, eventId: 1, user: { role: "miembro" }, eventRoles }),
}));

const mockedApi = vi.mocked(api);

function summary(status: string, validation: Record<string, unknown> = {}) {
  return {
    active_ecoe: { id: 1, name: "ECOE Medicina", status, date: "2026-11-23", course_name: "Medicina" },
    totals: { students: 20, stations: 4, evaluations: 0 },
    validation: {
      students_count: 20,
      station_count: 4,
      can_pilot: true,
      can_publish: true,
      warnings: [],
      blockers: [],
      ...validation,
    },
    timeline: [],
    live_panel: { status: "sin_sesion", current_station_index: 1, remaining_seconds: 0 },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  eventRoles = ["admin_ecoe"];
});

describe("Inicio", () => {
  it("marca la fase actual del ciclo y ofrece el siguiente paso con enlace", async () => {
    mockedApi.dashboard.mockResolvedValue(summary("en_pilotaje") as never);
    render(<DashboardPage />);
    expect(await screen.findByText("Ensaya el circuito y registra hallazgos")).toBeInTheDocument();
    expect(screen.getByText("Pilotar").closest("li")).toHaveAttribute("aria-current", "step");
    expect(screen.getByRole("link", { name: "Ir a Pilotaje" })).toHaveAttribute("href", "/pilotage");
  });

  it("no ofrece el botón cuando el paso está en una pantalla que el rol no tiene", async () => {
    eventRoles = ["coordinador_operativo"];
    mockedApi.dashboard.mockResolvedValue(summary("pilotaje_validado") as never);
    render(<DashboardPage />);
    expect(await screen.findByText("Publica el ECOE")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Ir a Publicación" })).toBeNull();
    expect(screen.getByText("Este paso lo realiza la administración del ECOE.")).toBeInTheDocument();
  });

  it("no muestra tiempo de sesión cuando el cronómetro no ha partido", async () => {
    mockedApi.dashboard.mockResolvedValue(summary("publicado") as never);
    render(<DashboardPage />);
    await screen.findByText("Sin sesión");
    expect(screen.queryByText(/quedan/)).toBeNull();
  });
});
