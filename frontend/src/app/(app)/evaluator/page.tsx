"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";

export default function EvaluatorPage() {
  const { token, eventId, user } = useAuth();
  const { data: students } = useApi(
    () => api.students(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );
  const { data: stations } = useApi(
    () => api.stations(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );

  const [message, setMessage] = useState<string | null>(null);

  return (
    <SectionCard title="Interfaz del evaluador" subtitle="Flujo de pocos clics, botones grandes y confirmacion inmediata">
      <form
        className="grid gap-4 md:grid-cols-2"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          try {
            await api.submitEvaluator(
              {
                ecoe_event_id: eventId,
                station_id: Number(form.get("station_id")),
                student_id: Number(form.get("student_id")),
                evaluator_name: user?.full_name ?? "Evaluador",
                score_obtained: Number(form.get("score_obtained")),
                max_score: Number(form.get("max_score")),
                observation: String(form.get("observation") ?? ""),
                answers: { checklist: "completada" },
              },
              token!,
            );
            setMessage("Evaluacion guardada correctamente.");
            event.currentTarget.reset();
          } catch (error) {
            setMessage(error instanceof Error ? error.message : "No se pudo guardar.");
          }
        }}
      >
        <label className="space-y-2">
          <span className="text-sm font-semibold">Estacion asignada</span>
          <select name="station_id" defaultValue="">
            <option value="">Seleccionar</option>
            {(stations ?? []).map((station) => (
              <option key={String(station.id)} value={String(station.id)}>
                {String(station.station_number)} - {String(station.name)}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-2">
          <span className="text-sm font-semibold">Estudiante por numero ECOE</span>
          <select name="student_id" defaultValue="">
            <option value="">Seleccionar</option>
            {(students ?? []).map((student) => (
              <option key={String(student.id)} value={String(student.id)}>
                {String(student.ecoe_number)} - {String(student.name)} {String(student.last_name)}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-2">
          <span className="text-sm font-semibold">Puntaje obtenido</span>
          <input name="score_obtained" type="number" min="0" step="0.1" defaultValue="18" />
        </label>
        <label className="space-y-2">
          <span className="text-sm font-semibold">Puntaje maximo</span>
          <input name="max_score" type="number" min="1" step="0.1" defaultValue="20" />
        </label>
        <label className="space-y-2 md:col-span-2">
          <span className="text-sm font-semibold">Observacion opcional</span>
          <textarea name="observation" rows={4} placeholder="Comentario breve para retroalimentacion o trazabilidad." />
        </label>
        <div className="md:col-span-2">
          <button className="btn-primary w-full text-base">Enviar evaluacion</button>
          {message ? <p className="mt-3 text-sm text-slate-600">{message}</p> : null}
        </div>
      </form>
    </SectionCard>
  );
}
