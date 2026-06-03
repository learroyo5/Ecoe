"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";

export default function StationsPage() {
  const { token, eventId, user } = useECOE();
  const router = useRouter();
  const { data, loading, error } = useApi(
    () => api.stations(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );

  useEffect(() => {
    if (user?.role === "evaluador") {
      router.replace("/evaluator");
    }
  }, [router, user?.role]);

  if (user?.role === "evaluador") {
    return (
      <SectionCard
        title="Acceso restringido"
        subtitle="El perfil evaluador no puede entrar a la gestión de estaciones."
      >
        <p>Te estamos redirigiendo a tu interfaz operativa.</p>
      </SectionCard>
    );
  }

  return (
    <div className="space-y-6">
      <SectionCard title="Gestión de estaciones" subtitle="Vista resumida del circuito, acceso al constructor y control de avance por estación.">
        <div className="flex flex-wrap gap-3">
          <Link href="/stations/builder" className="btn-primary">
            Abrir constructor de estación
          </Link>
          <Link href="/station-bank" className="btn-secondary">
            Abrir banco de estaciones
          </Link>
        </div>
      </SectionCard>
      <SectionCard title="Estaciones del ECOE" subtitle="Cada estación se presenta como unidad docente y operativa dentro del ECOE activo.">
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
              {
                key: "actions",
                label: "Acciones",
                render: (row) => (
                  <Link
                    href={`/stations/builder?stationId=${String((row as { id?: number }).id ?? "")}`}
                    className="text-sm font-semibold text-[var(--color-primary)] underline-offset-4 hover:underline"
                  >
                    Abrir y editar
                  </Link>
                ),
              },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
