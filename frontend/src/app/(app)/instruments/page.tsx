"use client";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";

export default function InstrumentsPage() {
  const { token } = useAuth();
  const { data, loading, error, setData } = useApi(
    () => api.instruments(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );

  return (
    <div className="space-y-6">
      <SectionCard title="Banco de instrumentos" subtitle="Repositorio de listas de cotejo, rubricas y escalas para reutilizar en estaciones del ECOE.">
        <div className="clinical-panel">
          <p className="text-sm leading-6 text-slate-600">
            Esta pantalla todavia usa una accion rapida de demostracion. El constructor de estaciones ya permite crear pautas reales dentro del flujo docente.
          </p>
          <button
            className="btn-primary mt-4"
            onClick={async () => {
              await api.createInstrument(
                {
                  name: "Rubrica de comunicacion",
                  tool_type: "rubrica_simple",
                  max_score: 10,
                  free_observation: true,
                  items: [
                    { label: "Presentacion", score_per_item: 2, order_index: 1 },
                    { label: "Estructura", score_per_item: 4, order_index: 2 },
                    { label: "Cierre", score_per_item: 4, order_index: 3 },
                  ],
                },
                token!,
              );
              setData((await api.instruments(token!)) as Record<string, unknown>[]);
            }}
          >
            Crear instrumento demo
          </button>
        </div>
      </SectionCard>
      <SectionCard title="Instrumentos reutilizables" subtitle="Las pautas aqui guardadas pueden vincularse a distintas estaciones del banco o del ECOE activo.">
        {loading ? (
          <p>Cargando instrumentos...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            columns={[
              { key: "name", label: "Nombre" },
              { key: "tool_type", label: "Tipo" },
              { key: "max_score", label: "Puntaje maximo" },
              {
                key: "items",
                label: "Items",
                render: (row) => String((row.items as { length?: number })?.length ?? 0),
              },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
