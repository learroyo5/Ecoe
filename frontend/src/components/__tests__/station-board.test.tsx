import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

import { StationBoardPanel } from "@/components/station-board";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({ api: { liveBoard: vi.fn() } }));
const mockedApi = vi.mocked(api);

beforeEach(() => vi.clearAllMocks());

describe("Tablero de estaciones", () => {
  it("resume la verificación previa y marca qué falta en cada estación", async () => {
    mockedApi.liveBoard.mockResolvedValue({
      preflight: { ready: false, issues: ["Estación 2: Kiosco sin vincular"] },
      stations: [
        {
          station_id: 1, station_number: 1, station_name: "Anamnesis", circuit_name: "Circuito A",
          requires_evaluator: true, needs_kiosk: false,
          evaluator: { name: "Camila Soto", email: "e@e.cl", has_account: true, online: true, last_seen_at: null },
          kiosk: null,
          occupant: { ecoe_number: "E007", student_name: "Ana Pérez", evaluation: "borrador", response: null },
          alerts: [],
        },
        {
          station_id: 2, station_number: 2, station_name: "ECG", circuit_name: "Circuito A",
          requires_evaluator: false, needs_kiosk: true, evaluator: null,
          kiosk: { linked: false, online: false, last_seen_at: null },
          occupant: null, alerts: ["Kiosco sin vincular"],
        },
      ],
    } as never);
    render(<StationBoardPanel eventId={1} />);

    expect(await screen.findByText("Verificación previa: 1 pendiente")).toBeInTheDocument();
    expect(screen.getByText("Estación 2: Kiosco sin vincular")).toBeInTheDocument();
    const first = within(screen.getByTestId("board-station-1"));
    expect(first.getByText("E007 · Ana Pérez")).toBeInTheDocument();
    expect(first.getByText("Evaluación: en borrador")).toBeInTheDocument();
    const second = within(screen.getByTestId("board-station-2"));
    expect(second.getByText("Sin vincular")).toBeInTheDocument();
    expect(second.getByText("Sin evaluador: confirma coordinación")).toBeInTheDocument();
  });

  it("dice que todo está listo sólo cuando no hay pendientes", async () => {
    mockedApi.liveBoard.mockResolvedValue({ preflight: { ready: true, issues: [] }, stations: [] } as never);
    render(<StationBoardPanel eventId={1} />);
    expect(await screen.findByText("Verificación previa: todo listo")).toBeInTheDocument();
  });

  it("muestra el error si el tablero no carga, sin afirmar que está listo", async () => {
    mockedApi.liveBoard.mockRejectedValue(new Error("Sin permiso"));
    render(<StationBoardPanel eventId={1} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Sin permiso");
    expect(screen.queryByText(/Verificación previa/)).toBeNull();
  });
});
