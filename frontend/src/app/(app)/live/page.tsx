"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { SectionCard } from "@/components/section-card";
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

export default function LivePage() {
  const { token, eventId } = useECOE();
  const wsRef = useRef<WebSocket | null>(null);
  const [timerState, setTimerState] = useState<TimerState>({
    status: "sin_sesion",
    remaining_seconds: 0,
    current_station_index: 0,
    station_time_seconds: 480,
    transition_time_seconds: 120,
  });

  // Incident form state
  const [showIncidentForm, setShowIncidentForm] = useState(false);
  const [incidentTitle, setIncidentTitle] = useState("");
  const [incidentDetail, setIncidentDetail] = useState("");
  const [incidentSeverity, setIncidentSeverity] = useState("media");
  const [incidentStationId, setIncidentStationId] = useState("");
  const [incidentSubmitting, setIncidentSubmitting] = useState(false);
  const [incidentMessage, setIncidentMessage] = useState<string | null>(null);

  const liveQuery = useApi(
    () => api.live(eventId, token!),
    [eventId, token],
  );

  const incidentsQuery = useApi(
    () => api.incidents(eventId, token!) as unknown as Promise<Record<string, unknown>>,
    [eventId, token],
  );
  const incidentsData = (incidentsQuery.data?.items as Incident[]) ?? [];

  const [incidents, setIncidents] = useState<Incident[]>([]);

  // Keep local incidents in sync with query
  useEffect(() => {
    setIncidents(incidentsData);
  }, [incidentsData]);

  // Sync initial timer state from REST
  useEffect(() => {
    const data = liveQuery.data;
    if (!data) return;
    setTimerState((prev) => ({
      ...prev,
      status: String(data.status ?? "sin_sesion"),
      remaining_seconds: Number(data.remaining_seconds ?? 0),
      current_station_index: Number(data.current_station_index ?? 0),
    }));
  }, [liveQuery.data]);

  // WebSocket connection for real-time timer + incidents
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsHost = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
      ? `${window.location.hostname}:8000`
      : window.location.host;
    const wsUrl = `${protocol}//${wsHost}/api/ws/live/${eventId}`;

    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;
    } catch {
      return;
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "timer_update") {
          setTimerState({
            status: data.status,
            remaining_seconds: data.remaining_seconds,
            current_station_index: data.current_station_index,
            station_time_seconds: data.station_time_seconds,
            transition_time_seconds: data.transition_time_seconds,
          });
        } else if (data.type === "incident_created") {
          setIncidents((prev) => [
            { ...data.incident, ecoe_event_id: data.ecoe_event_id } as Incident,
            ...prev,
          ]);
        } else if (data.type === "incident_resolved") {
          setIncidents((prev) =>
            prev.map((inc) =>
              inc.id === data.incident_id ? { ...inc, resolved: data.resolved } : inc,
            ),
          );
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onerror = () => { /* degrade gracefully */ };

    return () => {
      try { ws?.close(); } catch { /* ignore */ }
    };
  }, [eventId]);

  const sendAction = useCallback(async (action: string) => {
    await api.liveControl({ ecoe_event_id: eventId, action }, token!);
  }, [eventId, token]);

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
      }, token!);
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
      await api.resolveIncident(incidentId, resolved, token!);
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

  const activeIncidents = incidents.filter((i) => !i.resolved);
  const resolvedIncidents = incidents.filter((i) => i.resolved);

  return (
    <div className="space-y-6">
      {/* Timer panel */}
      <SectionCard title="Panel central en vivo" subtitle="Cronómetro central con sincronización en tiempo real vía WebSocket.">
        <div className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[2rem] bg-[linear-gradient(135deg,var(--color-primary-dark),var(--color-primary))] p-6 text-white shadow-[0_18px_40px_rgba(27,73,101,0.24)]">
            <div className="flex items-center justify-between">
              <p className="text-sm uppercase tracking-[0.18em] text-slate-100/80">Cronómetro central</p>
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
            <p className="mt-4 text-7xl font-bold tabular-nums tracking-tight">
              {formatTime(timerState.remaining_seconds)}
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
                  onClick={() => sendAction(action)}
                >
                  {action === "start" ? "Iniciar" :
                   action === "pause" ? "Pausar" :
                   action === "resume" ? "Reanudar" :
                   action === "reset" ? "Reiniciar" :
                   "Sig. estación"}
                </button>
              ))}
            </div>
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
