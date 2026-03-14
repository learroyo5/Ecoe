"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";

export default function StudentPage() {
  const { token, eventId } = useAuth();
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
    <SectionCard title="Interfaz del estudiante" subtitle="Identificacion simple, instrucciones visibles y bloqueo al enviar">
      <form
        className="grid gap-4"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          try {
            await api.submitStudent(
              {
                ecoe_event_id: eventId,
                station_id: Number(form.get("station_id")),
                student_id: Number(form.get("student_id")),
                answers: {
                  diagnostico: form.get("diagnostico"),
                  plan: form.get("plan"),
                },
                locked: true,
              },
              token!,
            );
            setMessage("Respuesta enviada. El formulario queda bloqueado.");
          } catch (error) {
            setMessage(error instanceof Error ? error.message : "No se pudo enviar.");
          }
        }}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-sm font-semibold">Numero ECOE</span>
            <select name="student_id" defaultValue="">
              <option value="">Seleccionar estudiante</option>
              {(students ?? []).map((student) => (
                <option key={String(student.id)} value={String(student.id)}>
                  {String(student.ecoe_number)} - {String(student.name)} {String(student.last_name)}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-2">
            <span className="text-sm font-semibold">Estacion cognitiva</span>
            <select name="station_id" defaultValue="">
              <option value="">Seleccionar estacion</option>
              {(stations ?? []).map((station) => (
                <option key={String(station.id)} value={String(station.id)}>
                  {String(station.station_number)} - {String(station.name)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="rounded-3xl bg-white/70 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-teal-700">
            Instruccion visible antes de entrar
          </p>
          <p className="mt-3 text-base text-slate-700">
            Lea el caso, identifique el problema principal y responda dentro del tiempo asignado.
          </p>
        </div>
        <label className="space-y-2">
          <span className="text-sm font-semibold">Pregunta de seleccion unica</span>
          <select name="diagnostico" defaultValue="SCA">
            <option value="SCA">Sindrome coronario agudo</option>
            <option value="TEP">Tromboembolismo pulmonar</option>
            <option value="RGE">Reflujo gastroesofagico</option>
          </select>
        </label>
        <label className="space-y-2">
          <span className="text-sm font-semibold">Respuesta extensa</span>
          <textarea
            name="plan"
            rows={6}
            placeholder="Escriba su razonamiento clinico, plan diagnostico y conducta inicial."
          />
        </label>
        <button className="btn-primary w-full text-base">Enviar respuesta final</button>
        {message ? <p className="text-sm text-slate-600">{message}</p> : null}
      </form>
    </SectionCard>
  );
}
