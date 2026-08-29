import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ResultsPage from "@/app/(app)/results/page";
import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";

vi.mock("@/lib/auth", () => ({
  useECOE: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    results: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);
const mockedUseECOE = vi.mocked(useECOE);

const baseTraceability = {
  summary: {
    active_students: 0,
    stations: 0,
    expected_evaluations: 0,
    expected_student_submissions: 0,
    confirmed_checkins: 0,
    evaluator_submissions: 0,
    student_submissions: 0,
    pilot_runs: 0,
  },
  student_traceability: [],
  station_traceability: [],
  activity_log: [],
  by_station: { stations: [], students: [] },
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedUseECOE.mockReturnValue({ authenticated: true, eventId: 1 } as never);
});

describe("ResultsPage — inmutabilidad OPT-1", () => {
  it("muestra el chip de resultados consolidados cuando el payload trae frozen", async () => {
    mockedApi.results.mockResolvedValue({
      results: [],
      frozen: true,
      consolidated_at: "2026-08-20T15:30:00Z",
      ...baseTraceability,
    } as never);

    render(<ResultsPage />);

    const chip = await screen.findByTestId("results-frozen-chip");
    expect(chip.textContent).toContain("Resultados consolidados el");
  });

  it("no muestra el chip cuando frozen es false (comportamiento en vivo)", async () => {
    mockedApi.results.mockResolvedValue({
      results: [],
      frozen: false,
      consolidated_at: null,
      ...baseTraceability,
    } as never);

    render(<ResultsPage />);

    await waitFor(() => expect(mockedApi.results).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.queryByText("Calculando resultados...")).not.toBeInTheDocument(),
    );
    expect(screen.queryByTestId("results-frozen-chip")).not.toBeInTheDocument();
  });
});

describe("ResultsPage — resultados por estación OPT-16", () => {
  it("renderiza el agregado por estación y la nota por estudiante desde by_station", async () => {
    mockedApi.results.mockResolvedValue({
      results: [],
      frozen: false,
      consolidated_at: null,
      ...baseTraceability,
      by_station: {
        stations: [
          {
            station_id: 7,
            station_number: 1,
            station_name: "Anamnesis",
            circuit_name: "Circuito A",
            n: 2,
            mean_score: 8,
            sd_score: 2.83,
            mean_max: 10,
            mean_percent: 80,
            sd_percent: 28.28,
            min_percent: 60,
            max_percent: 100,
          },
        ],
        students: [
          {
            student_id: 1,
            ecoe_number: "001",
            student_name: "Ana Pérez",
            station_id: 7,
            station_number: 1,
            station_name: "Anamnesis",
            obtained_score: 10,
            max_score: 10,
            percent_score: 100,
          },
        ],
      },
    } as never);

    render(<ResultsPage />);

    expect(await screen.findByText("Resultados por estación")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Anamnesis")).toBeInTheDocument());
    expect(screen.getByText("Ana Pérez")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "1. Anamnesis" })).toBeInTheDocument();
  });

  it("no rompe cuando by_station.stations está vacío", async () => {
    mockedApi.results.mockResolvedValue({
      results: [],
      frozen: false,
      consolidated_at: null,
      ...baseTraceability,
    } as never);

    render(<ResultsPage />);

    expect(await screen.findByText("Resultados por estación")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.queryByText("Calculando resultados por estación...")).not.toBeInTheDocument(),
    );
  });
});

describe("ResultsPage — normalización por estación OPT-17", () => {
  it("aclara en el subtítulo que el porcentaje es el promedio del % por estación", async () => {
    mockedApi.results.mockResolvedValue({
      results: [],
      frozen: false,
      consolidated_at: null,
      ...baseTraceability,
    } as never);

    render(<ResultsPage />);

    expect(
      await screen.findByText(/promedio del % de logro de cada estación/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/sumas crudas informativas/i)).toBeInTheDocument();
  });

  it("muestra la columna Estaciones con stations_counted del consolidado", async () => {
    mockedApi.results.mockResolvedValue({
      results: [
        {
          student_id: 1,
          student_name: "Ana Pérez",
          ecoe_number: "001",
          total_score: 20,
          max_score: 25,
          percentage: 50,
          equivalent_grade: 3.5,
          stations_counted: 2,
        },
      ],
      frozen: false,
      consolidated_at: null,
      ...baseTraceability,
    } as never);

    render(<ResultsPage />);

    expect(await screen.findByText("Estaciones")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Ana Pérez")).toBeInTheDocument());
    const row = screen.getByText("Ana Pérez").closest("tr");
    expect(row).not.toBeNull();
    expect(row).toHaveTextContent("2");
  });
});
