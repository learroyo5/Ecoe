"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { clockOffsetMs, parseServerUtc } from "@/lib/time";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

export default function EvaluatorPage() {
  const { authenticated, eventId, user } = useECOE();
  const { data: context, setData: setContext } = useApi(
    () => api.evaluatorContext(eventId) as Promise<Record<string, unknown>>,
    [eventId, authenticated],
  );
  const [ecoeNumber, setEcoeNumber] = useState("");
  const [scoreObtained, setScoreObtained] = useState("0");
  const [observation, setObservation] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [confirmingStudent, setConfirmingStudent] = useState(false);
  const [submittingEvaluation, setSubmittingEvaluation] = useState(false);
  const [itemScoreState, setItemScoreState] = useState<{
    checkinId: string;
    scores: Record<string, number>;
  }>({
    checkinId: "",
    scores: {},
  });

  const stations = (context?.stations as Record<string, unknown>[] | undefined) ?? [];
  const assignedStation = stations[0];
  const activeCheckin = (context?.active_checkin as Record<string, unknown> | null | undefined) ?? null;
  const stationLabel = assignedStation
    ? `${String(assignedStation.station_number)} - ${String(assignedStation.name)}`
    : "Sin estación asignada";
  const stationId = Number(assignedStation?.id ?? 0);
  const maxScore = String(assignedStation?.max_score ?? "0");
  const timerDurationSeconds =
    Number(activeCheckin?.station_time_minutes ?? assignedStation?.station_time_minutes ?? 0) *
    60;
  const confirmedAt = String(activeCheckin?.confirmed_at ?? "");
  // Deadline autoritativo del servidor para el REGISTRO del evaluador:
  // incluye el tiempo de transición (el evaluador marca después de que el
  // estudiante sale). Sin esto, la UI bloqueaba antes que el backend.
  const evaluatorDeadline = String(activeCheckin?.evaluator_deadline ?? "");
  const serverNow = String(context?.server_now ?? "");
  // Offset reloj servidor - reloj local: el bloqueo por tiempo no depende
  // del reloj del dispositivo (el backend igualmente re-valida al enviar).
  const serverClockOffsetMs = useMemo(
    () => (serverNow ? clockOffsetMs(serverNow) : 0),
    [serverNow],
  );
  const activeCheckinId = String(activeCheckin?.id ?? "");
  const assessmentTool = (activeCheckin?.assessment_tool ??
    assignedStation?.assessment_tool) as
    | {
        id?: number;
        name?: string;
        tool_type?: string;
        max_score?: number;
        free_observation?: boolean;
        items?: Array<{
          id?: number;
          label?: string;
          score_per_item?: number;
          order_index?: number;
        }>;
      }
    | undefined;
  const assessmentItems = useMemo(() => assessmentTool?.items ?? [], [assessmentTool]);
  const submitted = Boolean(activeCheckin?.evaluator_submission_exists);
  const evaluatorInstruction = String(
    activeCheckin?.evaluator_instruction ?? assignedStation?.evaluator_instruction ?? "",
  ).trim();
  const initialItemScores = useMemo(() => {
    const nextScores: Record<string, number> = {};
    for (const item of assessmentItems) {
      nextScores[String(item.id ?? item.order_index ?? "")] = 0;
    }
    return nextScores;
  }, [assessmentItems]);
  const itemScores =
    itemScoreState.checkinId === activeCheckinId ? itemScoreState.scores : initialItemScores;

  useEffect(() => {
    if (!activeCheckin || !confirmedAt || !timerDurationSeconds) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setNowMs(Date.now());
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [activeCheckin, confirmedAt, timerDurationSeconds]);

  const remainingSeconds = useMemo(() => {
    if (!activeCheckin) {
      return null;
    }
    if (evaluatorDeadline) {
      return Math.max(
        0,
        Math.floor((parseServerUtc(evaluatorDeadline) - (nowMs + serverClockOffsetMs)) / 1000),
      );
    }
    if (!confirmedAt || !timerDurationSeconds) {
      return timerDurationSeconds || null;
    }
    const elapsedSeconds = Math.max(
      0,
      Math.floor((nowMs + serverClockOffsetMs - parseServerUtc(confirmedAt)) / 1000),
    );
    return Math.max(timerDurationSeconds - elapsedSeconds, 0);
  }, [activeCheckin, confirmedAt, evaluatorDeadline, nowMs, serverClockOffsetMs, timerDurationSeconds]);

  const timerLabel = useMemo(() => {
    if (remainingSeconds === null) {
      return "Sin cronómetro activo";
    }
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = remainingSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }, [remainingSeconds]);

  const timeExpired = remainingSeconds !== null && remainingSeconds <= 0 && Boolean(activeCheckin);

  const computedScore = useMemo(
    () => Object.values(itemScores).reduce((sum, value) => sum + Number(value || 0), 0),
    [itemScores],
  );

  const updateItemScore = (itemKey: string, value: number) => {
    setItemScoreState((current) => ({
      checkinId: activeCheckinId,
      scores: {
        ...(current.checkinId === activeCheckinId ? current.scores : initialItemScores),
        [itemKey]: value,
      },
    }));
  };

  const resetForNextStudent = (notice: string) => {
    setEcoeNumber("");
    setScoreObtained("0");
    setObservation("");
    setItemScoreState({ checkinId: "", scores: {} });
    setNowMs(Date.now());
    setContext((current) => (current ? { ...current, active_checkin: null } : current));
    setMessage(notice);
  };

  return (
    <SectionCard
      title="Interfaz del evaluador"
      subtitle="Confirma primero al estudiante correcto y luego registra la evaluación sobre esa misma sesión."
    >
      <div className="grid gap-4 lg:gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <section className="space-y-4 rounded-3xl border border-slate-200 bg-white/80 p-4 lg:p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Estación asignada
            </p>
            <h3 className="mt-2 text-2xl text-slate-900">{stationLabel}</h3>
            <p className="mt-2 text-sm text-slate-600">
              Evaluador: {user?.full_name ?? "Evaluador"}.
            </p>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Tiempo visible de la estación
            </p>
            <p className={`mt-2 text-3xl font-semibold tabular-nums ${timeExpired ? "text-red-600 animate-pulse" : "text-slate-900"}`}>
              {timerLabel}
            </p>
            <p className="mt-2 text-sm text-slate-600">
              {timeExpired
                ? "El tiempo de registro ha terminado. Si necesitas ingresar esta evaluación, contacta a coordinación (registro por contingencia)."
                : "Incluye el tiempo de transición: puedes terminar de registrar mientras el estudiante cambia de estación."}
            </p>
          </div>

          {assignedStation ? (
            <form
              className="space-y-4"
              onSubmit={async (event) => {
                event.preventDefault();
                setMessage(null);
                setConfirmingStudent(true);
                try {
                  const checkin = (await api.confirmStationCheckin(
                    {
                      ecoe_event_id: eventId,
                      station_id: stationId,
                      ecoe_number: ecoeNumber,
                    },
                  )) as Record<string, unknown>;
                  setContext((current) => ({
                    ...(current ?? {}),
                    server_now: checkin.server_now,
                    active_checkin: {
                      id: checkin.checkin_id,
                      station_id: checkin.station_id,
                      student_id: checkin.student_id,
                      student_name: checkin.student_name,
                      student_ecoe_number: checkin.student_ecoe_number,
                      station_name: checkin.station_name,
                      station_number: checkin.station_number,
                      assessment_tool: checkin.assessment_tool,
                      station_time_minutes: checkin.station_time_minutes,
                      confirmed_at: checkin.confirmed_at,
                      submission_deadline: checkin.submission_deadline,
                      evaluator_deadline: checkin.evaluator_deadline,
                      evaluator_submission_exists: false,
                      student_response_exists: false,
                      status: "confirmado",
                    },
                  }));
                  setScoreObtained("0");
                  setObservation("");
                  setEcoeNumber("");
                  setItemScoreState({
                    checkinId: String(checkin.checkin_id ?? ""),
                    scores: Object.fromEntries(
                      (
                        (
                          checkin.assessment_tool as
                            | {
                                items?: Array<{ id?: number; order_index?: number }>;
                              }
                            | undefined
                        )?.items ?? []
                      ).map((item) => [String(item.id ?? item.order_index ?? ""), 0]),
                    ),
                  });
                  setNowMs(Date.now());
                  setMessage("Estudiante confirmado correctamente para esta estación.");
                } catch (error) {
                  setMessage(error instanceof Error ? error.message : "No se pudo confirmar.");
                } finally {
                  setConfirmingStudent(false);
                }
              }}
            >
              <label className="space-y-2">
                <span className="text-sm font-semibold text-slate-700">
                  Numero ECOE del estudiante
                </span>
                <input
                  value={ecoeNumber}
                  onChange={(event) => setEcoeNumber(event.target.value)}
                  placeholder="Ejemplo: 008"
                />
              </label>
              <button className="btn-primary w-full" disabled={confirmingStudent}>
                {confirmingStudent ? "Confirmando..." : "Confirmar ingreso del estudiante"}
              </button>
            </form>
          ) : (
            <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Tu usuario no tiene una estacion asignada en este ECOE.
            </p>
          )}

          {activeCheckin ? (
            <div className="clinical-panel">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
                Estudiante confirmado
              </p>
              <p className="mt-3 text-lg font-semibold text-slate-900">
                {String(activeCheckin.student_ecoe_number)} · {String(activeCheckin.student_name)}
              </p>
              <p className="mt-2 text-sm text-slate-600">
                Verifica siempre número y nombre antes de evaluar.
              </p>
            </div>
          ) : null}
        </section>

        <section className="space-y-4 rounded-3xl border border-slate-200 bg-white/80 p-4 lg:p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Registro de evaluación
            </p>
            <h3 className="mt-2 text-2xl text-slate-900">Pauta de la estación</h3>
          </div>
          {evaluatorInstruction ? (
            <div className="clinical-panel">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
                Guía para el evaluador
              </p>
              <p className="mt-4 text-base leading-7 text-slate-800">
                {evaluatorInstruction}
              </p>
            </div>
          ) : null}

          {!activeCheckin ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Primero confirma al estudiante con su Número ECOE. Cuando envíes la evaluación, esta
              vista se limpiará para identificar al siguiente estudiante.
            </div>
          ) : timeExpired ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 font-semibold">
              ⏰ El tiempo de la estación ha terminado. La evaluación ya no puede enviarse.
            </div>
          ) : (
            <form
              className="grid gap-4"
              onSubmit={async (event) => {
                event.preventDefault();
                const confirmed = window.confirm(
                  "Vas a enviar la evaluación final de esta estación. Luego no se podrá modificar durante el ECOE. ¿Quieres continuar?",
                );
                if (!confirmed) {
                  return;
                }
                setMessage(null);
                setSubmittingEvaluation(true);
                try {
                  await api.submitEvaluator(
                    {
                      checkin_id: Number(activeCheckin.id),
                      ecoe_event_id: eventId,
                      station_id: stationId,
                      student_id: Number(activeCheckin.student_id),
                      evaluator_name: user?.full_name ?? "Evaluador",
                      score_obtained: assessmentItems.length ? computedScore : Number(scoreObtained),
                      max_score: Number(assessmentTool?.max_score ?? maxScore),
                      observation,
                      answers: {
                        tool_id: assessmentTool?.id ?? null,
                        tool_name: assessmentTool?.name ?? null,
                        tool_type: assessmentTool?.tool_type ?? null,
                        item_scores: itemScores,
                      },
                    },
                  );
                  resetForNextStudent(
                    "Evaluación enviada correctamente. Ingresa el Número ECOE del siguiente estudiante.",
                  );
                } catch (error) {
                  setMessage(error instanceof Error ? error.message : "No se pudo guardar.");
                } finally {
                  setSubmittingEvaluation(false);
                }
              }}
            >
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
                Evaluando a {String(activeCheckin.student_ecoe_number)} ·{" "}
                {String(activeCheckin.student_name)}
              </div>
              {assessmentTool ? (
                <div className="space-y-4 rounded-2xl border border-slate-200 bg-white/80 p-4">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">
                      {String(assessmentTool.name ?? "Pauta de evaluación")}
                    </p>
                    <p className="mt-1 text-sm text-slate-600">
                      Tipo: {String(assessmentTool.tool_type ?? "sin definir")}
                    </p>
                  </div>
                  <div className="space-y-3">
                    {assessmentItems.map((item, index) => {
                      const itemKey = String(item.id ?? item.order_index ?? index);
                      const maxItemScore = Number(item.score_per_item ?? 0);
                      const isChecklist = assessmentTool.tool_type === "lista_cotejo";
                      return (
                        <div
                          key={itemKey}
                          className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4"
                        >
                          <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-start">
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-slate-900">
                                {index + 1}. {String(item.label ?? "")}
                              </p>
                              <p className="mt-1 text-xs uppercase tracking-[0.12em] text-slate-500">
                                Puntaje máximo: {maxItemScore}
                              </p>
                            </div>
                            {isChecklist ? (
                              <button
                                type="button"
                                disabled={submitted || timeExpired}
                                className={`flex w-full items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-sm font-semibold transition md:w-auto ${
                                  Number(itemScores[itemKey] ?? 0) > 0
                                    ? "border-[var(--color-primary)] bg-[var(--color-bg-soft)] text-[var(--color-primary-dark)]"
                                    : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                                } ${submitted ? "cursor-not-allowed opacity-70" : ""}`}
                                onClick={() =>
                                  updateItemScore(
                                    itemKey,
                                    Number(itemScores[itemKey] ?? 0) > 0 ? 0 : maxItemScore,
                                  )
                                }
                              >
                                <span>Cumplido</span>
                                <span
                                  className={`rounded-full px-3 py-1 text-xs uppercase tracking-[0.12em] ${
                                    Number(itemScores[itemKey] ?? 0) > 0
                                      ? "bg-[var(--color-primary)] text-white"
                                      : "bg-slate-100 text-slate-500"
                                  }`}
                                >
                                  {Number(itemScores[itemKey] ?? 0) > 0 ? "Sí" : "No"}
                                </span>
                              </button>
                            ) : (
                              <input
                                type="number"
                                min="0"
                                max={String(maxItemScore)}
                                step="0.5"
                                className="w-full md:w-28"
                                value={String(itemScores[itemKey] ?? 0)}
                                disabled={submitted || timeExpired}
                                onChange={(event) =>
                                  updateItemScore(
                                    itemKey,
                                    Math.min(
                                      maxItemScore,
                                      Math.max(0, Number(event.target.value) || 0),
                                    ),
                                  )
                                }
                              />
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  Esta estacion aun no tiene una pauta de evaluacion visible para el evaluador.
                </div>
              )}
              <label className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4">
                <span className="text-sm font-semibold">Puntaje obtenido</span>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={assessmentItems.length ? String(computedScore) : scoreObtained}
                  disabled={submitted || assessmentItems.length > 0}
                  onChange={(event) => setScoreObtained(event.target.value)}
                />
              </label>
              <label className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4">
                <span className="text-sm font-semibold">Puntaje maximo de la estacion</span>
                <input
                  value={String(assessmentTool?.max_score ?? maxScore)}
                  readOnly
                  className="bg-slate-100 text-slate-600"
                />
              </label>
              <label className="space-y-2 rounded-[22px] border border-slate-200 bg-white/80 p-4">
                <span className="text-sm font-semibold">Observación opcional</span>
                <textarea
                  rows={5}
                  value={observation}
                  disabled={submitted || timeExpired}
                  onChange={(event) => setObservation(event.target.value)}
                  placeholder="Comentario breve para retroalimentación o trazabilidad."
                />
              </label>
              <button
                className="btn-primary w-full text-base"
                disabled={submitted || submittingEvaluation || timeExpired}
              >
                {submitted
                  ? "Evaluación ya enviada"
                  : timeExpired
                    ? "Tiempo agotado"
                    : submittingEvaluation
                      ? "Guardando evaluación..."
                      : "Guardar evaluación"}
              </button>
              {submitted ? (
                <p className="text-sm text-amber-700">
                  Esta evaluación ya fue enviada y quedó cerrada para edición durante el ECOE.
                </p>
              ) : null}
            </form>
          )}
        </section>
      </div>
      <StatusNotice message={message} className="mt-4" />
    </SectionCard>
  );
}
