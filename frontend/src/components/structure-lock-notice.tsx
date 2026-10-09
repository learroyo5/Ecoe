"use client";

import { useECOE } from "@/lib/auth";
import { ecoeStatusLabel } from "@/lib/labels";

const STRUCTURE_LOCKED = ["publicado", "en_ejecucion", "cerrado", "archivado"];
const FROZEN = ["cerrado", "archivado"];

/** ¿La estructura del ECOE activo está bloqueada? (espejo de event_lock.py) */
export function useStructureLock(): { locked: boolean; frozen: boolean } {
  const { ecoeEvent } = useECOE();
  const status = String(ecoeEvent?.status ?? "");
  return { locked: STRUCTURE_LOCKED.includes(status), frozen: FROZEN.includes(status) };
}

/**
 * Aviso de que el backend rechazará cambios de estructura (PROC-5): desde la
 * publicación no se editan estaciones, formularios, numeración ni tiempos.
 */
export function StructureLockNotice({ what }: { what: string }) {
  const { ecoeEvent } = useECOE();
  const { locked, frozen } = useStructureLock();
  if (!locked) return null;
  return (
    <div role="status" className="rounded-2xl border border-amber-200 bg-[var(--color-warning-soft)] px-4 py-3 text-sm text-amber-900">
      <strong>ECOE {ecoeStatusLabel(ecoeEvent?.status).toLowerCase()}:</strong>{" "}
      {frozen
        ? `${what} ya no se puede modificar; el acta está congelada.`
        : `${what} queda bloqueado desde la publicación. Para modificarlo, despublica el ECOE desde Datos del ECOE.`}
    </div>
  );
}
