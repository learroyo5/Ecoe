/**
 * Aviso sonoro de inicio / fin de fase para la vista proyector y el kiosco.
 *
 * Sin archivos de audio: los tonos se sintetizan con la Web Audio API, así
 * funciona offline y sin pipeline de assets. Los navegadores bloquean el audio
 * hasta que hay un gesto del usuario, por eso `armAudio()` debe llamarse desde
 * un handler de click/tap (el operador que inicia el cronómetro, o el primer
 * toque en la tablet). Si el audio no está disponible, todo degrada en silencio
 * y el aviso visual (semáforo) sigue igual.
 */

let ctx: AudioContext | null = null;

type AudioCtor = typeof AudioContext;

export function armAudio(): void {
  try {
    if (typeof window === "undefined") return;
    if (!ctx) {
      const AC: AudioCtor | undefined =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext?: AudioCtor }).webkitAudioContext;
      if (!AC) return;
      ctx = new AC();
    }
    if (ctx.state === "suspended") void ctx.resume();
  } catch {
    /* audio no disponible: se ignora */
  }
}

function tone(freq: number, startAt: number, duration: number, peak = 0.22): void {
  if (!ctx) return;
  const now = ctx.currentTime;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0.0001, now + startAt);
  gain.gain.exponentialRampToValueAtTime(peak, now + startAt + 0.015);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + startAt + duration);
  osc.connect(gain).connect(ctx.destination);
  osc.start(now + startAt);
  osc.stop(now + startAt + duration + 0.05);
}

/** Reproduce el aviso. `end` = timbre descendente de "se acabó el tiempo";
 *  `start` = doble tono ascendente breve de "comiencen". No-op si el audio
 *  aún no fue habilitado por un gesto del usuario. */
export function chime(kind: "start" | "end"): void {
  armAudio();
  if (!ctx || ctx.state !== "running") return;
  if (kind === "end") {
    tone(880, 0, 0.4);
    tone(659, 0.34, 0.4);
    tone(440, 0.68, 0.7);
  } else {
    tone(523, 0, 0.22);
    tone(784, 0.2, 0.4);
  }
}
