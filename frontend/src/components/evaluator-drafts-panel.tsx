"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { EvaluatorDraftRow } from "@/lib/types";
import { SectionCard } from "@/components/section-card";

/**
 * OPT-20 F3 (D3): pantalla de contingencia de coordinación. Lista los
 * registros de evaluador que quedaron como borrador al vencer la fase y
 * permite finalizarlos (promueve la fila a definitiva vía
 * `/contingency/evaluator-record`, con puntaje autoritativo del servidor).
 */
export function EvaluatorDraftsPanel({ eventId }: { eventId: number }) {
  const [rows, setRows] = useState<EvaluatorDraftRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [scores, setScores] = useState<Record<number, string>>({});
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(() => {
    setLoading(true);
    api
      .pendingEvaluatorDrafts(eventId)
      .then((data) => {
        setRows(data.drafts);
        setScores(Object.fromEntries(data.drafts.map((d) => [d.record_id, String(d.score_obtained)])));
      })
      .catch((err) => setMessage(err instanceof Error ? err.message : "No se pudo cargar."))
      .finally(() => setLoading(false));
  }, [eventId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const finalize = async (row: EvaluatorDraftRow) => {
    setBusyId(row.record_id);
    setMessage(null);
    try {
      await api.finalizeEvaluatorRecord({
        ecoe_event_id: eventId,
        station_id: row.station_id,
        student_id: row.student_id,
        evaluator_name: row.evaluator_name || "Coordinación",
        score_obtained: Number(scores[row.record_id] ?? row.score_obtained) || 0,
        max_score: row.max_score,
        observation: notes[row.record_id] ?? row.observation ?? "",
        answers: {},
      });
      setRows((current) => current.filter((r) => r.record_id !== row.record_id));
      setMessage(
        `Borrador de ${row.student_ecoe_number} (estación ${row.station_number ?? "?"}) finalizado.`,
      );
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo finalizar.");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <SectionCard
      title="Borradores de evaluador pendientes"
      subtitle="Registros que quedaron a medio llenar al sonar el buzzer; finalízalos con el puntaje de la hoja de contingencia."
    >
      {message ? <p className="mb-3 text-sm text-slate-600">{message}</p> : null}
      {loading ? (
        <p className="text-sm text-slate-500">Cargando…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-slate-500">No hay borradores de evaluador sin finalizar.</p>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => (
            <div
              key={row.record_id}
              className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4 space-y-3"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">
                  Estación {row.station_number ?? "?"} · {row.station_name}
                </p>
                <p className="text-sm text-slate-600">
                  {row.student_ecoe_number} · {row.student_name}
                </p>
              </div>
              {row.observation ? (
                <p className="text-sm text-slate-600">Observación del evaluador: {row.observation}</p>
              ) : null}
              <div className="grid gap-3 md:grid-cols-[auto_1fr_auto] md:items-end">
                <label className="space-y-1">
                  <span className="text-xs font-semibold text-slate-600">
                    Puntaje final (0–{row.max_score})
                  </span>
                  <input
                    type="number"
                    min="0"
                    max={String(row.max_score)}
                    step="0.5"
                    className="w-32"
                    value={scores[row.record_id] ?? String(row.score_obtained)}
                    onChange={(e) =>
                      setScores((c) => ({ ...c, [row.record_id]: e.target.value }))
                    }
                  />
                </label>
                <label className="space-y-1">
                  <span className="text-xs font-semibold text-slate-600">Nota de contingencia (opcional)</span>
                  <input
                    value={notes[row.record_id] ?? ""}
                    onChange={(e) => setNotes((c) => ({ ...c, [row.record_id]: e.target.value }))}
                    placeholder="Motivo o referencia de la hoja de papel"
                  />
                </label>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={busyId === row.record_id}
                  onClick={() => finalize(row)}
                >
                  {busyId === row.record_id ? "Finalizando…" : "Finalizar"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}
