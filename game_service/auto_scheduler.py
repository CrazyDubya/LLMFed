"""
Auto-Ticker Scheduler - makes the wrestling world run on its own clock.

Runs as an asyncio background task inside the FastAPI process.
Each interval it advances every active world by one game day,
then broadcasts results to connected WebSocket clients.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from agent_service.database import SessionLocal
from models.game_models import WorldDB

logger = logging.getLogger(__name__)


class AutoScheduler:
    """Background scheduler that auto-ticks game worlds."""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._interval_seconds: float = 60.0  # default: 1 game-day per 60 real seconds
        self._paused_worlds: set[str] = set()
        self._tick_count: int = 0
        self._last_tick_at: Optional[str] = None
        self._errors: list[str] = []

    @property
    def is_running(self) -> bool:
        return self._running and self._task is not None and not self._task.done()

    def status(self) -> dict:
        return {
            "running": self.is_running,
            "interval_seconds": self._interval_seconds,
            "ticks_completed": self._tick_count,
            "last_tick_at": self._last_tick_at,
            "paused_worlds": list(self._paused_worlds),
            "recent_errors": self._errors[-5:],
        }

    async def start(self, interval_seconds: float = None):
        """Start the auto-ticker loop."""
        if self.is_running:
            logger.warning("AutoScheduler already running")
            return
        if interval_seconds is not None:
            self._interval_seconds = max(10.0, interval_seconds)  # floor: 10s
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("AutoScheduler started (interval=%ss)", self._interval_seconds)

    async def stop(self):
        """Stop the auto-ticker loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("AutoScheduler stopped")

    def set_interval(self, seconds: float):
        """Change tick interval (minimum 10 seconds)."""
        self._interval_seconds = max(10.0, seconds)

    def pause_world(self, world_id: str):
        self._paused_worlds.add(world_id)

    def resume_world(self, world_id: str):
        self._paused_worlds.discard(world_id)

    # ----- internal loop -----

    async def _loop(self):
        """Main ticker loop - advances all active worlds each interval."""
        while self._running:
            try:
                await self._tick_all_worlds()
                self._tick_count += 1
                self._last_tick_at = datetime.now(timezone.utc).isoformat()
            except Exception as e:
                msg = f"Scheduler tick error: {e}"
                logger.error(msg, exc_info=True)
                self._errors.append(msg)
                if len(self._errors) > 50:
                    self._errors = self._errors[-25:]

            try:
                await asyncio.sleep(self._interval_seconds)
            except asyncio.CancelledError:
                break

    async def _tick_all_worlds(self):
        """Advance every non-paused world by one game day and broadcast."""
        # Import here to avoid circular imports at module level
        from api_gateway.websocket_hub import manager as ws_manager
        from game_service.world_ticker import WorldTicker

        # Run DB work in a thread so we don't block the event loop
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, self._tick_worlds_sync)

        # Broadcast results via WebSocket
        for world_id, result in results.items():
            await ws_manager.broadcast_to_world(world_id, {
                "type": "tick",
                "world_id": world_id,
                "game_date": result.get("new_game_date"),
                "tick": result.get("new_tick"),
                "events": result.get("day_results", [{}])[-1].get("events", []) if result.get("day_results") else [],
                "auto": True,
            })

            # If any shows were completed this tick, send show_completed events
            day_results = result.get("day_results", [])
            for day in day_results:
                for event in day.get("events", []):
                    if "show" in event.lower() and "completed" in event.lower():
                        await ws_manager.broadcast_to_world(world_id, {
                            "type": "show_completed",
                            "world_id": world_id,
                            "description": event,
                        })

    def _tick_worlds_sync(self) -> Dict[str, dict]:
        """Synchronous DB work: tick each world and return results."""
        from game_service.world_ticker import WorldTicker

        db: Session = SessionLocal()
        results: Dict[str, dict] = {}
        try:
            worlds = db.query(WorldDB).filter(WorldDB.is_active == True).all()
            for world in worlds:
                if world.id in self._paused_worlds:
                    continue
                try:
                    ticker = WorldTicker(db, world.id)
                    result = ticker.tick(1)
                    db.commit()
                    results[world.id] = result
                except Exception as e:
                    db.rollback()
                    msg = f"Tick failed for world {world.id}: {e}"
                    logger.error(msg)
                    self._errors.append(msg)
        finally:
            db.close()
        return results


# Singleton
scheduler = AutoScheduler()
