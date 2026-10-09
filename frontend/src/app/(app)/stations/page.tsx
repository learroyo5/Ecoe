"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { canAccessStationArea } from "@/lib/permissions";
import { stationStatusLabel, stationTypeLabel } from "@/lib/labels";
import { defaultRouteForRole } from "@/lib/routes";
import { useApi } from "@/hooks/use-api";
import { useConfirm } from "@/components/confirm-provider";
import { StructureLockNotice, useStructureLock } from "@/components/structure-lock-notice";
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
      {stationStatusLabel(status)}
    </span>
  );
}

export default function StationsPage() {
  const { authenticated, eventId, user, eventRoles, eventRolesLoaded } = useECOE();
  const router = useRouter();
  // Gating por rol EFECTIVO de evento, no por el rol global del JWT: una
  // cuenta cuyo rol global es "evaluador" puede ser admin/coeditor/coordinador
  // en este ECOE y el backend le deja leer las estaciones (OPT-3).
  const canAccess = canAccessStationArea(user?.role, eventRoles);
  const accessDenied = eventRolesLoaded && !canAccess;
  const { data, loading, error, setData } = useApi(
    () => api.stations(eventId) as Promise<Record<string, unknown>[]>,
    [eventId, authenticated],
  );
  const confirm = useConfirm();
  const { locked: structureLocked } = useStructureLock();
  const [message, setMessage] = useState<string | null>(null);
  // Circuitos espejo
  const [mirrorDialog, setMirrorDialog] = useState(false);
  const [mirrorSource, setMirrorSource] = useState("");
  const [mirrorName, setMirrorName] = useState("");
  const [mirrorBusy, setMirrorBusy] = useState(false);
  const { data: validationData, setData: setValidationData } = useApi(
    () => api.validation(eventId).catch(() => null),
    [eventId, authenticated],
  );
  const mirrorIssues = ((validationData as { mirror_issues?: string[] } | null)?.mirror_issues ?? []);

  const refreshAfterMirrorChange = async (updated?: Record<string, unknown>[]) => {
    setData(updated ?? ((await api.stations(eventId)) as Record<string, unknown>[]));
    setValidationData(await api.validation(eventId).catch(() => null));
  };

  const runMirror = async (source: string, target: string, okMessage: string) => {
    setMirrorBusy(true);
    setMessage(null);
    try {
      const updated = await api.mirrorCircuit(eventId, { source_circuit: source, mirror_circuit: target });
      await refreshAfterMirrorChange(updated as unknown as Record<string, unknown>[]);
      setMessage(okMessage);
      setMirrorDialog(false);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo crear el circuito espejo.");
    } finally {
      setMirrorBusy(false);
    }
  };

  const handleDeleteMirrorCircuit = async (circuit: string) => {
    if (!(await confirm(
      `Se eliminarán todas las estaciones de «${circuit}». El circuito original no cambia.`,
      { title: "Eliminar circuito espejo", confirmLabel: "Eliminar", severity: "danger" },
    ))) return;
    setMessage(null);
    try {
      await api.deleteMirrorCircuit(eventId, circuit);
      await refreshAfterMirrorChange();
      setMessage(`Circuito espejo «${circuit}» eliminado.`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "No se pudo eliminar el circuito espejo.");
    }
  };
  const [kioskLink, setKioskLink] = useState<{ stationId: number; url: string; expiresAt: string } | null>(null);
  const [issuingKioskFor, setIssuingKioskFor] = useState<number | null>(null);

  const handleIssueKiosk = async (stationId: number) => {
    if (!(await confirm(
      "Se generará un nuevo enlace de kiosco para esta estación y se invalidará el anterior (si existía).",
      { title: "Generar enlace de kiosco", confirmLabel: "Generar enlace" },
    ))) return;
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
    if (!(await confirm(
      "Vas a eliminar esta estación permanentemente. Esta acción no se puede deshacer.",
      { title: "Eliminar estación", confirmLabel: "Eliminar", severity: "danger" },
    ))) return;
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
    if (accessDenied) {
      router.replace(defaultRouteForRole(user?.role ?? ""));
    }
  }, [router, accessDenied, user?.role]);

  if (accessDenied) {
    return (
      <SectionCard
        title="Acceso restringido"
        subtitle="Tu rol en este ECOE no permite entrar a la gestión de estaciones."
      >
        <p>Te estamos redirigiendo a tu interfaz operativa.</p>
      </SectionCard>
    );
  }

  const stations = data ?? [];
  // Agrupación por circuito. Un circuito es "espejo" si sus estaciones apuntan
  // a una original; el original es donde se diseña.
  const stationsById = new Map(stations.map((station) => [Number(station.id), station]));
  const circuits: { name: string; isMirror: boolean; stations: Record<string, unknown>[] }[] = [];
  for (const station of [...stations].sort(
    (a, b) => Number(a.station_number ?? 0) - Number(b.station_number ?? 0),
  )) {
    const name = String(station.circuit_name ?? "");
    let group = circuits.find((item) => item.name === name);
    if (!group) {
      group = { name, isMirror: false, stations: [] };
      circuits.push(group);
    }
    group.stations.push(station);
    if (station.mirror_of_id) group.isMirror = true;
  }
  circuits.sort((a, b) => Number(a.isMirror) - Number(b.isMirror) || a.name.localeCompare(b.name));
  const originalCircuits = circuits.filter((circuit) => !circuit.isMirror);
  const hasMirrors = circuits.some((circuit) => circuit.isMirror);
  const sourceOf = (circuit: { stations: Record<string, unknown>[] }) =>
    String(stationsById.get(Number(circuit.stations[0]?.mirror_of_id))?.circuit_name ?? "");
  const suggestMirrorName = () => {
    const taken = new Set(circuits.map((circuit) => circuit.name.toLowerCase()));
    for (const letter of "BCDEFGH") {
      if (!taken.has(`circuito ${letter.toLowerCase()}`)) return `Circuito ${letter}`;
    }
    return "Circuito espejo";
  };

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
          {originalCircuits.length === 1 && stations.length > 0 ? (
            <button
              type="button"
              className="btn-secondary disabled:opacity-50"
              disabled={structureLocked}
              onClick={() => {
                setMirrorSource(originalCircuits[0].name);
                setMirrorName(suggestMirrorName());
                setMirrorDialog(true);
              }}
            >
              Crear circuito espejo
            </button>
          ) : null}
        </div>
        {stations.length > 0 && !hasMirrors ? (
          <p className="text-sm leading-6 text-slate-600">
            <strong>¿ECOE en espejo?</strong> Diseña las estaciones <strong>una sola vez</strong>, en un
            circuito. Cuando estén listas, usa «Crear circuito espejo»: la plataforma genera el
            segundo circuito (otro piso, otros evaluadores y tablets) con las mismas estaciones. No
            crees la estación 1 dos veces.
          </p>
        ) : null}
        {mirrorIssues.length > 0 ? (
          <div role="alert" className="rounded-2xl border border-red-200 bg-[var(--color-error-soft)] px-4 py-3 text-sm text-red-900">
            <p className="font-semibold">Los circuitos no son espejo exacto (bloquea pilotaje y publicación):</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5">
              {mirrorIssues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          </div>
        ) : null}
        <StatusNotice message={message} className="mt-4" />
        <StructureLockNotice what="El diseño de las estaciones" />
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
        <div className="space-y-6">
          {circuits.map((circuit) => (
          <div key={circuit.name} className="space-y-3" data-testid={`circuit-${circuit.name}`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h4 className="text-lg text-slate-900">
                {circuit.name || "Sin circuito"}
                <span className="ml-2 text-sm font-normal text-slate-500">
                  {circuit.isMirror
                    ? `espejo de ${sourceOf(circuit)} · ${circuit.stations.length} estaciones`
                    : `${circuit.stations.length} estaciones${hasMirrors ? " · circuito original" : ""}`}
                </span>
              </h4>
              {circuit.isMirror ? (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="btn-secondary px-4 py-1.5 text-xs disabled:opacity-50"
                    disabled={structureLocked || mirrorBusy}
                    onClick={() => runMirror(sourceOf(circuit), circuit.name, `«${circuit.name}» quedó igual a su original.`)}
                  >
                    Sincronizar espejo
                  </button>
                  <button
                    type="button"
                    className="rounded-xl border border-red-300 px-3 py-1.5 text-xs font-semibold text-red-600 transition hover:bg-red-50 disabled:opacity-50"
                    disabled={structureLocked}
                    onClick={() => handleDeleteMirrorCircuit(circuit.name)}
                  >
                    Eliminar circuito espejo
                  </button>
                </div>
              ) : null}
            </div>
          {circuit.stations.map((station) => {
            const id = Number(station.id);
            const original = station.mirror_of_id ? stationsById.get(Number(station.mirror_of_id)) : null;
            const needsKiosk = Boolean(station.requires_student_form) || Boolean(station.uses_multimedia);
            return (
              <div
                key={id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-slate-300"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-600">
                      {String((original ?? station).station_number ?? "?")}
                    </span>
                    <p className="truncate text-sm font-semibold text-slate-900">{String(station.name ?? "Sin nombre")}</p>
                    {original ? (
                      <span
                        className="inline-flex shrink-0 items-center rounded-full bg-sky-100 px-2.5 py-0.5 text-xs font-semibold text-sky-800"
                        title="Su diseño es el de la estación original; se edita allí y los cambios se copian solos."
                      >
                        Espejo
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                    <span>{stationTypeLabel(station.station_type)}</span>
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
                  {station.requires_deferred_grading ? (
                    <span
                      className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-700"
                      title="Las respuestas se puntúan después de la rotación en la pantalla Corrección"
                    >
                      Corrección diferida
                    </span>
                  ) : null}
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
                  {original ? (
                    <Link
                      href={`/stations/builder?stationId=${Number(original.id)}`}
                      className="inline-flex items-center gap-1 rounded-xl border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-slate-400"
                    >
                      Editar la original
                    </Link>
                  ) : (
                  <>
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
                  </>
                  )}
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
          ))}
        </div>
      )}

      {mirrorDialog ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="Crear circuito espejo"
          onClick={() => setMirrorDialog(false)}
        >
          <div className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}>
            <h3 className="text-xl font-semibold text-slate-900">Crear circuito espejo</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              Se creará un circuito con las mismas {originalCircuits[0]?.stations.length ?? 0} estaciones de «{mirrorSource}»:
              misma pauta, formulario, puntaje e instrucciones. Después asigna a cada estación espejo
              su evaluador y su tablet. Para cambiar el diseño, edita la estación original: el espejo
              se actualiza solo.
            </p>
            <label className="mt-4 block space-y-1 text-sm">
              <span className="font-semibold text-slate-700">Nombre del circuito espejo</span>
              <input value={mirrorName} onChange={(event) => setMirrorName(event.target.value)} placeholder="Circuito B" />
            </label>
            <div className="mt-6 flex justify-end gap-3">
              <button type="button" className="btn-secondary" onClick={() => setMirrorDialog(false)} disabled={mirrorBusy}>
                Cancelar
              </button>
              <button
                type="button"
                className="btn-primary disabled:opacity-50"
                disabled={mirrorBusy || !mirrorName.trim()}
                onClick={() => runMirror(mirrorSource, mirrorName.trim(), `Circuito espejo «${mirrorName.trim()}» creado. Asigna evaluadores y tablets a sus estaciones.`)}
              >
                {mirrorBusy ? "Creando..." : "Crear circuito espejo"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
