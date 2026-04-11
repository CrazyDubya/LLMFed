"""
Analytics Service — aggregation and data analysis for the wrestling simulation.

Provides backend analytics endpoints for wrestler performance, federation health,
match quality trends, storyline heat, and head-to-head comparisons.
"""

import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict

from sqlalchemy import func, case, desc
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def wrestler_performance(
    db: Session,
    world_id: str,
    wrestler_id: str,
    limit: int = 50,
) -> Dict[str, Any]:
    """Get a wrestler's performance over time (recent matches, win rate, ratings)."""
    from models.show_models import MatchDB, MatchParticipantDB
    from models.game_models import GameWrestlerDB

    wrestler = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id == wrestler_id
    ).first()
    if not wrestler:
        return {"error": "Wrestler not found"}

    # Recent match history
    participations = (
        db.query(MatchParticipantDB, MatchDB)
        .join(MatchDB, MatchParticipantDB.match_id == MatchDB.id)
        .filter(
            MatchParticipantDB.wrestler_id == wrestler_id,
            MatchDB.world_id == world_id,
            MatchDB.winner_id.isnot(None),
        )
        .order_by(MatchDB.created_at.desc())
        .limit(limit)
        .all()
    )

    matches = []
    wins = 0
    total = 0
    ratings = []
    for part, match in participations:
        total += 1
        is_win = match.winner_id == wrestler_id
        if is_win:
            wins += 1
        if match.match_rating:
            ratings.append(match.match_rating)
        matches.append({
            "match_id": match.id,
            "match_type": match.match_type,
            "result": "win" if is_win else "loss",
            "rating": match.match_rating,
            "crowd_heat": match.crowd_heat,
        })

    return {
        "wrestler_id": wrestler_id,
        "name": wrestler.ring_name,
        "total_matches": total,
        "wins": wins,
        "losses": total - wins,
        "win_rate": round(wins / total, 3) if total > 0 else 0.0,
        "avg_match_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
        "best_match_rating": max(ratings) if ratings else 0.0,
        "recent_matches": matches[:10],
    }


def federation_health(
    db: Session,
    world_id: str,
    federation_id: str,
) -> Dict[str, Any]:
    """Get federation health metrics: roster size, show quality, finances."""
    from models.game_models import GameFederationDB, GameWrestlerDB, ContractDB
    from models.show_models import ShowDB, MatchDB

    fed = db.query(GameFederationDB).filter(
        GameFederationDB.id == federation_id
    ).first()
    if not fed:
        return {"error": "Federation not found"}

    # Roster size
    roster_count = db.query(func.count(ContractDB.id)).filter(
        ContractDB.federation_id == federation_id,
        ContractDB.status == "active",
    ).scalar() or 0

    # Show stats
    shows = db.query(ShowDB).filter(
        ShowDB.federation_id == federation_id,
        ShowDB.is_completed == True,
    ).order_by(ShowDB.game_date.desc()).limit(20).all()

    show_ratings = [s.overall_rating for s in shows if s.overall_rating]
    tv_ratings = [s.tv_rating for s in shows if s.tv_rating]
    gate_revenues = [s.gate_revenue for s in shows if s.gate_revenue]

    return {
        "federation_id": federation_id,
        "name": fed.name,
        "roster_count": roster_count,
        "balance": getattr(fed, "balance", 0),
        "shows_completed": len(shows),
        "avg_show_rating": round(sum(show_ratings) / len(show_ratings), 2) if show_ratings else 0.0,
        "avg_tv_rating": round(sum(tv_ratings) / len(tv_ratings), 2) if tv_ratings else 0.0,
        "avg_gate_revenue": round(sum(gate_revenues) / len(gate_revenues), 0) if gate_revenues else 0.0,
        "total_gate_revenue": round(sum(gate_revenues), 0) if gate_revenues else 0.0,
    }


