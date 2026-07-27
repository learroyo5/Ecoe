/** Resolve the live-timer WebSocket URL for the given ECOE event. */
export function resolveLiveWsUrl(eventId: number): string {
  const explicit = process.env.NEXT_PUBLIC_WS_URL;
  if (explicit) {
    return `${explicit.replace(/\/$/, "")}/ws/live/${eventId}`;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const isLocalHost =
    window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";

  if (!isLocalHost) {
    // Behind a reverse proxy (production): same origin, proxy forwards
    // /api/ to the backend (see datos_proyecto/nginx_ecoe_publico.conf).
    return `${protocol}//${window.location.host}/api/ws/live/${eventId}`;
  }

  // Bare docker-compose / local dev without a reverse proxy in front:
  // the backend is reachable directly on its own exposed port.
  const backendPort = process.env.NEXT_PUBLIC_BACKEND_WS_PORT ?? "8000";
  return `${protocol}//${window.location.hostname}:${backendPort}/api/ws/live/${eventId}`;
}
