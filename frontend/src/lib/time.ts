/** Utilidades de tiempo para timestamps del backend (UTC naive, sin sufijo Z). */

/**
 * Parsea un timestamp del backend como UTC. El backend serializa datetimes
 * naive en UTC (sin "Z"), y `new Date("...")` sin zona los interpretaría
 * como hora local del navegador.
 */
export function parseServerUtc(value: string): number {
  if (!value) return NaN;
  const hasTimezone = /Z|[+-]\d{2}:?\d{2}$/.test(value);
  return new Date(hasTimezone ? value : `${value}Z`).getTime();
}

/**
 * Diferencia entre el reloj del servidor y el local, a partir del campo
 * `server_now` que devuelven los contextos de evaluador/estudiante.
 * Sumar este offset a Date.now() da la hora del servidor.
 */
export function clockOffsetMs(serverNow: string): number {
  const serverMs = parseServerUtc(serverNow);
  return Number.isNaN(serverMs) ? 0 : serverMs - Date.now();
}
