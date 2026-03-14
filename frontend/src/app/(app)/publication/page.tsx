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
    <SectionCard title="Publicacion" subtitle="Revision final antes de abrir la ejecucion real">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl bg-white/70 p-5">
          <p className="text-sm text-slate-500">Estaciones completas</p>
          <p className="mt-3 text-3xl font-semibold">
            {String(data?.complete_stations ?? 0)} / {String(data?.station_count ?? 0)}
          </p>
        </div>
        <div className="rounded-2xl bg-white/70 p-5">
          <p className="text-sm text-slate-500">Pilotajes realizados</p>
          <p className="mt-3 text-3xl font-semibold">{String(data?.pilot_count ?? 0)}</p>
        </div>
      </div>
      <div className="rounded-2xl bg-slate-900 p-5 text-white">
        <p className="text-sm uppercase tracking-[0.18em] text-slate-300">Estado</p>
        <p className="mt-2 text-2xl font-semibold">
          {data?.can_publish ? "Listo para publicar" : "Aun no cumple validacion completa"}
        </p>
      </div>
    </SectionCard>
  );
}
