"use client";

import { api } from "@/lib/api";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";
import type {
  GradeHistogramBucket,
  PsychometricsResponse,
} from "@/lib/types";

function fmt(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}

/** Mini-histograma de nota 1–7 en barras horizontales compactas. */
function GradeHistogram({ buckets }: { buckets: GradeHistogramBucket[] }) {
  const max = Math.max(1, ...buckets.map((b) => b.count));
  return (
    <div className="flex items-end gap-0.5" title="Distribución de nota 1.0–7.0">
      {buckets.map((bucket) => (
        <div key={bucket.grade} className="flex flex-col items-center gap-0.5">
          <div
            className="w-3 rounded-sm bg-[var(--color-primary)]/70"
            style={{ height: `${4 + (bucket.count / max) * 28}px` }}
          />
          <span className="text-[10px] text-slate-400">{bucket.grade}</span>
        </div>
      ))}
    </div>
  );
}

const MODE_LABEL: Record<string, string> = {
  ejecucion: "ejecución",
  pilotaje: "pilotaje",
};

export function PsychometricsSection({
  eventId,
  mode,
  authenticated,
  title,
  subtitle,
}: {
  eventId: number;
  mode: "ejecucion" | "pilotaje";
  authenticated: boolean;
  title?: string;
  subtitle?: string;
}) {
  const { data, loading, error } = useApi<PsychometricsResponse>(
    () => api.psychometrics(eventId, mode),
    [eventId, mode, authenticated],
  );

  const stations = data?.station_stats ?? [];
  const reliability = data?.reliability ?? null;
  const items = data?.item_analysis ?? [];
  const warnings = data?.warnings ?? [];
  const qualityWarnings = warnings.filter((w) => w.severity === "warning");
  const sampleCaveats = warnings.filter((w) => w.severity === "caveat");

  return (
    <SectionCard
      title={title ?? `Análisis de respuestas (${MODE_LABEL[mode] ?? mode})`}
      subtitle={
        subtitle ??
        "Media y dispersión por estación, consistencia interna (α de Cronbach, listwise), discriminación estación-total corregida y análisis por criterio de pauta. Las advertencias no bloquean: son señales de calidad de la medición."
      }
    >
      {loading ? (
        <p>Calculando métricas psicométricas...</p>
      ) : error ? (
        <p>{error}</p>
      ) : !data || (stations.length === 0 && items.length === 0) ? (
        <p className="text-sm text-slate-500">
          Aún no hay datos de {MODE_LABEL[mode] ?? mode} suficientes para calcular métricas.
        </p>
      ) : (
        <div className="space-y-6">
          {data.frozen ? (
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-sm font-semibold text-emerald-800">
              <span aria-hidden>🔒</span> Métricas sobre el acta consolidada (congelada al cierre)
            </div>
          ) : null}

          {reliability ? (
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="clinical-panel">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  α de Cronbach
                </p>
                <p className="mt-2 text-3xl font-semibold">
                  {reliability.cronbach_alpha === null ? "—" : fmt(reliability.cronbach_alpha, 2)}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {reliability.k_stations} estaciones · n listwise {reliability.n_complete} de{" "}
                  {reliability.n_total}
                </p>
              </div>
              <div className="clinical-panel sm:col-span-2">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                  Discriminación estación-total (r corregida)
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {reliability.station_discrimination.map((entry) => (
                    <span
                      key={entry.station_id}
                      className={`status-badge ${
                        entry.r === null
                          ? "status-badge-muted"
                          : entry.r < 0
                            ? "status-badge-error"
                            : entry.r < 0.2
                              ? "status-badge-warning"
                              : "status-badge-success"
                      }`}
                      title={entry.station_name}
                    >
                      E{entry.station_number}: {entry.r === null ? "—" : fmt(entry.r, 2)}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ) : null}

          <DataTable
            rows={stations}
            columns={[
              { key: "station_number", label: "Estación" },
              { key: "station_name", label: "Nombre" },
              { key: "n", label: "n" },
              { key: "mean_percent", label: "Media %", render: (r) => fmt(r.mean_percent) },
              { key: "sd_percent", label: "DE %", render: (r) => fmt(r.sd_percent) },
              { key: "mean_score", label: "Media pts", render: (r) => fmt(r.mean_score) },
              {
                key: "grade_histogram",
                label: "Nota 1–7",
                render: (r) => <GradeHistogram buckets={r.grade_histogram} />,
              },
            ]}
          />

          {items.length > 0 ? (
            <div className="space-y-2">
              <h4 className="text-lg font-semibold text-slate-800">Análisis por criterio de pauta</h4>
              <p className="text-xs leading-5 text-slate-500">
                Best-effort: solo estaciones con pauta estructurada (evaluador) o formulario
                puntuable. El puntaje por ítem del evaluador lo aporta el cliente y no se valida
                contra el total; las estaciones con puntaje libre no aparecen.
              </p>
              <DataTable
                rows={items}
                searchKeys={["criterion_label", "station_name"]}
                searchPlaceholder="Buscar criterio..."
                columns={[
                  {
                    key: "station_name",
                    label: "Estación",
                    render: (r) => `${r.station_number}. ${r.station_name}`,
                  },
                  { key: "criterion_label", label: "Criterio" },
                  { key: "n", label: "n" },
                  {
                    key: "difficulty",
                    label: "Dificultad (p)",
                    render: (r) => {
                      const v = r.difficulty;
                      const out = fmt(v, 2);
                      if (v === null) return out;
                      const bad = v < 0.2 || v > 0.9;
                      return <span className={bad ? "font-semibold text-amber-700" : ""}>{out}</span>;
                    },
                  },
                  {
                    key: "point_biserial",
                    label: "Punto-biserial",
                    render: (r) => {
                      const v = r.point_biserial;
                      const out = fmt(v, 2);
                      if (v === null) return out;
                      const bad = v < 0.2;
                      return (
                        <span className={bad ? "font-semibold text-amber-700" : ""}>{out}</span>
                      );
                    },
                  },
                ]}
              />
            </div>
          ) : null}

          {qualityWarnings.length > 0 ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-semibold text-amber-900">
                Advertencias de calidad ({qualityWarnings.length})
              </p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-amber-900">
                {qualityWarnings.map((warning, index) => (
                  <li key={`${warning.code}-${index}`}>{warning.message}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-sm text-emerald-700">
              Ninguna métrica cae fuera de los umbrales por defecto.
            </p>
          )}

          {sampleCaveats.length > 0 ? (
            <ul className="list-disc space-y-1 pl-5 text-xs text-slate-500">
              {sampleCaveats.map((warning, index) => (
                <li key={`${warning.code}-${index}`}>{warning.message}</li>
              ))}
            </ul>
          ) : null}
        </div>
      )}
    </SectionCard>
  );
}
