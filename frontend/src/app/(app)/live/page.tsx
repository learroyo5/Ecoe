"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { useLiveTimer } from "@/lib/ws";
import { SectionCard } from "@/components/section-card";
import { StatusNotice } from "@/components/forms";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { EvaluatorDraftsPanel } from "@/components/evaluator-drafts-panel";
import type { Incident } from "@/lib/types";

type TimerState = {
  status: string;
  remaining_seconds: number;
  current_station_index: number;
  station_time_seconds: number;
  transition_time_seconds: number;
};

const SEVERITY_OPTIONS = [
  { value: "baja", label: "Baja" },
  { value: "media", label: "Media" },
  { value: "alta", label: "Alta" },
  { value: "critica", label: "Crítica" },
] as const;

const SEVERITY_COLORS: Record<string, string> = {
  baja: "bg-blue-100 text-blue-700",
  media: "bg-amber-100 text-amber-700",
  alta: "bg-orange-100 text-orange-700",
  critica: "bg-red-100 text-red-700",
};

function ProjectorEscape({ onExit }: { onExit: () => void }) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onExit();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onExit]);
  return null;
}

export default function LivePage() {
  const { authenticated, eventId, user, eventRoles } = useECOE();
  // El panel de contingencia solo lo opera coordinación (mismo gate que
  // /contingency/evaluator-record); un cronometrador no lo ve.
  const canRunContingency =
    user?.role === "admin_global" ||
    eventRoles.includes("admin_ecoe") ||
    eventRoles.includes("coordinador_operativo");
  const [timerState, setTimerState] = useState<TimerState>({
    status: "sin_sesion",
    remaining_seconds: 0,
    current_station_index: 0,
    station_time_seconds: 480,
    transition_time_seconds: 120,
  });

  const [controlMessage, setControlMessage] = useState<string | null>(null);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showStartConfirm, setShowStartConfirm] = useState(false);
  const [showExpireConfirm, setShowExpireConfirm] = useState(false);
  const [projectorMode, setProjectorMode] = useState(false);

  // Incident form state
  const [showIncidentForm, setShowIncidentForm] = useState(false);
  const [incidentTitle, setIncidentTitle] = useState("");
  const [incidentDetail, setIncidentDetail] = useState("");
  const [incidentSeverity, setIncidentSeverity] = useState("media");
  const [incidentStationId, setIncidentStationId] = useState("");
  const [incidentSubmitting, setIncidentSubmitting] = useState(false);
  const [incidentMessage, setIncidentMessage] = useState<string | null>(null);

  // Momento local en que recibimos el último estado del servidor: el
  // countdown se deriva de (remaining_seconds del servidor - transcurrido
  // local), nunca de un contador local ciego.
  const [receivedAt, setReceivedAt] = useState<number>(0);
  const [displaySeconds, setDisplaySeconds] = useState(0);

  const liveQuery = useApi(
    () => api.live(eventId),
    [eventId, authenticated],
  );

  const incidentsQuery = useApi(
    () => api.incidents(eventId),
    [eventId, authenticated],
  );

  const [incidents, setIncidents] = useState<Incident[]>([]);

  // Keep local incidents in sync with query
  useEffect(() => {
    setIncidents(incidentsQuery.data?.items ?? []);
  }, [incidentsQuery.data]);

  // Sync initial timer state from REST
  useEffect(() => {
    const data = liveQuery.data;
    if (!data) return;
    setTimerState((prev) => ({
      ...prev,
      status: String(data.status ?? "sin_sesion"),
      remaining_seconds: Number(data.remaining_seconds ?? 0),
      current_station_index: Number(data.current_station_index ?? 0),
      station_time_seconds: Number(data.station_time_seconds ?? prev.station_time_seconds),
      transition_time_seconds: Number(data.transition_time_seconds ?? prev.transition_time_seconds),
    }));
    setReceivedAt(Date.now());
  }, [liveQuery.data]);

  // Tick del display: proyecta el remaining del servidor con el tiempo local
  // transcurrido desde que lo recibimos.
  useEffect(() => {
    const compute = () => {
      const running = timerState.status === "running" || timerState.status === "transition";
      const elapsed = running && receivedAt ? (Date.now() - receivedAt) / 1000 : 0;
      setDisplaySeconds(Math.max(0, Math.round(timerState.remaining_seconds - elapsed)));
    };
    compute();
    const intervalId = setInterval(compute, 250);
    return () => clearInterval(intervalId);
  }, [timerState, receivedAt]);

  // WebSocket en tiempo real con reconexión automática (hook compartido
  // useLiveTimer): el timer_update alimenta timerState y receivedAt, los
  // frames de incidencias van por onMessage, y al (re)conectar se resincroniza
  // el estado vía REST por si cambió mientras estuvimos desconectados.
  const handleLiveMessage = useCallback((data: Record<string, unknown>) => {
    if (data.type === "incident_created") {
      const incident = data.incident as Incident;
      setIncidents((prev) => [
        { ...incident, ecoe_event_id: Number(data.ecoe_event_id) } as Incident,
        ...prev,
      ]);
    } else if (data.type === "incident_resolved") {
      setIncidents((prev) =>
        prev.map((inc) =>
          inc.id === data.incident_id ? { ...inc, resolved: Boolean(data.resolved) } : inc,
        ),
      );
    }
  }, []);

  const resyncFromRest = useCallback(() => {
    api.live(eventId).then((data) => {
      setTimerState((prev) => ({
        ...prev,
        status: String(data.status ?? prev.status),
        remaining_seconds: Number(data.remaining_seconds ?? prev.remaining_seconds),
        current_station_index: Number(data.current_station_index ?? prev.current_station_index),
        station_time_seconds: Number(data.station_time_seconds ?? prev.station_time_seconds),
        transition_time_seconds: Number(data.transition_time_seconds ?? prev.transition_time_seconds),
      }));
      setReceivedAt(Date.now());
    }).catch(() => { /* el WS seguirá empujando updates */ });
  }, [eventId]);

  const { snapshot: liveSnapshot, connected: wsConnected } = useLiveTimer(eventId, {
    onMessage: handleLiveMessage,
    onReconnect: resyncFromRest,
  });

  useEffect(() => {
    if (!liveSnapshot) return;
    setTimerState({
      status: liveSnapshot.status,
      remaining_seconds: liveSnapshot.remainingSeconds,
      current_station_index: liveSnapshot.currentStationIndex,
      station_time_seconds: liveSnapshot.stationTimeSeconds,
      transition_time_seconds: liveSnapshot.transitionTimeSeconds,
    });
    setReceivedAt(liveSnapshot.receivedAt);
  }, [liveSnapshot]);

  const sendAction = useCallback(async (action: string) => {
    setControlMessage(null);
    try {
      await api.liveControl({ ecoe_event_id: eventId, action });
    } catch (err) {
      setControlMessage(
        err instanceof Error ? err.message : "No se pudo enviar la acción al cronómetro.",
      );
    }
  }, [eventId]);

  const handleCreateIncident = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!incidentTitle.trim()) return;
    setIncidentSubmitting(true);
    setIncidentMessage(null);
    try {
      await api.createIncident({
        ecoe_event_id: eventId,
        station_id: incidentStationId ? Number(incidentStationId) : null,
        title: incidentTitle.trim(),
        detail: incidentDetail.trim(),
        severity: incidentSeverity,
      });
      setIncidentTitle("");
      setIncidentDetail("");
      setIncidentSeverity("media");
      setIncidentStationId("");
      setShowIncidentForm(false);
      setIncidentMessage("Incidencia registrada correctamente.");
    } catch (err) {
      setIncidentMessage(err instanceof Error ? err.message : "Error al registrar incidencia.");
    } finally {
      setIncidentSubmitting(false);
    }
  };

  const handleResolveIncident = async (incidentId: number, resolved: boolean) => {
    try {
      await api.resolveIncident(incidentId, resolved);
      // State updated via WebSocket, but also update locally
      setIncidents((prev) =>
        prev.map((inc) => (inc.id === incidentId ? { ...inc, resolved } : inc)),
      );
    } catch {
      // Ignore — WebSocket will correct state
    }
  };

  const formatTime = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // OPT-9 / H-vivo-8: "Iniciar" resetea el reloj a tiempo completo para todos
  // los paneles. Si la rotación ya está en curso (o pausada / en transición, o
  // más allá de la estación 1) un click accidental es destructivo → pedir
  // confirmación como en "Reiniciar". El primer arranque no tiene fricción.
  const timerAlreadyRunning =
    ["running", "paused", "transition"].includes(timerState.status) ||
    timerState.current_station_index > 1;

  const handleStartClick = () => {
    if (timerAlreadyRunning) {
      setShowStartConfirm(true);
    } else {
      sendAction("start");
    }
  };

  const activeIncidents = incidents.filter((i) => !i.resolved);
  const resolvedIncidents = incidents.filter((i) => i.resolved);

  if (projectorMode) {
    return (
      <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950 text-white">
        <div className="absolute right-6 top-6 flex items-center gap-3">
          <span
            className={`inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-semibold ${
              wsConnected ? "bg-emerald-600" : "bg-red-600"
            }`}
          >
            <span className={`h-2.5 w-2.5 rounded-full bg-white ${wsConnected ? "" : "animate-ping"}`} />
            {wsConnected ? "En línea" : "Reconectando"}
          </span>
          <button
            className="rounded-full border border-white/30 px-4 py-1.5 text-sm font-semibold text-white/80 transition hover:bg-white/10"
            onClick={() => setProjectorMode(false)}
          >
            Salir (Esc)
          </button>
        </div>
        <p className="text-[3vw] font-semibold uppercase tracking-[0.3em] text-white/60">
          {timerState.status === "transition" ? "Transición" : `Estación ${timerState.current_station_index}`}
        </p>
        <p
          className={`font-bold tabular-nums leading-none ${
            displaySeconds <= 60 && (timerState.status === "running" || timerState.status === "transition")
              ? "animate-pulse text-red-500"
              : "text-white"
          }`}
          style={{ fontSize: "24vw" }}
        >
          {formatTime(displaySeconds)}
        </p>
        <p className="mt-4 text-[2.5vw] font-semibold uppercase tracking-[0.2em] text-white/70">
          {timerState.status === "running" ? "▶ En curso" :
           timerState.status === "paused" ? "⏸ Pausado" :
           timerState.status === "transition" ? "↻ Cambio de estación" :
           timerState.status === "ready" ? "Listo para iniciar" : timerState.status}
        </p>
        <ProjectorEscape onExit={() => setProjectorMode(false)} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Timer panel */}
      <SectionCard title="Panel central en vivo" subtitle="Cronómetro central con sincronización en tiempo real vía WebSocket.">
        <div className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[2rem] bg-[linear-gradient(135deg,var(--color-primary-dark),var(--color-primary))] p-6 text-white shadow-[0_18px_40px_rgba(27,73,101,0.24)]">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm uppercase tracking-[0.18em] text-slate-100/80">Cronómetro central</p>
              <div className="flex items-center gap-2">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${
                    wsConnected ? "bg-emerald-500/90" : "bg-red-500/90"
                  }`}
                  title={wsConnected ? "Sincronización en tiempo real activa" : "Reconectando..."}
                >
                  <span className={`h-2 w-2 rounded-full bg-white ${wsConnected ? "" : "animate-ping"}`} />
                  {wsConnected ? "Conectado" : "Reconectando"}
                </span>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                  timerState.status === "running" ? "bg-green-500" :
                  timerState.status === "paused" ? "bg-yellow-500" :
                  timerState.status === "transition" ? "bg-orange-500" : "bg-slate-500"
                }`}>
                  {timerState.status === "running" ? "▶ EN VIVO" :
                   timerState.status === "paused" ? "⏸ PAUSADO" :
                   timerState.status === "transition" ? "↻ TRANSICIÓN" :
                   timerState.status.toUpperCase()}
                </span>
              </div>
            </div>
            <p className="mt-4 text-7xl font-bold tabular-nums tracking-tight">
              {formatTime(displaySeconds)}
            </p>
            <p className="mt-3 text-lg text-slate-100/80">
              Estación {timerState.current_station_index} ·{" "}
              {timerState.status === "transition" ? "Transición" : "Estación"}:{" "}
              {timerState.status === "transition"
                ? formatTime(timerState.transition_time_seconds)
                : formatTime(timerState.station_time_seconds)}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              {(["start", "pause", "resume", "reset", "next_transition"] as const).map((action) => (
                <button
                  key={action}
                  className={action === "start" ? "btn-primary" : "btn-secondary"}
                  onClick={() =>
                    action === "reset"
                      ? setShowResetConfirm(true)
                      : action === "start"
                        ? handleStartClick()
                        : sendAction(action)
                  }
                >
                  {action === "start" ? "Iniciar" :
                   action === "pause" ? "Pausar" :
                   action === "resume" ? "Reanudar" :
                   action === "reset" ? "Reiniciar" :
                   "Sig. estación"}
                </button>
              ))}
              <button
                className="rounded-full border border-white/40 px-4 py-2 text-sm font-semibold text-white transition hover:bg-white/10"
                onClick={() => setProjectorMode(true)}
              >
                🖥 Vista proyector
              </button>
            </div>
            {/* OPT-20 F2: el buzzer — cierra la ventana de envío de la estación
                en curso sin avanzar de estación. El servidor recoge los
                formularios pendientes (autoenvío). */}
            <button
              className="mt-3 inline-flex items-center gap-2 rounded-full border border-amber-300 bg-amber-500/90 px-4 py-2 text-sm font-semibold text-white transition hover:bg-amber-500"
              onClick={() => setShowExpireConfirm(true)}
            >
              ⏹ Finalizar la estación en curso ahora
            </button>
          </div>
          <div className="clinical-panel">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
              Supervisión operativa
            </p>
            <ul className="mt-4 space-y-3 text-sm text-slate-700">
              <li>✓ Sincronización en tiempo real por WebSocket.</li>
              <li>✓ Control de pausa, reanudación y reinicio controlado.</li>
              <li>✓ Transición entre estaciones.</li>
              <li>✓ Registro y resolución de incidencias en vivo.</li>
            </ul>
          </div>
        </div>
        <StatusNotice message={controlMessage} className="mt-4" />
        <ConfirmDialog
          open={showResetConfirm}
          title="Reiniciar cronómetro"
          message="El cronómetro volverá a la estación 1 con el tiempo completo. Esto afecta a todos los paneles conectados. ¿Continuar?"
          confirmLabel="Reiniciar"
          severity="danger"
          onConfirm={() => {
            setShowResetConfirm(false);
            sendAction("reset");
          }}
          onCancel={() => setShowResetConfirm(false)}
        />
        <ConfirmDialog
          open={showStartConfirm}
          title="Reiniciar el cronómetro con Iniciar"
          message="El cronómetro ya está en marcha. Iniciar lo vuelve a poner en el tiempo completo de la estación actual para todos los paneles conectados. Si querés reanudar tras una pausa, usá Reanudar. ¿Continuar?"
          confirmLabel="Iniciar de nuevo"
          severity="danger"
          onConfirm={() => {
            setShowStartConfirm(false);
            sendAction("start");
          }}
          onCancel={() => setShowStartConfirm(false)}
        />
        <ConfirmDialog
          open={showExpireConfirm}
          title="Finalizar la estación en curso ahora"
          message="Se cierra la ventana de envío de la estación actual y el servidor recoge automáticamente los formularios de estudiante que quedaron sin enviar. El cronómetro NO avanza a la siguiente estación. ¿Continuar?"
          confirmLabel="Finalizar estación"
          severity="danger"
          onConfirm={() => {
            setShowExpireConfirm(false);
            sendAction("expire_phase");
          }}
          onCancel={() => setShowExpireConfirm(false)}
        />
      </SectionCard>

      {/* Incidents panel */}
      <SectionCard
        title="Incidencias"
        subtitle={`${activeIncidents.length} activas · ${resolvedIncidents.length} resueltas`}
      >
        {/* Quick-add form */}
        {showIncidentForm ? (
          <form onSubmit={handleCreateIncident} className="mb-4 rounded-2xl border border-amber-200 bg-amber-50/60 p-4 space-y-3">
            <div className="grid gap-3 md:grid-cols-[1fr_auto]">
              <input
                placeholder="Título de la incidencia"
                value={incidentTitle}
                onChange={(e) => setIncidentTitle(e.target.value)}
                required
                autoFocus
              />
              <select value={incidentSeverity} onChange={(e) => setIncidentSeverity(e.target.value)}>
                {SEVERITY_OPTIONS.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
            <div className="grid gap-3 md:grid-cols-[1fr_auto]">
              <input
                placeholder="Detalle (opcional)"
                value={incidentDetail}
                onChange={(e) => setIncidentDetail(e.target.value)}
              />
              <input
                type="number"
                placeholder="N° estación (opcional)"
                value={incidentStationId}
                onChange={(e) => setIncidentStationId(e.target.value)}
                className="w-36"
              />
            </div>
            <div className="flex gap-2">
              <button type="submit" className="btn-primary" disabled={incidentSubmitting || !incidentTitle.trim()}>
                {incidentSubmitting ? "Registrando..." : "Registrar incidencia"}
              </button>
              <button type="button" className="btn-secondary" onClick={() => setShowIncidentForm(false)}>
                Cancelar
              </button>
            </div>
            {incidentMessage ? (
              <p className={`text-sm ${incidentMessage.startsWith("Error") ? "text-red-600" : "text-emerald-600"}`}>
                {incidentMessage}
              </p>
            ) : null}
          </form>
        ) : (
          <button className="btn-secondary mb-4" onClick={() => setShowIncidentForm(true)}>
            + Registrar incidencia
          </button>
        )}

        {activeIncidents.length === 0 && resolvedIncidents.length === 0 ? (
          <p className="text-sm text-slate-500">No hay incidencias registradas.</p>
        ) : (
          <div className="space-y-3">
            {/* Active incidents first */}
            {activeIncidents.map((inc) => (
              <IncidentCard key={inc.id} incident={inc} onResolve={handleResolveIncident} />
            ))}
            {/* Resolved incidents */}
            {resolvedIncidents.map((inc) => (
              <IncidentCard key={inc.id} incident={inc} onResolve={handleResolveIncident} />
            ))}
          </div>
        )}
      </SectionCard>

      {/* OPT-20 F3: contingencia de coordinación — finalizar borradores de evaluador */}
      {canRunContingency ? <EvaluatorDraftsPanel eventId={eventId} /> : null}
    </div>
  );
}

