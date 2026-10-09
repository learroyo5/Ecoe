/**
 * Qué controles del cronómetro tienen sentido en cada estado de la sesión.
 * Es una guarda de UX: `/live/control` sigue siendo la autoridad. Evita, por
 * ejemplo, "Reanudar" sin sesión iniciada (arrancaría el reloj sin "Iniciar").
 */
export type LiveAction = "start" | "pause" | "resume" | "reset" | "next_transition" | "skip_phase";

const IN_PHASE = ["running", "transition", "round_pause"];
const NOT_STARTED = ["idle", "ready", "sin_sesion"];

/** null = habilitado; string = motivo (se usa como tooltip del botón deshabilitado). */
export function liveActionBlockedReason(action: LiveAction, status: string): string | null {
  switch (action) {
    case "pause":
      return IN_PHASE.includes(status) ? null : "No hay una fase en curso que pausar.";
    case "resume":
      return status === "paused" ? null : "Sólo se reanuda un cronómetro en pausa.";
    case "skip_phase":
      return IN_PHASE.includes(status) ? null : "No hay una fase automática en curso para adelantar.";
    case "next_transition":
      if (NOT_STARTED.includes(status)) return "Inicia el cronómetro antes de pasar a la siguiente estación.";
      if (status === "circuit_complete") return "El circuito ya terminó.";
      return null;
    default:
      return null;
  }
}
