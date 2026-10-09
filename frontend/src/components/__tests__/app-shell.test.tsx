import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { AppShell } from "@/components/app-shell";

const setEventId = vi.fn();
let pathname = "/students";
let ecoeStatus = "en_configuracion";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

vi.mock("@/lib/auth", () => ({
  useECOE: () => ({
    user: { id: 1, email: "admin@ecoe.cl", full_name: "Admin Demo", role: "admin_ecoe" },
    eventRoles: ["admin_ecoe"],
    authenticated: true,
    ready: true,
    logout: vi.fn(),
    eventId: 1,
    setEventId,
    ecoeList: [
      { id: 1, name: "ECOE Medicina", status: ecoeStatus, course_name: "Medicina Interna" },
      { id: 2, name: "ECOE Enfermería", status: "borrador", course_name: "Enfermería" },
    ],
    ecoeEvent: {
      id: 1,
      name: "ECOE Medicina",
      status: ecoeStatus,
      date: "2026-11-23",
      course_name: "Medicina Interna",
      school_name: "Escuela de Medicina",
    },
    loadError: null,
    noAccessibleEvents: false,
  }),
}));

function renderShell() {
  return render(
    <AppShell title="Operación académica del ECOE" description="">
      <p>contenido</p>
    </AppShell>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  pathname = "/students";
  ecoeStatus = "en_configuracion";
});

describe("AppShell (layout de gestión)", () => {
  it("titula el encabezado con la pantalla actual, no con un texto fijo", () => {
    renderShell();
    expect(screen.getByRole("heading", { level: 2, name: "Estudiantes" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Operación académica del ECOE" })).toBeNull();
  });

  it("resuelve el título de una subruta por el item más específico", () => {
    pathname = "/ecoe/7";
    renderShell();
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent(/ECOE/);
  });

  it("muestra el estado legible y la fecha del ECOE activo", () => {
    renderShell();
    expect(screen.getByTestId("active-ecoe-status")).toHaveTextContent("En configuración");
    expect(screen.getByText(/23-11-2026/)).toBeInTheDocument();
  });

  it("cambia de ECOE sin preguntar cuando el evento no está en ejecución", async () => {
    const native = vi.spyOn(window, "confirm");
    renderShell();
    fireEvent.change(screen.getByLabelText("Seleccionar ECOE activo"), { target: { value: "2" } });
    await waitFor(() => expect(setEventId).toHaveBeenCalledWith(2));
    expect(native).not.toHaveBeenCalled();
    native.mockRestore();
  });

  it("no cambia de ECOE en ejecución si se cancela la confirmación", async () => {
    ecoeStatus = "en_ejecucion";
    const native = vi.spyOn(window, "confirm").mockReturnValue(false);
    renderShell();
    fireEvent.change(screen.getByLabelText("Seleccionar ECOE activo"), { target: { value: "2" } });
    await waitFor(() => expect(native).toHaveBeenCalled());
    expect(setEventId).not.toHaveBeenCalled();
    native.mockRestore();
  });

  it("cambia de ECOE en ejecución sólo tras confirmar", async () => {
    ecoeStatus = "en_ejecucion";
    const native = vi.spyOn(window, "confirm").mockReturnValue(true);
    renderShell();
    fireEvent.change(screen.getByLabelText("Seleccionar ECOE activo"), { target: { value: "2" } });
    await waitFor(() => expect(setEventId).toHaveBeenCalledWith(2));
    native.mockRestore();
  });
});
