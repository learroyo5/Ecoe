"use client";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { QuickForm } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

export default function SimulatedPatientPage() {
  const { token } = useECOE();
  const { data, loading, error, setData } = useApi(
    () => api.simulatedPatients(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );

  const refresh = async () =>
    setData((await api.simulatedPatients(token!)) as Record<string, unknown>[]);

  return (
    <div className="space-y-6">
      <SectionCard title="Gestor de paciente simulado" subtitle="Construye personajes y guiones reutilizables para estaciones con interaccion clinica.">
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
      <SectionCard title="Banco de personajes" subtitle="Repositorio docente para asignar personajes simulados segun tipo de estacion.">
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
