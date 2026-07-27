"use client";

import Link from "next/link";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";

type ValidationCheck = {
  label?: string;
  ok?: boolean;
  detail?: string;
};

type StationIssue = {
  station_id?: number;
  station_number?: number;
  station_name?: string;
  circuit_name?: string;
  ready_for_pilot?: boolean;
  blockers?: string[];
  warnings?: string[];
};

function CheckList({
  title,
  checks,
}: {
  title: string;
  checks: ValidationCheck[];
}) {
  return (
    <div className="clinical-panel">
      <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{title}</p>
      <div className="mt-4 space-y-3">
        {checks.map((check) => (
          <div
            key={`${check.label}-${check.detail}`}
            className="rounded-2xl border border-slate-200 bg-white px-4 py-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-sm font-semibold text-slate-900">{check.label}</p>
              <span
                className={`status-badge ${
                  check.ok ? "status-badge-success" : "status-badge-warning"
                }`}
              >
                {check.ok ? "Cumple" : "Pendiente"}
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-600">{check.detail}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ValidationPage() {
  const { authenticated, eventId } = useECOE();
  const { data, loading, error } = useApi(
    () => api.validation(eventId) as Promise<Record<string, unknown>>,
    [eventId, authenticated],
  );

  const pilotChecks = ((data?.pilot_checks as ValidationCheck[] | undefined) ?? []);
  const publicationChecks = ((data?.publication_checks as ValidationCheck[] | undefined) ?? []);
  const liveChecks = ((data?.live_checks as ValidationCheck[] | undefined) ?? []);
  const stationIssues = ((data?.station_issues as StationIssue[] | undefined) ?? []);
  const warnings = ((data?.warnings as string[] | undefined) ?? []);
  const blockers = ((data?.blockers as string[] | undefined) ?? []);

  return (
    <div className="space-y-6">
      <SectionCard
        title="Validación previa"
        subtitle="Chequeos estructurados antes de pilotar, publicar o iniciar la ejecución real del ECOE."
      >
        <div className="mb-4 flex flex-wrap gap-3">
          <Link href="/stations" className="btn-secondary">
            Revisar estaciones
          </Link>
          <Link href="/evaluators" className="btn-secondary">
            Revisar evaluadores
          </Link>
          <Link href="/publication" className="btn-secondary">
            Ir a publicación
          </Link>
        </div>
        {loading ? <p>Validando configuración...</p> : null}
        {error ? <p>{error}</p> : null}
        {data ? (
          <div className="grid gap-4 md:grid-cols-3">
            <div className="clinical-panel">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Para pilotaje
              </p>
              <p
                className={`mt-3 status-badge ${
                  data.can_pilot ? "status-badge-success" : "status-badge-warning"
                }`}
              >
                {data.can_pilot ? "Cumple requisitos" : "Faltan requisitos"}
              </p>
            </div>
            <div className="clinical-panel">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Para publicación
              </p>
              <p
                className={`mt-3 status-badge ${
                  data.can_publish ? "status-badge-success" : "status-badge-warning"
                }`}
              >
                {data.can_publish ? "Cumple requisitos" : "Pendiente"}
              </p>
            </div>
            <div className="clinical-panel">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                Para ejecución real
              </p>
              <p
                className={`mt-3 status-badge ${
                  data.can_start_live ? "status-badge-success" : "status-badge-warning"
                }`}
              >
                {data.can_start_live ? "Disponible" : "No disponible"}
              </p>
            </div>
          </div>
        ) : null}
      </SectionCard>

      {blockers.length ? (
        <SectionCard
          title="Bloqueos detectados"
          subtitle="Estos puntos impiden avanzar con seguridad hacia pilotaje, publicación o ejecución real."
        >
          <div className="space-y-3">
            {blockers.map((blocker) => (
              <div
                key={blocker}
                className="rounded-2xl border border-red-200 bg-[var(--color-error-soft)] px-4 py-3 text-sm text-red-900"
              >
                {blocker}
              </div>
            ))}
          </div>
        </SectionCard>
      ) : null}

      {warnings.length ? (
        <SectionCard
          title="Advertencias"
          subtitle="No siempre bloquean el avance, pero conviene resolverlas para operar con menos riesgo."
        >
          <div className="space-y-3">
            {warnings.map((warning) => (
              <div
                key={warning}
                className="rounded-2xl border border-amber-200 bg-[var(--color-warning-soft)] px-4 py-3 text-sm text-amber-900"
              >
                {warning}
              </div>
            ))}
          </div>
        </SectionCard>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-3">
        <CheckList title="Checklist de pilotaje" checks={pilotChecks} />
        <CheckList title="Checklist de publicación" checks={publicationChecks} />
        <CheckList title="Checklist de ejecución real" checks={liveChecks} />
      </div>

      <SectionCard
        title="Revisión por estación"
        subtitle="Aquí puedes ver exactamente qué estación ya está lista y cuál sigue con faltantes operativos."
      >
        <div className="space-y-4">
          {stationIssues.map((issue) => (
            <div
              key={String(issue.station_id)}
              className="rounded-[24px] border border-slate-200 bg-white p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-lg font-semibold text-slate-900">
                    Estación {String(issue.station_number)} · {String(issue.station_name)}
                  </p>
                  <p className="text-sm text-slate-600">
                    {String(issue.circuit_name ?? "Sin circuito definido")}
                  </p>
                </div>
                <span
                  className={`status-badge ${
                    issue.ready_for_pilot ? "status-badge-success" : "status-badge-warning"
                  }`}
                >
                  {issue.ready_for_pilot ? "Lista para pilotaje" : "Con faltantes"}
                </span>
              </div>
              <div className="mt-3 flex flex-wrap gap-3">
                <Link
                  href={`/stations/builder?stationId=${String(issue.station_id ?? "")}`}
                  className="text-sm font-semibold text-[var(--color-primary)] underline-offset-4 hover:underline"
                >
                  Abrir estación
                </Link>
                <Link
                  href="/evaluators"
                  className="text-sm font-semibold text-slate-700 underline-offset-4 hover:underline"
                >
                  Revisar asignaciones
                </Link>
              </div>

              {issue.blockers?.length ? (
                <div className="mt-4 space-y-2">
                  {issue.blockers.map((blocker) => (
                    <div
                      key={blocker}
                      className="rounded-2xl border border-red-200 bg-[var(--color-error-soft)] px-4 py-3 text-sm text-red-900"
                    >
                      {blocker}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-4 rounded-2xl border border-green-200 bg-[var(--color-success-soft)] px-4 py-3 text-sm text-green-900">
                  Esta estación cumple el mínimo estructural para pilotaje y publicación.
                </div>
              )}

              {issue.warnings?.length ? (
                <div className="mt-3 space-y-2">
                  {issue.warnings.map((warning) => (
                    <div
                      key={warning}
                      className="rounded-2xl border border-amber-200 bg-[var(--color-warning-soft)] px-4 py-3 text-sm text-amber-900"
                    >
                      {warning}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}
