"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";
import { StatusNotice } from "@/components/forms";

const STATUS_COLORS: Record<string, string> = {
  en_diseno: "bg-slate-100 text-slate-700",
  activa: "bg-emerald-100 text-emerald-700",
  publicada: "bg-blue-100 text-blue-700",
  finalizada: "bg-amber-100 text-amber-700",
  cerrada: "bg-gray-200 text-gray-600",
};

function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] ?? "bg-slate-100 text-slate-700";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${color}`}>
      {status.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
    </span>
  );
}

export default function StationsPage() {
  const { authenticated, eventId, user } = useECOE();
  const router = useRouter();
  const { data, loading, error, setData } = useApi(
    () => api.stations(eventId) as Promise<Record<string, unknown>[]>,
    [eventId, authenticated],
  );
  const [message, setMessage] = useState<string | null>(null);
  const [kioskLink, setKioskLink] = useState<{ stationId: number; url: string; expiresAt: string } | null>(null);
  const [issuingKioskFor, setIssuingKioskFor] = useState<number | null>(null);

  const handleIssueKiosk = async (stationId: number) => {
    if (!window.confirm(
      "Se generará un nuevo enlace de kiosco para esta estación y se invalidará el anterior (si existía). ¿Continuar?",
    )) return;
    setMessage(null);
    setIssuingKioskFor(stationId);
    try {
      const result = await api.issueKioskToken(stationId);
      setKioskLink({
        stationId,
        url: `${window.location.origin}${result.kiosk_path}`,
        expiresAt: result.expires_at,
      });
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo generar el enlace de kiosco");
    } finally {
      setIssuingKioskFor(null);
    }
  };

  const handleDelete = async (stationId: number) => {
    if (!window.confirm("Vas a eliminar esta estación permanentemente. Esta acción no se puede deshacer. ¿Continuar?")) return;
    setMessage(null);
    try {
      await api.deleteStation(stationId);
      setData((prev) => (prev ?? []).filter((s) => Number(s.id) !== stationId));
      setMessage("Estación borrada correctamente.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo eliminar la estación");
    }
  };

  useEffect(() => {
    if (user?.role === "evaluador") {
      router.replace("/evaluator");
    }
  }, [router, user?.role]);

  if (user?.role === "evaluador") {
    return (
      <SectionCard
        title="Acceso restringido"
        subtitle="El perfil evaluador no puede entrar a la gestión de estaciones."
      >
        <p>Te estamos redirigiendo a tu interfaz operativa.</p>
      </SectionCard>
    );
  }

  const stations = data ?? [];

  return (
    <div className="space-y-6">
      <SectionCard
        title="Gestión de estaciones"
        subtitle={`${stations.length} estaciones configuradas en el ECOE activo.`}
      >
        <div className="flex flex-wrap gap-3">
          <Link href="/stations/builder" className="btn-primary">
            + Nueva estación
          </Link>
          <Link href="/station-bank" className="btn-secondary">
            Banco de estaciones
          </Link>
        </div>
        <StatusNotice message={message} className="mt-4" />
      </SectionCard>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-2xl bg-slate-100" />
          ))}
        </div>
      ) : error ? (
        <SectionCard title="Error"><p className="text-red-600">{error}</p></SectionCard>
      ) : stations.length === 0 ? (
        <SectionCard title="Sin estaciones" subtitle="Aún no has creado ninguna estación para este ECOE.">
          <Link href="/stations/builder" className="btn-primary">
            Crear primera estación
          </Link>
        </SectionCard>
      ) : (
        <div className="space-y-3">
          {stations.map((station) => {
            const id = Number(station.id);
            const needsKiosk = Boolean(station.requires_student_form) || Boolean(station.uses_multimedia);
            return (
              <div
                key={id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-slate-300"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-600">
                      {String(station.station_number ?? "?")}
                    </span>
                    <p className="truncate text-sm font-semibold text-slate-900">{String(station.name ?? "Sin nombre")}</p>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                    <span>{String(station.station_type ?? "")}</span>
                    <span>·</span>
                    <span>{String(station.circuit_name ?? "")}</span>
                    <span>·</span>
                    <span>{String(station.station_time_minutes ?? 0)} min</span>
                    <span>·</span>
                    <span>Máx {String(station.max_score ?? 0)} pts</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <StatusBadge status={String(station.status ?? "en_diseno")} />
                  {needsKiosk ? (
                    <span
                      className="inline-flex items-center rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-semibold text-purple-700"
                      title="Tiene formulario de estudiante y/o multimedia: necesita una tablet en Modo kiosco"
                    >
                      Requiere kiosco
                    </span>
                  ) : null}
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-xl border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-slate-400 disabled:cursor-not-allowed disabled:opacity-40"
                    disabled={issuingKioskFor === id || !needsKiosk}
                    title={
                      needsKiosk
                        ? undefined
                        : "Esta estación no tiene formulario de estudiante ni multimedia: no necesita tablet en kiosco"
                    }
                    onClick={() => handleIssueKiosk(id)}
                  >
                    {issuingKioskFor === id ? "Generando..." : "Modo kiosco"}
                  </button>
                  <Link
                    href={`/stations/builder?stationId=${id}`}
                    className="inline-flex items-center gap-1 rounded-xl border border-[var(--color-primary)] px-3 py-1.5 text-xs font-semibold text-[var(--color-primary)] transition hover:bg-[var(--color-primary)] hover:text-white"
                  >
                    Editar
                  </Link>
                  <button
                    type="button"
                    className="inline-flex items-center gap-1 rounded-xl border border-red-300 px-3 py-1.5 text-xs font-semibold text-red-600 transition hover:bg-red-50"
                    onClick={() => handleDelete(id)}
                  >
                    Eliminar
                  </button>
                </div>
                {kioskLink?.stationId === id ? (
                  <div className="w-full rounded-2xl border border-emerald-200 bg-emerald-50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-800">
                      Enlace de kiosco — se muestra una sola vez
                    </p>
                    <p className="mt-2 break-all rounded-xl bg-white px-3 py-2 font-mono text-xs text-slate-800">
                      {kioskLink.url}
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        className="btn-primary px-4 py-1.5 text-xs"
                        onClick={() => {
                          navigator.clipboard.writeText(kioskLink.url).then(
                            () => setMessage("Enlace copiado al portapapeles."),
                            () => setMessage("No se pudo copiar; selecciona y copia el enlace manualmente."),
                          );
                        }}
                      >
                        Copiar enlace
                      </button>
                      <button
                        type="button"
                        className="text-xs font-semibold text-slate-600 underline-offset-4 hover:underline"
                        onClick={() => setKioskLink(null)}
                      >
                        Ocultar
                      </button>
                      <span className="text-xs text-emerald-800">
                        Ábrelo en la tablet de la estación. Expira: {new Date(kioskLink.expiresAt).toLocaleString()}
                      </span>
                    </div>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
