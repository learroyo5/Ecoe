"use client";

import { Fragment, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { StationTemplate } from "@/lib/types";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { ConfirmDialog } from "@/components/confirm-dialog";
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

function configFeatures(configuration: Record<string, unknown>): string[] {
  return [
    configuration.requires_evaluator ? "Evaluador" : null,
    configuration.requires_student_form ? "Formulario" : null,
    configuration.uses_multimedia ? "Multimedia" : null,
    configuration.uses_simulated_patient ? "Paciente simulado" : null,
  ].filter(Boolean) as string[];
}

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
    <label
      className={`flex cursor-pointer items-start gap-3 rounded-2xl border px-4 py-3 transition ${
        checked
          ? "border-[var(--color-primary)] bg-[var(--color-bg-soft)]"
          : "border-slate-200 bg-white hover:border-slate-300"
      }`}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="sr-only"
      />
      <span
        className={`mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md border-2 transition ${
          checked
            ? "border-[var(--color-primary)] bg-[var(--color-primary)]"
            : "border-slate-300 bg-white"
        }`}
      >
        {checked ? (
          <svg className="size-3 text-white" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M2 6l3 3 5-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        ) : null}
      </span>
      <div className="min-w-0 text-sm leading-5">
        <p className="font-semibold text-slate-900">{label}</p>
        <p className="text-xs text-slate-500">{description}</p>
      </div>
    </label>
  );
}

