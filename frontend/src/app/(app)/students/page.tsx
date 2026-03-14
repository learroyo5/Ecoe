"use client";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { FileImport, QuickForm } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

export default function StudentsPage() {
  const { token, eventId } = useAuth();
  const { data, loading, error, setData } = useApi(
    () => api.students(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );

  const refresh = async () => setData((await api.students(eventId, token!)) as Record<string, unknown>[]);

  return (
    <div className="space-y-6">
      <SectionCard title="Gestion de estudiantes" subtitle="Carga masiva por Excel/CSV y alta manual">
        <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <FileImport
            label="Importar estudiantes"
            onImport={async (file) => {
              await api.importStudents(eventId, file, token!);
              await refresh();
            }}
          />
          <QuickForm
            fields={[
              { name: "name", label: "Nombre" },
              { name: "last_name", label: "Apellidos" },
              { name: "rut", label: "RUT" },
              { name: "email", label: "Correo", type: "email" },
              { name: "ecoe_number", label: "Numero ECOE" },
              { name: "group_name", label: "Grupo/circuito" },
            ]}
            onSubmit={async (values) => {
              await api.createStudent(
                {
                  ecoe_event_id: eventId,
                  circuit_name: values.group_name ?? "Circuito A",
                  ...values,
                },
                token!,
              );
              await refresh();
            }}
          />
        </div>
      </SectionCard>
      <SectionCard title="Nomina actual">
        {loading ? (
          <p>Cargando estudiantes...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            columns={[
              { key: "ecoe_number", label: "N ECOE" },
              { key: "name", label: "Nombre" },
              { key: "last_name", label: "Apellidos" },
              { key: "rut", label: "RUT" },
              { key: "email", label: "Correo" },
              { key: "group_name", label: "Grupo" },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
