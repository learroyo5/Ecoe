"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";

const bankStatusOptions = [
  { value: "en_diseno", label: "En diseño" },
  { value: "piloteada", label: "Piloteada" },
  { value: "aprobada", label: "Aprobada" },
  { value: "archivada", label: "Archivada" },
];

export default function StationBankPage() {
  const { authenticated, eventId, eventRoles, user } = useECOE();
  const canEditContent = user?.role === "admin_global"
    || eventRoles.some((role) => role === "admin_ecoe" || role === "coeditor_docente");
  const router = useRouter();
  const { data: templates } = useApi(
    () => api.templates(eventId) as Promise<Record<string, unknown>[]>,
    [authenticated, eventId],
  );
  const { data, loading, error, setData } = useApi(
    () => api.stationBank(eventId) as Promise<Record<string, unknown>[]>,
    [authenticated, eventId],
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
        subtitle="Aquí viven las estaciones reutilizables del hospital o de la institución para estandarizar y escalar diseños docentes."
      >
        <div className="flex flex-wrap gap-3">
          {canEditContent ? (
            <Link href="/stations/builder?scope=bank" className="btn-primary">
              Crear estación de banco
            </Link>
          ) : null}
          <Link href="/stations" className="btn-secondary">
            Volver a estaciones del ECOE
          </Link>
        </div>
      </SectionCard>

      <SectionCard
        title="Estaciones reutilizables"
        subtitle="Una estación puede quedar en diseño, piloteada, aprobada o archivada según su nivel de madurez."
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
                render: (row) => {
                  const templateId = (row as { template_id?: number | null }).template_id;
                  const template = (templates ?? []).find(
                    (item) => Number(item.id) === Number(templateId),
                  );
                  return String(template?.name ?? "Sin plantilla");
                },
              },
              {
                key: "status",
                label: "Estado",
                render: (row) => {
                  const currentRow = row as { id?: number; status?: string };
                  return (
                    <select
                      disabled={!canEditContent}
                      value={String(currentRow.status ?? "en_diseno")}
                      onChange={async (event) => {
                        const updated = (await api.updateStationBankStatus(
                          eventId,
                          Number(currentRow.id),
                          { status: event.target.value },
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
