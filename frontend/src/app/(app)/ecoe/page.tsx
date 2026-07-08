"use client";

import { useMemo, useState } from "react";
import Link from "next/link";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";
import { ECOEFormFields, buildECOEPayload, toEditableValues, validateECOEPayload, StatusTransitionBar } from "@/components/ecoe-form";
import type { ECOEEvent } from "@/lib/types";

const DEFAULT_CREATE_VALUES: Record<string, string> = {
  name: "", date: "", course_name: "", school_name: "",
  responsible_teacher: "", contact_email: "", circuit_mode: "paralelo_espejo",
  total_stations: "8", station_time_minutes: "8", transition_time_minutes: "2",
  total_students: "0", total_groups: "1", passing_reference_percent: "60",
};

export default function ECOEPage() {
  const { authenticated, eventId, setEventId, user } = useECOE();
  const { data: ecoeList, loading: listLoading, error: listError, setData: setECOEList } = useApi(
    () => api.listECOE() as Promise<ECOEEvent[]>,
    [authenticated],
  );
  const { data: ecoeEvent, setData } = useApi(
    () => api.ecoe(eventId) as Promise<ECOEEvent>,
    [eventId, authenticated],
  );
  const [formValues, setFormValues] = useState<Record<string, string> | null>(null);
  const [createValues, setCreateValues] = useState<Record<string, string>>({ ...DEFAULT_CREATE_VALUES });
  const [message, setMessage] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [createMessage, setCreateMessage] = useState<string | null>(null);
  const [createErrors, setCreateErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [duplicating, setDuplicating] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  const [dupModal, setDupModal] = useState(false);
  const [dupName, setDupName] = useState("");
  const [dupDate, setDupDate] = useState("");
  const [dupCopyEvaluators, setDupCopyEvaluators] = useState(false);

  const editableValues = useMemo(() => toEditableValues(ecoeEvent as unknown as Record<string, unknown> | null), [ecoeEvent]);
  const activeValues = formValues ?? editableValues;

  const refreshList = async (targetId?: number) => {
    const refreshed = (await api.listECOE()) as ECOEEvent[];
    setECOEList(refreshed);
    if (targetId && !refreshed.some((e) => e.id === targetId)) setEventId(refreshed[0]?.id ?? eventId);
  };

  const updateField = (name: string, value: string) =>
    setFormValues((c) => ({ ...(c ?? editableValues ?? {}), [name]: value }));

  const handleStatusTransition = async (targetStatus: string) => {
    if (!ecoeEvent) return;
    setTransitioning(true); setMessage(null);
    try {
      const updated = await api.updateECOE(
        ecoeEvent.id,
        { ...buildECOEPayload(activeValues ?? toEditableValues(ecoeEvent as unknown as Record<string, unknown>)!), status: targetStatus },
      ) as ECOEEvent;
      setData(updated);
      setFormValues(toEditableValues(updated as unknown as Record<string, unknown>));
      await refreshList(updated.id);
      setMessage(`ECOE ahora en estado: ${targetStatus.replace(/_/g, " ")}`);
      setErrors({});
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Error al cambiar estado.");
    } finally {
      setTransitioning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* ECOE selector bar */}
      <SectionCard title="Gestión del ECOE" subtitle="Edita los datos generales, cambia el estado, duplica o crea un nuevo evento.">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Evento activo</p>
            <p className="mt-3 text-2xl font-semibold">{ecoeEvent?.name ?? "Sin cargar"}</p>
            <p className="mt-2 text-sm text-slate-600">{ecoeEvent?.course_name ?? "Curso sin definir"}</p>
            {ecoeEvent ? (
              <Link href={`/ecoe/${ecoeEvent.id}`} className="mt-2 inline-block text-sm font-medium text-[var(--color-primary)] hover:underline">
                Ver detalle completo &rarr;
              </Link>
            ) : null}
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Estado</p>
            <p className="mt-3 text-2xl font-semibold">{ecoeEvent?.status ?? "—"}</p>
            <p className="mt-2 text-sm text-slate-600">{ecoeEvent?.date ?? "—"}</p>
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Selección</p>
            <select className="mt-3" value={String(eventId)}
              onChange={(e) => { setEventId(Number(e.target.value)); setFormValues(null); setMessage(null); setErrors({}); }}>
              {(ecoeList ?? []).map((e) => <option key={e.id} value={String(e.id)}>{e.name} · {e.course_name}</option>)}
            </select>
          </div>
        </div>
      </SectionCard>

      {/* Edit form */}
      <SectionCard title="Datos generales y estado" subtitle="Configuración académica base del ECOE activo.">
        {listLoading && <p className="text-sm text-slate-500">Cargando...</p>}
        {listError && <p className="text-sm text-red-600">{listError}</p>}
        {activeValues && (
          <form className="space-y-4" onSubmit={async (e) => {
            e.preventDefault();
            if (!ecoeEvent) return;
            const validationErrors = validateECOEPayload(activeValues);
            setErrors(validationErrors);
            if (Object.keys(validationErrors).length > 0) return;
            setSaving(true); setMessage(null);
            try {
              const updated = await api.updateECOE(ecoeEvent.id, { ...buildECOEPayload(activeValues), status: activeValues.status }) as ECOEEvent;
              setData(updated);
              setFormValues(toEditableValues(updated as unknown as Record<string, unknown>));
              await refreshList(updated.id);
              setMessage("ECOE guardado correctamente.");
              setErrors({});
            } catch (err) { setMessage(err instanceof Error ? err.message : "Error al guardar."); }
            finally { setSaving(false); }
          }}>
            <ECOEFormFields values={activeValues} onChange={updateField} errors={errors} />
            <StatusTransitionBar
              currentStatus={activeValues.status ?? "borrador"}
              onTransition={handleStatusTransition}
              disabled={saving || transitioning}
              loading={transitioning}
            />
            <div className="flex flex-wrap gap-3">
              <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Guardando..." : "Guardar ECOE"}</button>
              <button type="button" className="btn-secondary" onClick={() => { setFormValues(editableValues); setMessage(null); setErrors({}); }} disabled={saving}>Revertir</button>
              <button type="button" className="btn-secondary" disabled={!ecoeEvent || user?.role !== "admin_ecoe"}
                onClick={() => {
                  if (!ecoeEvent) return;
                  setDupName(`${ecoeEvent.name} (copia)`);
                  setDupDate(ecoeEvent.date ?? "");
                  setDupCopyEvaluators(false);
                  setDupModal(true);
                }}>Duplicar ECOE</button>
            </div>
            <StatusNotice message={message} />
          </form>
        )}
      </SectionCard>

      {/* Create form */}
      <SectionCard title="Crear nuevo ECOE" subtitle="Nuevo evento desde cero. Quedará en borrador y seleccionado automáticamente.">
        <form className="space-y-4" onSubmit={async (e) => {
          e.preventDefault();
          const validationErrors = validateECOEPayload(createValues);
          setCreateErrors(validationErrors);
          if (Object.keys(validationErrors).length > 0) return;
          setCreating(true); setCreateMessage(null);
          try {
            const created = await api.createECOE(buildECOEPayload(createValues)) as ECOEEvent;
            await refreshList(created.id); setEventId(created.id); setData(created);
            setFormValues(toEditableValues(created as unknown as Record<string, unknown>));
            setCreateValues({ ...DEFAULT_CREATE_VALUES });
            setCreateErrors({});
            setCreateMessage("ECOE creado y seleccionado.");
          } catch (err) { setCreateMessage(err instanceof Error ? err.message : "Error al crear."); }
          finally { setCreating(false); }
        }}>
          <ECOEFormFields values={createValues} onChange={(n, v) => { setCreateValues((c) => ({ ...c, [n]: v })); setCreateErrors((prev) => { const next = { ...prev }; delete next[n]; return next; }); }} errors={createErrors} />
          <button type="submit" className="btn-primary" disabled={creating}>{creating ? "Creando..." : "Crear nuevo ECOE"}</button>
          <StatusNotice message={createMessage} />
        </form>
      </SectionCard>

      {/* Duplicate modal */}
      {dupModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={() => setDupModal(false)}>
          <div className="mx-4 w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl animate-fade-in" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-xl font-semibold text-slate-900">Duplicar ECOE</h3>
            <p className="mt-1 text-sm text-slate-500">La estructura de estaciones siempre se copia. Los estudiantes nunca se copian (es un nuevo grupo).</p>

            <div className="mt-4 space-y-4">
              <label className="block space-y-1">
                <span className="text-sm font-semibold text-slate-700">Nombre del nuevo ECOE</span>
                <input value={dupName} onChange={(e) => setDupName(e.target.value)}
                  placeholder="Ej: ECOE Medicina Interna 2027" />
              </label>
              <label className="block space-y-1">
                <span className="text-sm font-semibold text-slate-700">Fecha</span>
                <input type="date" value={dupDate} onChange={(e) => setDupDate(e.target.value)} />
              </label>
              <label className="flex items-center gap-3 rounded-2xl border border-slate-200 px-4 py-3 cursor-pointer">
                <input type="checkbox" checked={dupCopyEvaluators}
                  onChange={(e) => setDupCopyEvaluators(e.target.checked)}
                  className="size-4 accent-[var(--color-primary)]" />
                <span className="text-sm text-slate-700">Copiar también los evaluadores asignados</span>
              </label>
            </div>

            <div className="mt-6 flex gap-3 justify-end">
              <button className="btn-secondary" onClick={() => setDupModal(false)}>Cancelar</button>
              <button className="btn-primary" disabled={duplicating || !dupName.trim()}
                onClick={async () => {
                  if (!ecoeEvent || !dupName.trim()) return;
                  setDuplicating(true); setMessage(null); setDupModal(false);
                  try {
                    const dup = await api.duplicateECOE(ecoeEvent.id, {
                      name: dupName.trim(),
                      new_date: dupDate || undefined,
                      copy_evaluators: dupCopyEvaluators,
                    }) as ECOEEvent;
                    await refreshList(dup.id); setEventId(dup.id); setData(dup);
                    setFormValues(toEditableValues(dup as unknown as Record<string, unknown>));
                    setMessage("ECOE duplicado. Estructura copiada, estudiantes en blanco.");
                  } catch (err) { setMessage(err instanceof Error ? err.message : "Error al duplicar."); }
                  finally { setDuplicating(false); }
                }}>
                {duplicating ? "Duplicando..." : "Crear copia"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
