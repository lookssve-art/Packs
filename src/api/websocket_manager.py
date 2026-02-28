"""WebSocket connection manager for real-time broadcasting."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasts events to all clients."""

    def __init__(self):
        self.active: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active.append(websocket)
        logger.info("WS client connected. Total: %d", len(self.active))

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self.active:
                self.active.remove(websocket)
        logger.info("WS client disconnected. Total: %d", len(self.active))

    async def broadcast(self, event: str, data: Any) -> None:
        """Send a JSON event to all connected clients."""
        if not self.active:
            return
        message = json.dumps({"event": event, "data": data}, default=str)
        disconnected: list[WebSocket] = []
        async with self._lock:
            for ws in self.active:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.append(ws)
            for ws in disconnected:
                self.active.remove(ws)

    async def broadcast_cycle(
        self, summary: dict, ev_data: list[dict], new_pulls: list[dict], alerts: list[dict],
    ) -> None:
        """Broadcast a full cycle result to all connected clients."""
        if not self.active:
            return

        await self.broadcast("status", summary)

        for pull in new_pulls:
            await self.broadcast("new_pull", pull)

        if ev_data:
            await self.broadcast("ev_update", ev_data)

        for alert in alerts:
            await self.broadcast("alert", alert)
