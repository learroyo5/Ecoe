import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import InstrumentsPage from "@/app/(app)/instruments/page";
import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";

vi.mock("@/lib/auth", () => ({ useECOE: vi.fn() }));

vi.mock("@/lib/api", () => ({
  api: {
    instruments: vi.fn(),
    updateInstrument: vi.fn(),
    archiveInstrument: vi.fn(),
    restoreInstrument: vi.fn(),
    purgeInstrument: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);
const mockedUseECOE = vi.mocked(useECOE);

const TOOL_IN_USE = {
  id: 10, name: "Pauta dolor torácico", tool_type: "lista_cotejo",
  max_score: 6, free_observation: true, archived: false, reference_count: 3,
  items: [{ id: 1, label: "A", score_per_item: 3, order_index: 1 }],
};
const TOOL_FREE = {
  id: 11, name: "Pauta libre", tool_type: "rubrica_simple",
  max_score: 4, free_observation: true, archived: false, reference_count: 0,
  items: [{ id: 2, label: "B", score_per_item: 4, order_index: 1 }],
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedUseECOE.mockReturnValue({
    authenticated: true, eventId: 1, eventRoles: ["admin_ecoe"],
    user: { role: "admin_ecoe" },
  } as never);
  mockedApi.instruments.mockResolvedValue([TOOL_IN_USE, TOOL_FREE] as never);
});

describe("InstrumentsPage — CRUD real (OPT-7)", () => {
  it("lista instrumentos con su uso y estado", async () => {
    render(<InstrumentsPage />);
    expect(await screen.findByText("Pauta dolor torácico")).toBeInTheDocument();
    expect(screen.getByText("En uso por 3")).toBeInTheDocument();
    expect(screen.getAllByText("Activa").length).toBeGreaterThan(0);
  });

  it("solo ofrece «Purgar» cuando reference_count es 0", async () => {
    render(<InstrumentsPage />);
    await screen.findByText("Pauta dolor torácico");
    // Un único botón Purgar, el de la pauta sin uso.
    const purgeButtons = screen.getAllByRole("button", { name: "Purgar" });
    expect(purgeButtons).toHaveLength(1);
  });

  it("archivar recarga la lista sin el instrumento archivado", async () => {
    mockedApi.archiveInstrument.mockResolvedValue({} as never);
    mockedApi.instruments
      .mockResolvedValueOnce([TOOL_IN_USE, TOOL_FREE] as never)
      .mockResolvedValueOnce([TOOL_IN_USE] as never);

    render(<InstrumentsPage />);
    await screen.findByText("Pauta libre");
    fireEvent.click(screen.getAllByRole("button", { name: "Archivar" })[1]);

    await waitFor(() => expect(mockedApi.archiveInstrument).toHaveBeenCalledWith(1, 11));
    await waitFor(() => expect(screen.queryByText("Pauta libre")).not.toBeInTheDocument());
  });

  it("editar envía un PATCH con los ids de criterio preservados", async () => {
    mockedApi.updateInstrument.mockResolvedValue({} as never);
    render(<InstrumentsPage />);
    await screen.findByText("Pauta dolor torácico");

    fireEvent.click(screen.getAllByRole("button", { name: "Editar" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(mockedApi.updateInstrument).toHaveBeenCalled());
    const [, toolId, payload] = mockedApi.updateInstrument.mock.calls[0];
    expect(toolId).toBe(10);
    expect((payload as { items: { id?: number }[] }).items[0].id).toBe(1);
  });
});
