"use client";

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { useConfirm } from "@/components/confirm-provider";
import { StatusNotice } from "@/components/forms";
import { SectionCard } from "@/components/section-card";

type IssuedLink = { url: string; expiresAt: string };

/**
 * Enlaces de kiosco de todo el circuito en una sola pantalla, para preparar
 * las tablets el día del examen. Usa el mismo endpoint que el botón por fila
 * de Estaciones: emitir un enlace invalida el anterior de esa estación y el
 * enlace sólo es visible mientras esta pantalla esté abierta.
 */
export default function KiosksPage() {
  const { authenticated, eventId } = useECOE();
  const confirm = useConfirm();
  const { data, loading, error } = useApi(
    () => api.stations(eventId) as Promise<Record<string, unknown>[]>,
    [eventId, authenticated],
  );
  const [links, setLinks] = useState<Record<number, IssuedLink>>({});
  const [failures, setFailures] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState<number | "all" | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const kioskStations = (data ?? []).filter(
    (station) => Boolean(station.requires_student_form) || Boolean(station.uses_multimedia),
  );
  const otherCount = (data ?? []).length - kioskStations.length;

  const issue = async (stationId: number): Promise<boolean> => {
    try {
      const result = await api.issueKioskToken(stationId);
      setLinks((current) => ({
        ...current,
        [stationId]: { url: `${window.location.origin}${result.kiosk_path}`, expiresAt: result.expires_at },
      }));
      setFailures((current) => {
        const next = { ...current };
        delete next[stationId];
        return next;
      });
      return true;
    } catch (err) {
      setFailures((current) => ({
        ...current,
        [stationId]: err instanceof Error ? err.message : "No se pudo generar el enlace",
      }));
      return false;
    }
  };

  const handleIssueOne = async (stationId: number) => {
    const ok = await confirm(
      "Se generará un nuevo enlace de kiosco para esta estación y se invalidará el anterior (si existía).",
      { title: "Generar enlace de kiosco", confirmLabel: "Generar enlace" },
    );
    if (!ok) return;
    setMessage(null);
    setBusy(stationId);
    await issue(stationId);
    setBusy(null);
  };

  const handleIssueAll = async () => {
    const ok = await confirm(
      `Se generará un enlace nuevo para las ${kioskStations.length} estaciones con kiosco y se invalidarán los anteriores: las tablets que ya estén abiertas tendrán que volver a cargarse con el enlace nuevo.`,
      { title: "Generar todos los enlaces", confirmLabel: "Generar todos" },
    );
    if (!ok) return;
    setMessage(null);
    setBusy("all");
    let issued = 0;
    for (const station of kioskStations) {
      if (await issue(Number(station.id))) issued += 1;
    }
    setBusy(null);
    setMessage(
      issued === kioskStations.length
        ? `Se generaron ${issued} enlaces. Cópialos antes de salir de esta pantalla.`
        : `Se generaron ${issued} de ${kioskStations.length} enlaces. Revisa las estaciones con error.`,
    );
  };

  const copy = (text: string, okMessage: string) => {
    navigator.clipboard.writeText(text).then(
      () => setMessage(okMessage),
      () => setMessage("No se pudo copiar; selecciona y copia el texto manualmente."),
    );
  };

  const issuedStations = kioskStations.filter((station) => links[Number(station.id)]);
  const allLinksText = issuedStations
    .map((station) => `Estación ${String(station.station_number ?? "?")} · ${String(station.name ?? "")}: ${links[Number(station.id)].url}`)
    .join("\n");

  return (
    <div className="space-y-6">
      <SectionCard
        title="Kioscos del circuito"
        subtitle="Cada estación con formulario de estudiante o multimedia usa una tablet en modo kiosco. Genera aquí sus enlaces y ábrelos en la tablet de cada estación."
      >
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn-primary disabled:opacity-50"
            disabled={busy !== null || kioskStations.length === 0}
            onClick={handleIssueAll}
          >
            {busy === "all" ? "Generando..." : "Generar todos los enlaces"}
          </button>
          <button
            type="button"
            className="btn-secondary disabled:opacity-50"
            disabled={issuedStations.length === 0}
            onClick={() => copy(allLinksText, "Enlaces copiados al portapapeles.")}
          >
            Copiar todos
          </button>
        </div>
        <p className="text-sm text-slate-500">
          Los enlaces se muestran una sola vez: si sales de esta pantalla hay que generarlos de nuevo.
        </p>
        <StatusNotice message={message} />
      </SectionCard>

      {loading ? (
        <div className="h-40 animate-pulse rounded-3xl bg-slate-100" />
      ) : error ? (
        <SectionCard title="No se pudieron cargar las estaciones">
          <p className="text-sm text-red-600">{error}</p>
        </SectionCard>
      ) : kioskStations.length === 0 ? (
        <SectionCard
          title="Ninguna estación necesita kiosco"
          subtitle="Sólo las estaciones con formulario de estudiante o multimedia usan una tablet en modo kiosco."
        >
          <Link href="/stations" className="btn-secondary">
            Ir a Estaciones
          </Link>
        </SectionCard>
      ) : (
        <div className="space-y-3">
          {kioskStations.map((station) => {
            const id = Number(station.id);
            const link = links[id];
            return (
              <div key={id} className="rounded-2xl border border-slate-200 bg-white p-4" data-testid={`kiosk-station-${id}`}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-600">
                      {String(station.station_number ?? "?")}
                    </span>
                    <p className="truncate text-sm font-semibold text-slate-900">{String(station.name ?? "Sin nombre")}</p>
                    <span className="text-xs text-slate-500">· {String(station.circuit_name ?? "")}</span>
                  </div>
                  <button
                    type="button"
                    className="btn-secondary px-4 py-1.5 text-xs disabled:opacity-50"
                    disabled={busy !== null}
                    onClick={() => handleIssueOne(id)}
                  >
                    {busy === id ? "Generando..." : link ? "Generar de nuevo" : "Generar enlace"}
                  </button>
                </div>
                {failures[id] ? (
                  <p role="alert" className="mt-3 text-sm text-red-600">{failures[id]}</p>
                ) : null}
                {link ? (
                  <div className="mt-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-3">
                    <p className="break-all rounded-xl bg-white px-3 py-2 font-mono text-xs text-slate-800">{link.url}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        className="btn-primary px-4 py-1.5 text-xs"
                        onClick={() => copy(link.url, `Enlace de la estación ${String(station.station_number ?? "")} copiado.`)}
                      >
                        Copiar enlace
                      </button>
                      <span className="text-xs text-emerald-800">
                        Expira: {new Date(link.expiresAt).toLocaleString()}
                      </span>
                    </div>
                  </div>
                ) : null}
              </div>
            );
          })}
          {otherCount > 0 ? (
            <p className="text-sm text-slate-500">
              {otherCount === 1
                ? "1 estación no necesita kiosco (sin formulario de estudiante ni multimedia)."
                : `${otherCount} estaciones no necesitan kiosco (sin formulario de estudiante ni multimedia).`}
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
