"use client";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";

export default function ValidationPage() {
  const { token, eventId } = useAuth();
  const { data, loading, error } = useApi(
    () => api.validation(eventId, token!) as Promise<Record<string, unknown>>,
    [eventId, token],
  );

  return (
    <SectionCard title="Validacion previa" subtitle="Chequeos estructurados antes de pilotar, publicar o iniciar la ejecucion real del ECOE.">
      {loading ? <p>Validando configuracion...</p> : null}
      {error ? <p>{error}</p> : null}
      {data ? (
        <div className="grid gap-4 md:grid-cols-3">
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Para pilotaje</p>
            <p className={`mt-3 status-badge ${data.can_pilot ? "status-badge-success" : "status-badge-warning"}`}>
              {data.can_pilot ? "Cumple requisitos" : "Faltan requisitos"}
            </p>
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Para publicacion</p>
            <p className={`mt-3 status-badge ${data.can_publish ? "status-badge-success" : "status-badge-warning"}`}>
              {data.can_publish ? "Cumple requisitos" : "Pendiente"}
            </p>
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Para ejecucion real</p>
            <p className={`mt-3 status-badge ${data.can_start_live ? "status-badge-success" : "status-badge-warning"}`}>
              {data.can_start_live ? "Disponible" : "No disponible"}
            </p>
          </div>
        </div>
      ) : null}
    </SectionCard>
  );
}
