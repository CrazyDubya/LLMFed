"""Tests for move engine."""

import pytest
from core_engine.move_engine import (
    MoveEngine,
    _cycle_position,
    _infer_style,
    FINISHER_IDS,
    MOVE_BY_ID,
    ALL_MOVES,
)


def test_cycle_position():
    """Position cycles through standing, ground, corner, ropes, top_rope."""
    assert _cycle_position(1) == "standing"
    assert _cycle_position(5) == "ground"
    assert _cycle_position(8) == "corner"
    assert _cycle_position(10) == "ropes"
    assert _cycle_position(11) == "top_rope"


def test_infer_style():
    """Style inferred from gimmick keywords."""
    assert _infer_style("powerhouse slam artist") == "powerhouse"
    assert _infer_style("technical mat wrestler") == "technical"
    assert _infer_style("high-flying acrobat") == "high_flyer"
    assert _infer_style("street brawler") == "brawler"
    assert _infer_style("submission specialist") == "submission"
    assert _infer_style("generic fighter") == "brawler"  # No style keywords → default brawler


def test_get_available_moves_returns_tuples():
    """get_available_moves returns list of (id, desc) tuples."""
    moves = MoveEngine.get_available_moves(
        position="standing",
        momentum=0,
        style="brawler",
    )
    assert isinstance(moves, list)
    assert len(moves) >= 5
    for m in moves:
        assert isinstance(m, tuple)
        assert len(m) == 2
        assert isinstance(m[0], str)
        assert isinstance(m[1], str)


def test_get_available_moves_filters_by_position():
    """ground position returns different moves than standing."""
    standing = MoveEngine.get_available_moves(position="standing", momentum=0, style="brawler")
    ground = MoveEngine.get_available_moves(position="ground", momentum=0, style="brawler")
    # Ground has stomp, elbow_drop etc; standing has punch, kick etc
    standing_ids = {m[0] for m in standing}
    ground_ids = {m[0] for m in ground}
    assert "stomp" in ground_ids or "elbow_drop" in ground_ids
    assert "punch" in standing_ids or "kick" in standing_ids


def test_get_available_moves_filters_by_momentum():
    """Finishers appear when momentum is high enough."""
    low = MoveEngine.get_available_moves(position="standing", momentum=0, style="powerhouse")
    high = MoveEngine.get_available_moves(position="standing", momentum=50, style="powerhouse")
    low_ids = {m[0] for m in low}
    high_ids = {m[0] for m in high}
    # Chokeslam needs momentum_min 35; should appear in high
    assert "chokeslam" in high_ids


def test_is_finisher():
    """is_finisher identifies finisher moves."""
    assert MoveEngine.is_finisher("chokeslam") is True
    assert MoveEngine.is_finisher("stunner") is True
    assert MoveEngine.is_finisher("punch") is False
    assert MoveEngine.is_finisher("unknown") is False


def test_finisher_ids_nonempty():
    """At least one finisher in pool."""
    assert len(FINISHER_IDS) >= 5
    assert "chokeslam" in FINISHER_IDS
