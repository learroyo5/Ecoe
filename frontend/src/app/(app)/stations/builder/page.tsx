"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";

const defaultForm = {
  station_number: "6",
  name: "",
  station_type: "procedimental",
  circuit_name: "Circuito A",
  station_time_minutes: "8",
  transition_time_minutes: "2",
  expected_outcomes: "",
  student_activity: "",
  pre_entry_instruction: "",
  evaluator_instruction: "",
  max_score: "20",
  materials: "",
  multimedia_notes: "",
};

export default function StationBuilderPage() {
  const { token, eventId } = useAuth();
  const { data: templates } = useApi(
    () => api.templates(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );
  const { data: instruments } = useApi(
    () => api.instruments(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );
  const { data: patients } = useApi(
    () => api.simulatedPatients(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );
  const [form, setForm] = useState(defaultForm);
  const [message, setMessage] = useState<string | null>(null);

  return (
    <SectionCard
      title="Constructor de estacion"
      subtitle="Configuracion pedagica, operativa, evaluativa y de contingencia"
    >
      <form
        className="grid gap-4 lg:grid-cols-2"
        onSubmit={async (event) => {
          event.preventDefault();
          setMessage(null);
          try {
            await api.createStation(
              {
                ecoe_event_id: eventId,
                template_id: Number((event.currentTarget.elements.namedItem("template_id") as HTMLSelectElement).value) || null,
                assessment_tool_id:
                  Number((event.currentTarget.elements.namedItem("assessment_tool_id") as HTMLSelectElement).value) || null,
                simulated_patient_id:
                  Number((event.currentTarget.elements.namedItem("simulated_patient_id") as HTMLSelectElement).value) || null,
                ...form,
                station_number: Number(form.station_number),
                station_time_minutes: Number(form.station_time_minutes),
                transition_time_minutes: Number(form.transition_time_minutes),
                max_score: Number(form.max_score),
                requires_evaluator: true,
                requires_student_form: form.station_type === "formulario_estudiante" || form.station_type === "hibrida",
                uses_multimedia: form.station_type === "multimedia" || form.station_type === "hibrida",
                uses_simulated_patient: form.station_type === "paciente_simulado" || form.station_type === "hibrida",
                uses_physical_resources: true,
                student_form_definition: {
                  questions: [
                    {
                      type: "single_choice",
                      label: "Pregunta demo",
                      options: ["Opcion A", "Opcion B", "Opcion C"],
                    },
                  ],
                },
                contingency_ready: true,
                status: "en_diseno",
              },
              token!,
            );
            setMessage("Estacion creada correctamente.");
            setForm(defaultForm);
          } catch (error) {
            setMessage(error instanceof Error ? error.message : "No se pudo guardar.");
          }
        }}
      >
        <label className="space-y-2">
          <span className="text-sm font-semibold">Plantilla base</span>
          <select name="template_id" defaultValue="">
            <option value="">Sin plantilla</option>
            {(templates ?? []).map((template) => (
              <option key={String(template.id)} value={String(template.id)}>
                {String(template.name)}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-2">
          <span className="text-sm font-semibold">Instrumento</span>
          <select name="assessment_tool_id" defaultValue="">
            <option value="">Sin instrumento</option>
            {(instruments ?? []).map((instrument) => (
              <option key={String(instrument.id)} value={String(instrument.id)}>
                {String(instrument.name)}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-2">
          <span className="text-sm font-semibold">Paciente simulado</span>
          <select name="simulated_patient_id" defaultValue="">
            <option value="">No aplica</option>
            {(patients ?? []).map((patient) => (
              <option key={String(patient.id)} value={String(patient.id)}>
                {String(patient.character_name)}
              </option>
            ))}
          </select>
        </label>
        {Object.entries(form).map(([key, value]) => (
          <label key={key} className={`space-y-2 ${key.includes("instruction") || key.includes("outcomes") || key.includes("activity") || key === "materials" || key === "multimedia_notes" ? "lg:col-span-2" : ""}`}>
            <span className="text-sm font-semibold">{key.replaceAll("_", " ")}</span>
            {key.includes("instruction") || key.includes("outcomes") || key.includes("activity") || key === "materials" || key === "multimedia_notes" ? (
              <textarea
                rows={4}
                value={value}
                onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))}
              />
            ) : (
              <input
                value={value}
                onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))}
              />
            )}
          </label>
        ))}
        <div className="lg:col-span-2">
          <button className="btn-primary">Guardar estacion</button>
          {message ? <p className="mt-3 text-sm text-slate-600">{message}</p> : null}
        </div>
      </form>
    </SectionCard>
  );
}
