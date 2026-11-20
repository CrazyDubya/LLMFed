"""Tests for the show booking service."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    ContractDB, MatchDB, MatchParticipantDB, GameFederationDB, GameWrestlerDB, PPVEventDB, WorldDB,
)
from game_service.world_service import create_world
from game_service.show_service import (
    create_show, book_match, book_promo_segment, get_show_card,
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
    fed = db_session.query(GameFederationDB).filter(
        GameFederationDB.world_id == world.id
    ).first()
    return world, fed


class TestShowCreation:
    def test_create_show(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(
            db_session, world.id, fed.id,
            "Monday Night", show_type="weekly",
            game_date="2026-01-05",
        )
        assert show.id is not None
        assert show.name == "Monday Night"
        assert show.show_type == "weekly"

    def test_book_match_on_show(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(db_session, world.id, fed.id, "Test Show", game_date="2026-01-05")

        wrestlers = db_session.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == world.id
        ).limit(2).all()

        seg = book_match(
            db_session, show.id, world.id,
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
        parts = db_session.query(MatchParticipantDB).filter(
            MatchParticipantDB.match_id == match.id
        ).all()
        assert len(parts) == 2

    def test_book_promo_segment(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(db_session, world.id, fed.id, "Promo Show", game_date="2026-01-05")

        seg = book_promo_segment(db_session, show.id, "Big promo time")
        assert seg.segment_type == "promo"
        assert seg.description == "Big promo time"

    def test_multiple_segments_auto_position(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(db_session, world.id, fed.id, "Multi Show", game_date="2026-01-05")

        wrestlers = db_session.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == world.id
        ).limit(4).all()

        seg1 = book_match(db_session, show.id, world.id,
                          [wrestlers[0].id, wrestlers[1].id])
        seg2 = book_promo_segment(db_session, show.id, "Mid-show promo")
        seg3 = book_match(db_session, show.id, world.id,
                          [wrestlers[2].id, wrestlers[3].id])

        assert seg1.position == 1
        assert seg2.position == 2
        assert seg3.position == 3

    def test_get_show_card(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(db_session, world.id, fed.id, "Card Show", game_date="2026-01-05")

        wrestlers = db_session.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == world.id
        ).limit(2).all()

        book_match(db_session, show.id, world.id, [w.id for w in wrestlers])
        book_promo_segment(db_session, show.id, "Promo")
        db_session.commit()

        card = get_show_card(db_session, show.id)
        assert len(card) == 2
        assert card[0].position < card[1].position


class TestNPCBooking:
    def test_completed_show_rejects_booking(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(db_session, world.id, fed.id, "Completed show")
        show.is_completed = True
        db_session.flush()
        wrestlers = db_session.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == world.id,
        ).limit(2).all()
        for book in [
            lambda: book_match(db_session, show.id, world.id, [w.id for w in wrestlers]),
            lambda: book_promo_segment(db_session, show.id),
            lambda: npc_book_card(db_session, show),
        ]:
            with pytest.raises(ValueError, match="Cannot book segments on a completed show"):
                book()
        assert get_show_card(db_session, show.id) == []

    @pytest.mark.parametrize("roster_size", [0, 12])
    def test_npc_booking_select_count(self, db_session, roster_size):
        world = WorldDB(name="SQL count world")
        db_session.add(world)
        db_session.flush()
        fed = GameFederationDB(world_id=world.id, name="SQL count federation")
        db_session.add(fed)
        db_session.flush()
        for i in range(roster_size):
            wrestler = GameWrestlerDB(world_id=world.id, name=f"Wrestler {i}", is_npc=True)
            db_session.add(wrestler)
            db_session.flush()
            db_session.add(ContractDB(
                world_id=world.id, federation_id=fed.id, wrestler_id=wrestler.id,
                start_date="2026-01-01",
            ))
        show = create_show(db_session, world.id, fed.id, "SQL count show")
        statements = []

        def count_selects(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(db_session.bind, "before_cursor_execute", count_selects)
        try:
            segments = npc_book_card(db_session, show)
        finally:
            event.remove(db_session.bind, "before_cursor_execute", count_selects)

        if roster_size:
            assert len(segments) >= 3
            assert len(statements) <= 18
            assert sum("FROM shows" in sql for sql in statements) == 1
            assert sum("count(" in sql.lower() and "show_segments" in sql for sql in statements) == 1
            card = get_show_card(db_session, show.id)
            assert [seg.position for seg in card] == list(range(1, len(card) + 1))
        else:
            assert segments == []
            assert len(statements) == 2

    @pytest.mark.parametrize("main_event", [False, True], ids=["undercard", "main-event"])
    @pytest.mark.parametrize("available_count", [4, 3], ids=["complete-pairs", "injured-partner"])
    def test_npc_books_ppv_tag_match_only_with_both_pairs(self, db_session, main_event, available_count):
        world = WorldDB(name="PPV World")
        db_session.add(world)
        db_session.flush()
        fed = GameFederationDB(world_id=world.id, name="PPV Federation")
        wrestlers = [
            GameWrestlerDB(world_id=world.id, name=f"Wrestler {i}", is_injured=i >= available_count)
            for i in range(4)
        ]
        db_session.add_all([fed, *wrestlers])
        db_session.flush()
        wrestler_ids = [w.id for w in wrestlers]
        db_session.add_all(
            ContractDB(world_id=world.id, federation_id=fed.id, wrestler_id=wid, start_date="2026-01-01")
            for wid in wrestler_ids
        )
        show = create_show(db_session, world.id, fed.id, "PPV", show_type="ppv", game_date="2026-01-05")
        tag_plan = {"match_type": "tag_team", "wrestler_ids": wrestler_ids}
        ppv = PPVEventDB(
            world_id=world.id, federation_id=fed.id, name=show.name, scheduled_date=show.game_date,
            planned_main_event=tag_plan if main_event else {},
            planned_matches=[] if main_event else [tag_plan],
        )

        segments = npc_book_card(db_session, show, ppv_event=ppv)

        assert len(segments) == 1
        match = db_session.get(MatchDB, segments[0].match_id)
        if available_count == 4:
            assert match.match_type == "tag_team"
            assert {p.wrestler_id: p.team for p in match.participants} == dict(zip(wrestler_ids, [0, 0, 1, 1]))
        else:
            assert match.match_type == "singles"
            assert {p.wrestler_id for p in match.participants} <= set(wrestler_ids[:available_count])

    def test_npc_book_card_creates_matches(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(db_session, world.id, fed.id, "NPC Show", game_date="2026-01-05")

        segments = npc_book_card(db_session, show)
        db_session.commit()

        assert len(segments) > 0
        # All match segments should have valid matches
        for seg in segments:
            assert seg.match_id is not None
            match = db_session.query(MatchDB).filter(
                MatchDB.id == seg.match_id
            ).first()
            assert match is not None

    def test_npc_no_duplicate_wrestlers(self, db_session, world_with_fed):
        world, fed = world_with_fed
        show = create_show(db_session, world.id, fed.id, "Unique Show", game_date="2026-01-05")

        segments = npc_book_card(db_session, show)
        db_session.commit()

        # Collect all wrestler IDs across matches
        all_wrestler_ids = []
        for seg in segments:
            parts = db_session.query(MatchParticipantDB).filter(
                MatchParticipantDB.match_id == seg.match_id
            ).all()
            for p in parts:
                all_wrestler_ids.append(p.wrestler_id)

        # No wrestler should appear twice
        assert len(all_wrestler_ids) == len(set(all_wrestler_ids))
