"""
WebSocket hub for real-time game updates.

Players connect to receive live updates about their world:
- Show results
- Storyline developments
- Contract news
- World events

Connection lifecycle:
    connect -> welcome message -> ping/pong heartbeat -> disconnect

A background reaper task periodically closes stale connections that
haven't sent a heartbeat within HEARTBEAT_TIMEOUT_SECONDS.
"""

import asyncio
import logging
import json
import time
from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Heartbeat interval — clients should send ping within this window
HEARTBEAT_TIMEOUT_SECONDS = 60

# How often the reaper checks for stale connections
_REAPER_INTERVAL_SECONDS = 30


class ConnectionManager:
    """Manages WebSocket connections grouped by world_id."""

    def __init__(self):
        # world_id -> set of connected websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> (world_id, last activity timestamp)
        self._last_activity: Dict[WebSocket, float] = {}
        # reverse lookup: websocket -> world_id (needed by reaper)
        self._ws_to_world: Dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket, world_id: str):
        """Accept and register a new connection."""
        await websocket.accept()
        if world_id not in self.active_connections:
            self.active_connections[world_id] = set()
        self.active_connections[world_id].add(websocket)
        self._last_activity[websocket] = time.monotonic()
        self._ws_to_world[websocket] = world_id
        logger.info(
            "WebSocket connected to world %s (%d connections)",
            world_id,
            len(self.active_connections[world_id]),
        )

    def disconnect(self, websocket: WebSocket, world_id: str):
        """Remove a connection and clean up tracking state."""
        if world_id in self.active_connections:
            self.active_connections[world_id].discard(websocket)
            if not self.active_connections[world_id]:
                del self.active_connections[world_id]
        self._last_activity.pop(websocket, None)
        self._ws_to_world.pop(websocket, None)

    def touch(self, websocket: WebSocket):
        """Update the last-activity timestamp for heartbeat tracking."""
        self._last_activity[websocket] = time.monotonic()

    async def broadcast_to_world(self, world_id: str, message: dict):
        """Send a message to all connections in a world."""
        connections = self.active_connections.get(world_id)
        if not connections:
            return

        # Snapshot the set to avoid RuntimeError if it changes during iteration
        dead: Set[WebSocket] = set()
        for connection in list(connections):
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                dead.add(connection)
            except Exception as e:
                logger.warning(
                    "Failed to send WebSocket message to world %s: %s: %s",
                    world_id,
                    type(e).__name__,
                    e,
                )
                dead.add(connection)

        # Clean up dead connections
        for conn in dead:
            self.disconnect(conn, world_id)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a specific connection."""
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            logger.debug("WebSocket already disconnected during personal send")
        except Exception as e:
            logger.warning(
                "Failed to send personal WebSocket message: %s: %s",
                type(e).__name__,
                e,
            )

    def get_connection_count(self, world_id: Optional[str] = None) -> int:
        """Get number of active connections."""
        if world_id:
            return len(self.active_connections.get(world_id, set()))
        return sum(len(conns) for conns in self.active_connections.values())

    def get_stale_connections(self) -> list:
        """Return (websocket, world_id) pairs that haven't pinged recently."""
        now = time.monotonic()
        stale = []
        for ws, last in list(self._last_activity.items()):
            if now - last > HEARTBEAT_TIMEOUT_SECONDS:
                world_id = self._ws_to_world.get(ws)
                if world_id:
                    stale.append((ws, world_id))
        return stale

    async def close_stale_connections(self) -> int:
        """Close and remove all stale connections. Returns count closed."""
        stale = self.get_stale_connections()
        for ws, world_id in stale:
            logger.info("Closing stale WebSocket for world %s", world_id)
            self.disconnect(ws, world_id)
            try:
                await ws.close(code=1000, reason="heartbeat timeout")
            except Exception:
                pass  # already dead
        return len(stale)

    def stats(self) -> dict:
        """Return connection statistics for monitoring."""
        return {
            "total_connections": self.get_connection_count(),
            "worlds": len(self.active_connections),
            "per_world": {
                wid: len(conns) for wid, conns in self.active_connections.items()
            },
        }


# Singleton manager
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Background reaper task
# ---------------------------------------------------------------------------

_reaper_task: Optional[asyncio.Task] = None


async def _reaper_loop():
    """Periodically close stale connections."""
    while True:
        await asyncio.sleep(_REAPER_INTERVAL_SECONDS)
        try:
            closed = await manager.close_stale_connections()
            if closed:
                logger.info("Reaper closed %d stale WebSocket connection(s)", closed)
        except Exception as e:
            logger.error("WebSocket reaper error: %s", e)


def start_reaper():
    """Start the stale-connection reaper as a background task.

    Safe to call multiple times — only one reaper runs at a time.
    Call from a FastAPI ``startup`` event handler.
    """
    global _reaper_task
    if _reaper_task is None or _reaper_task.done():
        _reaper_task = asyncio.ensure_future(_reaper_loop())
        logger.info("WebSocket stale-connection reaper started")


# ---------------------------------------------------------------------------
# Public helpers for game services to push updates
# ---------------------------------------------------------------------------


async def notify_world(world_id: str, event_type: str, data: dict):
    """Push a typed event to all subscribers of a world.

    Call this from game services (e.g., after a show completes):

        from api_gateway.websocket_hub import notify_world
        await notify_world(world_id, "show_completed", {...})
    """
    await manager.broadcast_to_world(
        world_id,
        {
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
        },
    )


# ---------------------------------------------------------------------------
# WebSocket endpoint handler
# ---------------------------------------------------------------------------


async def websocket_endpoint(websocket: WebSocket, world_id: str):
    """WebSocket endpoint for world updates."""
    await manager.connect(websocket, world_id)
    try:
        # Send welcome message
        await manager.send_personal(
            websocket,
            {
                "type": "connected",
                "world_id": world_id,
                "message": "Connected to world feed",
            },
        )

        # Keep connection alive, handle incoming messages.
        # asyncio.wait_for enforces a receive timeout so silent clients
        # don't hold connections open forever.
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=HEARTBEAT_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                # Client hasn't sent anything within the heartbeat window
                logger.info("WebSocket timed out for world %s", world_id)
                await manager.send_personal(
                    websocket,
                    {
                        "type": "error",
                        "message": "Heartbeat timeout — closing connection",
                    },
                )
                break

            manager.touch(websocket)
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
                elif msg_type == "subscribe":
                    await manager.send_personal(
                        websocket,
                        {
                            "type": "subscribed",
                            "channel": msg.get("channel", "all"),
                        },
                    )
                else:
                    await manager.send_personal(
                        websocket,
                        {
                            "type": "error",
                            "message": f"Unknown message type: {msg_type}",
                        },
                    )
            except json.JSONDecodeError:
                await manager.send_personal(
                    websocket,
                    {
                        "type": "error",
                        "message": "Invalid JSON",
                    },
                )
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected from world %s", world_id)
    except Exception as e:
        logger.error(
            "WebSocket error for world %s: %s: %s", world_id, type(e).__name__, e
        )
    finally:
        manager.disconnect(websocket, world_id)
