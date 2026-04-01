"use client";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { QuickForm } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

export default function TemplatesPage() {
  const { token } = useAuth();
  const { data, loading, error, setData } = useApi(
    () => api.templates(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );

  const refresh = async () => setData((await api.templates(token!)) as Record<string, unknown>[]);

  return (
    <div className="space-y-6">
      <SectionCard title="Banco de plantillas" subtitle="Define estructuras base reutilizables para orientar el flujo real de cada tipo de estacion.">
        <QuickForm
          fields={[
            { name: "name", label: "Nombre" },
            { name: "category", label: "Categoria" },
            { name: "description", label: "Descripcion" },
          ]}
          onSubmit={async (values) => {
            await api.createTemplate(
              { ...values, default_configuration: { source: "manual" } },
              token!,
            );
            await refresh();
          }}
        />
      </SectionCard>
      <SectionCard title="Plantillas disponibles" subtitle="Repositorio de configuraciones operativas reutilizables para nuevos ECOE.">
        {loading ? (
          <p>Cargando plantillas...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            columns={[
              { key: "name", label: "Nombre" },
              { key: "category", label: "Categoria" },
              { key: "description", label: "Descripcion" },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
