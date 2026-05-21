"""
Real-time event system (ENHANCEMENT_PROPOSAL Phase 1.2).

WebSocket integration for live match updates.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """Broadcast tick results and match events to WebSocket connections."""

    def __init__(self):
        self.connections: List = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket) -> None:
        """Add a WebSocket connection."""
        async with self._lock:
            self.connections.append(websocket)

    async def disconnect(self, websocket) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if websocket in self.connections:
                self.connections.remove(websocket)

    async def broadcast_tick_result(self, result: Any) -> None:
        """Broadcast a tick result to all connected clients."""
        if hasattr(result, "__dict__"):
            data = getattr(result, "__dict__", result)
        else:
            data = result
        message = {
            "type": "tick_update",
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._broadcast(message)

    async def broadcast_match_event(self, event: Dict[str, Any]) -> None:
        """Broadcast a match event to all connected clients."""
        message = {
            "type": "match_event",
            "data": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await self._broadcast(message)

    async def _broadcast(self, message: Dict[str, Any]) -> None:
        """Send message to all connections."""
        import json
        dead = []
        async with self._lock:
            conns = list(self.connections)
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Broadcast failed to connection: {e}")
                dead.append(ws)
        async with self._lock:
            for ws in dead:
                if ws in self.connections:
                    self.connections.remove(ws)


# Singleton broadcaster
broadcaster = EventBroadcaster()
