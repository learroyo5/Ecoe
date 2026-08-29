"use client";

/**
 * Corrección manual de formularios del estudiante (evaluación diferida).
 *
 * Las alternativas se autocorrigen en el servidor al enviar; aquí se
 * resuelven las preguntas de respuesta breve con puntaje. Solo las
 * respuestas con puntaje definitivo entran al consolidado de resultados.
 *
 * OPT-15: cola personal del corrector — progreso por estación, panel de
 * pauta de referencia, autoavance a la siguiente pendiente sin re-fetch.
 */

import { useCallback, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { submissionKindLabel } from "@/lib/labels";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";
import { StatusNotice } from "@/components/forms";
import { EmptyState } from "@/components/toast";
import { ConfirmDialog } from "@/components/confirm-dialog";
import type { GradableResponse, GradingListResult, GradingScope } from "@/lib/types";

/** ¿La respuesta llegó incompleta (algún ítem puntuable sin responder)? */
function hasUnansweredItems(row: GradableResponse): boolean {
  return Object.values(row.grading ?? {}).some((item) => item?.answered === false);
}

/**
 * ¿Es un autoenvío realmente en blanco? El servidor lo cerró al vencer el
 * cronómetro (`submission_kind === "auto"`) y ninguna de sus preguntas
 * manuales pendientes fue respondida. Estas son las candidatas al bulk-0.
 */
function isBlankAuto(row: GradableResponse): boolean {
  return (
    row.submission_kind === "auto" &&
    row.pending_questions.length > 0 &&
    row.pending_questions.every((key) => row.grading[key]?.answered === false)
  );
}

const CLOSED_STATUSES = new Set(["cerrado", "archivado"]);

const DEFAULT_SCOPE: GradingScope = {
  is_corrector: false,
  has_assignment: true,
  assigned_station_ids: [],
};

function scrollToResponse(responseId: number) {
  if (typeof window === "undefined") return;
  window.requestAnimationFrame(() => {
    const node = document.getElementById(`grading-row-${responseId}`);
    node?.scrollIntoView?.({ behavior: "smooth", block: "center" });
  });
}

export default function GradingPage() {
  const { authenticated, eventId, ecoeEvent } = useECOE();
  const eventClosed = ecoeEvent ? CLOSED_STATUSES.has(ecoeEvent.status) : false;
  const { data, loading, error, setData } = useApi<GradingListResult>(
    () =>
      eventClosed
        ? Promise.resolve({
            responses: [],
            pending_count: 0,
            scope: DEFAULT_SCOPE,
            pending_by_station: {},
          })
        : api.gradingList(eventId),
    [eventId, authenticated, eventClosed],
  );
  const [message, setMessage] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [draftScores, setDraftScores] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [showRubric, setShowRubric] = useState(true);
  const [confirmStation, setConfirmStation] = useState<number | null>(null);
  const [zeroing, setZeroing] = useState(false);

  const [stationFilter, setStationFilter] = useState<string>("");

  const responses = useMemo(() => data?.responses ?? [], [data]);
  const scope = data?.scope ?? DEFAULT_SCOPE;
  const pendingByStation = useMemo(() => data?.pending_by_station ?? {}, [data]);

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

  // Progreso a partir de `pending_by_station` (respeta el scope del corrector);
  // si hay filtro de estación activo, el encabezado se acota a esa estación.
  const stationProgress = useMemo(() => {
    const entries = Object.entries(pendingByStation).map(([id, s]) => ({ station_id: id, ...s }));
    entries.sort((a, b) => Number(a.station_number ?? 0) - Number(b.station_number ?? 0));
    return stationFilter
      ? entries.filter((s) => String(s.station_number ?? "") === stationFilter)
      : entries;
  }, [pendingByStation, stationFilter]);
  // Autoenvíos en blanco por estación (candidatos al bulk-0). `responses` ya
  // viene acotado al scope del corrector desde el backend.
  const blankAutoByStation = useMemo(() => {
    const map = new Map<
      number,
      { station_number: number | null; station_name: string; count: number }
    >();
    for (const row of responses) {
      if (!isBlankAuto(row)) continue;
      const current = map.get(row.station_id) ?? {
        station_number: row.station_number,
        station_name: row.station_name,
        count: 0,
      };
      current.count += 1;
      map.set(row.station_id, current);
    }
    return [...map.entries()]
      .map(([station_id, value]) => ({ station_id, ...value }))
      .sort((a, b) => Number(a.station_number ?? 0) - Number(b.station_number ?? 0));
  }, [responses]);
  const visibleBlankAuto = stationFilter
    ? blankAutoByStation.filter((s) => String(s.station_number ?? "") === stationFilter)
    : blankAutoByStation;
  const confirmTarget =
    confirmStation !== null
      ? blankAutoByStation.find((s) => s.station_id === confirmStation) ?? null
      : null;

  const totalAll = stationProgress.reduce((acc, s) => acc + s.total, 0);
  const pendingAll = stationProgress.reduce((acc, s) => acc + s.pending, 0);
  const gradedAll = Math.max(0, totalAll - pendingAll);
  const scopeWord = scope.is_corrector ? "en tus estaciones" : "en el evento";

  const questionLabel = (row: GradableResponse, key: string) => {
    const index = Number(key.replace("question_", "")) - 1;
    return row.questions[index]?.label ?? key;
  };

  const answerText = (row: GradableResponse, key: string) => {
    const value = row.answers?.[key];
    if (Array.isArray(value)) return value.join(", ");
    return String(value ?? "").trim() || "(sin respuesta)";
  };

  const openResponse = useCallback((row: GradableResponse) => {
    setExpandedId(row.response_id);
    setDraftScores(Object.fromEntries(row.pending_questions.map((key) => [key, ""])));
  }, []);

  const saveGrading = useCallback(
    async (row: GradableResponse) => {
      if (saving) return;
      if (row.pending_questions.some((key) => draftScores[key] === "" || draftScores[key] == null)) {
        return;
      }
      setMessage(null);
      setSaving(true);
      try {
        const scores = Object.fromEntries(
          row.pending_questions.map((key) => [key, Number(draftScores[key])]),
        );
        const result = await api.gradeResponse(row.response_id, scores);

        // Mutar la fila local + los contadores en vez de re-fetchear la lista.
        setData((prev) => {
          if (!prev) return prev;
          const nextResponses = prev.responses.map((item) =>
            item.response_id === row.response_id
              ? {
                  ...item,
                  score_obtained: result.score_obtained,
                  max_score: result.max_score ?? item.max_score,
                  pending_questions: [],
                  graded_by_email: item.graded_by_email ?? "manual",
                }
              : item,
          );
          const key = String(row.station_id);
          const bucket = prev.pending_by_station[key];
          const nextByStation = bucket
            ? {
                ...prev.pending_by_station,
                [key]: { ...bucket, pending: Math.max(0, bucket.pending - 1) },
              }
            : prev.pending_by_station;
          return {
            ...prev,
            responses: nextResponses,
            pending_by_station: nextByStation,
            pending_count: result.pending_remaining,
          };
        });

        if (result.next) {
          const nextRow = responses.find((item) => item.response_id === result.next!.response_id);
          if (nextRow) {
            openResponse(nextRow);
            scrollToResponse(nextRow.response_id);
            setMessage("Corrección guardada. Abrí la siguiente respuesta pendiente.");
          } else {
            setExpandedId(null);
            setMessage("Corrección guardada; el puntaje ya suma al consolidado.");
          }
        } else {
          setExpandedId(null);
          setMessage(
            scope.is_corrector
              ? "Corrección guardada. No quedan pendientes en tus estaciones ✓"
              : "Corrección guardada; el puntaje ya suma al consolidado.",
          );
        }
      } catch (gradeError) {
        setMessage(
          gradeError instanceof Error ? gradeError.message : "No se pudo guardar la corrección.",
        );
      } finally {
        setSaving(false);
      }
    },
    [draftScores, openResponse, responses, saving, scope.is_corrector, setData],
  );

  const zeroBlanks = useCallback(
    async (stationId: number) => {
      if (zeroing) return;
      setMessage(null);
      setZeroing(true);
      try {
        const result = await api.gradingZeroBlank(eventId, stationId);
        const affected = new Set(result.response_ids);
        // Mutar las filas afectadas + contadores en vez de re-fetchear la lista.
        setData((prev) => {
          if (!prev) return prev;
          const nextResponses = prev.responses.map((item) =>
            affected.has(item.response_id)
              ? {
                  ...item,
                  score_obtained: 0,
                  pending_questions: [],
                  graded_by_email: item.graded_by_email ?? "manual",
                }
              : item,
          );
          const key = String(stationId);
          const bucket = prev.pending_by_station[key];
          const nextByStation = bucket
            ? {
                ...prev.pending_by_station,
                [key]: { ...bucket, pending: Math.max(0, bucket.pending - result.zeroed) },
              }
            : prev.pending_by_station;
          return {
            ...prev,
            responses: nextResponses,
            pending_by_station: nextByStation,
            pending_count: result.pending_remaining,
          };
        });
        setMessage(
          result.zeroed > 0
            ? `Se puntuaron 0 ${result.zeroed} respuesta(s) automática(s) en blanco. Ya suman al consolidado.`
            : "No había autoenvíos en blanco pendientes en esa estación.",
        );
      } catch (zeroError) {
        setMessage(
          zeroError instanceof Error
            ? zeroError.message
            : "No se pudo puntuar los autoenvíos en blanco.",
        );
      } finally {
        setZeroing(false);
        setConfirmStation(null);
      }
    },
    [eventId, zeroing, setData],
  );

  const renderResponseCard = (row: GradableResponse, gradable: boolean) => {
    const expanded = expandedId === row.response_id;
    const canSave =
      !saving && row.pending_questions.every((key) => draftScores[key] !== "" && draftScores[key] != null);
    return (
      <div
        key={row.response_id}
        id={`grading-row-${row.response_id}`}
        className="rounded-2xl border border-slate-200 bg-white p-4"
      >
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
            {row.assessment_tool ? (
              <div className="rounded-2xl border border-slate-200 bg-white">
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left text-sm font-semibold text-slate-700"
                  aria-expanded={showRubric}
                  onClick={() => setShowRubric((value) => !value)}
                >
                  <span data-testid="grading-rubric-toggle">
                    Pauta de referencia · {row.assessment_tool.name}
                  </span>
                  <span className="text-xs font-normal text-slate-500">
                    {showRubric ? "Ocultar" : "Mostrar"}
                  </span>
                </button>
                {showRubric ? (
                  <div
                    data-testid="grading-rubric-panel"
                    className="space-y-2 border-t border-slate-100 px-4 py-3 text-sm text-slate-700"
                  >
                    <p className="text-xs text-slate-500">
                      Solo referencia — el puntaje se ingresa libre por pregunta (máx del formulario).
                    </p>
                    <ul className="space-y-1">
                      {(row.assessment_tool.items ?? []).map((item) => (
                        <li key={item.id} className="flex justify-between gap-4">
                          <span>{item.label}</span>
                          <span className="shrink-0 font-semibold text-slate-500">
                            {item.score_per_item} pts
                          </span>
                        </li>
                      ))}
                    </ul>
                    {row.assessment_tool.free_observation ? (
                      <p className="text-xs text-slate-500">Incluye observación libre.</p>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}

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
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        void saveGrading(row);
                      }
                    }}
                  />
                </label>
              </div>
            ))}
            <button
              className="btn-primary"
              disabled={!canSave}
              onClick={() => void saveGrading(row)}
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

  const noStations = scope.is_corrector && !scope.has_assignment;

  return (
    <div className="space-y-6">
      <SectionCard
        title="Corrección de formularios"
        subtitle="Las alternativas se corrigen automáticamente al enviarse; aquí resuelves las respuestas breves con puntaje (evaluación diferida). Solo lo corregido entra a Resultados."
      >
        <StatusNotice message={message} />

        {!noStations && totalAll > 0 ? (
          <div data-testid="grading-progress" className="mt-3 space-y-2">
            <p className="text-sm font-semibold text-slate-700">
              {gradedAll} de {totalAll} corregidas {scopeWord}
            </p>
            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all"
                style={{ width: `${totalAll ? (gradedAll / totalAll) * 100 : 0}%` }}
              />
            </div>
            {stationProgress.length > 1 ? (
              <div className="flex flex-wrap gap-2">
                {stationProgress.map((s) => (
                  <span
                    key={s.station_id}
                    className="status-badge status-badge-info"
                    title={s.station_name}
                  >
                    Estación {s.station_number}: {s.total - s.pending}/{s.total}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        ) : null}

        {!noStations && visibleBlankAuto.length > 0 ? (
          <div
            data-testid="grading-zero-blank"
            className="mt-3 space-y-2 rounded-2xl border border-amber-200 bg-amber-50/60 p-3"
          >
            <p className="text-sm font-semibold text-amber-900">Autoenvíos en blanco</p>
            <p className="text-xs leading-5 text-amber-800">
              Respuestas que el servidor cerró al vencer el cronómetro sin ningún ítem
              respondido. Podés puntuarlas 0 en bloque por estación.
            </p>
            <div className="flex flex-wrap gap-2">
              {visibleBlankAuto.map((s) => (
                <button
                  key={s.station_id}
                  type="button"
                  className="btn-secondary"
                  disabled={zeroing}
                  onClick={() => setConfirmStation(s.station_id)}
                >
                  Estación {s.station_number}: puntuar 0 los blancos ({s.count})
                </button>
              ))}
            </div>
          </div>
        ) : null}

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
      ) : noStations ? (
        <SectionCard title="Sin estaciones asignadas">
          <EmptyState
            icon="📋"
            title="No tenés estaciones asignadas para corregir"
            description="Pedile a un coordinador o al administrador del ECOE que te asigne estaciones de evaluación diferida."
          />
        </SectionCard>
      ) : !responses.length ? (
        <SectionCard title="Sin respuestas puntuables">
          <EmptyState
            icon="🧮"
            title={
              scope.is_corrector
                ? "Todavía no hay respuestas para corregir en tus estaciones"
                : "Nada que corregir todavía"
            }
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
              <p className="text-sm text-slate-600">Todo corregido {scopeWord} ✓</p>
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

      <ConfirmDialog
        open={confirmStation !== null}
        title="Puntuar 0 los autoenvíos en blanco"
        message={
          confirmTarget
            ? `Se asignará 0 a ${confirmTarget.count} respuesta(s) automática(s) sin contenido de la Estación ${confirmTarget.station_number}. Suman al consolidado de inmediato.`
            : undefined
        }
        confirmLabel="Puntuar 0"
        busy={zeroing}
        onConfirm={() => {
          if (confirmStation !== null) void zeroBlanks(confirmStation);
        }}
        onCancel={() => setConfirmStation(null)}
      />
    </div>
  );
}
