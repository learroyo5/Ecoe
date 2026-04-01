"use client";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";

export default function PublicationPage() {
  const { token, eventId } = useAuth();
  const { data } = useApi(
    () => api.validation(eventId, token!) as Promise<Record<string, unknown>>,
    [eventId, token],
  );

  return (
    <SectionCard title="Publicacion" subtitle="Revision final antes de abrir la ejecucion real del ECOE y dejar listo el entorno operativo.">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="clinical-panel">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Estaciones completas</p>
          <p className="mt-3 text-3xl font-semibold">
            {String(data?.complete_stations ?? 0)} / {String(data?.station_count ?? 0)}
          </p>
        </div>
        <div className="clinical-panel">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Pilotajes realizados</p>
          <p className="mt-3 text-3xl font-semibold">{String(data?.pilot_count ?? 0)}</p>
        </div>
      </div>
      <div className="rounded-[28px] bg-[linear-gradient(135deg,var(--color-primary-dark),var(--color-primary))] p-5 text-white shadow-[0_18px_40px_rgba(27,73,101,0.18)]">
        <p className="text-sm uppercase tracking-[0.18em] text-slate-100/80">Estado</p>
        <p className="mt-2 text-2xl font-semibold">
          {data?.can_publish ? "Listo para publicar" : "Aun no cumple validacion completa"}
        </p>
      </div>
    </SectionCard>
  );
}
