"""
WebSocket hub for real-time game updates.

Players connect to receive live updates about their world:
- Show results
- Storyline developments
- Contract news
- World events
"""

import logging
import json
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections grouped by world_id."""

    def __init__(self):
        # world_id -> set of connected websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, world_id: str):
        """Accept and register a new connection."""
        await websocket.accept()
        if world_id not in self.active_connections:
            self.active_connections[world_id] = set()
        self.active_connections[world_id].add(websocket)
        logger.info(f"WebSocket connected to world {world_id} "
                     f"({len(self.active_connections[world_id])} connections)")

    def disconnect(self, websocket: WebSocket, world_id: str):
        """Remove a connection."""
        if world_id in self.active_connections:
            self.active_connections[world_id].discard(websocket)
            if not self.active_connections[world_id]:
                del self.active_connections[world_id]

    async def broadcast_to_world(self, world_id: str, message: dict):
        """Send a message to all connections in a world."""
        if world_id not in self.active_connections:
            return

        dead = set()
        for connection in self.active_connections[world_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead.add(connection)

        # Clean up dead connections
        for conn in dead:
            self.active_connections[world_id].discard(conn)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a specific connection."""
        try:
            await websocket.send_json(message)
        except Exception:
            pass

    def get_connection_count(self, world_id: str = None) -> int:
        """Get number of active connections."""
        if world_id:
            return len(self.active_connections.get(world_id, set()))
        return sum(len(conns) for conns in self.active_connections.values())


# Singleton manager
manager = ConnectionManager()


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
            try:
                msg = json.loads(data)
                msg_type = msg.get("type", "")

                if msg_type == "ping":
                    await manager.send_personal(websocket, {"type": "pong"})
                elif msg_type == "subscribe":
                    # Future: subscribe to specific event types
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
