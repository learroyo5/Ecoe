import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import KiosksPage from "../page";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({ api: { stations: vi.fn(), issueKioskToken: vi.fn() } }));
vi.mock("@/lib/auth", () => ({ useECOE: () => ({ authenticated: true, eventId: 1 }) }));

const mockedApi = vi.mocked(api);

const STATIONS = [
  { id: 1, station_number: 1, name: "Anamnesis", circuit_name: "A" },
  { id: 2, station_number: 2, name: "ECG", circuit_name: "A", requires_student_form: true },
  { id: 3, station_number: 3, name: "Radiografía", circuit_name: "A", uses_multimedia: true },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.stations.mockResolvedValue(STATIONS as never);
  mockedApi.issueKioskToken.mockImplementation(async (stationId: number) => ({
    token: `t${stationId}`,
    kiosk_path: `/kiosk?token=t${stationId}`,
    expires_at: "2026-11-23T20:00:00",
  }));
});

describe("Kioscos", () => {
  it("lista sólo las estaciones que necesitan kiosco", async () => {
    render(<KiosksPage />);
    expect(await screen.findByText("ECG")).toBeInTheDocument();
    expect(screen.getByText("Radiografía")).toBeInTheDocument();
    expect(screen.queryByText("Anamnesis")).toBeNull();
    expect(screen.getByText(/1 estación no necesita kiosco/)).toBeInTheDocument();
  });

  it("no emite ningún enlace si se cancela la confirmación", async () => {
    const native = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(<KiosksPage />);
    await screen.findByText("ECG");
    await userEvent.click(screen.getByRole("button", { name: "Generar todos los enlaces" }));
    expect(mockedApi.issueKioskToken).not.toHaveBeenCalled();
    native.mockRestore();
  });

  it("genera todos los enlaces de una vez y los muestra por estación", async () => {
    const native = vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<KiosksPage />);
    await screen.findByText("ECG");
    await userEvent.click(screen.getByRole("button", { name: "Generar todos los enlaces" }));
    await waitFor(() => expect(mockedApi.issueKioskToken).toHaveBeenCalledTimes(2));
    expect(mockedApi.issueKioskToken.mock.calls.map((call) => call[0])).toEqual([2, 3]);
    expect(await within(screen.getByTestId("kiosk-station-2")).findByText(/\/kiosk\?token=t2$/)).toBeInTheDocument();
    expect(within(screen.getByTestId("kiosk-station-3")).getByText(/\/kiosk\?token=t3$/)).toBeInTheDocument();
    expect(screen.getByText(/Se generaron 2 enlaces/)).toBeInTheDocument();
    native.mockRestore();
  });

  it("informa la estación que falló sin ocultar las que sí se generaron", async () => {
    const native = vi.spyOn(window, "confirm").mockReturnValue(true);
    mockedApi.issueKioskToken.mockImplementation(async (stationId: number) => {
      if (stationId === 3) throw new Error("No autorizado");
      return { token: "t2", kiosk_path: "/kiosk?token=t2", expires_at: "2026-11-23T20:00:00" };
    });
    render(<KiosksPage />);
    await screen.findByText("ECG");
    await userEvent.click(screen.getByRole("button", { name: "Generar todos los enlaces" }));
    expect(await within(screen.getByTestId("kiosk-station-3")).findByRole("alert")).toHaveTextContent("No autorizado");
    expect(within(screen.getByTestId("kiosk-station-2")).getByText(/token=t2$/)).toBeInTheDocument();
    expect(screen.getByText(/Se generaron 1 de 2 enlaces/)).toBeInTheDocument();
    native.mockRestore();
  });
});
