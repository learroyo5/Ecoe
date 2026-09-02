/**
 * Aviso sonoro de inicio / fin de fase para la vista proyector y el kiosco.
 *
 * Sin archivos de audio: los tonos se sintetizan con la Web Audio API, así
 * funciona offline y sin pipeline de assets. Los navegadores bloquean el audio
 * hasta que hay un gesto del usuario, por eso `armAudio()` debe llamarse desde
 * un handler de click/tap (el operador que inicia el cronómetro, o el primer
 * toque en la tablet). Si el audio no está disponible, todo degrada en silencio
 * y el aviso visual (semáforo) sigue igual.
 *
 * El volumen es configurable (suave / medio / alto) y se guarda por navegador;
 * `alto` es el valor por defecto porque el aviso tiene que llegar a toda la sala.
 */

let ctx: AudioContext | null = null;

type AudioCtor = typeof AudioContext;
export type ChimeVolume = "suave" | "medio" | "alto";

const VOLUME_KEY = "ecoe-chime-volume";
const GAIN_BY_VOLUME: Record<ChimeVolume, number> = { suave: 0.16, medio: 0.34, alto: 0.6 };

export function getChimeVolume(): ChimeVolume {
  try {
    const v = localStorage.getItem(VOLUME_KEY);
    if (v === "suave" || v === "medio" || v === "alto") return v;
  } catch {
    /* private mode */
  }
  return "alto";
}

export function setChimeVolume(v: ChimeVolume): void {
  try {
    localStorage.setItem(VOLUME_KEY, v);
  } catch {
    /* private mode */
  }
}

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

/** Un golpe de campana: fundamental + un armónico grave, con caída exponencial. */
function bell(freq: number, startAt: number, duration: number, peak: number): void {
  if (!ctx) return;
  const now = ctx.currentTime;
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.0001, now + startAt);
  g.gain.exponentialRampToValueAtTime(peak, now + startAt + 0.008);
  g.gain.exponentialRampToValueAtTime(0.0001, now + startAt + duration);
  g.connect(ctx.destination);
  [
    { f: freq, type: "triangle" as OscillatorType, mul: 1 },
    { f: freq * 2.01, type: "sine" as OscillatorType, mul: 0.35 },
    { f: freq * 0.5, type: "sine" as OscillatorType, mul: 0.25 },
  ].forEach((p) => {
    const osc = ctx!.createOscillator();
    const og = ctx!.createGain();
    osc.type = p.type;
    osc.frequency.value = p.f;
    og.gain.value = p.mul;
    osc.connect(og).connect(g);
    osc.start(now + startAt);
    osc.stop(now + startAt + duration + 0.05);
  });
}

/** `end` = triple campanada descendente de "se acabó el tiempo"; `start` = doble
 *  tono ascendente breve de "comiencen". No-op si el audio no fue habilitado. */
export function chime(kind: "start" | "end"): void {
  armAudio();
  if (!ctx || ctx.state !== "running") return;
  const peak = GAIN_BY_VOLUME[getChimeVolume()];
  if (kind === "end") {
    bell(880, 0, 0.55, peak);
    bell(659, 0.28, 0.55, peak);
    bell(440, 0.56, 1.0, peak);
  } else {
    bell(523, 0, 0.3, peak * 0.9);
    bell(784, 0.16, 0.5, peak * 0.9);
  }
}
