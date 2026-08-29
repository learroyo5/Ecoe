"use client";

import { useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { modeLabel, submissionKindLabel } from "@/lib/labels";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";
import type { ResultsResponse } from "@/lib/types";

function formatTimestamp(value: unknown) {
  if (!value || typeof value !== "string") {
    return "Sin registro";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleString("es-CL", {
    dateStyle: "short",
    timeStyle: "short",
  });
}

function formatNumber(value: number | null | undefined) {
  return value === null || value === undefined ? "—" : String(value);
}

export default function ResultsPage() {
  const { authenticated, eventId } = useECOE();
  const { data, loading, error } = useApi<ResultsResponse>(
    () => api.results(eventId),
    [eventId, authenticated],
  );
  const summary: Partial<ResultsResponse["summary"]> = data?.summary ?? {};
  const studentTraceability = data?.student_traceability ?? [];
  const stationTraceability = data?.station_traceability ?? [];
  const activityLog = data?.activity_log ?? [];
  const frozen = data?.frozen === true;
  const consolidatedLabel = frozen && data?.consolidated_at ? formatTimestamp(data.consolidated_at) : null;
  const byStation = data?.by_station ?? { stations: [], students: [] };
  const [stationFilter, setStationFilter] = useState<string>("all");
  const filteredStationScores =
    stationFilter === "all"
      ? byStation.students
      : byStation.students.filter((row) => String(row.station_id) === stationFilter);

  return (
    <div className="space-y-6">
      <SectionCard
        title="Resumen operativo"
        subtitle="Trazabilidad mínima para saber cuántas confirmaciones, evaluaciones y respuestas se han registrado realmente."
      >
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Check-ins confirmados</p>
            <p className="mt-3 text-3xl font-semibold">{String(summary.confirmed_checkins ?? 0)}</p>
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Evaluaciones enviadas</p>
            <p className="mt-3 text-3xl font-semibold">
              {String(summary.evaluator_submissions ?? 0)} / {String(summary.expected_evaluations ?? 0)}
            </p>
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Respuestas estudiantiles</p>
            <p className="mt-3 text-3xl font-semibold">
              {String(summary.student_submissions ?? 0)} / {String(summary.expected_student_submissions ?? 0)}
            </p>
          </div>
          <div className="clinical-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">Pilotajes acumulados</p>
            <p className="mt-3 text-3xl font-semibold">{String(summary.pilot_runs ?? 0)}</p>
          </div>
        </div>
      </SectionCard>
      <SectionCard
        title="Resultados y exportación"
        subtitle={
          frozen
            ? "Los resultados están consolidados: la app sirve el acta congelada al cierre, no un recálculo en vivo."
            : "Consolidación automática de puntajes, porcentaje y nota equivalente"
        }
      >
        {frozen ? (
          <div
            data-testid="results-frozen-chip"
            className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-sm font-semibold text-emerald-800"
          >
            <span aria-hidden>🔒</span>
            {consolidatedLabel
              ? `Resultados consolidados el ${consolidatedLabel}`
              : "Resultados consolidados"}
          </div>
        ) : null}
        <div className="flex flex-wrap gap-3">
          <a
            className="btn-primary"
            href={`${process.env.NEXT_PUBLIC_API_URL ?? "/api"}/results/${eventId}/export/excel`}
            target="_blank"
            rel="noreferrer"
          >
            Exportar Excel consolidado
          </a>
          <a
            className="btn-secondary"
            href={`${process.env.NEXT_PUBLIC_API_URL ?? "/api"}/results/${eventId}/export/pdf`}
            target="_blank"
            rel="noreferrer"
          >
            Descargar respaldo de contingencia (PDF)
          </a>
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-500">
          El Excel consolidado es el que contiene los resultados (puntajes, porcentaje y nota por
          estudiante). El PDF de contingencia <strong>no</strong> trae resultados: es la hoja
          imprimible con instrucciones, materiales y listado de estaciones para operar el examen si
          se cae la plataforma.
        </p>
      </SectionCard>
      <SectionCard title="Consolidado por estudiante" subtitle="Vista tipo ficha de resultados, pensada para una lectura académica clara y una exportación segura.">
        {loading ? (
          <p>{frozen ? "Cargando resultados consolidados..." : "Calculando resultados..."}</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={data?.results ?? []}
            columns={[
              { key: "ecoe_number", label: "N ECOE" },
              { key: "student_name", label: "Estudiante" },
              { key: "total_score", label: "Puntaje" },
              { key: "max_score", label: "Máximo" },
              { key: "percentage", label: "Porcentaje" },
              { key: "equivalent_grade", label: "Nota equivalente" },
            ]}
          />
        )}
      </SectionCard>
      <SectionCard
        title="Resultados por estación"
        subtitle="Desempeño desglosado por estación: promedio y dispersión del circuito, y la nota de cada estudiante en cada estación. La DE es muestral y aparece como “—” cuando hay menos de dos notas."
      >
        {loading ? (
          <p>{frozen ? "Cargando resultados por estación..." : "Calculando resultados por estación..."}</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <div className="space-y-6">
            <DataTable
              rows={byStation.stations}
              columns={[
                { key: "station_number", label: "Estación" },
                { key: "station_name", label: "Nombre" },
                { key: "circuit_name", label: "Circuito" },
                { key: "n", label: "n" },
                {
                  key: "mean_percent",
                  label: "Media %",
                  render: (row) => formatNumber(row.mean_percent),
                },
                {
                  key: "sd_percent",
                  label: "DE %",
                  render: (row) => formatNumber(row.sd_percent),
                },
                {
                  key: "mean_score",
                  label: "Media pts",
                  render: (row) => formatNumber(row.mean_score),
                },
                {
                  key: "mean_max",
                  label: "Máx.",
                  render: (row) => formatNumber(row.mean_max),
                },
              ]}
            />
            <div className="space-y-3">
              <label className="flex flex-wrap items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                <span className="font-semibold">Filtrar por estación</span>
                <select
                  className="max-w-xs"
                  value={stationFilter}
                  onChange={(event) => setStationFilter(event.target.value)}
                >
                  <option value="all">Todas las estaciones</option>
                  {byStation.stations.map((station) => (
                    <option key={station.station_id} value={String(station.station_id)}>
                      {station.station_number}. {station.station_name}
                    </option>
                  ))}
                </select>
              </label>
              <DataTable
                rows={filteredStationScores}
                searchKeys={["student_name", "ecoe_number"]}
                searchPlaceholder="Buscar estudiante..."
                columns={[
                  { key: "ecoe_number", label: "N ECOE" },
                  { key: "student_name", label: "Estudiante" },
                  {
                    key: "station_name",
                    label: "Estación",
                    render: (row) => `${row.station_number ?? "?"}. ${row.station_name}`,
                  },
                  { key: "obtained_score", label: "Puntaje" },
                  { key: "max_score", label: "Máximo" },
                  {
                    key: "percent_score",
                    label: "%",
                    render: (row) => formatNumber(row.percent_score),
                  },
                ]}
              />
            </div>
          </div>
        )}
      </SectionCard>
      <SectionCard
        title="Trazabilidad por estudiante"
        subtitle="Verifica rápidamente quién ya fue confirmado, evaluado y quién ya dejó respuesta dentro del circuito."
      >
        {loading ? (
          <p>Construyendo trazabilidad por estudiante...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={studentTraceability}
            columns={[
              { key: "ecoe_number", label: "N ECOE" },
              { key: "student_name", label: "Estudiante" },
              {
                key: "completion_status",
                label: "Estado",
                render: (row) => {
                  const status = String(row.completion_status ?? "sin actividad");
                  const className =
                    status === "completo"
                      ? "status-badge status-badge-success"
                      : status === "parcial"
                        ? "status-badge status-badge-warning"
                        : "status-badge status-badge-muted";
                  return <span className={className}>{status}</span>;
                },
              },
              { key: "checkins_confirmed", label: "Check-ins" },
              { key: "evaluator_submissions", label: "Evaluaciones" },
              { key: "student_submissions", label: "Respuestas" },
              {
                key: "blank_auto_submissions",
                label: "Autoenvíos en blanco",
                render: (row) => {
                  const n = row.blank_auto_submissions ?? 0;
                  return n > 0 ? (
                    <span
                      className="status-badge status-badge-warning"
                      title="Respuestas cerradas por el servidor al vencer el cronómetro, sin contenido. Suman 0 al consolidado; no fueron entregas deliberadas."
                    >
                      {n}
                    </span>
                  ) : (
                    <span className="text-[var(--color-text-muted)]">—</span>
                  );
                },
              },
              {
                key: "last_activity_at",
                label: "Última actividad",
                render: (row) => formatTimestamp(row.last_activity_at),
              },
            ]}
          />
        )}
      </SectionCard>
      <SectionCard
        title="Trazabilidad por estación"
        subtitle="Ayuda a detectar estaciones sin registros, sin evaluador visible o con flujo parcial durante el pilotaje o la ejecución."
      >
        {loading ? (
          <p>Construyendo trazabilidad por estación...</p>
        ) : error ? (
          <p>{error}</p>
        ) : (
          <DataTable
            rows={stationTraceability}
            columns={[
              { key: "station_number", label: "Estación" },
              { key: "station_name", label: "Nombre" },
              { key: "assigned_evaluator", label: "Evaluador principal" },
              { key: "checkins_count", label: "Check-ins" },
              { key: "evaluations_count", label: "Evaluaciones" },
              { key: "student_submissions_count", label: "Respuestas" },
              {
                key: "blank_auto_submissions",
                label: "Autoenvíos en blanco",
                render: (row) => {
                  const n = row.blank_auto_submissions ?? 0;
                  return n > 0 ? (
                    <span className="status-badge status-badge-warning">{n}</span>
                  ) : (
                    <span className="text-[var(--color-text-muted)]">—</span>
                  );
                },
              },
              {
                key: "status",
                label: "Estado",
                render: (row) => {
                  const status = String(row.status ?? "sin registros");
                  const className =
                    status === "con evidencia"
                      ? "status-badge status-badge-success"
                      : status === "con check-in"
                        ? "status-badge status-badge-info"
                        : "status-badge status-badge-muted";
                  return <span className={className}>{status}</span>;
                },
              },
              {
                key: "last_activity_at",
                label: "Última actividad",
                render: (row) => formatTimestamp(row.last_activity_at),
              },
            ]}
          />
        )}
      </SectionCard>
      <SectionCard
        title="Actividad reciente"
        subtitle="Secuencia cronológica breve para reconstruir el flujo real del ECOE y revisar si los pasos se dieron en el orden esperado."
      >
        {loading ? (
          <p>Ordenando actividad reciente...</p>
        ) : error ? (
          <p>{error}</p>
        ) : activityLog.length ? (
          <div className="space-y-3">
            {activityLog.map((item, index) => (
              <div key={`${String(item.timestamp)}-${index}`} className="clinical-panel">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="status-badge status-badge-info">{String(item.type ?? "actividad")}</span>
                  <p className="text-sm font-semibold text-[var(--color-text-main)]">{String(item.label ?? "")}</p>
                  {item.submission_kind && item.submission_kind !== "manual" ? (
                    <span
                      className={
                        item.submission_kind === "auto" && item.answered === false
                          ? "status-badge status-badge-warning"
                          : "status-badge status-badge-muted"
                      }
                    >
                      {item.submission_kind === "auto" && item.answered === false
                        ? "Automática · sin respuesta"
                        : submissionKindLabel(item.submission_kind)}
                    </span>
                  ) : null}
                  <span className="text-xs text-[var(--color-text-muted)]">{formatTimestamp(item.timestamp)}</span>
                </div>
                <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{String(item.detail ?? "")}</p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  {String(item.actor ?? "Sistema")} · modo {modeLabel(item.mode ?? "ejecucion")}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <p>Aún no hay actividad registrada para este ECOE.</p>
        )}
      </SectionCard>
    </div>
  );
}
