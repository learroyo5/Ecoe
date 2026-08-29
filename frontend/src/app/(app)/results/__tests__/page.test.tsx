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
    psychometrics: vi.fn(),
  },
}));

const EMPTY_PSYCHOMETRICS = {
  mode: "ejecucion",
  frozen: false,
  passing_reference_percent: 60,
  student_count: 0,
  station_stats: [],
  reliability: {
    cronbach_alpha: null,
    n_complete: 0,
    n_total: 0,
    k_stations: 0,
    station_discrimination: [],
  },
  item_analysis: [],
  warnings: [],
  thresholds: {},
};

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
  mockedApi.psychometrics.mockResolvedValue(EMPTY_PSYCHOMETRICS as never);
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

describe("ResultsPage — psicometría OPT-18", () => {
  const baseResults = {
    results: [],
    frozen: false,
    consolidated_at: null,
    ...baseTraceability,
  };

  it("renderiza α de Cronbach y la tabla por estación desde psychometrics", async () => {
    mockedApi.results.mockResolvedValue(baseResults as never);
    mockedApi.psychometrics.mockResolvedValue({
      ...EMPTY_PSYCHOMETRICS,
      student_count: 3,
      station_stats: [
        {
          station_id: 7,
          station_number: 1,
          station_name: "Anamnesis",
          circuit_name: "Circuito A",
          n: 3,
          mean_percent: 80,
          sd_percent: 10,
          mean_score: 8,
          sd_score: 1,
          mean_max: 10,
          min_percent: 70,
          max_percent: 90,
          grade_histogram: [
            { grade: 1, label: "1.0–1.9", count: 0 },
            { grade: 2, label: "2.0–2.9", count: 0 },
            { grade: 3, label: "3.0–3.9", count: 0 },
            { grade: 4, label: "4.0–4.9", count: 1 },
            { grade: 5, label: "5.0–5.9", count: 1 },
            { grade: 6, label: "6.0–6.9", count: 1 },
            { grade: 7, label: "7.0", count: 0 },
          ],
        },
      ],
      reliability: {
        cronbach_alpha: 0.72,
        n_complete: 3,
        n_total: 3,
        k_stations: 2,
        station_discrimination: [
          { station_id: 7, station_number: 1, station_name: "Anamnesis", r: 0.35 },
        ],
      },
      warnings: [
        {
          code: "station_discrimination_low",
          severity: "warning",
          metric: "station_discrimination",
          value: 0.1,
          station_number: 2,
          message: "La estación 2 discrimina poco (r = 0.10).",
        },
      ],
    } as never);

    render(<ResultsPage />);

    expect(await screen.findByText("Psicometría (ejecución)")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("0.72")).toBeInTheDocument());
    expect(screen.getByText("La estación 2 discrimina poco (r = 0.10).")).toBeInTheDocument();
  });

  it("degrada sin romper cuando no hay datos psicométricos", async () => {
    mockedApi.results.mockResolvedValue(baseResults as never);
    mockedApi.psychometrics.mockResolvedValue(EMPTY_PSYCHOMETRICS as never);

    render(<ResultsPage />);

    expect(await screen.findByText("Psicometría (ejecución)")).toBeInTheDocument();
    await waitFor(() =>
      expect(
        screen.getByText(/Aún no hay datos de ejecución suficientes/i),
      ).toBeInTheDocument(),
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
