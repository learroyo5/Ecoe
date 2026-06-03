"use client";

import { useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

const defaultValues = {
  name: "",
  category: "procedimental",
  description: "",
  requires_evaluator: true,
  requires_student_form: false,
  uses_multimedia: false,
  uses_simulated_patient: false,
};

const categoryOptions = [
  { value: "procedimental", label: "Procedimental" },
  { value: "paciente_simulado", label: "Paciente simulado" },
  { value: "formulario_estudiante", label: "Formulario estudiante" },
  { value: "multimedia", label: "Multimedia" },
  { value: "hibrida", label: "Híbrida" },
];

function FeatureToggle({
  checked,
  description,
  label,
  onChange,
}: {
  checked: boolean;
  description: string;
  label: string;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 text-sm text-slate-700">
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-1"
      />
      <span className="space-y-1">
        <span className="block font-semibold text-slate-900">{label}</span>
        <span className="block text-xs leading-5 text-slate-500">{description}</span>
      </span>
    </label>
  );
}

export default function TemplatesPage() {
  const { token } = useECOE();
  const { data, loading, error, setData } = useApi(
    () => api.templates(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );
  const [values, setValues] = useState(defaultValues);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = async () => setData((await api.templates(token!)) as Record<string, unknown>[]);
  const selectedCategoryLabel =
    categoryOptions.find((option) => option.value === values.category)?.label ?? values.category;
  const activeFeatures = useMemo(() => {
    const features: string[] = [];
    if (values.requires_evaluator) {
      features.push("Evaluador");
    }
    if (values.requires_student_form) {
      features.push("Formulario estudiante");
    }
    if (values.uses_multimedia) {
      features.push("Multimedia");
    }
    if (values.uses_simulated_patient) {
      features.push("Paciente simulado");
    }
    return features;
  }, [values]);

  return (
    <div className="space-y-6">
      <SectionCard
        title="Banco de plantillas"
        subtitle="Define estructuras base reutilizables para orientar el flujo real de cada tipo de estación."
      >
        <form
          className="space-y-5"
          onSubmit={async (event) => {
            event.preventDefault();
            setSaving(true);
            setMessage(null);
            try {
              await api.createTemplate(
                {
                  name: values.name,
                  category: values.category,
                  description: values.description,
                  default_configuration: {
                    requires_evaluator: values.requires_evaluator,
                    requires_student_form: values.requires_student_form,
                    uses_multimedia: values.uses_multimedia,
                    uses_simulated_patient: values.uses_simulated_patient,
                    source: "manual",
                  },
                },
                token!,
              );
              await refresh();
              setValues(defaultValues);
              setMessage("Plantilla guardada correctamente.");
            } catch (saveError) {
              setMessage(
                saveError instanceof Error ? saveError.message : "No se pudo guardar la plantilla.",
              );
            } finally {
              setSaving(false);
            }
          }}
        >
          <div className="grid gap-4 lg:grid-cols-2">
            <label className="space-y-2">
              <span className="text-sm font-semibold text-slate-800">Nombre</span>
              <input
                value={values.name}
                onChange={(event) => setValues((current) => ({ ...current, name: event.target.value }))}
                placeholder="Ejemplo: Estación híbrida con multimedia"
              />
            </label>
            <label className="space-y-2">
              <span className="text-sm font-semibold text-slate-800">Categoría</span>
              <select
                value={values.category}
                onChange={(event) =>
                  setValues((current) => ({ ...current, category: event.target.value }))
                }
              >
                {categoryOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-2 lg:col-span-2">
              <span className="text-sm font-semibold text-slate-800">Descripción</span>
              <textarea
                rows={4}
                value={values.description}
                onChange={(event) =>
                  setValues((current) => ({ ...current, description: event.target.value }))
                }
                placeholder="Describe cuándo conviene usar esta plantilla y qué tipo de flujo activa."
              />
            </label>
          </div>

          <div className="space-y-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">Configuración operativa por defecto</p>
              <p className="mt-1 text-xs leading-5 text-slate-500">
                Estas banderas son las que luego consume el constructor para activar evaluador,
                formulario del estudiante, multimedia o paciente simulado.
              </p>
            </div>
            <div className="grid gap-3 lg:grid-cols-2">
              <FeatureToggle
                checked={values.requires_evaluator}
                label="Requiere evaluador"
                description="La estación espera pauta e instrucciones para evaluación observacional."
                onChange={(checked) =>
                  setValues((current) => ({ ...current, requires_evaluator: checked }))
                }
              />
              <FeatureToggle
                checked={values.requires_student_form}
                label="Usa formulario del estudiante"
                description="Activa preguntas que el estudiante responderá dentro de la estación."
                onChange={(checked) =>
                  setValues((current) => ({ ...current, requires_student_form: checked }))
                }
              />
              <FeatureToggle
                checked={values.uses_multimedia}
                label="Usa multimedia"
                description="Marca que la estación puede requerir imágenes, audio, video o PDF."
                onChange={(checked) =>
                  setValues((current) => ({ ...current, uses_multimedia: checked }))
                }
              />
              <FeatureToggle
                checked={values.uses_simulated_patient}
                label="Usa paciente simulado"
                description="Marca que esta plantilla normalmente espera un personaje asociado."
                onChange={(checked) =>
                  setValues((current) => ({ ...current, uses_simulated_patient: checked }))
                }
              />
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-700">
            <p className="font-semibold text-slate-900">Resumen de la plantilla</p>
            <p className="mt-2">Categoría: {selectedCategoryLabel}</p>
            <p className="mt-1">
              Flujo activado: {activeFeatures.length ? activeFeatures.join(" · ") : "Sin banderas activas"}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button className="btn-primary" disabled={saving}>
              {saving ? "Guardando..." : "Guardar plantilla"}
            </button>
            <span className="text-sm text-slate-600">
              El constructor usará esta configuración como base al seleccionar la plantilla.
            </span>
          </div>
          <StatusNotice message={message} />
        </form>
      </SectionCard>

      <SectionCard
        title="Plantillas disponibles"
        subtitle="Repositorio de configuraciones operativas reutilizables para nuevos ECOE."
      >
        {loading ? (
          <p>Cargando plantillas...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            columns={[
              { key: "name", label: "Nombre" },
              { key: "category", label: "Categoría" },
              { key: "description", label: "Descripción" },
              {
                key: "default_configuration",
                label: "Flujo por defecto",
                render: (row) => {
                  const configuration =
                    ((row as { default_configuration?: Record<string, unknown> }).default_configuration ??
                      {});
                  const features = [
                    configuration.requires_evaluator ? "Evaluador" : null,
                    configuration.requires_student_form ? "Formulario" : null,
                    configuration.uses_multimedia ? "Multimedia" : null,
                    configuration.uses_simulated_patient ? "Paciente simulado" : null,
                  ].filter(Boolean);
                  return features.length ? features.join(" · ") : "Sin banderas";
                },
              },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
