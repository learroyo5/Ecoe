import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import StationBuilderPage from "@/app/(app)/stations/builder/page";
import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";

// ── Mocks ──────────────────────────────────────────────────────────────

let currentSearch = "";
const replaceMock = vi.fn();

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(currentSearch),
  useRouter: () => ({ replace: replaceMock, push: vi.fn(), prefetch: vi.fn() }),
}));

vi.mock("@/lib/auth", () => ({ useECOE: vi.fn() }));

vi.mock("@/lib/api", () => ({
  api: {
    templates: vi.fn(),
    instruments: vi.fn(),
    instrument: vi.fn(),
    createInstrument: vi.fn(),
    updateInstrument: vi.fn(),
    stations: vi.fn(),
    stationBank: vi.fn(),
    simulatedPatients: vi.fn(),
    media: vi.fn(),
    updateStation: vi.fn(),
    createStation: vi.fn(),
    createStationBank: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);
const mockedUseECOE = vi.mocked(useECOE);

// jsdom no implementa scrollIntoView; el efecto de scroll del stepper lo llama.
window.HTMLElement.prototype.scrollIntoView = vi.fn();

const TOOL = {
  id: 10,
  name: "Pauta dolor torácico",
  tool_type: "lista_cotejo",
  max_score: 6,
  free_observation: true,
  archived: false,
  reference_count: 2,
  items: [
    { id: 1, label: "Criterio A", score_per_item: 3, order_index: 1 },
    { id: 2, label: "Criterio B", score_per_item: 3, order_index: 2 },
  ],
};

const STATION = {
  id: 5,
  station_number: 3,
  name: "Estación con pauta",
  station_type: "procedimental",
  circuit_name: "Circuito A",
  expected_outcomes: "x",
  student_activity: "y",
  assessment_tool_id: 10,
  requires_evaluator: true,
  requires_student_form: false,
  requires_deferred_grading: false,
  uses_multimedia: false,
  uses_simulated_patient: false,
  max_score: 6,
  status: "en_diseno",
  student_form_definition: { questions: [] },
};

function mockAuth() {
  mockedUseECOE.mockReturnValue({
    authenticated: true,
    eventId: 1,
    user: { role: "admin_ecoe" },
    eventRoles: ["admin_ecoe"],
    eventRolesLoaded: true,
  } as never);
}

beforeEach(() => {
  vi.clearAllMocks();
  currentSearch = "";
  mockAuth();
  mockedApi.templates.mockResolvedValue([] as never);
  mockedApi.instruments.mockResolvedValue([TOOL] as never);
  mockedApi.instrument.mockResolvedValue(TOOL as never);
  mockedApi.stations.mockResolvedValue([STATION] as never);
  mockedApi.stationBank.mockResolvedValue([] as never);
  mockedApi.simulatedPatients.mockResolvedValue([] as never);
  mockedApi.media.mockResolvedValue([] as never);
});

async function openEvaluationSection() {
  fireEvent.click(await screen.findByRole("button", { name: /Evaluación y puntaje/ }));
}

describe("Constructor · editar pauta en sitio (OPT-7c)", () => {
  it("al abrir una estación con assessment_tool_id carga los ítems del tool", async () => {
    currentSearch = "stationId=5";
    render(<StationBuilderPage />);

    await waitFor(() => expect(mockedApi.instrument).toHaveBeenCalledWith(1, 10));

    await openEvaluationSection();
    fireEvent.click(await screen.findByRole("button", { name: "Editar esta pauta" }));

    expect(screen.getByDisplayValue("Criterio A")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Criterio B")).toBeInTheDocument();
    // Aviso de referencias múltiples.
    expect(screen.getByText(/la usan 2 estaciones o eventos/i)).toBeInTheDocument();
  });

  it("modo \"edit\" hace PATCH preservando los id de ítem y no hace POST", async () => {
    currentSearch = "stationId=5";
    mockedApi.updateInstrument.mockResolvedValue({ ...TOOL } as never);
    render(<StationBuilderPage />);
    await waitFor(() => expect(mockedApi.instrument).toHaveBeenCalled());

    await openEvaluationSection();
    fireEvent.click(await screen.findByRole("button", { name: "Editar esta pauta" }));

    fireEvent.change(screen.getByDisplayValue("Criterio A"), {
      target: { value: "Criterio A corregido" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios en la pauta" }));

    await waitFor(() => expect(mockedApi.updateInstrument).toHaveBeenCalledTimes(1));
    expect(mockedApi.createInstrument).not.toHaveBeenCalled();

    const [eventId, toolId, payload] = mockedApi.updateInstrument.mock.calls[0];
    expect(eventId).toBe(1);
    expect(toolId).toBe(10);
    const items = (payload as { items: { id?: number; label: string }[] }).items;
    expect(items.map((i) => i.id)).toEqual([1, 2]);
    expect(items[0].label).toBe("Criterio A corregido");
  });

  it("un 409 al guardar en modo edit ofrece «guardar como copia» (POST sin id)", async () => {
    currentSearch = "stationId=5";
    mockedApi.updateInstrument.mockRejectedValue(
      Object.assign(new Error("La pauta pertenece a un ECOE ya piloteado."), { status: 409 }),
    );
    mockedApi.createInstrument.mockResolvedValue({ ...TOOL, id: 99 } as never);
    render(<StationBuilderPage />);
    await waitFor(() => expect(mockedApi.instrument).toHaveBeenCalled());

    await openEvaluationSection();
    fireEvent.click(await screen.findByRole("button", { name: "Editar esta pauta" }));
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios en la pauta" }));

    expect(
      await screen.findByText(/La pauta pertenece a un ECOE ya piloteado/i),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Guardar como copia nueva" }));

    await waitFor(() => expect(mockedApi.createInstrument).toHaveBeenCalledTimes(1));
    const [, payload] = mockedApi.createInstrument.mock.calls[0];
    const items = (payload as { items: { id?: number }[] }).items;
    expect(items.every((i) => i.id === undefined)).toBe(true);
  });

  it("modo \"create\" sigue haciendo POST de una pauta nueva", async () => {
    currentSearch = "";
    mockedApi.stations.mockResolvedValue([] as never);
    mockedApi.createInstrument.mockResolvedValue({ id: 50, name: "Nueva", items: [] } as never);
    render(<StationBuilderPage />);

    await openEvaluationSection();
    fireEvent.click(screen.getByRole("button", { name: "Crear pauta en esta estación" }));

    fireEvent.change(
      screen.getByPlaceholderText("Ejemplo: Lista de cotejo - dolor torácico"),
      { target: { value: "Lista nueva" } },
    );
    fireEvent.change(
      screen.getAllByPlaceholderText(
        "Ejemplo: Identifica signos de alarma al inicio de la entrevista",
      )[0],
      { target: { value: "Primer criterio" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Guardar pauta" }));

    await waitFor(() => expect(mockedApi.createInstrument).toHaveBeenCalledTimes(1));
    expect(mockedApi.updateInstrument).not.toHaveBeenCalled();
  });

  it("no ofrece «Editar esta pauta» cuando la estación no referencia ninguna", async () => {
    currentSearch = "";
    mockedApi.stations.mockResolvedValue([] as never);
    render(<StationBuilderPage />);
    await openEvaluationSection();

    expect(
      screen.queryByRole("button", { name: "Editar esta pauta" }),
    ).not.toBeInTheDocument();
  });
});
