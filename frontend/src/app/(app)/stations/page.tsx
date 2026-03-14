"use client";

import Link from "next/link";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";

export default function StationsPage() {
  const { token, eventId } = useAuth();
  const { data, loading, error } = useApi(
    () => api.stations(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );

  return (
    <div className="space-y-6">
      <SectionCard title="Gestion de estaciones" subtitle="Vista resumida del circuito y acceso al constructor">
        <Link href="/stations/builder" className="btn-primary">
          Abrir constructor de estacion
        </Link>
      </SectionCard>
      <SectionCard title="Estaciones del ECOE">
        {loading ? (
          <p>Cargando estaciones...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            columns={[
              { key: "station_number", label: "N" },
              { key: "name", label: "Nombre" },
              { key: "station_type", label: "Tipo" },
              { key: "circuit_name", label: "Circuito" },
              { key: "station_time_minutes", label: "Tiempo" },
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
          />
        )}
      </SectionCard>
    </div>
  );
}
