"""
WebSocket hub for real-time game updates.

Players connect to receive live updates about their world:
- Show results
- Storyline developments
- Contract news
- World events

Connection lifecycle:
    connect -> welcome message -> ping/pong heartbeat -> disconnect
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


class ConnectionManager:
    """Manages WebSocket connections grouped by world_id."""

    def __init__(self):
        # world_id -> set of connected websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # websocket -> last activity timestamp (for heartbeat tracking)
        self._last_activity: Dict[WebSocket, float] = {}

    async def connect(self, websocket: WebSocket, world_id: str):
        """Accept and register a new connection."""
        await websocket.accept()
        if world_id not in self.active_connections:
            self.active_connections[world_id] = set()
        self.active_connections[world_id].add(websocket)
        self._last_activity[websocket] = time.monotonic()
        logger.info(
            f"WebSocket connected to world {world_id} "
            f"({len(self.active_connections[world_id])} connections)"
        )

    def disconnect(self, websocket: WebSocket, world_id: str):
        """Remove a connection and clean up tracking state."""
        if world_id in self.active_connections:
            self.active_connections[world_id].discard(websocket)
            if not self.active_connections[world_id]:
                del self.active_connections[world_id]
        self._last_activity.pop(websocket, None)

    def touch(self, websocket: WebSocket):
        """Update the last-activity timestamp for heartbeat tracking."""
        self._last_activity[websocket] = time.monotonic()

    async def broadcast_to_world(self, world_id: str, message: dict):
        """Send a message to all connections in a world."""
        if world_id not in self.active_connections:
            return

        dead: Set[WebSocket] = set()
        for connection in self.active_connections[world_id]:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                dead.add(connection)
            except Exception as e:
                logger.warning(
                    f"Failed to send WebSocket message to world {world_id}: "
                    f"{type(e).__name__}: {e}"
                )
                dead.add(connection)

        # Clean up dead connections
        for conn in dead:
            self.active_connections[world_id].discard(conn)
            self._last_activity.pop(conn, None)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a specific connection."""
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            logger.debug("WebSocket already disconnected during personal send")
        except Exception as e:
            logger.warning(
                f"Failed to send personal WebSocket message: "
                f"{type(e).__name__}: {e}"
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
        for world_id, conns in self.active_connections.items():
            for ws in conns:
                last = self._last_activity.get(ws, 0)
                if now - last > HEARTBEAT_TIMEOUT_SECONDS:
                    stale.append((ws, world_id))
        return stale


# Singleton manager
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Public helpers for game services to push updates
# ---------------------------------------------------------------------------

async def notify_world(world_id: str, event_type: str, data: dict):
    """Push a typed event to all subscribers of a world.

    Call this from game services (e.g., after a show completes):

        from api_gateway.websocket_hub import notify_world
        await notify_world(world_id, "show_completed", {...})
    """
    await manager.broadcast_to_world(world_id, {
        "type": event_type,
        "data": data,
        "timestamp": time.time(),
    })


# ---------------------------------------------------------------------------
# WebSocket endpoint handler
# ---------------------------------------------------------------------------

async def websocket_endpoint(websocket: WebSocket, world_id: str):
    """WebSocket endpoint for world updates."""
    await manager.connect(websocket, world_id)
    try:
        # Send welcome message
        await manager.send_personal(websocket, {
            "type": "connected",
            "world_id": world_id,
            "message": "Connected to world feed",
        })

        # Keep connection alive, handle incoming messages
        while True:
            data = await websocket.receive_text()
            manager.touch(websocket)
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
                elif msg_type == "subscribe":
                    await manager.send_personal(websocket, {
                        "type": "subscribed",
                        "channel": msg.get("channel", "all"),
                    })
                else:
                    await manager.send_personal(websocket, {
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                    })
            except json.JSONDecodeError:
                await manager.send_personal(websocket, {
                    "type": "error",
                    "message": "Invalid JSON",
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket, world_id)
        logger.info(f"WebSocket disconnected from world {world_id}")
    except Exception as e:
        logger.error(f"WebSocket error for world {world_id}: {type(e).__name__}: {e}")
        manager.disconnect(websocket, world_id)
