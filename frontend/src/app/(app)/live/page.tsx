"use client";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";

export default function LivePage() {
  const { token, eventId } = useAuth();
  const liveQuery = useApi(
    () => api.live(eventId, token!) as Promise<Record<string, unknown>>,
    [eventId, token],
  );
  const incidentsQuery = useApi(
    () => api.incidents(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );

  const sendAction = async (action: string) => {
    await api.liveControl({ ecoe_event_id: eventId, action }, token!);
    liveQuery.setData((await api.live(eventId, token!)) as Record<string, unknown>);
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Panel central en vivo" subtitle="Cronometro central, flujo del circuito e incidencias con una lectura clara para coordinacion operativa.">
        <div className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[2rem] bg-[linear-gradient(135deg,var(--color-primary-dark),var(--color-primary))] p-6 text-white shadow-[0_18px_40px_rgba(27,73,101,0.24)]">
            <p className="text-sm uppercase tracking-[0.18em] text-slate-100/80">Cronometro central</p>
            <p className="mt-4 text-6xl font-semibold">
              {String(liveQuery.data?.remaining_seconds ?? 0)}s
            </p>
            <p className="mt-2 text-slate-100/80">
              Estado: {String(liveQuery.data?.status ?? "sin sesion")} · Estacion{" "}
              {String(liveQuery.data?.current_station_index ?? 0)}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              {["start", "pause", "resume", "reset", "next_transition"].map((action) => (
                <button
                  key={action}
                  className={action === "start" ? "btn-primary" : "btn-secondary"}
                  onClick={() => sendAction(action)}
                >
                  {action}
                </button>
              ))}
            </div>
          </div>
          <div className="clinical-panel">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
              Supervision operativa
            </p>
            <ul className="mt-4 space-y-3 text-sm text-slate-700">
              <li>Inicio manual del ECOE preparado.</li>
              <li>Control de pausa, reanudacion y reinicio controlado.</li>
              <li>Base lista para conectar sonido simple por parlantes locales.</li>
              <li>Seguimiento de incidencias y avance del circuito.</li>
            </ul>
          </div>
        </div>
      </SectionCard>
      <SectionCard title="Incidencias activas" subtitle="Registro visible de problemas operativos para reaccionar rapido durante la sesion.">
        <DataTable
          rows={incidentsQuery.data ?? []}
          columns={[
            { key: "title", label: "Incidencia" },
            { key: "detail", label: "Detalle" },
            {
              key: "severity",
              label: "Severidad",
              render: (row) => {
                const severity = String((row as { severity?: string }).severity ?? "").toLowerCase();
                const badgeClass =
                  severity.includes("alta") || severity.includes("crit")
                    ? "status-badge-error"
                    : severity.includes("media")
                      ? "status-badge-warning"
                      : "status-badge-info";
                return <span className={`status-badge ${badgeClass}`}>{severity || "sin definir"}</span>;
              },
            },
          ]}
        />
      </SectionCard>
    </div>
  );
}
