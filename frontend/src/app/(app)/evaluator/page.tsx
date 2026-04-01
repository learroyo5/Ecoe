"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";

export default function EvaluatorPage() {
  const { token, eventId, user } = useAuth();
  const { data: context, setData: setContext } = useApi(
    () => api.evaluatorContext(eventId, token!) as Promise<Record<string, unknown>>,
    [eventId, token],
  );
  const [ecoeNumber, setEcoeNumber] = useState("");
  const [scoreObtained, setScoreObtained] = useState("0");
  const [observation, setObservation] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [itemScores, setItemScores] = useState<Record<string, number>>({});

  const stations = (context?.stations as Record<string, unknown>[] | undefined) ?? [];
  const assignedStation = stations[0];
  const activeCheckin = (context?.active_checkin as Record<string, unknown> | null | undefined) ?? null;
  const stationLabel = assignedStation
    ? `${String(assignedStation.station_number)} - ${String(assignedStation.name)}`
    : "Sin estacion asignada";
  const stationId = Number(assignedStation?.id ?? 0);
  const maxScore = String(assignedStation?.max_score ?? "0");
  const timerDurationSeconds = Number(activeCheckin?.station_time_minutes ?? assignedStation?.station_time_minutes ?? 0) * 60;
  const confirmedAt = String(activeCheckin?.confirmed_at ?? "");
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
  const assessmentItems = assessmentTool?.items ?? [];

  useEffect(() => {
    const nextScores: Record<string, number> = {};
    for (const item of assessmentItems) {
      nextScores[String(item.id ?? item.order_index ?? "")] = 0;
    }
    setItemScores(nextScores);
  }, [activeCheckin?.id, assessmentItems]);

  useEffect(() => {
    setSubmitted(Boolean(activeCheckin?.evaluator_submission_exists));
  }, [activeCheckin]);

  useEffect(() => {
    if (!activeCheckin || !confirmedAt || !timerDurationSeconds) {
      setRemainingSeconds(timerDurationSeconds || null);
      return;
    }

    const updateTimer = () => {
      const elapsedSeconds = Math.max(
        0,
        Math.floor((Date.now() - new Date(confirmedAt).getTime()) / 1000),
      );
      setRemainingSeconds(Math.max(timerDurationSeconds - elapsedSeconds, 0));
    };

    updateTimer();
    const intervalId = window.setInterval(updateTimer, 1000);
    return () => window.clearInterval(intervalId);
  }, [activeCheckin, confirmedAt, timerDurationSeconds]);

  const timerLabel = useMemo(() => {
    if (remainingSeconds === null) {
      return "Sin cronometro activo";
    }
    const minutes = Math.floor(remainingSeconds / 60);
    const seconds = remainingSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }, [remainingSeconds]);

  const computedScore = useMemo(
    () => Object.values(itemScores).reduce((sum, value) => sum + Number(value || 0), 0),
    [itemScores],
  );

  const resetForNextStudent = (notice: string) => {
    setEcoeNumber("");
    setScoreObtained("0");
    setObservation("");
    setSubmitted(false);
    setItemScores({});
    setRemainingSeconds(Number(assignedStation?.station_time_minutes ?? 0) * 60 || null);
    setContext((current) => (current ? { ...current, active_checkin: null } : current));
    setMessage(notice);
  };

  return (
    <SectionCard
      title="Interfaz del evaluador"
      subtitle="Confirma primero al estudiante correcto y luego registra la evaluacion sobre esa misma sesion."
    >
      <div className="grid gap-4 lg:gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <section className="space-y-4 rounded-3xl border border-slate-200 bg-white/80 p-4 lg:p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Estacion asignada
            </p>
            <h3 className="mt-2 text-2xl text-slate-900">{stationLabel}</h3>
            <p className="mt-2 text-sm text-slate-600">
              Evaluador: {user?.full_name ?? "Evaluador"}.
            </p>
          </div>

          <div className="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Tiempo visible de la estacion
            </p>
            <p className="mt-2 text-3xl font-semibold text-slate-900">{timerLabel}</p>
            <p className="mt-2 text-sm text-slate-600">
              El evaluador visualiza el tiempo, pero el cierre de su evaluacion sigue siendo manual.
            </p>
          </div>

          {assignedStation ? (
            <form
              className="space-y-4"
              onSubmit={async (event) => {
                event.preventDefault();
                setMessage(null);
                try {
                  const checkin = (await api.confirmStationCheckin(
                    {
                      ecoe_event_id: eventId,
                      station_id: stationId,
                      ecoe_number: ecoeNumber,
                    },
                    token!,
                  )) as Record<string, unknown>;
                  setContext((current) => ({
                    ...(current ?? {}),
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
                      evaluator_submission_exists: false,
                      student_response_exists: false,
                      status: "confirmado",
                    },
                  }));
                  setScoreObtained("0");
                  setObservation("");
                  setEcoeNumber("");
                  setSubmitted(false);
                  setMessage("Estudiante confirmado correctamente para esta estacion.");
                } catch (error) {
                  setMessage(error instanceof Error ? error.message : "No se pudo confirmar.");
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
              <button className="btn-primary w-full">Confirmar ingreso del estudiante</button>
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
                Verifica siempre numero y nombre antes de evaluar.
              </p>
            </div>
          ) : null}
        </section>

        <section className="space-y-4 rounded-3xl border border-slate-200 bg-white/80 p-4 lg:p-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
              Registro de evaluacion
            </p>
            <h3 className="mt-2 text-2xl text-slate-900">Pauta de la estacion</h3>
          </div>

          {!activeCheckin ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Primero confirma al estudiante con su Numero ECOE. Cuando envies la evaluacion, esta
              vista se limpiara para identificar al siguiente estudiante.
            </div>
          ) : (
            <form
              className="grid gap-4"
              onSubmit={async (event) => {
                event.preventDefault();
                const confirmed = window.confirm(
                  "Vas a enviar la evaluacion final de esta estacion. Luego no se podra modificar durante el ECOE. ¿Quieres continuar?",
                );
                if (!confirmed) {
                  return;
                }
                setMessage(null);
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
                    token!,
                  );
                  resetForNextStudent(
                    "Evaluacion enviada correctamente. Ingresa el Numero ECOE del siguiente estudiante.",
                  );
                } catch (error) {
                  setMessage(error instanceof Error ? error.message : "No se pudo guardar.");
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
                      {String(assessmentTool.name ?? "Pauta de evaluacion")}
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
                                Puntaje maximo: {maxItemScore}
                              </p>
                            </div>
                            {isChecklist ? (
                              <button
                                type="button"
                                disabled={submitted}
                                className={`flex w-full items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-sm font-semibold transition md:w-auto ${
                                  Number(itemScores[itemKey] ?? 0) > 0
                                    ? "border-[var(--color-primary)] bg-[var(--color-bg-soft)] text-[var(--color-primary-dark)]"
                                    : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                                } ${submitted ? "cursor-not-allowed opacity-70" : ""}`}
                                onClick={() =>
                                  setItemScores((current) => ({
                                    ...current,
                                    [itemKey]:
                                      Number(current[itemKey] ?? 0) > 0 ? 0 : maxItemScore,
                                  }))
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
                                  {Number(itemScores[itemKey] ?? 0) > 0 ? "Si" : "No"}
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
                                disabled={submitted}
                                onChange={(event) =>
                                  setItemScores((current) => ({
                                    ...current,
                                    [itemKey]: Math.min(
                                      maxItemScore,
                                      Math.max(0, Number(event.target.value) || 0),
                                    ),
                                  }))
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
                <span className="text-sm font-semibold">Observacion opcional</span>
                <textarea
                  rows={5}
                  value={observation}
                  disabled={submitted}
                  onChange={(event) => setObservation(event.target.value)}
                  placeholder="Comentario breve para retroalimentacion o trazabilidad."
                />
              </label>
              <button className="btn-primary w-full text-base" disabled={submitted}>
                {submitted ? "Evaluacion ya enviada" : "Guardar evaluacion"}
              </button>
              {submitted ? (
                <p className="text-sm text-amber-700">
                  Esta evaluacion ya fue enviada y quedo cerrada para edicion durante el ECOE.
                </p>
              ) : null}
            </form>
          )}
        </section>
      </div>
      {message ? <p className="mt-4 text-sm text-slate-600">{message}</p> : null}
    </SectionCard>
  );
}
