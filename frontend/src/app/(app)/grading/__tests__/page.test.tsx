import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import GradingPage from "@/app/(app)/grading/page";
import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";

vi.mock("@/lib/auth", () => ({
  useECOE: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    gradingList: vi.fn(),
    gradeResponse: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);
const mockedUseECOE = vi.mocked(useECOE);

const OPEN_SCOPE = { is_corrector: true, has_assignment: true, assigned_station_ids: [7] };

function emptyList(overrides = {}) {
  return {
    responses: [],
    pending_count: 0,
    scope: { is_corrector: false, has_assignment: true, assigned_station_ids: [] },
    pending_by_station: {},
    ...overrides,
  };
}

function pendingRow(id: number, overrides = {}) {
  return {
    response_id: id,
    mode: "ejecucion",
    submission_kind: "manual",
    student_id: id,
    student_name: `Alumna ${id}`,
    student_ecoe_number: `00${id}`,
    station_id: 7,
    station_number: 3,
    station_name: "Informe",
    submitted_at: "2026-08-29T10:00:00",
    answers: { question_1: "Ritmo sinusal" },
    grading: { question_1: { kind: "manual", earned: null, max: 6, answered: true } },
    pending_questions: ["question_1"],
    score_obtained: null,
    max_score: 6,
    graded_by_email: null,
    questions: [{ label: "Interpreta el ECG", type: "short_text" }],
    assessment_tool: null,
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.gradingList.mockResolvedValue(emptyList() as never);
});

describe("GradingPage — gate de ECOE cerrado (OPT-1)", () => {
  it("oculta el formulario y muestra el aviso cuando el evento está cerrado", async () => {
    mockedUseECOE.mockReturnValue({
      authenticated: true,
      eventId: 1,
      ecoeEvent: { id: 1, status: "cerrado" },
    } as never);

    render(<GradingPage />);

    const notice = await screen.findByTestId("grading-closed-notice");
    expect(notice.textContent).toContain("ECOE cerrado");
    expect(screen.queryByText(/Pendientes de corrección/)).not.toBeInTheDocument();
    expect(mockedApi.gradingList).not.toHaveBeenCalled();
  });

  it("también bloquea la corrección cuando el evento está archivado", async () => {
    mockedUseECOE.mockReturnValue({
      authenticated: true,
      eventId: 1,
      ecoeEvent: { id: 1, status: "archivado" },
    } as never);

    render(<GradingPage />);

    expect(await screen.findByTestId("grading-closed-notice")).toBeInTheDocument();
  });

  it("muestra la cola de corrección normal cuando el evento está en ejecución", async () => {
    mockedUseECOE.mockReturnValue({
      authenticated: true,
      eventId: 1,
      ecoeEvent: { id: 1, status: "en_ejecucion" },
    } as never);

    render(<GradingPage />);

    await waitFor(() => expect(mockedApi.gradingList).toHaveBeenCalled());
    expect(screen.queryByTestId("grading-closed-notice")).not.toBeInTheDocument();
  });
});

describe("GradingPage — OPT-15 cola del corrector", () => {
  beforeEach(() => {
    mockedUseECOE.mockReturnValue({
      authenticated: true,
      eventId: 1,
      ecoeEvent: { id: 1, status: "en_ejecucion" },
    } as never);
  });

  it("empty-state diferenciado cuando el corrector no tiene estaciones asignadas", async () => {
    mockedApi.gradingList.mockResolvedValue(
      emptyList({
        scope: { is_corrector: true, has_assignment: false, assigned_station_ids: [] },
      }) as never,
    );

    render(<GradingPage />);

    expect(
      await screen.findByText("No tenés estaciones asignadas para corregir"),
    ).toBeInTheDocument();
  });

  it("autoavanza a la siguiente fila pendiente sin volver a pedir la lista", async () => {
    mockedApi.gradingList.mockResolvedValue({
      responses: [pendingRow(1), pendingRow(2)],
      pending_count: 2,
      scope: OPEN_SCOPE,
      pending_by_station: {
        "7": { station_number: 3, station_name: "Informe", pending: 2, total: 2 },
      },
    } as never);
    mockedApi.gradeResponse.mockResolvedValue({
      graded: true,
      response_id: 1,
      score_obtained: 5,
      max_score: 6,
      next: { response_id: 2 },
      pending_remaining: 1,
    } as never);

    render(<GradingPage />);

    fireEvent.click((await screen.findAllByRole("button", { name: "Corregir" }))[0]);
    fireEvent.change(screen.getByRole("spinbutton"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar corrección" }));

    await waitFor(() => expect(mockedApi.gradeResponse).toHaveBeenCalledWith(1, { question_1: 5 }));
    // La lista solo se pidió al montar: el autoavance no re-fetchea.
    expect(mockedApi.gradingList).toHaveBeenCalledTimes(1);
    // La fila 2 quedó abierta (su input de puntaje visible) y la 1 pasó a corregidas.
    await waitFor(() => expect(screen.getByRole("spinbutton")).toBeInTheDocument());
    expect(screen.getByText("5 / 6 pts")).toBeInTheDocument();
  });

  it("muestra el panel de pauta solo cuando la fila trae assessment_tool", async () => {
    mockedApi.gradingList.mockResolvedValue({
      responses: [
        pendingRow(1, {
          assessment_tool: {
            id: 9,
            name: "Pauta informe",
            tool_type: "checklist",
            max_score: 6,
            free_observation: true,
            items: [
              { id: 1, label: "Identifica el ritmo", score_per_item: 3, order_index: 0 },
              { id: 2, label: "Propone manejo", score_per_item: 3, order_index: 1 },
            ],
          },
        }),
        pendingRow(2),
      ],
      pending_count: 2,
      scope: OPEN_SCOPE,
      pending_by_station: {
        "7": { station_number: 3, station_name: "Informe", pending: 2, total: 2 },
      },
    } as never);

    render(<GradingPage />);

    const buttons = await screen.findAllByRole("button", { name: "Corregir" });
    fireEvent.click(buttons[0]);
    expect(await screen.findByTestId("grading-rubric-panel")).toBeInTheDocument();
    expect(screen.getByText("Identifica el ritmo")).toBeInTheDocument();

    // Abre la fila 2 (sin pauta): solo una fila expandida a la vez, el panel desaparece.
    fireEvent.click(screen.getByRole("button", { name: "Corregir" }));
    expect(screen.queryByTestId("grading-rubric-panel")).not.toBeInTheDocument();
  });
});