def match_quality_distribution(
    db: Session,
    world_id: str,
    federation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Match rating distribution (star rating histogram)."""
    from models.show_models import MatchDB, ShowDB

    query = (
        db.query(MatchDB.match_rating)
        .join(ShowDB, MatchDB.world_id == ShowDB.world_id)
        .filter(
            MatchDB.world_id == world_id,
            MatchDB.match_rating.isnot(None),
        )
    )
    if federation_id:
        query = query.filter(ShowDB.federation_id == federation_id)

    ratings = [r[0] for r in query.all()]

    if not ratings:
        return {"total_matches": 0, "distribution": {}}

    # Bucket into half-star increments
    buckets = defaultdict(int)
    for r in ratings:
        bucket = round(r * 2) / 2  # Round to nearest 0.5
        buckets[f"{bucket:.1f}"] += 1

    return {
        "total_matches": len(ratings),
        "avg_rating": round(sum(ratings) / len(ratings), 2),
        "min_rating": round(min(ratings), 2),
        "max_rating": round(max(ratings), 2),
        "distribution": dict(sorted(buckets.items())),
    }


def head_to_head(
    db: Session,
    world_id: str,
    wrestler_a_id: str,
    wrestler_b_id: str,
) -> Dict[str, Any]:
    """Head-to-head comparison between two wrestlers."""
    from models.show_models import MatchDB, MatchParticipantDB

    # Find matches where both participated
    a_matches = db.query(MatchParticipantDB.match_id).filter(
        MatchParticipantDB.wrestler_id == wrestler_a_id
    ).subquery()
    b_matches = db.query(MatchParticipantDB.match_id).filter(
        MatchParticipantDB.wrestler_id == wrestler_b_id
    ).subquery()

    shared_matches = (
        db.query(MatchDB)
        .filter(
            MatchDB.id.in_(db.query(a_matches)),
            MatchDB.id.in_(db.query(b_matches)),
            MatchDB.world_id == world_id,
            MatchDB.winner_id.isnot(None),
        )
        .all()
    )

    a_wins = sum(1 for m in shared_matches if m.winner_id == wrestler_a_id)
    b_wins = sum(1 for m in shared_matches if m.winner_id == wrestler_b_id)
    ratings = [m.match_rating for m in shared_matches if m.match_rating]

    return {
        "wrestler_a_id": wrestler_a_id,
        "wrestler_b_id": wrestler_b_id,
        "total_matches": len(shared_matches),
        "a_wins": a_wins,
        "b_wins": b_wins,
        "draws": len(shared_matches) - a_wins - b_wins,
        "avg_match_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0.0,
        "best_match_rating": max(ratings) if ratings else 0.0,
    }


def llm_usage_summary() -> Dict[str, Any]:
    """Return LLM cost/usage summary from the LLM abstraction budget tracker.

    This gives operators visibility into API costs and call volumes.
    """
    try:
        from llm_abstraction.provider import get_llm
        llm = get_llm()
        return llm.get_budget_summary()
    except Exception as e:
        logger.warning("Could not retrieve LLM budget summary: %s", e)
        return {"error": str(e), "total_cost": 0, "total_calls": 0}


def top_performers(
    db: Session,
    world_id: str,
    metric: str = "win_rate",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Return top-N wrestlers by a chosen metric (win_rate, avg_rating, matches)."""
    from models.show_models import MatchDB, MatchParticipantDB
    from models.game_models import GameWrestlerDB

    wrestlers = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.world_id == world_id
    ).all()

    leaderboard = []
    for w in wrestlers:
        parts = (
            db.query(MatchParticipantDB, MatchDB)
            .join(MatchDB, MatchParticipantDB.match_id == MatchDB.id)
            .filter(
                MatchParticipantDB.wrestler_id == w.id,
                MatchDB.world_id == world_id,
                MatchDB.winner_id.isnot(None),
            )
            .all()
        )
        total = len(parts)
        if total == 0:
            continue
        wins = sum(1 for p, m in parts if m.winner_id == w.id)
        ratings = [m.match_rating for p, m in parts if m.match_rating]
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
        leaderboard.append({
            "wrestler_id": w.id,
            "name": w.ring_name,
            "total_matches": total,
            "wins": wins,
            "win_rate": round(wins / total, 3),
            "avg_match_rating": avg_rating,
        })

    # Sort by requested metric
    sort_key = metric if metric in ("win_rate", "avg_match_rating", "total_matches", "wins") else "win_rate"
    leaderboard.sort(key=lambda x: x.get(sort_key, 0), reverse=True)
    return leaderboard[:limit]


def world_summary(
    db: Session,
    world_id: str,
) -> Dict[str, Any]:
    """High-level summary stats for a world."""
    from models.game_models import (
        WorldDB, GameFederationDB, GameWrestlerDB, ContractDB,
    )
    from models.show_models import ShowDB, MatchDB
    from models.social_models import StorylineDB

    world = db.query(WorldDB).filter(WorldDB.id == world_id).first()
    if not world:
        return {"error": "World not found"}

    return {
        "world_id": world_id,
        "name": world.name,
        "game_date": getattr(world, "current_game_date", "?"),
        "tick": getattr(world, "current_tick", 0),
        "federations": db.query(func.count(GameFederationDB.id)).filter(
            GameFederationDB.world_id == world_id
        ).scalar() or 0,
        "wrestlers": db.query(func.count(GameWrestlerDB.id)).filter(
            GameWrestlerDB.world_id == world_id
        ).scalar() or 0,
        "active_contracts": db.query(func.count(ContractDB.id)).filter(
            ContractDB.world_id == world_id, ContractDB.status == "active"
        ).scalar() or 0,
        "shows_completed": db.query(func.count(ShowDB.id)).filter(
            ShowDB.world_id == world_id, ShowDB.is_completed == True
        ).scalar() or 0,
        "total_matches": db.query(func.count(MatchDB.id)).filter(
            MatchDB.world_id == world_id
        ).scalar() or 0,
        "active_storylines": db.query(func.count(StorylineDB.id)).filter(
            StorylineDB.world_id == world_id, StorylineDB.status == "active"
        ).scalar() or 0,
    }
