import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SimulatedPatientPage from "@/app/(app)/simulated-patient/page";
import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";

vi.mock("@/lib/auth", () => ({ useECOE: vi.fn() }));

vi.mock("@/lib/api", () => ({
  api: {
    simulatedPatients: vi.fn(),
    createSimulatedPatient: vi.fn(),
    updateSimulatedPatient: vi.fn(),
    archiveSimulatedPatient: vi.fn(),
    restoreSimulatedPatient: vi.fn(),
    purgeSimulatedPatient: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);
const mockedUseECOE = vi.mocked(useECOE);

const PATIENT_IN_USE = {
  id: 20, character_name: "Sra. Díaz", summary_profile: "dolor abdominal",
  base_story: "b", key_answers: "k", emotional_tone: "ansiosa",
  special_instructions: "i", archived: false, reference_count: 1,
};
const PATIENT_FREE = {
  id: 21, character_name: "Sr. Rojas", summary_profile: "cefalea",
  base_story: "b", key_answers: "k", emotional_tone: "tranquilo",
  special_instructions: "i", archived: false, reference_count: 0,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedUseECOE.mockReturnValue({
    authenticated: true, eventId: 1, eventRoles: ["admin_ecoe"],
    user: { role: "admin_ecoe" },
  } as never);
  mockedApi.simulatedPatients.mockResolvedValue([PATIENT_IN_USE, PATIENT_FREE] as never);
});

describe("SimulatedPatientPage — CRUD real (OPT-7b)", () => {
  it("lista fichas con su uso", async () => {
    render(<SimulatedPatientPage />);
    expect(await screen.findByText("Sra. Díaz")).toBeInTheDocument();
    expect(screen.getByText("En uso por 1")).toBeInTheDocument();
  });

  it("solo ofrece «Purgar» cuando reference_count es 0", async () => {
    render(<SimulatedPatientPage />);
    await screen.findByText("Sra. Díaz");
    expect(screen.getAllByRole("button", { name: "Purgar" })).toHaveLength(1);
  });

  it("archivar recarga la lista sin la ficha archivada", async () => {
    mockedApi.archiveSimulatedPatient.mockResolvedValue({} as never);
    mockedApi.simulatedPatients
      .mockResolvedValueOnce([PATIENT_IN_USE, PATIENT_FREE] as never)
      .mockResolvedValueOnce([PATIENT_IN_USE] as never);

    render(<SimulatedPatientPage />);
    await screen.findByText("Sr. Rojas");
    fireEvent.click(screen.getAllByRole("button", { name: "Archivar" })[1]);

    await waitFor(() => expect(mockedApi.archiveSimulatedPatient).toHaveBeenCalledWith(1, 21));
    await waitFor(() => expect(screen.queryByText("Sr. Rojas")).not.toBeInTheDocument());
  });

  it("editar envía un PATCH con el borrador de la ficha", async () => {
    mockedApi.updateSimulatedPatient.mockResolvedValue({} as never);
    render(<SimulatedPatientPage />);
    await screen.findByText("Sra. Díaz");

    fireEvent.click(screen.getAllByRole("button", { name: "Editar" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));

    await waitFor(() => expect(mockedApi.updateSimulatedPatient).toHaveBeenCalled());
    const [, id, payload] = mockedApi.updateSimulatedPatient.mock.calls[0];
    expect(id).toBe(20);
    expect((payload as { character_name: string }).character_name).toBe("Sra. Díaz");
  });
});
