"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

export default function InstrumentsPage() {
  const { token } = useECOE();
  const { data, loading, error, setData } = useApi(
    () => api.instruments(token!) as Promise<Record<string, unknown>[]>,
    [token],
  );
  const [message, setMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [lastCreateSucceeded, setLastCreateSucceeded] = useState(false);

  return (
    <div className="space-y-6">
      <SectionCard title="Banco de instrumentos" subtitle="Repositorio de listas de cotejo, rúbricas y escalas para reutilizar en estaciones del ECOE.">
        <div className="clinical-panel">
          <p className="text-sm leading-6 text-slate-600">
            Esta pantalla todavía usa una acción rápida de demostración. El constructor de estaciones ya permite crear pautas reales dentro del flujo docente.
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              className={`btn-primary transition-all ${
                isSaving
                  ? "cursor-wait opacity-90"
                  : lastCreateSucceeded
                    ? "border-emerald-600 bg-emerald-600 text-white hover:bg-emerald-700"
                    : "shadow-[0_12px_30px_-18px_rgba(13,148,136,0.75)]"
              }`}
              disabled={isSaving}
              onClick={async () => {
                const confirmed = window.confirm(
                  "Vas a crear un instrumento de prueba en el banco. ¿Quieres continuar?",
                );
                if (!confirmed) {
                  setLastCreateSucceeded(false);
                  setMessage("Creación cancelada por el usuario.");
                  return;
                }
                setIsSaving(true);
                setMessage(null);
                try {
                  await api.createInstrument(
                    {
                      name: "Rúbrica de comunicación",
                      tool_type: "rubrica_simple",
                      max_score: 10,
                      free_observation: true,
                      items: [
                        { label: "Presentación", score_per_item: 2, order_index: 1 },
                        { label: "Estructura", score_per_item: 4, order_index: 2 },
                        { label: "Cierre", score_per_item: 4, order_index: 3 },
                      ],
                    },
                    token!,
                  );
                  setData((await api.instruments(token!)) as Record<string, unknown>[]);
                  setLastCreateSucceeded(true);
                  setMessage("Instrumento de prueba creado correctamente.");
                } catch (saveError) {
                  setLastCreateSucceeded(false);
                  setMessage(
                    saveError instanceof Error
                      ? saveError.message
                      : "No se pudo crear el instrumento de prueba.",
                  );
                } finally {
                  setIsSaving(false);
                }
              }}
            >
              {isSaving
                ? "Creando..."
                : lastCreateSucceeded
                  ? "Instrumento creado"
                  : "Crear instrumento de prueba"}
            </button>
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold ${
                isSaving
                  ? "bg-slate-100 text-slate-600"
                  : lastCreateSucceeded
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-sky-100 text-sky-800"
              }`}
            >
              {isSaving
                ? "Creando ahora"
                : lastCreateSucceeded
                  ? "Acción completada"
                  : "Requiere confirmación"}
            </span>
          </div>
          <StatusNotice message={message} className="mt-4" />
        </div>
      </SectionCard>
      <SectionCard title="Instrumentos reutilizables" subtitle="Las pautas aquí guardadas pueden vincularse a distintas estaciones del banco o del ECOE activo.">
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
              { key: "max_score", label: "Puntaje máximo" },
              {
                key: "items",
                label: "Ítems",
                render: (row) => String((row.items as { length?: number })?.length ?? 0),
              },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
