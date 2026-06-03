"""WebSocket manager for live ECOE timer synchronization."""

import json
from collections import defaultdict

from fastapi import WebSocket


class LiveTimerManager:
    """Manages WebSocket connections per ECOE event for real-time timer sync."""

    def __init__(self) -> None:
        self._connections: dict[int, list[WebSocket]] = defaultdict(list)

    async def connect(self, ecoe_event_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[ecoe_event_id].append(websocket)

    def disconnect(self, ecoe_event_id: int, websocket: WebSocket) -> None:
        conns = self._connections.get(ecoe_event_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns and ecoe_event_id in self._connections:
            del self._connections[ecoe_event_id]

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

    @property
    def connection_count(self, ecoe_event_id: int) -> int:
        return len(self._connections.get(ecoe_event_id, []))


# Singleton
live_timer = LiveTimerManager()