function IncidentCard({
  incident,
  onResolve,
}: {
  incident: Incident;
  onResolve: (id: number, resolved: boolean) => void;
}) {
  const severityColor = SEVERITY_COLORS[incident.severity] ?? "bg-slate-100 text-slate-700";

  return (
    <div className={`rounded-2xl border p-4 transition ${
      incident.resolved
        ? "border-slate-100 bg-slate-50/70 opacity-60"
        : incident.severity === "critica" || incident.severity === "alta"
          ? "border-red-200 bg-red-50/50"
          : "border-slate-200 bg-white"
    }`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className={`font-semibold text-slate-900 ${incident.resolved ? "line-through" : ""}`}>
              {incident.title}
            </p>
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${severityColor}`}>
              {incident.severity}
            </span>
            {incident.station_id ? (
              <span className="text-xs text-slate-400">Estación {incident.station_id}</span>
            ) : null}
            {incident.resolved ? (
              <span className="text-xs text-slate-400">· Resuelta</span>
            ) : null}
          </div>
          {incident.detail ? (
            <p className="mt-1 text-sm text-slate-600">{incident.detail}</p>
          ) : null}
          <p className="mt-1 text-xs text-slate-400">
            {new Date(incident.created_at).toLocaleTimeString("es-CL", { hour: "2-digit", minute: "2-digit" })}
          </p>
        </div>
        {incident.resolved ? (
          <button
            className="text-xs font-medium text-slate-500 hover:text-slate-700 underline"
            onClick={() => onResolve(incident.id, false)}
          >
            Reabrir
          </button>
        ) : (
          <button
            className="inline-flex items-center gap-1 rounded-xl bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 transition"
            onClick={() => onResolve(incident.id, true)}
          >
            ✓ Resolver
          </button>
        )}
      </div>
    </div>
  );
}
