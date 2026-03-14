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
    <SectionCard title="Validacion previa" subtitle="Chequeos antes de pilotar, publicar o iniciar la ejecucion real">
      {loading ? <p>Validando configuracion...</p> : null}
      {error ? <p>{error}</p> : null}
      {data ? (
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl bg-white/70 p-5">
            <p className="text-sm text-slate-500">Para pilotaje</p>
            <p className={`mt-2 pill ${data.can_pilot ? "pill-ok" : "pill-warn"}`}>
              {data.can_pilot ? "Cumple" : "Faltan requisitos"}
            </p>
          </div>
          <div className="rounded-2xl bg-white/70 p-5">
            <p className="text-sm text-slate-500">Para publicacion</p>
            <p className={`mt-2 pill ${data.can_publish ? "pill-ok" : "pill-warn"}`}>
              {data.can_publish ? "Cumple" : "Pendiente"}
            </p>
          </div>
          <div className="rounded-2xl bg-white/70 p-5">
            <p className="text-sm text-slate-500">Para ejecucion real</p>
            <p className={`mt-2 pill ${data.can_start_live ? "pill-ok" : "pill-warn"}`}>
              {data.can_start_live ? "Disponible" : "No disponible"}
            </p>
          </div>
        </div>
      ) : null}
    </SectionCard>
  );
}
