"use client";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";
import { StatCard } from "@/components/stat-card";
import { DataTable } from "@/components/data-table";
import type { DashboardSummary } from "@/lib/types";

export default function DashboardPage() {
  const { token, eventId } = useAuth();
  const { data, loading, error } = useApi(
    () => api.dashboard(eventId, token!) as Promise<DashboardSummary>,
    [eventId, token],
  );

  if (loading) return <p>Cargando dashboard...</p>;
  if (error || !data) return <p>{error ?? "No hay datos disponibles."}</p>;

  return (
    <div className="space-y-6">
      <div className="grid-auto">
        <StatCard label="ECOE activo" value={data.active_ecoe.status} hint={data.active_ecoe.name} />
        <StatCard label="Estudiantes" value={data.totals.students} hint="cargados y asignados" />
        <StatCard label="Estaciones" value={data.totals.stations} hint="incluye estaciones espejo" />
        <StatCard label="Envios" value={data.totals.evaluations} hint="evaluaciones registradas" />
      </div>

      <SectionCard title="Preparacion del ECOE" subtitle="Resumen operativo del evento vigente">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl bg-white/70 p-4">
            <p className="text-sm text-slate-500">Pilotaje</p>
            <p className={`mt-2 pill ${data.validation.can_pilot ? "pill-ok" : "pill-warn"}`}>
              {data.validation.can_pilot ? "Listo para pilotaje" : "Pendiente"}
            </p>
          </div>
          <div className="rounded-2xl bg-white/70 p-4">
            <p className="text-sm text-slate-500">Publicacion</p>
            <p className={`mt-2 pill ${data.validation.can_publish ? "pill-ok" : "pill-warn"}`}>
              {data.validation.can_publish ? "Publicable" : "Requiere ajustes"}
            </p>
          </div>
          <div className="rounded-2xl bg-white/70 p-4">
            <p className="text-sm text-slate-500">Sesion en vivo</p>
            <p className="mt-2 text-2xl font-semibold">{data.live_panel.status}</p>
            <p className="text-sm text-slate-600">
              Estacion {data.live_panel.current_station_index} · {data.live_panel.remaining_seconds}s
            </p>
          </div>
        </div>
        {data.validation.warnings.length ? (
          <div className="rounded-2xl bg-amber-50 p-4 text-sm text-amber-900">
            {data.validation.warnings.map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="Estado de estaciones" subtitle="Linea de tiempo del circuito activo">
        <DataTable
          columns={[
            { key: "label", label: "Estacion" },
            { key: "circuit", label: "Circuito" },
            {
              key: "status",
              label: "Estado",
              render: (row) => (
                <span className="pill pill-ok">
                  {String((row as { status?: string }).status ?? "")}
                </span>
              ),
            },
          ]}
          rows={data.timeline}
        />
      </SectionCard>
    </div>
  );
}
