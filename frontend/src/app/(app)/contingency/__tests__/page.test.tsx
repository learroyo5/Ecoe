import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ContingencyPage from "../page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    stations: vi.fn(),
    students: vi.fn(),
    contingencyStudentResponse: vi.fn(),
    finalizeEvaluatorRecord: vi.fn(),
    rectifyEvaluatorRecord: vi.fn(),
  },
}));
vi.mock("@/lib/auth", () => ({
  useECOE: () => ({ authenticated: true, eventId: 1, user: { full_name: "Coord" } }),
}));

const mockedApi = vi.mocked(api);

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.stations.mockResolvedValue([
    {
      id: 2, station_number: 2, name: "ECG", max_score: 20,
      requires_student_form: true, requires_evaluator: true,
      student_form_definition: { questions: [{ type: "single_choice", label: "Dx", options: ["SCA", "TEP"] }] },
    },
  ] as never);
  mockedApi.students.mockResolvedValue({
    items: [{ id: 7, ecoe_number: "E007", name: "Ana", last_name: "Pérez" }],
  } as never);
  mockedApi.contingencyStudentResponse.mockResolvedValue({ saved: true } as never);
  mockedApi.rectifyEvaluatorRecord.mockResolvedValue({ saved: true } as never);
});

async function pickTarget(number = "7") {
  render(<ContingencyPage />);
  await screen.findByRole("option", { name: "2 · ECG" });
  await userEvent.selectOptions(screen.getByRole("combobox"), "2");
  await userEvent.type(screen.getByPlaceholderText("Ejemplo: E007"), number);
}

describe("Contingencia", () => {
  it("resuelve al estudiante por número sin importar el formato y envía la respuesta", async () => {
    await pickTarget("7");
    expect(await screen.findByText("E007 · Ana Pérez")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("SCA"));
    await userEvent.click(screen.getByRole("button", { name: "Registrar respuesta del estudiante" }));
    await waitFor(() =>
      expect(mockedApi.contingencyStudentResponse).toHaveBeenCalledWith({
        ecoe_event_id: 1, station_id: 2, student_id: 7, answers: { question_1: "SCA" },
      }),
    );
  });

  it("no ofrece ningún formulario si el número no corresponde a un estudiante", async () => {
    await pickTarget("99");
    expect(await screen.findByText("No hay un estudiante con ese número en este ECOE.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Registrar respuesta del estudiante" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Registrar evaluación" })).toBeNull();
  });

  it("no deja rectificar sin motivo", async () => {
    await pickTarget("E007");
    await screen.findByText("E007 · Ana Pérez");
    await userEvent.type(screen.getByRole("spinbutton"), "12");
    const rectify = screen.getByRole("button", { name: "Rectificar evaluación enviada" });
    expect(rectify).toBeDisabled();
    await userEvent.type(screen.getByPlaceholderText(/puntaje mal digitado/), "Puntaje mal digitado en la tablet");
    expect(rectify).toBeEnabled();
    await userEvent.click(rectify);
    await waitFor(() =>
      expect(mockedApi.rectifyEvaluatorRecord).toHaveBeenCalledWith(
        expect.objectContaining({ student_id: 7, score_obtained: 12, reason: "Puntaje mal digitado en la tablet" }),
      ),
    );
  });
});
