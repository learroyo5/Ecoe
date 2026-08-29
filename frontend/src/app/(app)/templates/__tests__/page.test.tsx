import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TemplatesPage from "@/app/(app)/templates/page";
import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";

vi.mock("@/lib/auth", () => ({ useECOE: vi.fn() }));

vi.mock("@/lib/api", () => ({
  api: {
    templates: vi.fn(),
    createTemplate: vi.fn(),
    updateTemplate: vi.fn(),
    archiveTemplate: vi.fn(),
    restoreTemplate: vi.fn(),
    purgeTemplate: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);
const mockedUseECOE = vi.mocked(useECOE);

const TEMPLATE_IN_USE = {
  id: 10, name: "Estación híbrida", category: "hibrida", description: "d",
  default_configuration: { requires_evaluator: true }, archived: false, reference_count: 2,
};
const TEMPLATE_FREE = {
  id: 11, name: "Estación libre", category: "procedimental", description: "d",
  default_configuration: {}, archived: false, reference_count: 0,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedUseECOE.mockReturnValue({
    authenticated: true, eventId: 1, eventRoles: ["admin_ecoe"],
    user: { role: "admin_ecoe" },
  } as never);
  mockedApi.templates.mockResolvedValue([TEMPLATE_IN_USE, TEMPLATE_FREE] as never);
});

describe("TemplatesPage — CRUD real (OPT-7b)", () => {
  it("lista plantillas con su uso", async () => {
    render(<TemplatesPage />);
    expect(await screen.findByText("Estación híbrida")).toBeInTheDocument();
    expect(screen.getByText("En uso por 2")).toBeInTheDocument();
  });

  it("solo ofrece «Purgar» cuando reference_count es 0", async () => {
    render(<TemplatesPage />);
    await screen.findByText("Estación híbrida");
    expect(screen.getAllByRole("button", { name: "Purgar" })).toHaveLength(1);
  });

  it("archivar recarga la lista sin la plantilla archivada", async () => {
    mockedApi.archiveTemplate.mockResolvedValue({} as never);
    mockedApi.templates
      .mockResolvedValueOnce([TEMPLATE_IN_USE, TEMPLATE_FREE] as never)
      .mockResolvedValueOnce([TEMPLATE_IN_USE] as never);

    render(<TemplatesPage />);
    await screen.findByText("Estación libre");
    fireEvent.click(screen.getAllByRole("button", { name: "Archivar" })[1]);

    await waitFor(() => expect(mockedApi.archiveTemplate).toHaveBeenCalledWith(1, 11));
    await waitFor(() => expect(screen.queryByText("Estación libre")).not.toBeInTheDocument());
  });

  it("editar envía un PATCH con los campos del borrador", async () => {
    mockedApi.updateTemplate.mockResolvedValue({} as never);
    render(<TemplatesPage />);
    await screen.findByText("Estación híbrida");

    fireEvent.click(screen.getAllByRole("button", { name: "Editar" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(mockedApi.updateTemplate).toHaveBeenCalled());
    const [, id, payload] = mockedApi.updateTemplate.mock.calls[0];
    expect(id).toBe(10);
    expect((payload as { name: string }).name).toBe("Estación híbrida");
  });
});
