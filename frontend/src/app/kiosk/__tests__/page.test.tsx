import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import KioskPage from "@/app/kiosk/page";
import { api } from "@/lib/api";
import { useLiveTimer } from "@/lib/ws";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    isAlreadySubmittedError: actual.isAlreadySubmittedError,
    api: {
      kioskContext: vi.fn(),
      kioskSubmit: vi.fn(),
      kioskDraft: vi.fn(),
      kioskMediaFile: vi.fn(),
    },
  };
});

vi.mock("@/lib/ws", () => ({
  useLiveTimer: vi.fn(),
}));

const mockedApi = vi.mocked(api);
const mockedUseLiveTimer = vi.mocked(useLiveTimer);

const TOKEN = "kiosk-token-123";

function contextWith(liveStatus: "running" | "paused", deadlineOffsetMs = -60_000) {
  const now = Date.now();
  return {
    station_id: 4,
    station_number: 4,
    station_name: "Plan diagnóstico",
    ecoe_event_id: 1,
    ecoe_name: "ECOE Demo",
    ecoe_status: "en_ejecucion",
    server_now: new Date(now).toISOString(),
    live_status: liveStatus,
    current_phase_ends_at: liveStatus === "paused" ? null : new Date(now + 1000).toISOString(),
    paused: liveStatus === "paused",
    active: {
      checkin_id: 99,
      student_id: 7,
      student_name: "Estudiante 7 Demo",
      student_ecoe_number: "E007",
      student_activity: "Actividad",
      pre_entry_instruction: "",
      student_station_instruction: "Responde",
      student_form_definition: {
        questions: [{ label: "Q1", type: "single_choice", options: ["a", "b"] }],
      },
      media_assets: [],
      station_time_minutes: 8,
      // Ventana ya vencida por defecto: el contador local marca 0 → gatillaría autoenvío.
      confirmed_at: new Date(now - 600_000).toISOString(),
      submission_deadline: new Date(now + deadlineOffsetMs).toISOString(),
      student_response_exists: false,
    },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.setItem("ecoe-kiosk-token", TOKEN);
  mockedApi.kioskSubmit.mockResolvedValue({ saved: true } as never);
  mockedApi.kioskDraft.mockResolvedValue({ saved: true, updated_at: null } as never);
});

const runningSnapshot = (overrides: Record<string, unknown> = {}) =>
  ({
    snapshot: {
      status: "running",
      remainingSeconds: 0,
      currentStationIndex: 1,
      stationTimeSeconds: 480,
      transitionTimeSeconds: 120,
      phaseEndsAt: Date.now(),
      receivedAt: Date.now(),
      ...overrides,
    },
    connected: true,
  }) as never;

describe("KioskPage — propagación de pausa (OPT-20 F1)", () => {
  it("en pausa NO autoenvía al llegar a 0 y muestra el overlay de PAUSA", async () => {
    mockedApi.kioskContext.mockResolvedValue(contextWith("paused") as never);
    mockedUseLiveTimer.mockReturnValue({
      snapshot: {
        status: "paused",
        remainingSeconds: 0,
        currentStationIndex: 1,
        stationTimeSeconds: 480,
        transitionTimeSeconds: 120,
        phaseEndsAt: null,
        receivedAt: Date.now(),
      },
      connected: true,
    } as never);

    render(<KioskPage />);

    expect(
      await screen.findByText("PAUSA — el cronómetro está detenido"),
    ).toBeInTheDocument();

    // Damos tiempo a que corran los efectos de autoenvío.
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(mockedApi.kioskSubmit).not.toHaveBeenCalled();
  });

  it("con el reloj corriendo y la ventana vencida, sí autoenvía", async () => {
    mockedApi.kioskContext.mockResolvedValue(contextWith("running") as never);
    mockedUseLiveTimer.mockReturnValue({
      snapshot: {
        status: "running",
        remainingSeconds: 0,
        currentStationIndex: 1,
        stationTimeSeconds: 480,
        transitionTimeSeconds: 120,
        phaseEndsAt: Date.now(),
        receivedAt: Date.now(),
      },
      connected: true,
    } as never);

    render(<KioskPage />);

    await waitFor(() => expect(mockedApi.kioskSubmit).toHaveBeenCalledTimes(1));
    expect(mockedApi.kioskSubmit).toHaveBeenCalledWith(
      TOKEN,
      expect.objectContaining({ checkin_id: 99 }),
    );
    expect(
      screen.queryByText("PAUSA — el cronómetro está detenido"),
    ).not.toBeInTheDocument();
  });
});

describe("KioskPage — carrera con el barrido server-side (OPT-20 F2)", () => {
  it("test_client_autosubmit_conflict_is_treated_as_success: un 'ya fue enviada' del autoenvío muestra 'respuesta enviada', no un error", async () => {
    mockedApi.kioskContext.mockResolvedValue(contextWith("running") as never);
    mockedUseLiveTimer.mockReturnValue(runningSnapshot());
    mockedApi.kioskSubmit.mockRejectedValue(
      new Error("La respuesta de esta estación ya fue enviada y no puede reemplazarse"),
    );

    render(<KioskPage />);

    // El autoenvío corre (ventana vencida) → el backend rechaza por carrera.
    await waitFor(() => expect(mockedApi.kioskSubmit).toHaveBeenCalledTimes(1));

    // No se muestra el texto crudo del error; se muestra la pantalla de enviado.
    expect(await screen.findByText("Respuesta enviada ✓")).toBeInTheDocument();
    expect(
      screen.queryByText(/no puede reemplazarse/i),
    ).not.toBeInTheDocument();
    // reloadContext vuelve a consultar el contexto para confirmar.
    await waitFor(() =>
      expect(mockedApi.kioskContext.mock.calls.length).toBeGreaterThan(1),
    );
  });

  it("empuja el borrador al servidor (con debounce) en cada cambio de respuesta", async () => {
    // Ventana futura: sin autoenvío que interfiera.
    mockedApi.kioskContext.mockResolvedValue(contextWith("running", 300_000) as never);
    mockedUseLiveTimer.mockReturnValue(
      runningSnapshot({ remainingSeconds: 300, phaseEndsAt: Date.now() + 300_000 }),
    );

    render(<KioskPage />);

    const optionA = await screen.findByLabelText("a");
    fireEvent.click(optionA);

    await waitFor(
      () =>
        expect(mockedApi.kioskDraft).toHaveBeenCalledWith(
          TOKEN,
          expect.objectContaining({ checkin_id: 99, answers: { question_1: "a" } }),
        ),
      { timeout: 3000 },
    );
  });
});
