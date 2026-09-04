"""WebSocket manager for live ECOE timer synchronization."""

import asyncio
import json
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger("ecoe.websocket")


class LiveTimerManager:
    """Manages WebSocket connections per ECOE event for real-time timer sync.

    M1 F2: while at least one client is connected for an event, a per-event
    asyncio ticker advances the automatic circuit at each phase deadline and
    broadcasts the new timer state plus a ``phase_bell`` so every screen rings
    on time. The ticker is *best-effort*: it never owns the authoritative clock
    (``phase_started_at`` + duration does, and the lazy sweep on the context
    endpoints recovers state if the process restarts) — it only makes the bell
    punctual and keeps unattended screens in sync between operator actions.
    """

    # Flip to False in tests (like rate_limit thresholds) so the sync TestClient
    # doesn't spawn per-connection background tasks against the test DB.
    ticker_enabled: bool = True

    def __init__(self) -> None:
        self._connections: dict[int, list[WebSocket]] = defaultdict(list)
        self._tickers: dict[int, asyncio.Task] = {}

    async def connect(self, ecoe_event_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[ecoe_event_id].append(websocket)
        self._ensure_ticker(ecoe_event_id)

    def disconnect(self, ecoe_event_id: int, websocket: WebSocket) -> None:
        conns = self._connections.get(ecoe_event_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns and ecoe_event_id in self._connections:
            del self._connections[ecoe_event_id]
            self._stop_ticker(ecoe_event_id)

    async def broadcast(self, ecoe_event_id: int, data: dict) -> None:
        """Send data to all connected clients for a given ECOE event."""
        disconnected: list[WebSocket] = []
        for ws in self._connections.get(ecoe_event_id, []):
            try:
                await ws.send_text(json.dumps(data))
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ecoe_event_id, ws)

    def connection_count(self, ecoe_event_id: int) -> int:
        return len(self._connections.get(ecoe_event_id, []))

    # ── M1 F2: ticker del circuito automático ──────────────────────────

    def _ensure_ticker(self, ecoe_event_id: int) -> None:
        if not self.ticker_enabled:
            return
        task = self._tickers.get(ecoe_event_id)
        if task and not task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # pragma: no cover - no loop (sync test client)
            return
        self._tickers[ecoe_event_id] = loop.create_task(self._tick_loop(ecoe_event_id))

    def _stop_ticker(self, ecoe_event_id: int) -> None:
        task = self._tickers.pop(ecoe_event_id, None)
        if task and not task.done():
            task.cancel()

    async def _tick_loop(self, ecoe_event_id: int) -> None:
        # Lazy import: this module is imported very early (via the route
        # modules) and live_cycle pulls in the grading/sweep stack.
        from app.db.session import SessionLocal
        from app.services.live_cycle import pump_auto_cycle

        def _pump() -> dict:
            with SessionLocal() as db:
                return pump_auto_cycle(db, ecoe_event_id)

        try:
            while self.connection_count(ecoe_event_id) > 0:
                try:
                    result = await asyncio.to_thread(_pump)
                except Exception:  # pragma: no cover - defensive
                    logger.exception("ticker de circuito automático falló (evento %s)", ecoe_event_id)
                    await asyncio.sleep(5.0)
                    continue

                state = result.get("state")
                if state is not None:
                    await self.broadcast(ecoe_event_id, {"type": "timer_update", **state})
                    for kind in result.get("bells", []):
                        await self.broadcast(
                            ecoe_event_id,
                            {
                                "type": "phase_bell",
                                "kind": kind,
                                "station": state.get("current_station_index"),
                                "status": state.get("status"),
                            },
                        )

                await asyncio.sleep(min(float(result.get("sleep_seconds", 12.0)), 60.0))
        except asyncio.CancelledError:
            raise
        finally:
            self._tickers.pop(ecoe_event_id, None)


# Singleton
live_timer = LiveTimerManager()
