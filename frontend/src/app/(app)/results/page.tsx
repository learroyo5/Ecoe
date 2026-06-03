"use client";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";

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

export default function ResultsPage() {
  const { token, eventId } = useECOE();
  const { data, loading, error } = useApi(
    () =>
      api.results(eventId, token!) as Promise<{
        results: Record<string, unknown>[];
        summary: Record<string, unknown>;
        student_traceability: Record<string, unknown>[];
        station_traceability: Record<string, unknown>[];
        activity_log: Record<string, unknown>[];
      }>,
    [eventId, token],
  );
  const summary = (data?.summary as Record<string, unknown> | undefined) ?? {};
  const studentTraceability = (data?.student_traceability as Record<string, unknown>[] | undefined) ?? [];
  const stationTraceability = (data?.station_traceability as Record<string, unknown>[] | undefined) ?? [];
  const activityLog = (data?.activity_log as Record<string, unknown>[] | undefined) ?? [];

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
      <SectionCard title="Resultados y exportación" subtitle="Consolidación automática de puntajes, porcentaje y nota equivalente">
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
            Exportar PDF contingencia
          </a>
        </div>
      </SectionCard>
      <SectionCard title="Consolidado por estudiante" subtitle="Vista tipo ficha de resultados, pensada para una lectura académica clara y una exportación segura.">
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
              { key: "max_score", label: "Máximo" },
              { key: "percentage", label: "Porcentaje" },
              { key: "equivalent_grade", label: "Nota equivalente" },
            ]}
          />
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
                  <span className="text-xs text-[var(--color-text-muted)]">{formatTimestamp(item.timestamp)}</span>
                </div>
                <p className="mt-2 text-sm text-[var(--color-text-secondary)]">{String(item.detail ?? "")}</p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">
                  {String(item.actor ?? "Sistema")} · modo {String(item.mode ?? "ejecución")}
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
