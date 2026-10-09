"use client";

import { useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

type Question = { type?: string; label?: string; options?: string[]; points?: number };

/**
 * Transcripción por contingencia (PROC-2): lo que se resolvió en papel o lo
 * que quedó mal registrado se ingresa aquí, estación por estación. Sólo
 * mientras el ECOE está en pilotaje o en ejecución; tras el cierre el acta
 * queda congelada. Todo queda en la auditoría con el valor anterior.
 */
export default function ContingencyPage() {
  const { authenticated, eventId, user } = useECOE();
  const { data: stations } = useApi(
    () => api.stations(eventId) as Promise<Record<string, unknown>[]>,
    [eventId, authenticated],
  );
  // Nómina completa: se recorren todas las páginas (el máximo por página es 100).
  const { data: studentsPage } = useApi(async () => {
    const items: Record<string, unknown>[] = [];
    for (let page = 1; page <= 50; page += 1) {
      const chunk = (await api.students(eventId, page, 100)) as { items?: Record<string, unknown>[]; pages?: number };
      items.push(...(chunk.items ?? []));
      if (page >= Number(chunk.pages ?? 1)) break;
    }
    return { items };
  }, [eventId, authenticated]);
  const [stationId, setStationId] = useState("");
  const [ecoeNumber, setEcoeNumber] = useState("");
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [score, setScore] = useState("");
  const [observation, setObservation] = useState("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const station = (stations ?? []).find((item) => String(item.id) === stationId) ?? null;
  const students = useMemo(
    () => ((studentsPage as { items?: Record<string, unknown>[] } | null)?.items ?? []),
    [studentsPage],
  );
  const normalized = ecoeNumber.trim().toLowerCase().replace(/^[a-z]*0*/, "");
  const student = normalized
    ? students.find(
        (item) => String(item.ecoe_number ?? "").toLowerCase().replace(/^[a-z]*0*/, "") === normalized,
      ) ?? null
    : null;
  const questions = ((station?.student_form_definition as { questions?: Question[] } | undefined)?.questions ?? []);
  const ready = Boolean(station && student);

  const run = async (action: () => Promise<unknown>, okMessage: string) => {
    setBusy(true);
    setMessage(null);
    try {
      await action();
      setMessage(okMessage);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo registrar.");
    } finally {
      setBusy(false);
    }
  };

  const target = {
    ecoe_event_id: eventId,
    station_id: Number(stationId),
    student_id: Number(student?.id ?? 0),
  };
  const evaluatorPayload = {
    ...target,
    evaluator_name: user?.full_name ?? "Coordinación",
    score_obtained: Number(score),
    max_score: Number(station?.max_score ?? 0),
    observation,
    answers: {},
  };

  return (
    <div className="space-y-6">
      <SectionCard
        title="Registro por contingencia"
        subtitle="Transcribe aquí lo que se resolvió en papel o corrige un registro equivocado. Requiere que el ingreso del estudiante a la estación se haya confirmado alguna vez. Sólo funciona con el ECOE en pilotaje o en ejecución: hazlo antes de cerrar."
      >
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-1 text-sm">
            <span className="font-semibold">Estación</span>
            <select value={stationId} onChange={(event) => { setStationId(event.target.value); setAnswers({}); setMessage(null); }}>
              <option value="">Selecciona una estación</option>
              {(stations ?? []).map((item) => (
                <option key={String(item.id)} value={String(item.id)}>
                  {String(item.station_number)} · {String(item.name)}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-sm">
            <span className="font-semibold">Número ECOE del estudiante</span>
            <input value={ecoeNumber} onChange={(event) => { setEcoeNumber(event.target.value); setMessage(null); }} placeholder="Ejemplo: E007" />
            <span className="block text-slate-600">
              {student
                ? `${String(student.ecoe_number)} · ${String(student.name)} ${String(student.last_name)}`
                : ecoeNumber.trim()
                  ? "No hay un estudiante con ese número en este ECOE."
                  : ""}
            </span>
          </label>
        </div>
        <StatusNotice message={message} />
      </SectionCard>

      {ready && station?.requires_student_form ? (
        <SectionCard
          title="Respuesta del estudiante"
          subtitle="Reemplaza una respuesta autoenviada por el servidor (en blanco o parcial). Una respuesta que el estudiante envió por sí mismo no se puede reemplazar."
        >
          <div className="space-y-4">
            {questions.map((question, index) => {
              const key = `question_${index + 1}`;
              return (
                <div key={key} className="rounded-2xl border border-slate-200 bg-white p-4">
                  <p className="text-sm font-semibold text-slate-900">
                    {index + 1}. {question.label ?? ""}
                  </p>
                  {question.type === "single_choice" ? (
                    <div className="mt-2 space-y-1">
                      {(question.options ?? []).map((option) => (
                        <label key={option} className="flex items-center gap-2 text-sm">
                          <input type="radio" name={key} checked={answers[key] === option}
                            onChange={() => setAnswers((current) => ({ ...current, [key]: option }))} />
                          {option}
                        </label>
                      ))}
                    </div>
                  ) : question.type === "multiple_choice" ? (
                    <div className="mt-2 space-y-1">
                      {(question.options ?? []).map((option) => {
                        const selected = Array.isArray(answers[key]) ? (answers[key] as string[]) : [];
                        return (
                          <label key={option} className="flex items-center gap-2 text-sm">
                            <input type="checkbox" checked={selected.includes(option)}
                              onChange={(event) => setAnswers((current) => ({
                                ...current,
                                [key]: event.target.checked ? [...selected, option] : selected.filter((item) => item !== option),
                              }))} />
                            {option}
                          </label>
                        );
                      })}
                    </div>
                  ) : (
                    <textarea className="mt-2" rows={3} value={String(answers[key] ?? "")}
                      aria-label={`Respuesta ${index + 1}`}
                      onChange={(event) => setAnswers((current) => ({ ...current, [key]: event.target.value }))} />
                  )}
                </div>
              );
            })}
            <button type="button" className="btn-primary disabled:opacity-50" disabled={busy}
              onClick={() => run(
                () => api.contingencyStudentResponse({ ...target, answers }),
                "Respuesta registrada por contingencia.",
              )}>
              Registrar respuesta del estudiante
            </button>
          </div>
        </SectionCard>
      ) : null}

      {ready && station?.requires_evaluator ? (
        <SectionCard
          title="Evaluación del evaluador"
          subtitle={`Puntaje total de la pauta en papel (máximo ${String(station?.max_score ?? "")}). Para corregir una evaluación ya enviada se exige el motivo, que queda en la auditoría junto al valor anterior.`}
        >
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-1 text-sm">
              <span className="font-semibold">Puntaje obtenido</span>
              <input type="number" min={0} step="0.5" value={score} onChange={(event) => setScore(event.target.value)} />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-semibold">Observación</span>
              <input value={observation} onChange={(event) => setObservation(event.target.value)} />
            </label>
            <label className="space-y-1 text-sm md:col-span-2">
              <span className="font-semibold">Motivo de la rectificación (sólo si ya había una evaluación enviada)</span>
              <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Ejemplo: puntaje mal digitado por el evaluador" />
            </label>
          </div>
          <div className="flex flex-wrap gap-3">
            <button type="button" className="btn-primary disabled:opacity-50" disabled={busy || score === ""}
              onClick={() => run(
                () => api.finalizeEvaluatorRecord(evaluatorPayload),
                "Evaluación registrada por contingencia.",
              )}>
              Registrar evaluación
            </button>
            <button type="button" className="btn-secondary disabled:opacity-50"
              disabled={busy || score === "" || reason.trim().length < 10}
              title={reason.trim().length < 10 ? "Escribe el motivo (al menos 10 caracteres)" : undefined}
              onClick={() => run(
                () => api.rectifyEvaluatorRecord({ ...target, evaluator_name: evaluatorPayload.evaluator_name, score_obtained: Number(score), observation, answers: {}, reason: reason.trim() }),
                "Evaluación rectificada. El valor anterior quedó en la auditoría.",
              )}>
              Rectificar evaluación enviada
            </button>
          </div>
        </SectionCard>
      ) : null}
    </div>
  );
}
