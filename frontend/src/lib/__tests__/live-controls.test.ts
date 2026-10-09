import { describe, expect, it } from "vitest";

import { liveActionBlockedReason } from "@/lib/live-controls";

describe("liveActionBlockedReason", () => {
  it("Iniciar y Reiniciar siempre están disponibles", () => {
    for (const status of ["sin_sesion", "idle", "ready", "running", "paused", "transition", "round_pause", "circuit_complete"]) {
      expect(liveActionBlockedReason("start", status)).toBeNull();
      expect(liveActionBlockedReason("reset", status)).toBeNull();
    }
  });

  it("Pausar sólo con una fase en curso", () => {
    expect(liveActionBlockedReason("pause", "running")).toBeNull();
    expect(liveActionBlockedReason("pause", "transition")).toBeNull();
    expect(liveActionBlockedReason("pause", "round_pause")).toBeNull();
    expect(liveActionBlockedReason("pause", "paused")).not.toBeNull();
    expect(liveActionBlockedReason("pause", "ready")).not.toBeNull();
  });

  it("Reanudar sólo desde pausa (nunca arranca una sesión sin iniciar)", () => {
    expect(liveActionBlockedReason("resume", "paused")).toBeNull();
    for (const status of ["sin_sesion", "idle", "ready", "running", "circuit_complete"]) {
      expect(liveActionBlockedReason("resume", status)).not.toBeNull();
    }
  });

  it("Sig. estación exige cronómetro iniciado y circuito sin terminar", () => {
    expect(liveActionBlockedReason("next_transition", "running")).toBeNull();
    expect(liveActionBlockedReason("next_transition", "paused")).toBeNull();
    expect(liveActionBlockedReason("next_transition", "ready")).not.toBeNull();
    expect(liveActionBlockedReason("next_transition", "circuit_complete")).not.toBeNull();
  });

  it("Adelantar fase replica la regla del backend (running/transition/round_pause)", () => {
    expect(liveActionBlockedReason("skip_phase", "round_pause")).toBeNull();
    expect(liveActionBlockedReason("skip_phase", "paused")).not.toBeNull();
    expect(liveActionBlockedReason("skip_phase", "ready")).not.toBeNull();
  });
});
