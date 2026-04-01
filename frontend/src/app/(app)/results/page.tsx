"use client";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";

export default function ResultsPage() {
  const { token, eventId } = useAuth();
  const { data, loading, error } = useApi(
    () => api.results(eventId, token!) as Promise<{ results: Record<string, unknown>[] }>,
    [eventId, token],
  );

  return (
    <div className="space-y-6">
      <SectionCard title="Resultados y exportacion" subtitle="Consolidacion automatica de puntajes, porcentaje y nota equivalente">
        <div className="flex flex-wrap gap-3">
          <a
            className="btn-primary"
            href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"}/results/${eventId}/export/excel`}
            target="_blank"
            rel="noreferrer"
          >
            Exportar Excel consolidado
          </a>
          <a
            className="btn-secondary"
            href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"}/results/${eventId}/export/pdf`}
            target="_blank"
            rel="noreferrer"
          >
            Exportar PDF contingencia
          </a>
        </div>
      </SectionCard>
      <SectionCard title="Consolidado por estudiante" subtitle="Vista tipo ficha de resultados, pensada para lectura academica clara y exportacion segura.">
        {loading ? (
          <p>Calculando resultados...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data?.results ?? []}
            columns={[
              { key: "ecoe_number", label: "N ECOE" },
              { key: "student_name", label: "Estudiante" },
              { key: "total_score", label: "Puntaje" },
              { key: "max_score", label: "Maximo" },
              { key: "percentage", label: "Porcentaje" },
              { key: "equivalent_grade", label: "Nota equivalente" },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
