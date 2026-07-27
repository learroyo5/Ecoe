"use client";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";
import { StatCard } from "@/components/stat-card";
import { DataTable } from "@/components/data-table";
import { DashboardSkeleton } from "@/components/skeleton";
import { ErrorState } from "@/components/toast";
import { ecoeStatusLabel, sessionStatusLabel, stationStatusLabel } from "@/lib/labels";
import type { DashboardSummary } from "@/lib/types";

export default function DashboardPage() {
  const { authenticated, eventId } = useECOE();
  const { data, loading, error, setData } = useApi(
    () => api.dashboard(eventId) as Promise<DashboardSummary>,
    [eventId, authenticated],
  );

  if (loading) return <DashboardSkeleton />;
  if (error) return <ErrorState message={error} onRetry={() => setData(null)} />;
  if (!data) return <ErrorState message="No hay datos disponibles." />;

  return (
    <div className="space-y-6">
      <div className="grid-auto">
        <StatCard label="ECOE activo" value={ecoeStatusLabel(data.active_ecoe.status)} hint={data.active_ecoe.name} />
        <StatCard label="Estudiantes" value={data.totals.students} hint="cargados y asignados" />
        <StatCard label="Estaciones" value={data.totals.stations} hint="incluye estaciones espejo" />
        <StatCard label="Envíos" value={data.totals.evaluations} hint="evaluaciones registradas" />
      </div>

      <SectionCard title="Preparación del ECOE" subtitle="Resumen operativo del evento vigente">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="clinical-panel">
            <p className="text-sm text-slate-500">Pilotaje</p>
            <p className={`mt-2 pill ${data.validation.can_pilot ? "pill-ok" : "pill-warn"}`}>
              {data.validation.can_pilot ? "Listo para pilotaje" : "Pendiente"}
            </p>
          </div>
          <div className="clinical-panel">
            <p className="text-sm text-slate-500">Publicación</p>
            <p className={`mt-2 pill ${data.validation.can_publish ? "pill-ok" : "pill-warn"}`}>
              {data.validation.can_publish ? "Publicable" : "Requiere ajustes"}
            </p>
          </div>
          <div className="clinical-panel">
            <p className="text-sm text-slate-500">Sesión en vivo</p>
            <p className="mt-2 text-2xl font-semibold">{sessionStatusLabel(data.live_panel.status)}</p>
            <p className="text-sm text-slate-600">
              Estación {data.live_panel.current_station_index} · {data.live_panel.remaining_seconds}s
            </p>
          </div>
        </div>
        {data.validation.warnings.length ? (
          <div className="rounded-2xl border border-amber-200 bg-[var(--color-warning-soft)] p-4 text-sm text-amber-900">
            {data.validation.warnings.map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="Estado de estaciones" subtitle="Línea de tiempo del circuito activo">
        <DataTable
          columns={[
            { key: "label", label: "Estación" },
            { key: "circuit", label: "Circuito" },
            {
              key: "status",
              label: "Estado",
              render: (row) => (
                <span className="pill pill-ok">
                  {stationStatusLabel((row as { status?: string }).status)}
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
