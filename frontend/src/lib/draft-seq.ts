/**
 * Número de orden creciente para los autoguardados de un dispositivo (F0.2).
 * El servidor descarta un borrador que llega con un número menor o igual al
 * ya guardado, así una respuesta atrasada de la red no pisa a una más nueva.
 * Basado en el reloj, pero nunca retrocede aunque el reloj lo haga.
 */
let last = 0;

export function nextDraftSeq(): number {
  last = Math.max(Date.now(), last + 1);
  return last;
}
