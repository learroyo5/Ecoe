import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EvaluatorsPage from "@/app/(app)/evaluators/page";
import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";

vi.mock("@/lib/auth", () => ({
  useECOE: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    staff: vi.fn(),
    stations: vi.fn(),
    updateStaff: vi.fn(),
    deleteStaff: vi.fn(),
    resetEventMemberAccess: vi.fn(),
    deduplicateStaffByEmail: vi.fn(),
    importStaff: vi.fn(),
    inviteEventMember: vi.fn(),
    lookupEventMember: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);
const mockedUseECOE = vi.mocked(useECOE);

const STATIONS = [
  { id: 1, station_number: 1, name: "Anamnesis" },
  { id: 2, station_number: 2, name: "Examen físico" },
  { id: 3, station_number: 3, name: "Informe" },
];

function corrector(overrides = {}) {
  return {
    id: 42,
    name: "Carla",
    last_name: "Correctora",
    email: "carla@example.edu",
    role_code: "corrector",
    station_ids: [1],
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockedUseECOE.mockReturnValue({
    authenticated: true,
    eventId: 1,
    eventRoles: ["admin_ecoe"],
    user: { role: "admin_ecoe" },
  } as never);
  mockedApi.stations.mockResolvedValue(STATIONS as never);
  mockedApi.updateStaff.mockResolvedValue({} as never);
});

describe("EvaluatorsPage — reasignar correctores in-place (OPT-15b)", () => {
  it("muestra un multi-select y guarda con station_ids array", async () => {
    mockedApi.staff.mockResolvedValue({ items: [corrector()] } as never);

    render(<EvaluatorsPage />);

    const select = await screen.findByRole("listbox", {
      name: "Estaciones de corrección diferida",
    });
    // Parte de [1] (su asignación actual) y suma 2 y 3.
    await userEvent.selectOptions(select, ["2", "3"]);

    const row = select.closest("div") as HTMLElement;
    fireEvent.click(within(row).getByRole("button", { name: "Guardar" }));

    await waitFor(() =>
      expect(mockedApi.updateStaff).toHaveBeenCalledWith(42, {
        role_code: "corrector",
        station_ids: [1, 2, 3],
      }),
    );
  });

  it("deshabilita Guardar cuando no hay estaciones seleccionadas", async () => {
    mockedApi.staff.mockResolvedValue({ items: [corrector({ station_ids: [] })] } as never);

    render(<EvaluatorsPage />);

    const select = await screen.findByRole("listbox", {
      name: "Estaciones de corrección diferida",
    });
    const row = select.closest("div") as HTMLElement;
    expect(within(row).getByRole("button", { name: "Guardar" })).toBeDisabled();
  });
});
