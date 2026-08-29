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
