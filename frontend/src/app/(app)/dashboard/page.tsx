"use client";

import Link from "next/link";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";
import { DataTable } from "@/components/data-table";
import { DashboardSkeleton } from "@/components/skeleton";
import { ErrorState } from "@/components/toast";
import { CYCLE_PHASES, nextStepFor, phaseIndexForStatus } from "@/lib/ecoe-cycle";
import { ecoeStatusLabel, sessionStatusLabel, stationStatusLabel } from "@/lib/labels";
import { isRouteAllowedForRole } from "@/lib/routes";
import type { DashboardSummary } from "@/lib/types";

function formatClock(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
}

function StatLink({ href, label, value, hint }: { href: string; label: string; value: string | number; hint: string }) {
  return (
    <Link href={href} className="clinical-panel block transition hover:border-[var(--color-primary)]">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-3 text-4xl font-semibold text-slate-900">{value}</p>
      <p className="mt-2 text-sm leading-6 text-slate-600">{hint}</p>
    </Link>
  );
}

export default function DashboardPage() {
  const { authenticated, eventId, user, eventRoles } = useECOE();
  const { data, loading, error, setData } = useApi(
    () => api.dashboard(eventId) as Promise<DashboardSummary>,
    [eventId, authenticated],
  );

  if (loading) return <DashboardSkeleton />;
  if (error) return <ErrorState message={error} onRetry={() => setData(null)} />;
  if (!data) return <ErrorState message="No hay datos disponibles." />;

  const status = data.active_ecoe.status;
  const currentPhase = phaseIndexForStatus(status);
  const nextStep = nextStepFor(status, data.validation);
  // El paso puede vivir en una pantalla que este rol no tiene (p. ej. el
  // coordinador operativo no publica): se muestra igual, sin botón.
  const effectiveRoles = user?.role === "admin_global"
    ? ["admin_global"]
    : eventRoles.length > 0
      ? eventRoles
      : [user?.role ?? ""];
  const canFollowNextStep = nextStep ? isRouteAllowedForRole(nextStep.href, effectiveRoles) : false;
  const sessionStarted = !["sin_sesion", "idle", "ready"].includes(data.live_panel.status);

  return (
    <div className="space-y-6">
      <SectionCard title={data.active_ecoe.name} subtitle={`Estado actual: ${ecoeStatusLabel(status)}`}>
        <ol className="grid gap-2 sm:grid-cols-5" aria-label="Fases del ciclo del ECOE">
          {CYCLE_PHASES.map((phase, index) => {
            const done = currentPhase > index;
            const current = currentPhase === index;
            return (
              <li
                key={phase.key}
                aria-current={current ? "step" : undefined}
                className={`flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm ${
                  current
                    ? "border-[var(--color-primary)] bg-[var(--color-bg-soft)] font-semibold text-[var(--color-primary-dark)]"
                    : done
                      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                      : "border-slate-200 bg-white text-slate-500"
                }`}
              >
                <span
                  className={`flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    current
                      ? "bg-[var(--color-primary)] text-white"
                      : done
                        ? "bg-emerald-600 text-white"
                        : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {done ? "✓" : index + 1}
                </span>
                {phase.label}
              </li>
            );
          })}
        </ol>

        {nextStep ? (
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-slate-200 bg-white p-5">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[var(--color-primary)]">
                Siguiente paso
              </p>
              <p className="mt-1 text-xl font-semibold text-slate-900">{nextStep.title}</p>
              <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-600">{nextStep.detail}</p>
            </div>
            {canFollowNextStep ? (
              <Link href={nextStep.href} className="btn-primary shrink-0">
                {nextStep.cta}
              </Link>
            ) : (
              <p className="max-w-xs text-sm text-slate-500">
                Este paso lo realiza la administración del ECOE.
              </p>
            )}
          </div>
        ) : null}
      </SectionCard>

      <div className="grid-auto">
        <StatLink href="/students" label="Estudiantes" value={data.totals.students} hint="cargados y asignados" />
        <StatLink href="/stations" label="Estaciones" value={data.totals.stations} hint="incluye estaciones espejo" />
        <StatLink href="/results" label="Envíos" value={data.totals.evaluations} hint="evaluaciones registradas" />
      </div>

      <SectionCard title="Preparación del ECOE" subtitle="Chequeos del evento antes de pilotar, publicar y ejecutar.">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="clinical-panel">
            <p className="text-sm text-slate-500">Pilotaje</p>
            <p className={`mt-2 pill ${data.validation.can_pilot ? "pill-ok" : "pill-warn"}`}>
              {data.validation.can_pilot ? "Listo para pilotaje" : "Pendiente"}
            </p>
          </div>
          <div className="clinical-panel">
            <p className="text-sm text-slate-500">Publicación</p>
            <p className={`mt-2 pill ${data.validation.can_publish ? "pill-ok" : "pill-warn"}`}>
              {data.validation.can_publish ? "Publicable" : "Requiere ajustes"}
            </p>
          </div>
          <div className="clinical-panel">
            <p className="text-sm text-slate-500">Sesión en vivo</p>
            <p className="mt-2 text-2xl font-semibold">{sessionStatusLabel(data.live_panel.status)}</p>
            {sessionStarted ? (
              <p className="text-sm text-slate-600">
                Estación {data.live_panel.current_station_index} · quedan{" "}
                {formatClock(data.live_panel.remaining_seconds)}
              </p>
            ) : null}
          </div>
        </div>
        {data.validation.warnings.length ? (
          <div className="rounded-2xl border border-amber-200 bg-[var(--color-warning-soft)] p-4 text-sm text-amber-900">
            {data.validation.warnings.map((warning) => (
              <p key={warning}>{warning}</p>
            ))}
          </div>
        ) : null}
        <Link href="/validation" className="inline-block text-sm font-semibold text-[var(--color-primary)] hover:underline">
          Ver el detalle en Validación &rarr;
        </Link>
      </SectionCard>

      <SectionCard title="Estado de estaciones" subtitle="Estaciones del circuito activo y su avance.">
        <DataTable
          columns={[
            { key: "label", label: "Estación" },
            { key: "circuit", label: "Circuito" },
            {
              key: "status",
              label: "Estado",
              render: (row) => (
                <span className="status-badge status-badge-info">
                  {stationStatusLabel((row as { status?: string }).status)}
                </span>
              ),
            },
          ]}
          rows={data.timeline}
        />
      </SectionCard>
    </div>
  );
}
