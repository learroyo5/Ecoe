import { useEffect, useRef, useState } from "react";

const WS_RETRY_MS = 5000;

/** Resolve the live-timer WebSocket URL for the given ECOE event.
 *
 * `kioskToken` is appended as a query param because a browser cannot attach
 * custom headers to a WebSocket handshake (see the backend handler comment on
 * the token-in-URL trade-off: short TTL + station scope).
 */
export function resolveLiveWsUrl(eventId: number, kioskToken?: string): string {
  const withToken = (base: string) =>
    kioskToken ? `${base}?kiosk_token=${encodeURIComponent(kioskToken)}` : base;

  const explicit = process.env.NEXT_PUBLIC_WS_URL;
  if (explicit) {
    return withToken(`${explicit.replace(/\/$/, "")}/ws/live/${eventId}`);
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const isLocalHost =
    window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";

  if (!isLocalHost) {
    // Behind a reverse proxy (production): same origin, proxy forwards
    // /api/ to the backend (see datos_proyecto/nginx_ecoe_publico.conf).
    return withToken(`${protocol}//${window.location.host}/api/ws/live/${eventId}`);
  }

  // Bare docker-compose / local dev without a reverse proxy in front:
  // the backend is reachable directly on its own exposed port.
  const backendPort = process.env.NEXT_PUBLIC_BACKEND_WS_PORT ?? "8000";
  return withToken(
    `${protocol}//${window.location.hostname}:${backendPort}/api/ws/live/${eventId}`,
  );
}

export type LiveTimerSnapshot = {
  status: string;
  remainingSeconds: number;
  currentStationIndex: number;
  stationTimeSeconds: number;
  transitionTimeSeconds: number;
  /** Epoch ms when the current phase ends, or null when it is not counting down. */
  phaseEndsAt: number | null;
  /** Epoch ms (local clock) when this snapshot was received. */
  receivedAt: number;
};

type UseLiveTimerOptions = {
  /** Station-scoped kiosk token; when present the socket authenticates with it
   * instead of the user session. */
  kioskToken?: string;
  /** Skip connecting entirely (e.g. before the event id is known). */
  enabled?: boolean;
  /** Called for every parsed frame (used by the live panel for incidents). */
  onMessage?: (data: Record<string, unknown>) => void;
  /** Called on every (re)connect — the live panel uses it to resync via REST. */
  onReconnect?: () => void;
};

/**
 * Subscribe to the central live timer over WebSocket with automatic
 * reconnection. Extracted from the inline logic that used to live in
 * `live/page.tsx` so kiosk / evaluador / estudiante can reuse it.
 */
export function useLiveTimer(eventId: number, options: UseLiveTimerOptions = {}) {
  const { kioskToken, enabled = true, onMessage, onReconnect } = options;
  const [snapshot, setSnapshot] = useState<LiveTimerSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const callbacksRef = useRef({ onMessage, onReconnect });

  useEffect(() => {
    callbacksRef.current = { onMessage, onReconnect };
  });

  useEffect(() => {
    if (!enabled || !eventId) return;
    let disposed = false;
    let retryTimer: number | null = null;

    const connect = () => {
      if (disposed) return;
      let ws: WebSocket | null = null;
      try {
        ws = new WebSocket(resolveLiveWsUrl(eventId, kioskToken));
        wsRef.current = ws;
      } catch {
        setConnected(false);
        retryTimer = window.setTimeout(connect, WS_RETRY_MS);
        return;
      }

      ws.onopen = () => {
        setConnected(true);
        callbacksRef.current.onReconnect?.();
      };

      ws.onmessage = (event) => {
        let data: Record<string, unknown>;
        try {
          data = JSON.parse(event.data);
        } catch {
          return;
        }
        if (data.type === "timer_update") {
          const now = Date.now();
          const status = String(data.status ?? "");
          const remainingSeconds = Number(data.remaining_seconds ?? 0);
          const counting = status === "running" || status === "transition";
          setSnapshot({
            status,
            remainingSeconds,
            currentStationIndex: Number(data.current_station_index ?? 0),
            stationTimeSeconds: Number(data.station_time_seconds ?? 0),
            transitionTimeSeconds: Number(data.transition_time_seconds ?? 0),
            phaseEndsAt: counting ? now + remainingSeconds * 1000 : null,
            receivedAt: now,
          });
        }
        callbacksRef.current.onMessage?.(data);
      };

      ws.onclose = () => {
        setConnected(false);
        if (!disposed) retryTimer = window.setTimeout(connect, WS_RETRY_MS);
      };
      ws.onerror = () => {
        try {
          ws?.close();
        } catch {
          /* onclose schedules the retry */
        }
      };
    };

    connect();

    return () => {
      disposed = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      try {
        wsRef.current?.close();
      } catch {
        /* ignore */
      }
      wsRef.current = null;
    };
  }, [enabled, eventId, kioskToken]);

  return { snapshot, connected };
}
