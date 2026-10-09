import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ECOEPage from "../page";
import ECOEDetailRedirect from "../[id]/page";
import { api } from "@/lib/api";

const setEventId = vi.fn();
const refreshECOE = vi.fn().mockResolvedValue(undefined);
const replace = vi.fn();
let routeId = "7";
let eventRoles: string[] = ["admin_ecoe"];

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({ id: routeId }),
  useRouter: () => ({ replace, push: vi.fn() }),
}));

vi.mock("@/lib/auth", () => ({
  useECOE: () => ({
    ready: true,
    authenticated: true,
    eventId: 1,
    setEventId,
    refreshECOE,
    user: { role: "miembro" },
    eventRoles,
  }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    listECOE: vi.fn(),
    ecoe: vi.fn(),
    validation: vi.fn(),
    psychometrics: vi.fn(),
    updateECOE: vi.fn(),
    createECOE: vi.fn(),
    duplicateECOE: vi.fn(),
    stations: vi.fn(),
    students: vi.fn(),
    staff: vi.fn(),
    pilotage: vi.fn(),
  },
}));

const mockedApi = vi.mocked(api);

const EVENT = {
  id: 1,
  name: "ECOE Medicina",
  date: "2026-11-23",
  course_name: "Medicina Interna",
  school_name: "Escuela de Medicina",
  responsible_teacher: "Dra. Demo",
  contact_email: "demo@ecoe.cl",
  circuit_mode: "secuencial",
  station_time_minutes: 8,
  transition_time_minutes: 2,
  inter_round_pause_minutes: 5,
  total_groups: 1,
  passing_reference_percent: 60,
  status: "en_configuracion",
};

beforeEach(() => {
  vi.clearAllMocks();
  routeId = "7";
  eventRoles = ["admin_ecoe"];
  mockedApi.listECOE.mockResolvedValue([EVENT] as never);
  mockedApi.ecoe.mockResolvedValue(EVENT as never);
  mockedApi.validation.mockResolvedValue({} as never);
  mockedApi.stations.mockResolvedValue([
    { id: 3, station_number: 1, name: "Anamnesis", station_type: "paciente_simulado", circuit_name: "A", max_score: 20, status: "en_diseno" },
  ] as never);
  mockedApi.students.mockResolvedValue({ items: [] } as never);
  mockedApi.staff.mockResolvedValue({ items: [] } as never);
  mockedApi.pilotage.mockResolvedValue([] as never);
});

describe("Datos del ECOE", () => {
  it("abre en General con la barra de estado y sin el formulario de creación a la vista", async () => {
    render(<ECOEPage />);
    expect(await screen.findByRole("button", { name: "Guardar ECOE" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "General" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("En configuración")).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Crear nuevo ECOE" })).toBeNull();
  });

  it("la pestaña Estaciones muestra el resumen con etiquetas legibles y enlace de gestión", async () => {
    render(<ECOEPage />);
    await screen.findByRole("button", { name: "Guardar ECOE" });
    await userEvent.click(screen.getByRole("tab", { name: "Estaciones" }));
    expect(await screen.findByText("Anamnesis")).toBeInTheDocument();
    expect(screen.getByText("Paciente simulado")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Gestionar estaciones/ })).toHaveAttribute("href", "/stations");
    expect(screen.queryByRole("button", { name: "Guardar ECOE" })).toBeNull();
  });

  it("crear un ECOE se hace en un diálogo y valida antes de enviar", async () => {
    mockedApi.createECOE.mockResolvedValue({ ...EVENT, id: 9, name: "Nuevo", status: "borrador" } as never);
    render(<ECOEPage />);
    await screen.findByRole("button", { name: "Guardar ECOE" });
    await userEvent.click(screen.getByRole("button", { name: "+ Nuevo ECOE" }));
    const dialog = screen.getByRole("dialog", { name: "Crear nuevo ECOE" });
    expect(dialog).toBeInTheDocument();
    // Vacío no envía: valida antes de llamar a la API.
    await userEvent.click(screen.getByRole("button", { name: "Crear ECOE" }));
    expect(mockedApi.createECOE).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Crear nuevo ECOE" })).toBeInTheDocument();
  });

  it("tras una transición de estado refresca el contexto que alimenta la barra del shell", async () => {
    mockedApi.updateECOE.mockResolvedValue({ ...EVENT, status: "listo_para_pilotaje" } as never);
    render(<ECOEPage />);
    await screen.findByRole("button", { name: "Guardar ECOE" });
    await userEvent.click(screen.getByRole("button", { name: "Listo para pilotaje" }));
    const buttons = screen.getAllByRole("button", { name: "Listo para pilotaje" });
    await userEvent.click(buttons[buttons.length - 1]);
    await waitFor(() => expect(refreshECOE).toHaveBeenCalled());
    expect(mockedApi.updateECOE).toHaveBeenCalledWith(1, expect.objectContaining({ status: "listo_para_pilotaje" }));
    expect(await screen.findByText("ECOE ahora en estado: Listo para pilotaje")).toBeInTheDocument();
  });

  it("no permite duplicar a quien no tiene el permiso", async () => {
    eventRoles = ["coordinador_operativo"];
    render(<ECOEPage />);
    await screen.findByRole("button", { name: "Guardar ECOE" });
    expect(screen.getByRole("button", { name: "Duplicar ECOE" })).toBeDisabled();
  });
});

describe("/ecoe/[id]", () => {
  it("selecciona el ECOE de la URL y redirige a Datos del ECOE", async () => {
    render(<ECOEDetailRedirect />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/ecoe"));
    expect(setEventId).toHaveBeenCalledWith(7);
  });

  it("con un id inválido redirige sin cambiar el ECOE activo", async () => {
    routeId = "abc";
    render(<ECOEDetailRedirect />);
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/ecoe"));
    expect(setEventId).not.toHaveBeenCalled();
  });
});
