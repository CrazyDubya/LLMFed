"""Analytics API routes — aggregation endpoints for the dashboard."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agent_service.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/game/analytics", tags=["analytics"])


@router.get("/world/{world_id}/summary")
async def api_world_summary(world_id: str, db: AsyncSession = Depends(get_db)):
    """Get high-level world summary statistics."""
    from game_service.analytics_service import world_summary
    return world_summary(db, world_id)


@router.get("/world/{world_id}/wrestler/{wrestler_id}")
async def api_wrestler_performance(
    world_id: str,
    wrestler_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Get wrestler performance analytics."""
    from game_service.analytics_service import wrestler_performance
    return wrestler_performance(db, world_id, wrestler_id, limit)


@router.get("/world/{world_id}/federation/{federation_id}")
async def api_federation_health(
    world_id: str,
    federation_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get federation health metrics."""
    from game_service.analytics_service import federation_health
    return federation_health(db, world_id, federation_id)


@router.get("/world/{world_id}/match-quality")
async def api_match_quality(
    world_id: str,
    federation_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get match rating distribution."""
    from game_service.analytics_service import match_quality_distribution
    return match_quality_distribution(db, world_id, federation_id)


@router.get("/world/{world_id}/head-to-head")
async def api_head_to_head(
    world_id: str,
    wrestler_a: str = Query(..., alias="a"),
    wrestler_b: str = Query(..., alias="b"),
    db: AsyncSession = Depends(get_db),
):
    """Get head-to-head comparison between two wrestlers."""
    from game_service.analytics_service import head_to_head
    return head_to_head(db, world_id, wrestler_a, wrestler_b)


@router.get("/llm-usage")
async def api_llm_usage():
    """Get LLM cost/usage summary (API calls, total cost, budget remaining)."""
    from game_service.analytics_service import llm_usage_summary
    return llm_usage_summary()


@router.get("/world/{world_id}/leaderboard")
async def api_leaderboard(
    world_id: str,
    metric: str = Query("win_rate", description="Sort by: win_rate, avg_match_rating, total_matches, wins"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Get top performers leaderboard."""
    from game_service.analytics_service import top_performers
    return top_performers(db, world_id, metric, limit)
