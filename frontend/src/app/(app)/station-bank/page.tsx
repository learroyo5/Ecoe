"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";

const bankStatusOptions = [
  { value: "en_diseno", label: "En diseno" },
  { value: "piloteada", label: "Piloteada" },
  { value: "aprobada", label: "Aprobada" },
  { value: "archivada", label: "Archivada" },
];

export default function StationBankPage() {
  const { token, user } = useAuth();
  const router = useRouter();
  const { data, loading, error, setData } = useApi(
    () => api.stationBank(token!) as Promise<Record<string, unknown>[]>,
    [token],
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
        subtitle="El perfil evaluador no puede entrar al banco de estaciones."
      >
        <p>Te estamos redirigiendo a tu interfaz operativa.</p>
      </SectionCard>
    );
  }

  return (
    <div className="space-y-6">
      <SectionCard
        title="Banco de estaciones"
        subtitle="Aqui viven las estaciones reutilizables del hospital o de la institucion para estandarizar y escalar disenos docentes."
      >
        <div className="flex flex-wrap gap-3">
          <Link href="/stations/builder?scope=bank" className="btn-primary">
            Crear estacion de banco
          </Link>
          <Link href="/stations" className="btn-secondary">
            Volver a estaciones del ECOE
          </Link>
        </div>
      </SectionCard>

      <SectionCard
        title="Estaciones reutilizables"
        subtitle="Una estacion puede quedar en diseno, piloteada, aprobada o archivada segun su nivel de madurez."
      >
        {loading ? (
          <p>Cargando banco de estaciones...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            columns={[
              { key: "name", label: "Nombre" },
              { key: "station_type", label: "Tipo" },
              {
                key: "template_id",
                label: "Plantilla",
                render: (row) =>
                  String((row as { template_id?: number | null }).template_id ?? "Sin plantilla"),
              },
              {
                key: "status",
                label: "Estado",
                render: (row) => {
                  const currentRow = row as { id?: number; status?: string };
                  return (
                    <select
                      value={String(currentRow.status ?? "en_diseno")}
                      onChange={async (event) => {
                        const updated = (await api.updateStationBankStatus(
                          Number(currentRow.id),
                          { status: event.target.value },
                          token!,
                        )) as Record<string, unknown>;
                        setData((current) =>
                          (current ?? []).map((item) =>
                            Number(item.id) === Number(currentRow.id) ? updated : item,
                          ),
                        );
                      }}
                    >
                      {bankStatusOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  );
                },
              },
              {
                key: "actions",
                label: "Acciones",
                render: (row) => {
                  const bankStationId = String((row as { id?: number }).id ?? "");
                  return (
                    <div className="flex flex-wrap gap-3">
                      <Link
                        href={`/stations/builder?scope=bank&bankStationId=${bankStationId}`}
                        className="text-sm font-semibold text-[var(--color-primary)] underline-offset-4 hover:underline"
                      >
                        Editar banco
                      </Link>
                      <Link
                        href={`/stations/builder?useBankStationId=${bankStationId}`}
                        className="text-sm font-semibold text-slate-700 underline-offset-4 hover:underline"
                      >
                        Usar en ECOE
                      </Link>
                    </div>
                  );
                },
              },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
