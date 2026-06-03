"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import { useECOE } from "@/lib/auth";
import { useApi } from "@/hooks/use-api";
import { DataTable } from "@/components/data-table";
import { SectionCard } from "@/components/section-card";
import type { Incident } from "@/lib/types";

type TimerState = {
  status: string;
  remaining_seconds: number;
  current_station_index: number;
  station_time_seconds: number;
  transition_time_seconds: number;
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

  const liveQuery = useApi(
    () => api.live(eventId, token!),
    [eventId, token],
  );

  const incidentsQuery = useApi(
    () => api.incidents(eventId, token!) as unknown as Promise<Record<string, unknown>>,
    [eventId, token],
  );
  const incidentsData = (incidentsQuery.data?.items as Incident[]) ?? [];

  // Sync initial state from REST
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

  // WebSocket connection for real-time timer
  // Connect directly to backend — Next.js proxy doesn't upgrade WebSocket
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
      return; // WebSocket not available, timer works via REST
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
    // Timer state will be updated via WebSocket broadcast
  }, [eventId, token]);

  const formatTime = (totalSeconds: number) => {
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  return (
    <div className="space-y-6">
      <SectionCard title="Panel central en vivo" subtitle="Cronometro central con sincronizacion en tiempo real via WebSocket.">
        <div className="grid gap-4 md:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-[2rem] bg-[linear-gradient(135deg,var(--color-primary-dark),var(--color-primary))] p-6 text-white shadow-[0_18px_40px_rgba(27,73,101,0.24)]">
            <div className="flex items-center justify-between">
              <p className="text-sm uppercase tracking-[0.18em] text-slate-100/80">Cronometro central</p>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
                timerState.status === "running" ? "bg-green-500" :
                timerState.status === "paused" ? "bg-yellow-500" :
                timerState.status === "transition" ? "bg-orange-500" : "bg-slate-500"
              }`}>
                {timerState.status === "running" ? "▶ EN VIVO" :
                 timerState.status === "paused" ? "⏸ PAUSADO" :
                 timerState.status === "transition" ? "↻ TRANSICION" :
                 timerState.status.toUpperCase()}
              </span>
            </div>
            <p className="mt-4 text-7xl font-bold tabular-nums tracking-tight">
              {formatTime(timerState.remaining_seconds)}
            </p>
            <p className="mt-3 text-lg text-slate-100/80">
              Estacion {timerState.current_station_index} ·{" "}
              {timerState.status === "transition" ? "Transicion" : "Estacion"}:{" "}
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
                   "Sig. estacion"}
                </button>
              ))}
            </div>
          </div>
          <div className="clinical-panel">
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[var(--color-primary)]">
              Supervision operativa
            </p>
            <ul className="mt-4 space-y-3 text-sm text-slate-700">
              <li>✓ Sincronizacion en tiempo real por WebSocket.</li>
              <li>✓ Control de pausa, reanudacion y reinicio controlado.</li>
              <li>✓ Transicion automatica entre estaciones.</li>
              <li>✓ Seguimiento de incidencias y avance del circuito.</li>
            </ul>
          </div>
        </div>
      </SectionCard>
      <SectionCard title="Incidencias activas" subtitle="Registro visible de problemas operativos para reaccionar rapido durante la sesion.">
        <DataTable
          rows={incidentsData}
          columns={[
            { key: "title", label: "Incidencia" },
            { key: "detail", label: "Detalle" },
            {
              key: "severity",
              label: "Severidad",
              render: (row) => {
                const severity = String((row as { severity?: string }).severity ?? "").toLowerCase();
                const badgeClass =
                  severity.includes("alta") || severity.includes("crit")
                    ? "status-badge-error"
                    : severity.includes("media")
                      ? "status-badge-warning"
                      : "status-badge-info";
                return <span className={`status-badge ${badgeClass}`}>{severity || "sin definir"}</span>;
              },
            },
          ]}
        />
      </SectionCard>
    </div>
  );
}
