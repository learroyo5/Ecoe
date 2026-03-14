"use client";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { QuickForm } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

export default function SimulatedPatientPage() {
  const { token } = useAuth();
  const { data, loading, error, setData } = useApi(
    () => api.simulatedPatients(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );

  const refresh = async () =>
    setData((await api.simulatedPatients(token!)) as Record<string, unknown>[]);

  return (
    <div className="space-y-6">
      <SectionCard title="Gestor de paciente simulado" subtitle="Guiones y perfil de personaje cargados por estacion">
        <QuickForm
          fields={[
            { name: "character_name", label: "Nombre personaje" },
            { name: "summary_profile", label: "Perfil resumido" },
            { name: "base_story", label: "Historia base" },
            { name: "key_answers", label: "Respuestas clave" },
            { name: "emotional_tone", label: "Actitud / emocion" },
            { name: "special_instructions", label: "Instrucciones especiales" },
          ]}
          onSubmit={async (values) => {
            await api.createSimulatedPatient(values, token!);
            await refresh();
          }}
        />
      </SectionCard>
      <SectionCard title="Banco de personajes">
        {loading ? (
          <p>Cargando pacientes simulados...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            columns={[
              { key: "character_name", label: "Personaje" },
              { key: "summary_profile", label: "Perfil" },
              { key: "emotional_tone", label: "Tono" },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
