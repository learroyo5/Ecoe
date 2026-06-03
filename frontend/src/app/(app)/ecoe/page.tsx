"use client";

import { useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";
import { ECOEFormFields, buildECOEPayload, toEditableValues } from "@/components/ecoe-form";
import type { ECOEEvent } from "@/lib/types";

const DEFAULT_CREATE_VALUES: Record<string, string> = {
  name: "", date: "", course_name: "", school_name: "",
  responsible_teacher: "", contact_email: "", circuit_mode: "paralelo_espejo",
  total_stations: "8", station_time_minutes: "8", transition_time_minutes: "2",
  total_students: "0", total_groups: "1", passing_reference_percent: "60",
};

export default function ECOEPage() {
  const { token, eventId, setEventId, user } = useECOE();
  const { data: ecoeList, loading: listLoading, error: listError, setData: setECOEList } = useApi(
    () => api.listECOE(token!) as Promise<ECOEEvent[]>,
    [token],
  );
  const { data: ecoeEvent, setData } = useApi(
    () => api.ecoe(eventId, token!) as Promise<ECOEEvent>,
    [eventId, token],
  );
  const [formValues, setFormValues] = useState<Record<string, string> | null>(null);
  const [createValues, setCreateValues] = useState<Record<string, string>>({ ...DEFAULT_CREATE_VALUES });
  const [message, setMessage] = useState<string | null>(null);
  const [createMessage, setCreateMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [creating, setCreating] = useState(false);
  const [duplicating, setDuplicating] = useState(false);

  const editableValues = useMemo(() => toEditableValues(ecoeEvent as unknown as Record<string, unknown> | null), [ecoeEvent]);
  const activeValues = formValues ?? editableValues;

  const refreshList = async (targetId?: number) => {
    const refreshed = (await api.listECOE(token!)) as ECOEEvent[];
    setECOEList(refreshed);
    if (targetId && !refreshed.some((e) => e.id === targetId)) setEventId(refreshed[0]?.id ?? eventId);
  };

  const updateField = (name: string, value: string) =>
    setFormValues((c) => ({ ...(c ?? editableValues ?? {}), [name]: value }));

  return (
    <div className="space-y-6">
      {/* ECOE selector bar */}
      <SectionCard title="Gestión del ECOE" subtitle="Edita los datos generales, cambia el estado, duplica o crea un nuevo evento.">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Evento activo</p>
            <p className="mt-3 text-2xl font-semibold">{ecoeEvent?.name ?? "Sin cargar"}</p>
            <p className="mt-2 text-sm text-slate-600">{ecoeEvent?.course_name ?? "Curso sin definir"}</p>
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Estado</p>
            <p className="mt-3 text-2xl font-semibold">{ecoeEvent?.status ?? "—"}</p>
            <p className="mt-2 text-sm text-slate-600">{ecoeEvent?.date ?? "—"}</p>
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Selección</p>
            <select className="mt-3" value={String(eventId)}
              onChange={(e) => { setEventId(Number(e.target.value)); setFormValues(null); setMessage(null); }}>
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
            setSaving(true); setMessage(null);
            try {
              const updated = await api.updateECOE(ecoeEvent.id, { ...buildECOEPayload(activeValues), status: activeValues.status }, token!) as ECOEEvent;
              setData(updated);
              setFormValues(toEditableValues(updated as unknown as Record<string, unknown>));
              await refreshList(updated.id);
              setMessage("ECOE guardado correctamente.");
            } catch (err) { setMessage(err instanceof Error ? err.message : "Error al guardar."); }
            finally { setSaving(false); }
          }}>
            <ECOEFormFields values={activeValues} onChange={updateField} includeStatus />
            <div className="flex flex-wrap gap-3">
              <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Guardando..." : "Guardar ECOE"}</button>
              <button type="button" className="btn-secondary" onClick={() => { setFormValues(editableValues); setMessage(null); }} disabled={saving}>Revertir</button>
              <button type="button" className="btn-secondary" disabled={!ecoeEvent || duplicating || user?.role !== "creador_ecoe"}
                onClick={async () => {
                  if (!ecoeEvent || !window.confirm("¿Duplicar este ECOE?")) return;
                  setDuplicating(true); setMessage(null);
                  try {
                    const dup = await api.duplicateECOE(ecoeEvent.id, token!) as ECOEEvent;
                    await refreshList(dup.id); setEventId(dup.id); setData(dup);
                    setFormValues(toEditableValues(dup as unknown as Record<string, unknown>));
                    setMessage("Copia creada y seleccionada.");
                  } catch (err) { setMessage(err instanceof Error ? err.message : "Error al duplicar."); }
                  finally { setDuplicating(false); }
                }}>{duplicating ? "Duplicando..." : "Duplicar ECOE"}</button>
            </div>
            <StatusNotice message={message} />
          </form>
        )}
      </SectionCard>

      {/* Create form */}
      <SectionCard title="Crear nuevo ECOE" subtitle="Nuevo evento desde cero. Quedará en borrador y seleccionado automáticamente.">
        <form className="space-y-4" onSubmit={async (e) => {
          e.preventDefault();
          setCreating(true); setCreateMessage(null);
          try {
            const created = await api.createECOE(buildECOEPayload(createValues), token!) as ECOEEvent;
            await refreshList(created.id); setEventId(created.id); setData(created);
            setFormValues(toEditableValues(created as unknown as Record<string, unknown>));
            setCreateValues({ ...DEFAULT_CREATE_VALUES });
            setCreateMessage("ECOE creado y seleccionado.");
          } catch (err) { setCreateMessage(err instanceof Error ? err.message : "Error al crear."); }
          finally { setCreating(false); }
        }}>
          <ECOEFormFields values={createValues} onChange={(n, v) => setCreateValues((c) => ({ ...c, [n]: v }))} />
          <button type="submit" className="btn-primary" disabled={creating}>{creating ? "Creando..." : "Crear nuevo ECOE"}</button>
          <StatusNotice message={createMessage} />
        </form>
      </SectionCard>
    </div>
  );
}
