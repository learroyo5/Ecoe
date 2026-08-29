"use client";

import { Fragment, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { SimulatedPatient } from "@/lib/types";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { QuickForm, StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

const EDITABLE_FIELDS: { name: keyof SimulatedPatient; label: string; textarea?: boolean }[] = [
  { name: "character_name", label: "Nombre personaje" },
  { name: "summary_profile", label: "Perfil resumido", textarea: true },
  { name: "base_story", label: "Historia base", textarea: true },
  { name: "key_answers", label: "Respuestas clave", textarea: true },
  { name: "emotional_tone", label: "Actitud / emoción" },
  { name: "special_instructions", label: "Instrucciones especiales", textarea: true },
];

export default function SimulatedPatientPage() {
  const { authenticated, eventId, eventRoles, user } = useECOE();
  const isAdmin = user?.role === "admin_global" || eventRoles.includes("admin_ecoe");
  const canEditContent = isAdmin || eventRoles.includes("coeditor_docente");

  const [includeArchived, setIncludeArchived] = useState(false);
  const { data, loading, error, setData } = useApi(
    () => api.simulatedPatients(eventId, { includeArchived }),
    [authenticated, eventId, includeArchived],
  );
  const patients = useMemo(() => data ?? [], [data]);

  const [message, setMessage] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [purgeTarget, setPurgeTarget] = useState<SimulatedPatient | null>(null);

  async function reload() {
    setData(await api.simulatedPatients(eventId, { includeArchived }));
  }

  function startEdit(patient: SimulatedPatient) {
    setEditingId(patient.id);
    setDraft(
      Object.fromEntries(
        EDITABLE_FIELDS.map((field) => [field.name, String(patient[field.name] ?? "")]),
      ),
    );
    setMessage(null);
  }

  async function saveEdit(patient: SimulatedPatient) {
    setBusyId(patient.id);
    setMessage(null);
    try {
      await api.updateSimulatedPatient(eventId, patient.id, draft);
      await reload();
      setMessage("Ficha actualizada.");
      setEditingId(null);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo actualizar la ficha.");
    } finally {
      setBusyId(null);
    }
  }

  async function runAction(patient: SimulatedPatient, action: "archive" | "restore") {
    setBusyId(patient.id);
    setMessage(null);
    try {
      if (action === "archive") await api.archiveSimulatedPatient(eventId, patient.id);
      else await api.restoreSimulatedPatient(eventId, patient.id);
      await reload();
      setMessage(action === "archive" ? "Ficha archivada." : "Ficha restaurada.");
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
      await api.purgeSimulatedPatient(eventId, target.id);
      await reload();
      setMessage(`Ficha «${target.character_name}» eliminada definitivamente.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo eliminar la ficha.");
    } finally {
      setBusyId(null);
      setPurgeTarget(null);
    }
  }

  return (
    <div className="space-y-6">
      <SectionCard
        title="Gestor de paciente simulado"
        subtitle="Construye personajes y guiones reutilizables para estaciones con interacción clínica. Editar una ficha no afecta al cálculo de notas."
      >
        {canEditContent ? (
          <QuickForm
            fields={[
              { name: "character_name", label: "Nombre personaje" },
              { name: "summary_profile", label: "Perfil resumido" },
              { name: "base_story", label: "Historia base" },
              { name: "key_answers", label: "Respuestas clave" },
              { name: "emotional_tone", label: "Actitud / emoción" },
              { name: "special_instructions", label: "Instrucciones especiales" },
            ]}
            onSubmit={async (values) => {
              await api.createSimulatedPatient(eventId, values);
              await reload();
            }}
          />
        ) : (
          <p className="text-sm text-slate-600">Tu rol permite consultar el banco, pero no modificarlo.</p>
        )}
        <StatusNotice message={message} className="mt-4" />
      </SectionCard>

      <SectionCard title="Banco de personajes" subtitle={`${patients.length} en la lista`}>
        <label className="mb-4 flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={includeArchived}
            onChange={(event) => setIncludeArchived(event.target.checked)}
          />
          Mostrar fichas archivadas
        </label>
        {loading ? (
          <p>Cargando pacientes simulados...</p>
        ) : error ? (
          <p className="text-red-700">{error}</p>
        ) : patients.length === 0 ? (
          <p className="text-sm text-slate-600">No hay pacientes simulados todavía.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-3">Personaje</th>
                  <th className="py-2 pr-3">Perfil</th>
                  <th className="py-2 pr-3">Tono</th>
                  <th className="py-2 pr-3">Uso</th>
                  <th className="py-2 pr-3">Estado</th>
                  <th className="py-2 pr-3">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {patients.map((patient) => {
                  const refCount = patient.reference_count ?? 0;
                  const isEditing = editingId === patient.id;
                  const rowBusy = busyId === patient.id;
                  return (
                    <Fragment key={patient.id}>
                      <tr className="border-b border-slate-100 align-top">
                        <td className="py-2 pr-3 font-medium text-slate-900">{patient.character_name}</td>
                        <td className="py-2 pr-3 text-slate-600">{patient.summary_profile}</td>
                        <td className="py-2 pr-3 text-slate-600">{patient.emotional_tone}</td>
                        <td className="py-2 pr-3 text-slate-600">
                          {refCount > 0 ? `En uso por ${refCount}` : "Sin uso"}
                        </td>
                        <td className="py-2 pr-3">
                          {patient.archived ? (
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
                              {!patient.archived ? (
                                <button
                                  type="button"
                                  className="btn-secondary px-2 py-1 text-xs"
                                  disabled={rowBusy}
                                  onClick={() => (isEditing ? setEditingId(null) : startEdit(patient))}
                                >
                                  {isEditing ? "Cerrar" : "Editar"}
                                </button>
                              ) : null}
                              <button
                                type="button"
                                className="btn-secondary px-2 py-1 text-xs"
                                disabled={rowBusy}
                                onClick={() => runAction(patient, patient.archived ? "restore" : "archive")}
                              >
                                {patient.archived ? "Restaurar" : "Archivar"}
                              </button>
                              {isAdmin && refCount === 0 ? (
                                <button
                                  type="button"
                                  className="rounded-full border border-red-300 px-2 py-1 text-xs font-semibold text-red-700 hover:bg-red-50"
                                  disabled={rowBusy}
                                  onClick={() => setPurgeTarget(patient)}
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
                              {EDITABLE_FIELDS.map((field) => (
                                <label key={field.name} className="block text-sm font-semibold text-slate-800">
                                  {field.label}
                                  {field.textarea ? (
                                    <textarea
                                      className="mt-1 w-full"
                                      rows={2}
                                      value={draft[field.name] ?? ""}
                                      onChange={(event) =>
                                        setDraft((current) => ({ ...current, [field.name]: event.target.value }))
                                      }
                                    />
                                  ) : (
                                    <input
                                      className="mt-1 w-full"
                                      value={draft[field.name] ?? ""}
                                      onChange={(event) =>
                                        setDraft((current) => ({ ...current, [field.name]: event.target.value }))
                                      }
                                    />
                                  )}
                                </label>
                              ))}
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  className="btn-primary px-3 py-1.5 text-sm"
                                  disabled={rowBusy}
                                  onClick={() => saveEdit(patient)}
                                >
                                  {rowBusy ? "Guardando..." : "Guardar cambios"}
                                </button>
                                <button
                                  type="button"
                                  className="btn-secondary px-3 py-1.5 text-sm"
                                  onClick={() => setEditingId(null)}
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
        title="Eliminar ficha definitivamente"
        message={
          purgeTarget
            ? `«${purgeTarget.character_name}» se borrará. Solo es posible porque no la usa ninguna estación ni el banco. Esta acción no se puede deshacer.`
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
