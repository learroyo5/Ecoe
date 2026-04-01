"use client";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";

export default function PilotagePage() {
  const { token, eventId } = useAuth();
  const { data, loading, error, setData } = useApi(
    () => api.pilotage(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );

  const refresh = async () => setData((await api.pilotage(eventId, token!)) as Record<string, unknown>[]);

  return (
    <div className="space-y-6">
      <SectionCard title="Pilotaje" subtitle="Simula una estacion o un circuito completo para revisar flujo, tiempos, formularios y observacion antes de la ejecucion real.">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Pilotaje focal
            </p>
            <h4 className="mt-3 text-xl text-slate-900">Probar una sola estacion</h4>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Sirve para revisar pauta, flujo del estudiante, material multimedia y claridad de las instrucciones.
            </p>
            <button
              className="btn-primary mt-4"
              onClick={async () => {
                await api.createPilotage(
                  { ecoe_event_id: eventId, name: "Pilotaje rapido", scope: "estacion" },
                  token!,
                );
                await refresh();
              }}
            >
              Pilotear estacion
            </button>
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Pilotaje integrado
            </p>
            <h4 className="mt-3 text-xl text-slate-900">Probar el circuito completo</h4>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Sirve para revisar continuidad entre estaciones, transiciones, tiempos y coordinacion operativa general.
            </p>
            <button
              className="btn-secondary mt-4"
              onClick={async () => {
                await api.createPilotage(
                  { ecoe_event_id: eventId, name: "Pilotaje de circuito", scope: "circuito_completo" },
                  token!,
                );
                await refresh();
              }}
            >
              Pilotear circuito completo
            </button>
          </div>
        </div>
      </SectionCard>
      <SectionCard title="Historial de pilotajes" subtitle="Cada pilotaje queda registrado para distinguir pruebas operativas de la ejecucion real.">
        {loading ? (
          <p>Cargando pilotajes...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            columns={[
              { key: "name", label: "Nombre" },
              {
                key: "scope",
                label: "Alcance",
                render: (row) => {
                  const scope = String((row as { scope?: string }).scope ?? "");
                  return (
                    <span className={`status-badge ${scope === "circuito_completo" ? "status-badge-info" : "status-badge-success"}`}>
                      {scope === "circuito_completo" ? "Circuito completo" : "Estacion"}
                    </span>
                  );
                },
              },
              {
                key: "archived",
                label: "Estado",
                render: (row) => (
                  <span className={`status-badge ${(row as { archived?: boolean }).archived ? "status-badge-warning" : "status-badge-success"}`}>
                    {(row as { archived?: boolean }).archived ? "Archivado" : "Activo"}
                  </span>
                ),
              },
              {
                key: "actions",
                label: "Accion",
                render: (row) => (
                  <button
                    className="btn-secondary"
                    onClick={async () => {
                      await api.archivePilotage(Number(row.id), token!);
                      await refresh();
                    }}
                  >
                    {(row as { archived?: boolean }).archived ? "Archivado" : "Archivar"}
                  </button>
                ),
              },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
