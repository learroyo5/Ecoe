"use client";

/**
 * Corrección manual de formularios del estudiante.
 *
 * Las alternativas se autocorrigen en el servidor al enviar; aquí se
 * resuelven las preguntas de respuesta breve con puntaje. Solo las
 * respuestas con puntaje definitivo entran al consolidado de resultados.
 */

import { useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { submissionKindLabel } from "@/lib/labels";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";
import { StatusNotice } from "@/components/forms";
import { EmptyState } from "@/components/toast";

type GradingItem = {
  kind: "auto" | "manual";
  earned: number | null;
  max: number;
  answered?: boolean;
};

type GradableResponse = {
  response_id: number;
  mode: string;
  submission_kind?: string;
  by_contingency?: boolean;
  student_name: string;
  student_ecoe_number: string;
  station_number: number | null;
  station_name: string;
  submitted_at: string;
  answers: Record<string, unknown>;
  grading: Record<string, GradingItem>;
  pending_questions: string[];
  score_obtained: number | null;
  max_score: number | null;
  graded_by_email: string | null;
  questions: { label?: string; type?: string }[];
};

/** ¿La respuesta llegó incompleta (algún ítem puntuable sin responder)? */
function hasUnansweredItems(row: GradableResponse): boolean {
  return Object.values(row.grading ?? {}).some((item) => item?.answered === false);
}

const CLOSED_STATUSES = new Set(["cerrado", "archivado"]);

export default function GradingPage() {
  const { authenticated, eventId, ecoeEvent } = useECOE();
  const eventClosed = ecoeEvent ? CLOSED_STATUSES.has(ecoeEvent.status) : false;
  const { data, loading, error, setData } = useApi(
    () =>
      eventClosed
        ? Promise.resolve({ responses: [] as GradableResponse[], pending_count: 0 })
        : (api.gradingList(eventId) as Promise<{
            responses: GradableResponse[];
            pending_count: number;
          }>),
    [eventId, authenticated, eventClosed],
  );
  const [message, setMessage] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [draftScores, setDraftScores] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const [stationFilter, setStationFilter] = useState<string>("");

  const responses = useMemo(() => data?.responses ?? [], [data]);
  const stationChoices = useMemo(() => {
    const seen = new Map<string, string>();
    for (const row of responses) {
      const key = String(row.station_number ?? "");
      if (key && !seen.has(key)) seen.set(key, `Estación ${key}: ${row.station_name}`);
    }
    return [...seen.entries()].sort((a, b) => Number(a[0]) - Number(b[0]));
  }, [responses]);
  const visibleResponses = stationFilter
    ? responses.filter((row) => String(row.station_number ?? "") === stationFilter)
    : responses;
  const pending = visibleResponses.filter((row) => row.pending_questions.length > 0);
  const graded = visibleResponses.filter((row) => row.pending_questions.length === 0);

  const questionLabel = (row: GradableResponse, key: string) => {
    const index = Number(key.replace("question_", "")) - 1;
    return row.questions[index]?.label ?? key;
  };

  const answerText = (row: GradableResponse, key: string) => {
    const value = row.answers?.[key];
    if (Array.isArray(value)) return value.join(", ");
    return String(value ?? "").trim() || "(sin respuesta)";
  };

  const openResponse = (row: GradableResponse) => {
    setExpandedId(row.response_id);
    setDraftScores(
      Object.fromEntries(row.pending_questions.map((key) => [key, ""])),
    );
  };

  const renderResponseCard = (row: GradableResponse, gradable: boolean) => {
    const expanded = expandedId === row.response_id;
    return (
      <div key={row.response_id} className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-900">
              {row.student_ecoe_number} · {row.student_name}
            </p>
            <p className="mt-1 text-xs text-slate-500">
              Estación {row.station_number}: {row.station_name} ·{" "}
              {row.mode === "pilotaje" ? "Pilotaje" : "Ejecución"} ·{" "}
              {new Date(row.submitted_at).toLocaleString()}
            </p>
            {(row.submission_kind && row.submission_kind !== "manual") ||
            hasUnansweredItems(row) ? (
              <div className="mt-2 flex flex-wrap gap-2">
                {row.submission_kind === "auto" ? (
                  <span
                    className="status-badge status-badge-warning"
                    title="El servidor cerró esta respuesta al vencer el cronómetro; no fue una entrega deliberada del estudiante."
                  >
                    Respuesta automática
                  </span>
                ) : row.submission_kind && row.submission_kind !== "manual" ? (
                  <span className="status-badge status-badge-info">
                    {submissionKindLabel(row.submission_kind)}
                  </span>
                ) : null}
                {hasUnansweredItems(row) ? (
                  <span className="status-badge status-badge-warning">
                    Incompleta — ítems sin responder
                  </span>
                ) : null}
              </div>
            ) : null}
          </div>
          <div className="flex items-center gap-3">
            {row.score_obtained !== null ? (
              <span className="status-badge status-badge-success">
                {row.score_obtained} / {row.max_score} pts
              </span>
            ) : (
              <span className="status-badge status-badge-warning">
                Pendiente ({row.pending_questions.length})
              </span>
            )}
            {gradable ? (
              <button
                className="btn-secondary"
                onClick={() => (expanded ? setExpandedId(null) : openResponse(row))}
              >
                {expanded ? "Cerrar" : "Corregir"}
              </button>
            ) : null}
          </div>
        </div>

        {expanded && gradable ? (
          <div className="mt-4 space-y-4 border-t border-slate-100 pt-4">
            {row.pending_questions.map((key) => (
              <div key={key} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold text-slate-900">{questionLabel(row, key)}</p>
                  {row.grading[key]?.answered === false ? (
                    <span className="status-badge status-badge-warning">Sin responder</span>
                  ) : null}
                </div>
                <p className="mt-2 rounded-xl bg-white px-3 py-2 text-sm leading-6 text-slate-800">
                  {answerText(row, key)}
                </p>
                <label className="mt-3 flex items-center gap-3 text-sm font-semibold text-slate-700">
                  Puntaje (máx {row.grading[key]?.max ?? 0})
                  <input
                    type="number"
                    min="0"
                    max={String(row.grading[key]?.max ?? 0)}
                    step="0.5"
                    className="w-28"
                    value={draftScores[key] ?? ""}
                    onChange={(event) =>
                      setDraftScores((prev) => ({ ...prev, [key]: event.target.value }))
                    }
                  />
                </label>
              </div>
            ))}
            <button
              className="btn-primary"
              disabled={saving || row.pending_questions.some((key) => draftScores[key] === "")}
              onClick={async () => {
                setMessage(null);
                setSaving(true);
                try {
                  const scores = Object.fromEntries(
                    row.pending_questions.map((key) => [key, Number(draftScores[key])]),
                  );
                  await api.gradeResponse(row.response_id, scores);
                  setData(
                    (await api.gradingList(eventId)) as {
                      responses: GradableResponse[];
                      pending_count: number;
                    },
                  );
                  setExpandedId(null);
                  setMessage("Corrección guardada; el puntaje ya suma al consolidado.");
                } catch (gradeError) {
                  setMessage(
                    gradeError instanceof Error
                      ? gradeError.message
                      : "No se pudo guardar la corrección.",
                  );
                } finally {
                  setSaving(false);
                }
              }}
            >
              {saving ? "Guardando..." : "Guardar corrección"}
            </button>
          </div>
        ) : null}
      </div>
    );
  };

  if (eventClosed) {
    return (
      <div className="space-y-6">
        <SectionCard
          title="Corrección de formularios"
          subtitle="El ECOE está cerrado; la cola de corrección no está disponible."
        >
          <div
            data-testid="grading-closed-notice"
            className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900"
          >
            <p className="font-semibold">ECOE cerrado — los resultados están consolidados.</p>
            <p className="mt-1">
              Para rectificar una nota, reabrí el evento (retroceso de estado) desde la pantalla del
              ECOE. Mientras el evento siga cerrado o archivado el servidor rechaza cualquier
              corrección.
            </p>
          </div>
        </SectionCard>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <SectionCard
        title="Corrección de formularios"
        subtitle="Las alternativas se corrigen automáticamente al enviarse; aquí resuelves las respuestas breves con puntaje (evaluación diferida). Solo lo corregido entra a Resultados."
      >
        <StatusNotice message={message} />
        {stationChoices.length > 1 ? (
          <label className="mt-3 flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-700">
            Estación
            <select
              value={stationFilter}
              onChange={(event) => setStationFilter(event.target.value)}
              className="font-normal"
            >
              <option value="">Todas ({responses.length})</option>
              {stationChoices.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </SectionCard>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-2xl bg-slate-100" />
          ))}
        </div>
      ) : error ? (
        <SectionCard title="Error"><p className="text-red-600">{error}</p></SectionCard>
      ) : !responses.length ? (
        <SectionCard title="Sin respuestas puntuables">
          <EmptyState
            icon="🧮"
            title="Nada que corregir todavía"
            description="Aquí aparecerán las respuestas de estaciones cuyo formulario tiene preguntas con puntaje."
          />
        </SectionCard>
      ) : (
        <>
          <SectionCard
            title={`Pendientes de corrección (${pending.length})`}
            subtitle="Respuestas con preguntas de texto sin puntaje asignado; no suman a Resultados hasta corregirse."
          >
            {pending.length ? (
              <div className="space-y-3">{pending.map((row) => renderResponseCard(row, true))}</div>
            ) : (
              <p className="text-sm text-slate-600">No hay correcciones pendientes. ✓</p>
            )}
          </SectionCard>
          <SectionCard
            title={`Corregidas (${graded.length})`}
            subtitle="Respuestas con puntaje definitivo (automático o manual)."
          >
            <div className="space-y-3">{graded.map((row) => renderResponseCard(row, false))}</div>
          </SectionCard>
        </>
      )}
    </div>
  );
}
