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
      <SectionCard title="Pilotaje" subtitle="Todos los registros quedan marcados como prueba y separados de la ejecucion real">
        <div className="flex flex-wrap gap-3">
          <button
            className="btn-primary"
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
          <button
            className="btn-secondary"
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
      </SectionCard>
      <SectionCard title="Historial de pilotajes">
        {loading ? (
          <p>Cargando pilotajes...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            columns={[
              { key: "name", label: "Nombre" },
              { key: "scope", label: "Alcance" },
              {
                key: "archived",
                label: "Archivado",
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
