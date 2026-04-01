"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";

export default function PilotagePage() {
  const { token, eventId } = useAuth();
  const { data, loading, error, setData } = useApi(
    () => api.pilotage(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );
  const { data: stations } = useApi(
    () => api.stations(eventId, token!) as Promise<Record<string, unknown>[]>,
    [eventId, token],
  );
  const { data: validation } = useApi(
    () => api.validation(eventId, token!) as Promise<Record<string, unknown>>,
    [eventId, token],
  );
  const [selectedStationId, setSelectedStationId] = useState("");
  const [message, setMessage] = useState<string | null>(null);

  const refresh = async () =>
    setData((await api.pilotage(eventId, token!)) as Record<string, unknown>[]);

  const readyStationIssues =
    ((validation?.station_issues as Record<string, unknown>[] | undefined) ?? []).filter((issue) =>
      Boolean(issue.ready_for_pilot),
    );

  const readyStationOptions = useMemo(
    () =>
      readyStationIssues
        .map((issue) => {
          const stationId = Number(issue.station_id);
          const station = (stations ?? []).find((item) => Number(item.id) === stationId);
          return {
            id: String(stationId),
            label: station
              ? `${String(station.station_number)} - ${String(station.name)}`
              : `Estacion ${String(issue.station_number)}`,
          };
        })
        .filter((option) => option.id),
    [readyStationIssues, stations],
  );

  useEffect(() => {
    if (!selectedStationId && readyStationOptions.length) {
      setSelectedStationId(readyStationOptions[0].id);
    }
  }, [readyStationOptions, selectedStationId]);

  const hasStationPilot = ((data ?? []) as Record<string, unknown>[]).some(
    (run) => String(run.scope ?? "") === "estacion",
  );
  const canPilotCircuit = Boolean(validation?.can_pilot) && hasStationPilot;

  return (
    <div className="space-y-6">
      <SectionCard
        title="Pilotaje"
        subtitle="Simula una estacion o un circuito completo para revisar flujo, tiempos, formularios y observacion antes de la ejecucion real."
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Pilotaje focal
            </p>
            <h4 className="mt-3 text-xl text-slate-900">Probar una sola estacion</h4>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Sirve para revisar pauta, flujo del estudiante, material multimedia y claridad de las instrucciones.
            </p>
            <label className="mt-4 block space-y-2">
              <span className="text-sm font-semibold text-slate-700">
                Estacion lista para pilotaje
              </span>
              <select
                value={selectedStationId}
                onChange={(event) => setSelectedStationId(event.target.value)}
                disabled={!readyStationOptions.length}
              >
                {!readyStationOptions.length ? (
                  <option value="">No hay estaciones listas para pilotaje</option>
                ) : null}
                {readyStationOptions.map((station) => (
                  <option key={station.id} value={station.id}>
                    {station.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              className="btn-primary mt-4"
              onClick={async () => {
                setMessage(null);
                try {
                  await api.createPilotage(
                    {
                      ecoe_event_id: eventId,
                      name: `Pilotaje de estacion ${selectedStationId}`,
                      scope: "estacion",
                      station_ids: selectedStationId ? [Number(selectedStationId)] : [],
                    },
                    token!,
                  );
                  await refresh();
                  setMessage("Pilotaje individual creado correctamente.");
                } catch (pilotageError) {
                  setMessage(
                    pilotageError instanceof Error
                      ? pilotageError.message
                      : "No se pudo crear el pilotaje individual.",
                  );
                }
              }}
              disabled={!selectedStationId}
            >
              Pilotear estacion
            </button>
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Pilotaje integrado
            </p>
            <h4 className="mt-3 text-xl text-slate-900">Probar el circuito completo</h4>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Sirve para revisar continuidad entre estaciones, transiciones, tiempos y coordinacion operativa general.
            </p>
            <button
              className="btn-secondary mt-4"
              onClick={async () => {
                setMessage(null);
                try {
                  await api.createPilotage(
                    {
                      ecoe_event_id: eventId,
                      name: "Pilotaje de circuito",
                      scope: "circuito_completo",
                    },
                    token!,
                  );
                  await refresh();
                  setMessage("Pilotaje de circuito completo creado correctamente.");
                } catch (pilotageError) {
                  setMessage(
                    pilotageError instanceof Error
                      ? pilotageError.message
                      : "No se pudo crear el pilotaje de circuito completo.",
                  );
                }
              }}
              disabled={!canPilotCircuit}
            >
              Pilotear circuito completo
            </button>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Solo se habilita despues de realizar al menos un pilotaje individual de estacion.
            </p>
            {!hasStationPilot ? (
              <p className="mt-2 text-sm text-amber-700">
                Aun no existe un pilotaje individual previo en este ECOE.
              </p>
            ) : null}
          </div>
        </div>
        {message ? <p className="text-sm text-slate-600">{message}</p> : null}
      </SectionCard>
      <SectionCard
        title="Historial de pilotajes"
        subtitle="Cada pilotaje queda registrado para distinguir pruebas operativas de la ejecucion real."
      >
        {loading ? (
          <p>Cargando pilotajes...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data ?? []}
            columns={[
              { key: "name", label: "Nombre" },
              {
                key: "scope",
                label: "Alcance",
                render: (row) => {
                  const scope = String((row as { scope?: string }).scope ?? "");
                  return (
                    <span
                      className={`status-badge ${
                        scope === "circuito_completo"
                          ? "status-badge-info"
                          : "status-badge-success"
                      }`}
                    >
                      {scope === "circuito_completo" ? "Circuito completo" : "Estacion"}
                    </span>
                  );
                },
              },
              {
                key: "archived",
                label: "Estado",
                render: (row) => (
                  <span
                    className={`status-badge ${
                      (row as { archived?: boolean }).archived
                        ? "status-badge-warning"
                        : "status-badge-success"
                    }`}
                  >
                    {(row as { archived?: boolean }).archived ? "Archivado" : "Activo"}
                  </span>
                ),
              },
              {
                key: "actions",
                label: "Accion",
                render: (row) => (
                  <button
                    className="btn-secondary"
                    onClick={async () => {
                      await api.archivePilotage(Number(row.id), token!);
                      await refresh();
                    }}
                  >
                    {(row as { archived?: boolean }).archived ? "Archivado" : "Archivar"}
                  </button>
                ),
              },
            ]}
          />
        )}
      </SectionCard>
    </div>
  );
}
