"""Tests for the show booking service."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    MatchDB,
    MatchParticipantDB,
    GameFederationDB,
    GameWrestlerDB,
)
from game_service.world_service import create_world
from game_service.show_service import (
    create_show,
    book_match,
    book_promo_segment,
    get_show_card,
    npc_book_card,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def world_with_fed(db_session):
    """Create a world and return (world, first_federation)."""
    world = create_world(db_session, "Show Test World")
    fed = (
        db_session.query(GameFederationDB)
        .filter(GameFederationDB.world_id == world.id)
        .first()
    )
    return world, fed


class TestShowCreation:
    def test_create_show(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(
            db_session,
            world.id,
            fed.id,
            "Monday Night",
            show_type="weekly",
            game_date="2026-01-05",
        )
        assert show.id is not None
        assert show.name == "Monday Night"
        assert show.show_type == "weekly"

    def test_book_match_on_show(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(
            db_session, world.id, fed.id, "Test Show", game_date="2026-01-05"
        )

        wrestlers = (
            db_session.query(GameWrestlerDB)
            .filter(GameWrestlerDB.world_id == world.id)
            .limit(2)
            .all()
        )

        seg = book_match(
            db_session,
            show.id,
            world.id,
            wrestler_ids=[w.id for w in wrestlers],
            planned_winner_id=wrestlers[0].id,
        )
        db_session.commit()

        assert seg.segment_type == "match"
        assert seg.match_id is not None
        assert seg.position == 1

        # Match and participants created
        match = db_session.query(MatchDB).filter(MatchDB.id == seg.match_id).first()
        assert match is not None
        parts = (
            db_session.query(MatchParticipantDB)
            .filter(MatchParticipantDB.match_id == match.id)
            .all()
        )
        assert len(parts) == 2

    def test_book_promo_segment(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(
            db_session, world.id, fed.id, "Promo Show", game_date="2026-01-05"
        )

        seg = book_promo_segment(db_session, show.id, "Big promo time")
        assert seg.segment_type == "promo"
        assert seg.description == "Big promo time"

    def test_multiple_segments_auto_position(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(
            db_session, world.id, fed.id, "Multi Show", game_date="2026-01-05"
        )

        wrestlers = (
            db_session.query(GameWrestlerDB)
            .filter(GameWrestlerDB.world_id == world.id)
            .limit(4)
            .all()
        )

        seg1 = book_match(
            db_session, show.id, world.id, [wrestlers[0].id, wrestlers[1].id]
        )
        seg2 = book_promo_segment(db_session, show.id, "Mid-show promo")
        seg3 = book_match(
            db_session, show.id, world.id, [wrestlers[2].id, wrestlers[3].id]
        )

        assert seg1.position == 1
        assert seg2.position == 2
        assert seg3.position == 3

    def test_get_show_card(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(
            db_session, world.id, fed.id, "Card Show", game_date="2026-01-05"
        )

        wrestlers = (
            db_session.query(GameWrestlerDB)
            .filter(GameWrestlerDB.world_id == world.id)
            .limit(2)
            .all()
        )

        book_match(db_session, show.id, world.id, [w.id for w in wrestlers])
        book_promo_segment(db_session, show.id, "Promo")
        db_session.commit()

        card = get_show_card(db_session, show.id)
        assert len(card) == 2
        assert card[0].position < card[1].position


class TestNPCBooking:
    def test_npc_book_card_creates_matches(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(
            db_session, world.id, fed.id, "NPC Show", game_date="2026-01-05"
        )

        segments = npc_book_card(db_session, show)
        db_session.commit()

        assert len(segments) > 0
        # All match segments should have valid matches
        for seg in segments:
            assert seg.match_id is not None
            match = db_session.query(MatchDB).filter(MatchDB.id == seg.match_id).first()
            assert match is not None

    def test_npc_no_duplicate_wrestlers(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(
            db_session, world.id, fed.id, "Unique Show", game_date="2026-01-05"
        )

        segments = npc_book_card(db_session, show)
        db_session.commit()

        # Collect all wrestler IDs across matches
        all_wrestler_ids = []
        for seg in segments:
            parts = (
                db_session.query(MatchParticipantDB)
                .filter(MatchParticipantDB.match_id == seg.match_id)
                .all()
            )
            for p in parts:
                all_wrestler_ids.append(p.wrestler_id)

        # No wrestler should appear twice
        assert len(all_wrestler_ids) == len(set(all_wrestler_ids))
