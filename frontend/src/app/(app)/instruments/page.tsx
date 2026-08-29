"use client";

import { Fragment, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { AssessmentItem, AssessmentTool } from "@/lib/types";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

const TOOL_TYPE_LABELS: Record<string, string> = {
  lista_cotejo: "Lista de cotejo",
  rubrica_simple: "Rúbrica simple",
  escala_puntaje: "Escala de puntaje",
};

type DraftItem = { id?: number; label: string; score_per_item: string };

function toDraft(tool: AssessmentTool): DraftItem[] {
  return [...(tool.items ?? [])]
    .sort((a, b) => a.order_index - b.order_index)
    .map((item: AssessmentItem) => ({
      id: item.id,
      label: item.label,
      score_per_item: String(item.score_per_item),
    }));
}

export default function InstrumentsPage() {
  const { authenticated, eventId, eventRoles, user } = useECOE();
  const isAdmin = user?.role === "admin_global" || eventRoles.includes("admin_ecoe");
  const canEditContent = isAdmin || eventRoles.includes("coeditor_docente");

  const [includeArchived, setIncludeArchived] = useState(false);
  const { data, loading, error, setData } = useApi(
    () => api.instruments(eventId, { includeArchived }),
    [authenticated, eventId, includeArchived],
  );

  const [message, setMessage] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftFreeObs, setDraftFreeObs] = useState(true);
  const [draftItems, setDraftItems] = useState<DraftItem[]>([]);
  const [purgeTarget, setPurgeTarget] = useState<AssessmentTool | null>(null);

  const tools = useMemo(() => data ?? [], [data]);

  async function reload() {
    setData(await api.instruments(eventId, { includeArchived }));
  }

  function startEdit(tool: AssessmentTool) {
    setEditingId(tool.id);
    setDraftName(tool.name);
    setDraftFreeObs(tool.free_observation);
    setDraftItems(toDraft(tool));
    setMessage(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setDraftItems([]);
  }

  async function saveEdit(tool: AssessmentTool) {
    const items = draftItems
      .map((item, index) => ({
        ...(item.id ? { id: item.id } : {}),
        label: item.label.trim(),
        score_per_item: Number(item.score_per_item) || 0,
        order_index: index + 1,
      }))
      .filter((item) => item.label.length > 0);
    if (items.length === 0) {
      setMessage("La pauta necesita al menos un criterio con texto.");
      return;
    }
    setBusyId(tool.id);
    setMessage(null);
    try {
      await api.updateInstrument(eventId, tool.id, {
        name: draftName.trim() || tool.name,
        free_observation: draftFreeObs,
        max_score: items.reduce((sum, item) => sum + item.score_per_item, 0),
        items,
      });
      await reload();
      setMessage("Pauta actualizada. Los identificadores de criterio se conservan.");
      cancelEdit();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo actualizar la pauta.");
    } finally {
      setBusyId(null);
    }
  }

  async function runAction(tool: AssessmentTool, action: "archive" | "restore") {
    setBusyId(tool.id);
    setMessage(null);
    try {
      if (action === "archive") await api.archiveInstrument(eventId, tool.id);
      else await api.restoreInstrument(eventId, tool.id);
      await reload();
      setMessage(action === "archive" ? "Instrumento archivado." : "Instrumento restaurado.");
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
      await api.purgeInstrument(eventId, target.id);
      await reload();
      setMessage(`Instrumento «${target.name}» eliminado definitivamente.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo eliminar el instrumento.");
    } finally {
      setBusyId(null);
      setPurgeTarget(null);
    }
  }

  return (
    <div className="space-y-6">
      <SectionCard
        title="Banco de instrumentos"
        subtitle="Listas de cotejo, rúbricas y escalas reutilizables. Corregir una pauta la edita en sitio, preservando el desglose criterio a criterio de las evaluaciones ya registradas; una pauta usada por un ECOE en pilotaje o posterior no se puede editar (hay que duplicarla)."
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={includeArchived}
              onChange={(event) => setIncludeArchived(event.target.checked)}
            />
            Mostrar instrumentos archivados
          </label>
          {!canEditContent ? (
            <span className="text-sm text-slate-500">Tu rol permite consultar, no editar.</span>
          ) : null}
        </div>
        <StatusNotice message={message} className="mt-4" />
      </SectionCard>

      <SectionCard title="Instrumentos" subtitle={`${tools.length} en la lista`}>
        {loading ? (
          <p>Cargando instrumentos...</p>
        ) : error ? (
          <p className="text-red-700">{error}</p>
        ) : tools.length === 0 ? (
          <p className="text-sm text-slate-600">
            No hay instrumentos todavía. Se crean desde el Constructor de estaciones.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="py-2 pr-3">Nombre</th>
                  <th className="py-2 pr-3">Tipo</th>
                  <th className="py-2 pr-3">Puntaje</th>
                  <th className="py-2 pr-3">Ítems</th>
                  <th className="py-2 pr-3">Uso</th>
                  <th className="py-2 pr-3">Estado</th>
                  <th className="py-2 pr-3">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {tools.map((tool) => {
                  const refCount = tool.reference_count ?? 0;
                  const isEditing = editingId === tool.id;
                  const rowBusy = busyId === tool.id;
                  return (
                    <Fragment key={tool.id}>
                      <tr className="border-b border-slate-100 align-top">
                        <td className="py-2 pr-3 font-medium text-slate-900">{tool.name}</td>
                        <td className="py-2 pr-3 text-slate-600">
                          {TOOL_TYPE_LABELS[tool.tool_type] ?? tool.tool_type}
                        </td>
                        <td className="py-2 pr-3 text-slate-600">{tool.max_score}</td>
                        <td className="py-2 pr-3 text-slate-600">{tool.items?.length ?? 0}</td>
                        <td className="py-2 pr-3 text-slate-600">
                          {refCount > 0 ? `En uso por ${refCount}` : "Sin uso"}
                        </td>
                        <td className="py-2 pr-3">
                          {tool.archived ? (
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
                              {!tool.archived ? (
                                <button
                                  type="button"
                                  className="btn-secondary px-2 py-1 text-xs"
                                  disabled={rowBusy}
                                  onClick={() => (isEditing ? cancelEdit() : startEdit(tool))}
                                >
                                  {isEditing ? "Cerrar" : "Editar"}
                                </button>
                              ) : null}
                              <button
                                type="button"
                                className="btn-secondary px-2 py-1 text-xs"
                                disabled={rowBusy}
                                onClick={() => runAction(tool, tool.archived ? "restore" : "archive")}
                              >
                                {tool.archived ? "Restaurar" : "Archivar"}
                              </button>
                              {isAdmin && refCount === 0 ? (
                                <button
                                  type="button"
                                  className="rounded-full border border-red-300 px-2 py-1 text-xs font-semibold text-red-700 hover:bg-red-50"
                                  disabled={rowBusy}
                                  onClick={() => setPurgeTarget(tool)}
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
                          <td colSpan={7} className="p-4">
                            <div className="space-y-3">
                              <label className="block text-sm font-semibold text-slate-800">
                                Nombre de la pauta
                                <input
                                  className="mt-1 w-full"
                                  value={draftName}
                                  onChange={(event) => setDraftName(event.target.value)}
                                />
                              </label>
                              <label className="flex items-center gap-2 text-sm text-slate-700">
                                <input
                                  type="checkbox"
                                  checked={draftFreeObs}
                                  onChange={(event) => setDraftFreeObs(event.target.checked)}
                                />
                                Permitir observación libre del evaluador
                              </label>
                              <div className="space-y-2">
                                {draftItems.map((item, index) => (
                                  <div key={index} className="flex flex-wrap items-center gap-2">
                                    <input
                                      className="min-w-[16rem] flex-1"
                                      value={item.label}
                                      placeholder={`Criterio ${index + 1}`}
                                      onChange={(event) =>
                                        setDraftItems((current) =>
                                          current.map((it, i) =>
                                            i === index ? { ...it, label: event.target.value } : it,
                                          ),
                                        )
                                      }
                                    />
                                    <input
                                      type="number"
                                      min="0"
                                      step="0.5"
                                      className="w-24"
                                      value={item.score_per_item}
                                      onChange={(event) =>
                                        setDraftItems((current) =>
                                          current.map((it, i) =>
                                            i === index
                                              ? { ...it, score_per_item: event.target.value }
                                              : it,
                                          ),
                                        )
                                      }
                                    />
                                    <button
                                      type="button"
                                      className="btn-secondary px-2 py-1 text-xs"
                                      disabled={draftItems.length === 1}
                                      onClick={() =>
                                        setDraftItems((current) => current.filter((_, i) => i !== index))
                                      }
                                    >
                                      Quitar
                                    </button>
                                  </div>
                                ))}
                                <button
                                  type="button"
                                  className="btn-secondary px-2 py-1 text-xs"
                                  onClick={() =>
                                    setDraftItems((current) => [
                                      ...current,
                                      { label: "", score_per_item: "1" },
                                    ])
                                  }
                                >
                                  Agregar criterio
                                </button>
                              </div>
                              <p className="text-xs text-slate-500">
                                Los criterios existentes conservan su identificador: quitar uno elimina
                                su registro histórico en las evaluaciones; agregar o editar es seguro.
                              </p>
                              <div className="flex gap-2">
                                <button
                                  type="button"
                                  className="btn-primary px-3 py-1.5 text-sm"
                                  disabled={rowBusy}
                                  onClick={() => saveEdit(tool)}
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
        title="Eliminar instrumento definitivamente"
        message={
          purgeTarget
            ? `«${purgeTarget.name}» se borrará junto con sus criterios. Solo es posible porque no lo usa ninguna estación ni el banco. Esta acción no se puede deshacer.`
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