export default function TemplatesPage() {
  const { authenticated, eventId, eventRoles, user } = useECOE();
  const isAdmin = user?.role === "admin_global" || eventRoles.includes("admin_ecoe");
  const canEditContent = isAdmin || eventRoles.includes("coeditor_docente");

  const [includeArchived, setIncludeArchived] = useState(false);
  const { data, loading, error, setData } = useApi(
    () => api.templates(eventId, { includeArchived }),
    [authenticated, eventId, includeArchived],
  );
  const templates = useMemo(() => data ?? [], [data]);

  const [values, setValues] = useState(defaultValues);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftCategory, setDraftCategory] = useState("procedimental");
  const [draftDescription, setDraftDescription] = useState("");
  const [purgeTarget, setPurgeTarget] = useState<StationTemplate | null>(null);

  const selectedCategoryLabel =
    categoryOptions.find((option) => option.value === values.category)?.label ?? values.category;
  const activeFeatures = useMemo(() => {
    const features: string[] = [];
    if (values.requires_evaluator) features.push("Evaluador");
    if (values.requires_student_form) features.push("Formulario estudiante");
    if (values.uses_multimedia) features.push("Multimedia");
    if (values.uses_simulated_patient) features.push("Paciente simulado");
    return features;
  }, [values]);

  async function reload() {
    setData(await api.templates(eventId, { includeArchived }));
  }

  function startEdit(template: StationTemplate) {
    setEditingId(template.id);
    setDraftName(template.name);
    setDraftCategory(template.category);
    setDraftDescription(template.description);
    setMessage(null);
  }

  function cancelEdit() {
    setEditingId(null);
  }

  async function saveEdit(template: StationTemplate) {
    if (!draftName.trim()) {
      setMessage("La plantilla necesita un nombre.");
      return;
    }
    setBusyId(template.id);
    setMessage(null);
    try {
      await api.updateTemplate(eventId, template.id, {
        name: draftName.trim(),
        category: draftCategory,
        description: draftDescription,
      });
      await reload();
      setMessage("Plantilla actualizada.");
      cancelEdit();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo actualizar la plantilla.");
    } finally {
      setBusyId(null);
    }
  }

  async function runAction(template: StationTemplate, action: "archive" | "restore") {
    setBusyId(template.id);
    setMessage(null);
    try {
      if (action === "archive") await api.archiveTemplate(eventId, template.id);
      else await api.restoreTemplate(eventId, template.id);
      await reload();
      setMessage(action === "archive" ? "Plantilla archivada." : "Plantilla restaurada.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo completar la acción.");
    } finally {
      setBusyId(null);
    }
  }

  async function confirmPurge() {
    if (!purgeTarget) return;
    const target = purgeTarget;
    setBusyId(target.id);
    setMessage(null);
    try {
      await api.purgeTemplate(eventId, target.id);
      await reload();
      setMessage(`Plantilla «${target.name}» eliminada definitivamente.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo eliminar la plantilla.");
    } finally {
      setBusyId(null);
      setPurgeTarget(null);
    }
  }

  return (
    <div className="space-y-6">
      <SectionCard
        title="Banco de plantillas"
        subtitle="Define estructuras base reutilizables para orientar el flujo real de cada tipo de estación. Corregir una plantilla la edita en sitio: no afecta a las estaciones ya creadas, solo a lo que verá el próximo diseñador que la aplique."
      >
        {!canEditContent ? (
          <p className="mb-4 text-sm text-slate-600">Tu rol permite consultar plantillas, pero no modificarlas.</p>
        ) : null}
        <form
          className={`space-y-5 ${canEditContent ? "" : "pointer-events-none opacity-60"}`}
          onSubmit={async (event) => {
            event.preventDefault();
            if (!canEditContent) return;
            setSaving(true);
            setMessage(null);
            try {
              await api.createTemplate(eventId, {
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
              });
              await reload();
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
            <div className="space-y-3">
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
            <button className="btn-primary" disabled={saving || !canEditContent}>
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
        subtitle={`${templates.length} en la lista`}
      >
        <label className="mb-4 flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(event) => setIncludeArchived(event.target.checked)}
          />
          Mostrar plantillas archivadas
        </label>
        {loading ? (
          <p>Cargando plantillas...</p>
        ) : error ? (
          <p className="text-red-700">{error}</p>
        ) : templates.length === 0 ? (
          <p className="text-sm text-slate-600">No hay plantillas todavía.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-3">Nombre</th>
                  <th className="py-2 pr-3">Categoría</th>
                  <th className="py-2 pr-3">Flujo por defecto</th>
                  <th className="py-2 pr-3">Uso</th>
                  <th className="py-2 pr-3">Estado</th>
                  <th className="py-2 pr-3">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {templates.map((template) => {
                  const refCount = template.reference_count ?? 0;
                  const isEditing = editingId === template.id;
                  const rowBusy = busyId === template.id;
                  return (
                    <Fragment key={template.id}>
                      <tr className="border-b border-slate-100 align-top">
                        <td className="py-2 pr-3 font-medium text-slate-900">{template.name}</td>
                        <td className="py-2 pr-3 text-slate-600">{template.category}</td>
                        <td className="py-2 pr-3 text-slate-600">
                          {configFeatures(template.default_configuration ?? {}).join(" · ") || "Sin banderas"}
                        </td>
                        <td className="py-2 pr-3 text-slate-600">
                          {refCount > 0 ? `En uso por ${refCount}` : "Sin uso"}
                        </td>
                        <td className="py-2 pr-3">
                          {template.archived ? (
                            <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-semibold text-slate-700">
                              Archivada
                            </span>
                          ) : (
                            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                              Activa
                            </span>
                          )}
                        </td>
                        <td className="py-2 pr-3">
                          {canEditContent ? (
                            <div className="flex flex-wrap gap-2">
                              {!template.archived ? (
                                <button
                                  type="button"
                                  className="btn-secondary px-2 py-1 text-xs"
                                  disabled={rowBusy}
                                  onClick={() => (isEditing ? cancelEdit() : startEdit(template))}
                                >
                                  {isEditing ? "Cerrar" : "Editar"}
                                </button>
                              ) : null}
                              <button
                                type="button"
                                className="btn-secondary px-2 py-1 text-xs"
                                disabled={rowBusy}
                                onClick={() => runAction(template, template.archived ? "restore" : "archive")}
                              >
                                {template.archived ? "Restaurar" : "Archivar"}
                              </button>
                              {isAdmin && refCount === 0 ? (
                                <button
                                  type="button"
                                  className="rounded-full border border-red-300 px-2 py-1 text-xs font-semibold text-red-700 hover:bg-red-50"
                                  disabled={rowBusy}
                                  onClick={() => setPurgeTarget(template)}
                                >
                                  Purgar
                                </button>
                              ) : null}
                            </div>
                          ) : (
                            <span className="text-xs text-slate-400">—</span>
                          )}
                        </td>
                      </tr>
                      {isEditing ? (
                        <tr className="border-b border-slate-100 bg-slate-50">
                          <td colSpan={6} className="p-4">
                            <div className="space-y-3">
                              <label className="block text-sm font-semibold text-slate-800">
                                Nombre
                                <input
                                  className="mt-1 w-full"
                                  value={draftName}
                                  onChange={(event) => setDraftName(event.target.value)}
                                />
                              </label>
                              <label className="block text-sm font-semibold text-slate-800">
                                Categoría
                                <select
                                  className="mt-1 w-full"
                                  value={draftCategory}
                                  onChange={(event) => setDraftCategory(event.target.value)}
                                >
                                  {categoryOptions.map((option) => (
                                    <option key={option.value} value={option.value}>
                                      {option.label}
                                    </option>
                                  ))}
                                </select>
                              </label>
                              <label className="block text-sm font-semibold text-slate-800">
                                Descripción
                                <textarea
                                  className="mt-1 w-full"
                                  rows={3}
                                  value={draftDescription}
                                  onChange={(event) => setDraftDescription(event.target.value)}
                                />
                              </label>
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  className="btn-primary px-3 py-1.5 text-sm"
                                  disabled={rowBusy}
                                  onClick={() => saveEdit(template)}
                                >
                                  {rowBusy ? "Guardando..." : "Guardar cambios"}
                                </button>
                                <button
                                  type="button"
                                  className="btn-secondary px-3 py-1.5 text-sm"
                                  onClick={cancelEdit}
                                >
                                  Cancelar
                                </button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      <ConfirmDialog
        open={purgeTarget !== null}
        title="Eliminar plantilla definitivamente"
        message={
          purgeTarget
            ? `«${purgeTarget.name}» se borrará. Solo es posible porque no la usa ninguna estación ni el banco. Esta acción no se puede deshacer.`
            : undefined
        }
        confirmLabel="Eliminar definitivamente"
        severity="danger"
        busy={busyId === purgeTarget?.id}
        onConfirm={confirmPurge}
        onCancel={() => setPurgeTarget(null)}
      />
    </div>
  );
}
