import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import StationsPage from "../page";
import { api } from "@/lib/api";

let status = "en_configuracion";

vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn(), push: vi.fn() }) }));
vi.mock("@/lib/auth", () => ({
  useECOE: () => ({
    authenticated: true, eventId: 1, user: { role: "admin_global" },
    eventRoles: ["admin_ecoe"], eventRolesLoaded: true, ecoeEvent: { status },
  }),
}));
vi.mock("@/lib/api", () => ({
  api: {
    stations: vi.fn(), validation: vi.fn(), mirrorCircuit: vi.fn(),
    deleteMirrorCircuit: vi.fn(), issueKioskToken: vi.fn(), deleteStation: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const ORIGINALS = [
  { id: 1, station_number: 1, name: "Anamnesis", circuit_name: "Circuito A", station_type: "procedimental", status: "en_diseno", max_score: 20 },
  { id: 2, station_number: 2, name: "ECG", circuit_name: "Circuito A", station_type: "procedimental", status: "en_diseno", max_score: 20 },
];
const WITH_MIRROR = [
  ...ORIGINALS,
  { id: 3, station_number: 3, name: "Anamnesis", circuit_name: "Circuito B", mirror_of_id: 1, station_type: "procedimental", status: "en_diseno", max_score: 20 },
  { id: 4, station_number: 4, name: "ECG", circuit_name: "Circuito B", mirror_of_id: 2, station_type: "procedimental", status: "en_diseno", max_score: 20 },
];

beforeEach(() => {
  vi.clearAllMocks();
  status = "en_configuracion";
  mockedApi.stations.mockResolvedValue(ORIGINALS as never);
  mockedApi.validation.mockResolvedValue({ mirror_issues: [] } as never);
});

describe("Estaciones — circuitos espejo", () => {
  it("explica que se diseña una vez y crea el espejo desde un diálogo", async () => {
    mockedApi.mirrorCircuit.mockResolvedValue(WITH_MIRROR as never);
    render(<StationsPage />);
    expect(await screen.findByText(/Diseña las estaciones/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Crear circuito espejo" }));
    const dialog = screen.getByRole("dialog", { name: "Crear circuito espejo" });
    expect(within(dialog).getByDisplayValue("Circuito B")).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Crear circuito espejo" }));
    await waitFor(() =>
      expect(mockedApi.mirrorCircuit).toHaveBeenCalledWith(1, {
        source_circuit: "Circuito A", mirror_circuit: "Circuito B",
      }),
    );
    expect(await screen.findByTestId("circuit-Circuito B")).toBeInTheDocument();
  });

  it("una estación espejo muestra el número de su original y no ofrece editarla ni eliminarla", async () => {
    mockedApi.stations.mockResolvedValue(WITH_MIRROR as never);
    render(<StationsPage />);
    const mirrorCircuit = within(await screen.findByTestId("circuit-Circuito B"));
    expect(mirrorCircuit.getByText(/espejo de Circuito A/)).toBeInTheDocument();
    expect(mirrorCircuit.getAllByText("Espejo")).toHaveLength(2);
    expect(mirrorCircuit.queryByRole("link", { name: "Editar" })).toBeNull();
    expect(mirrorCircuit.queryByRole("button", { name: "Eliminar" })).toBeNull();
    const links = mirrorCircuit.getAllByRole("link", { name: "Editar la original" });
    expect(links[0]).toHaveAttribute("href", "/stations/builder?stationId=1");
    // El circuito original conserva sus acciones.
    const originalCircuit = within(screen.getByTestId("circuit-Circuito A"));
    expect(originalCircuit.getAllByRole("link", { name: "Editar" })).toHaveLength(2);
    // Ya no se sugiere crear un espejo como primer paso.
    expect(screen.queryByText(/Diseña las estaciones/)).toBeNull();
  });

  it("muestra por qué los circuitos no son espejo exacto", async () => {
    mockedApi.stations.mockResolvedValue(WITH_MIRROR as never);
    mockedApi.validation.mockResolvedValue({
      mirror_issues: ["A «Circuito B» le faltan estaciones espejo: 3. Sutura. Usa «Sincronizar espejo»."],
    } as never);
    render(<StationsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("faltan estaciones espejo");
  });

  it("con el ECOE publicado no se puede crear ni sincronizar el espejo", async () => {
    status = "publicado";
    mockedApi.stations.mockResolvedValue(WITH_MIRROR as never);
    render(<StationsPage />);
    const mirrorCircuit = within(await screen.findByTestId("circuit-Circuito B"));
    expect(mirrorCircuit.getByRole("button", { name: "Sincronizar espejo" })).toBeDisabled();
    expect(mirrorCircuit.getByRole("button", { name: "Eliminar circuito espejo" })).toBeDisabled();
  });
});
