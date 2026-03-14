"use client";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { FileImport, QuickForm } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

export default function EvaluatorsPage() {
  const { token, eventId } = useAuth();
  const { data, loading, error, setData } = useApi(
    () => api.staff(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );

  const refresh = async () => setData((await api.staff(eventId, token!)) as Record<string, unknown>[]);

  return (
    <div className="space-y-6">
      <SectionCard title="Evaluadores y colaboradores" subtitle="Asignacion operativa por rol y estacion">
        <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <FileImport
            label="Importar evaluadores o colaboradores"
            onImport={async (file) => {
              await api.importStaff(eventId, file, token!);
              await refresh();
            }}
          />
          <QuickForm
            fields={[
              { name: "name", label: "Nombre" },
              { name: "last_name", label: "Apellidos" },
              { name: "email", label: "Correo", type: "email" },
              { name: "role_code", label: "Rol", placeholder: "evaluador" },
              { name: "station_ids", label: "Estaciones", placeholder: "1,2" },
            ]}
            onSubmit={async (values) => {
              await api.createStaff(
                {
                  ecoe_event_id: eventId,
                  ...values,
                  station_ids: (values.station_ids ?? "")
                    .split(",")
                    .map((value) => Number(value.trim()))
                    .filter(Boolean),
                },
                token!,
              );
              await refresh();
            }}
          />
        </div>
      </SectionCard>
      <SectionCard title="Equipo operativo">
        {loading ? (
          <p>Cargando equipo...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            columns={[
              { key: "name", label: "Nombre" },
              { key: "last_name", label: "Apellidos" },
              { key: "email", label: "Correo" },
              { key: "role_code", label: "Rol" },
              {
                key: "station_ids",
                label: "Estaciones",
                render: (row) => String((row as { station_ids?: unknown[] }).station_ids ?? []),
              },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
