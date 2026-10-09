"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { SectionCard } from "@/components/section-card";

type Presence = { online: boolean; last_seen_at: string | null };
export type StationBoardRow = {
  station_id: number;
  station_number: number;
  station_name: string;
  circuit_name: string;
  requires_evaluator: boolean;
  needs_kiosk: boolean;
  evaluator: (Presence & { name: string; email: string; has_account: boolean }) | null;
  kiosk: (Presence & { linked: boolean }) | null;
  occupant: {
    ecoe_number: string;
    student_name: string;
    evaluation: "enviada" | "borrador" | "pendiente" | null;
    response: "enviada" | "pendiente" | null;
  } | null;
  alerts: string[];
};
export type StationBoard = {
  stations: StationBoardRow[];
  preflight: { ready: boolean; issues: string[] };
};

const POLL_MS = 5000;

function Dot({ state, label }: { state: "ok" | "bad" | "na"; label: string }) {
  const color = state === "ok" ? "bg-emerald-500" : state === "bad" ? "bg-red-500" : "bg-slate-300";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-slate-700">
      <span className={`size-2 rounded-full ${color}`} aria-hidden="true" />
      {label}
    </span>
  );
}

function progressLabel(value: string | null): string {
  if (value === "enviada") return "enviada";
  if (value === "borrador") return "en borrador";
  return "pendiente";
}

/**
 * Tablero de estaciones para coordinación: quién debería estar en cada
 * estación, qué dispositivos reportan señal y qué falta. La verificación
 * previa es el mismo dato resumido: todo en verde antes de iniciar.
 */
export function StationBoardPanel({ eventId }: { eventId: number }) {
  const [board, setBoard] = useState<StationBoard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!eventId) return;
    let cancelled = false;
    const load = () =>
      api.liveBoard(eventId).then(
        (data) => {
          if (cancelled) return;
          setBoard(data);
          setError(null);
        },
        (err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : "No se pudo cargar el tablero.");
        },
      );
    void load();
    const timer = window.setInterval(load, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [eventId]);

  const issues = board?.preflight.issues ?? [];

  return (
    <SectionCard
      title="Estaciones en vivo"
      subtitle="Evaluador y tablet de cada estación, estudiante confirmado y lo que aún falta registrar. Se actualiza solo."
    >
      {error ? <p role="alert" className="text-sm text-red-600">{error}</p> : null}
      {board ? (
        <>
          <div
            role="status"
            className={`rounded-2xl border px-4 py-3 text-sm ${
              board.preflight.ready
                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                : "border-amber-200 bg-[var(--color-warning-soft)] text-amber-900"
            }`}
          >
            <p className="font-semibold">
              {board.preflight.ready
                ? "Verificación previa: todo listo"
                : `Verificación previa: ${issues.length} pendiente${issues.length === 1 ? "" : "s"}`}
            </p>
            {issues.length > 0 ? (
              <ul className="mt-1 list-disc space-y-0.5 pl-5">
                {issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            ) : null}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                  <th className="py-2 pr-4">Estación</th>
                  <th className="py-2 pr-4">Evaluador</th>
                  <th className="py-2 pr-4">Tablet</th>
                  <th className="py-2 pr-4">Estudiante confirmado</th>
                  <th className="py-2">Registro</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {board.stations.map((row) => (
                  <tr key={row.station_id} data-testid={`board-station-${row.station_number}`}>
                    <td className="py-2 pr-4">
                      <span className="font-semibold text-slate-900">{row.station_number} · {row.station_name}</span>
                      <span className="block text-xs text-slate-500">{row.circuit_name}</span>
                    </td>
                    <td className="py-2 pr-4">
                      {!row.requires_evaluator ? (
                        <Dot state="na" label="Sin evaluador: confirma coordinación" />
                      ) : row.evaluator ? (
                        <Dot
                          state={row.evaluator.online && row.evaluator.has_account ? "ok" : "bad"}
                          label={`${row.evaluator.name || row.evaluator.email}${
                            !row.evaluator.has_account ? " (sin cuenta activa)" : row.evaluator.online ? "" : " (sin conexión)"
                          }`}
                        />
                      ) : (
                        <Dot state="bad" label="Sin asignar" />
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      {!row.needs_kiosk ? (
                        <Dot state="na" label="No requiere" />
                      ) : row.kiosk?.linked ? (
                        <Dot state={row.kiosk.online ? "ok" : "bad"} label={row.kiosk.online ? "Conectada" : "Sin conexión"} />
                      ) : (
                        <Dot state="bad" label="Sin vincular" />
                      )}
                    </td>
                    <td className="py-2 pr-4">
                      {row.occupant ? `${row.occupant.ecoe_number} · ${row.occupant.student_name}` : <span className="text-slate-400">—</span>}
                    </td>
                    <td className="py-2 text-xs text-slate-700">
                      {row.occupant ? (
                        <>
                          {row.occupant.evaluation !== null ? <span className="block">Evaluación: {progressLabel(row.occupant.evaluation)}</span> : null}
                          {row.occupant.response !== null ? <span className="block">Respuesta: {progressLabel(row.occupant.response)}</span> : null}
                        </>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : !error ? (
        <div className="h-24 animate-pulse rounded-2xl bg-slate-100" />
      ) : null}
    </SectionCard>
  );
}
