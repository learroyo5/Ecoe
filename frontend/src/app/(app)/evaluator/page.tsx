"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { clockOffsetMs, parseServerUtc } from "@/lib/time";
import { useLiveTimer } from "@/lib/ws";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";
import { ConfirmDialog, TIMER_TONE_CLASSES, timerTone } from "@/components/confirm-dialog";

// OPT-20 F3 (D3): autoguardado server-side del registro del evaluador —
// debounce por cambio + latido periódico. Al vencer la fase el barrido /
// coordinación tiene un borrador que finalizar en vez de perderlo.
const DRAFT_DEBOUNCE_MS = 800;
const DRAFT_HEARTBEAT_MS = 10000;

export default function EvaluatorPage() {
  const { authenticated, eventId, user } = useECOE();
  const [selectedStationId, setSelectedStationId] = useState<number | null>(null);
  const { data: context, setData: setContext } = useApi(
    () =>
      api.evaluatorContext(eventId, selectedStationId ?? undefined) as Promise<
        Record<string, unknown>
      >,
    [eventId, authenticated, selectedStationId],
  );
  const [ecoeNumber, setEcoeNumber] = useState("");
  const [scoreObtained, setScoreObtained] = useState("0");
  const [observation, setObservation] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [confirmingStudent, setConfirmingStudent] = useState(false);
  const [submittingEvaluation, setSubmittingEvaluation] = useState(false);
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false);
  const [itemScoreState, setItemScoreState] = useState<{
    checkinId: string;
    scores: Record<string, number>;
  }>({
    checkinId: "",
    scores: {},
  });

  const stations = (context?.stations as Record<string, unknown>[] | undefined) ?? [];
  // admin_ecoe/coordinador_operativo ven todas las estaciones del ECOE (para
  // poder hacer check-in en una sin evaluador asignado); un evaluador solo
  // ve su unica estacion principal, asi que el selector no aparece.
  const canPickStation = stations.length > 1;
  const contextSelectedStationId = context?.selected_station_id != null
    ? Number(context.selected_station_id)
    : null;
  const assignedStation =
    stations.find((s) => Number(s.id) === (selectedStationId ?? contextSelectedStationId)) ??
    stations[0];
  useEffect(() => {
    if (selectedStationId === null && contextSelectedStationId !== null) {
      setSelectedStationId(contextSelectedStationId);
    }
  }, [contextSelectedStationId, selectedStationId]);
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

  // ── Reloj central (OPT-20 F1) ──────────────────────────────────────
  // El evaluador escucha el cronómetro: en pausa se muestra un banner y se
  // deshabilita "Guardar evaluación" (el registro sigue editable).
  const { snapshot: liveSnapshot } = useLiveTimer(eventId, { enabled: authenticated });
  const liveStatus =
    liveSnapshot?.status ?? (context?.live_status as string | null | undefined) ?? null;
  const livePaused = liveStatus === "paused";
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
  const windowTotalSeconds = useMemo(() => {
    if (evaluatorDeadline && confirmedAt) {
      return Math.max(0, Math.floor((parseServerUtc(evaluatorDeadline) - parseServerUtc(confirmedAt)) / 1000));
    }
    return timerDurationSeconds;
  }, [confirmedAt, evaluatorDeadline, timerDurationSeconds]);
  const tone = timeExpired ? "danger" : timerTone(remainingSeconds, windowTotalSeconds);

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

  // ── Borrador server-side (OPT-20 F3) ────────────────────────────────
  const [draftSavedAt, setDraftSavedAt] = useState<Date | null>(null);
  const draftBodyRef = useRef<Record<string, unknown> | null>(null);
  const scoreForDraft = assessmentItems.length ? computedScore : Number(scoreObtained) || 0;
  useEffect(() => {
    if (!activeCheckin) {
      draftBodyRef.current = null;
      return;
    }
    draftBodyRef.current = {
      ecoe_event_id: eventId,
      station_id: stationId,
      student_id: Number(activeCheckin.student_id),
      checkin_id: Number(activeCheckin.id),
      evaluator_name: user?.full_name ?? "Evaluador",
      score_obtained: scoreForDraft,
      observation,
      answers: {
        tool_id: assessmentTool?.id ?? null,
        tool_name: assessmentTool?.name ?? null,
        tool_type: assessmentTool?.tool_type ?? null,
        item_scores: itemScores,
      },
    };
  }, [activeCheckin, eventId, stationId, user, scoreForDraft, observation, assessmentTool, itemScores]);

  const pushDraft = useCallback(() => {
    const body = draftBodyRef.current;
    if (!body) return;
    api
      .evaluatorDraft(body as Parameters<typeof api.evaluatorDraft>[0])
      .then(() => setDraftSavedAt(new Date()))
      .catch(() => {
        /* mejor esfuerzo: el barrido / contingencia cubren el resto */
      });
  }, []);

  const draftActive = Boolean(activeCheckin) && !submitted && !timeExpired;
  useEffect(() => {
    if (!draftActive) return;
    const timeoutId = window.setTimeout(pushDraft, DRAFT_DEBOUNCE_MS);
    return () => window.clearTimeout(timeoutId);
  }, [draftActive, scoreForDraft, observation, itemScores, pushDraft]);
  useEffect(() => {
    if (!draftActive) return;
    const intervalId = window.setInterval(pushDraft, DRAFT_HEARTBEAT_MS);
    return () => window.clearInterval(intervalId);
  }, [draftActive, pushDraft]);

  const submitEvaluation = async () => {
    if (!activeCheckin) return;
    if (livePaused) {
      setShowSubmitConfirm(false);
      setMessage("El cronómetro central está en pausa: la evaluación se enviará al reanudar.");
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
      setShowSubmitConfirm(false);
      resetForNextStudent(
        "Evaluación enviada correctamente. Ingresa el Número ECOE del siguiente estudiante.",
      );
    } catch (error) {
      setShowSubmitConfirm(false);
      setMessage(error instanceof Error ? error.message : "No se pudo guardar.");
    } finally {
      setSubmittingEvaluation(false);
    }
  };

  const resetForNextStudent = (notice: string) => {
    setEcoeNumber("");
    setScoreObtained("0");
    setObservation("");
    setItemScoreState({ checkinId: "", scores: {} });
    setDraftSavedAt(null);
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
              {canPickStation ? "Estación a operar" : "Estación asignada"}
            </p>
            {canPickStation ? (
              <select
                className="mt-2 w-full"
                value={String(assignedStation?.id ?? "")}
                onChange={(event) => setSelectedStationId(Number(event.target.value))}
              >
                {stations.map((station) => (
                  <option key={String(station.id)} value={String(station.id)}>
                    {String(station.station_number)} - {String(station.name)}
                  </option>
                ))}
              </select>
            ) : (
              <h3 className="mt-2 text-2xl text-slate-900">{stationLabel}</h3>
            )}
            <p className="mt-2 text-sm text-slate-600">
              {canPickStation
                ? "Sin evaluador asignado a esta estación: puedes hacer el check-in tú mismo (contingencia o ensayo)."
                : `Evaluador: ${user?.full_name ?? "Evaluador"}.`}
            </p>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Tiempo visible de la estación
            </p>
            <p className={`mt-2 text-3xl font-semibold tabular-nums ${TIMER_TONE_CLASSES[tone]}`}>
              {timerLabel}
            </p>
            <p className="mt-2 text-sm text-slate-600">
              {timeExpired
                ? "El tiempo de registro ha terminado. Si necesitas ingresar esta evaluación, contacta a coordinación (registro por contingencia)."
                : "Incluye el tiempo de transición: puedes terminar de registrar mientras el estudiante cambia de estación."}
            </p>
          </div>

          {livePaused ? (
            <div
              role="alert"
              className="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-900"
            >
              ⏸ Pausa en curso — el cronómetro central está detenido. Tu registro
              sigue editable, pero no puede enviarse hasta que se reanude.
            </div>
          ) : null}

          {assignedStation ? (
            <form
              className="flex flex-col gap-4"
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
              <label className="flex flex-col gap-2">
                <span className="text-sm font-semibold text-slate-700">
                  Número ECOE del estudiante
                </span>
                <input
                  value={ecoeNumber}
                  onChange={(event) => setEcoeNumber(event.target.value)}
                  placeholder="Ejemplo: E007"
                />
              </label>
              <button className="btn-primary w-full" disabled={confirmingStudent}>
                {confirmingStudent ? "Confirmando..." : "Confirmar ingreso del estudiante"}
              </button>
            </form>
          ) : (
            <p className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Tu usuario no tiene una estación asignada en este ECOE.
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
            <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              <p className="font-semibold">⏰ Tiempo agotado.</p>
              <p className="mt-1">
                Tu registro quedó guardado como <strong>borrador</strong>
                {draftSavedAt ? ` (última copia ${draftSavedAt.toLocaleTimeString()})` : ""}. Complétalo
                con coordinación en la ventana de contingencia; ya no puede enviarse desde aquí.
              </p>
            </div>
          ) : (
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                setShowSubmitConfirm(true);
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
                  Esta estación aún no tiene una pauta de evaluación visible para el evaluador.
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
                <span className="text-sm font-semibold">Puntaje máximo de la estación</span>
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
                  onBlur={pushDraft}
                  placeholder="Comentario breve para retroalimentación o trazabilidad."
                />
              </label>
              {draftSavedAt && !submitted ? (
                <p className="text-xs text-slate-500">
                  ✓ Borrador guardado a las {draftSavedAt.toLocaleTimeString()} — si se acaba el
                  tiempo, coordinación puede finalizarlo por contingencia.
                </p>
              ) : null}
              <button
                className="btn-primary w-full text-base"
                disabled={submitted || submittingEvaluation || timeExpired || livePaused}
              >
                {submitted
                  ? "Evaluación ya enviada"
                  : timeExpired
                    ? "Tiempo agotado"
                    : livePaused
                      ? "Pausa en curso"
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
      <ConfirmDialog
        open={showSubmitConfirm}
        title="Enviar evaluación final"
        message="Una vez enviada, la evaluación queda cerrada y no puede modificarse durante el ECOE."
        confirmLabel="Enviar evaluación"
        severity="danger"
        busy={submittingEvaluation}
        onConfirm={submitEvaluation}
        onCancel={() => setShowSubmitConfirm(false)}
      >
        {activeCheckin ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-800">
            <p className="font-semibold">
              {String(activeCheckin.student_ecoe_number)} · {String(activeCheckin.student_name)}
            </p>
            <p className="mt-2">
              Puntaje a registrar:{" "}
              <span className="font-semibold">
                {assessmentItems.length ? computedScore : Number(scoreObtained)} /{" "}
                {String(assessmentTool?.max_score ?? maxScore)} pts
              </span>
            </p>
            {observation.trim() ? (
              <p className="mt-2 text-slate-600">Observación: {observation.trim().slice(0, 120)}</p>
            ) : null}
          </div>
        ) : null}
      </ConfirmDialog>
    </SectionCard>
  );
}
