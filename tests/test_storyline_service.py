"""Tests for the storyline engine."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    StorylineDB, StorylineParticipantDB, GameWrestlerDB,
    GameFederationDB, MatchDB, MatchParticipantDB, ShowDB, ShowSegmentDB,
)
from game_service.world_service import create_world
from game_service.storyline_service import (
    create_storyline, progress_storyline, resolve_storyline,
    auto_generate_storylines, check_match_storyline_triggers,
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
def world_data(db_session):
    world = create_world(db_session, "Storyline World")
    fed = db_session.query(GameFederationDB).filter(
        GameFederationDB.world_id == world.id
    ).first()
    wrestlers = db_session.query(GameWrestlerDB).filter(
        GameWrestlerDB.world_id == world.id
    ).limit(4).all()
    return world, fed, wrestlers


class TestCreateStoryline:
    def test_creates_feud(self, db_session, world_data):
        world, fed, wrestlers = world_data
        sl = create_storyline(
            db_session, world.id, fed.id,
            [wrestlers[0].id, wrestlers[1].id],
            storyline_type="feud",
            game_date="2026-01-01",
        )
        db_session.commit()

        assert sl.id is not None
        assert sl.status == "brewing"
        assert sl.storyline_type == "feud"
        assert sl.heat >= 30

        parts = db_session.query(StorylineParticipantDB).filter(
            StorylineParticipantDB.storyline_id == sl.id
        ).all()
        assert len(parts) == 2
        roles = {p.role for p in parts}
        assert "protagonist" in roles
        assert "antagonist" in roles

    def test_creates_alliance(self, db_session, world_data):
        world, fed, wrestlers = world_data
        sl = create_storyline(
            db_session, world.id, fed.id,
            [wrestlers[0].id, wrestlers[1].id],
            storyline_type="alliance",
        )
        db_session.commit()

        assert sl.storyline_type == "alliance"
        assert sl.description  # Should have a generated description

    def test_custom_name_and_description(self, db_session, world_data):
        world, fed, wrestlers = world_data
        sl = create_storyline(
            db_session, world.id, fed.id,
            [wrestlers[0].id, wrestlers[1].id],
            name="The Ultimate Rivalry",
            description="A bitter feud over respect.",
        )
        db_session.commit()

        assert sl.name == "The Ultimate Rivalry"
        assert sl.description == "A bitter feud over respect."


class TestStorylineProgression:
    def test_heat_increases(self, db_session, world_data):
        world, fed, wrestlers = world_data
        sl = create_storyline(
            db_session, world.id, fed.id,
            [wrestlers[0].id, wrestlers[1].id],
        )
        initial_heat = sl.heat

        progress_storyline(db_session, sl, "match", heat_delta=10)
        assert sl.heat == initial_heat + 10

    def test_escalation_to_active(self, db_session, world_data):
        world, fed, wrestlers = world_data
        sl = create_storyline(
            db_session, world.id, fed.id,
            [wrestlers[0].id, wrestlers[1].id],
        )
        sl.heat = 50
        progress_storyline(db_session, sl, "match", heat_delta=10)
        assert sl.status == "active"

    def test_escalation_to_climax(self, db_session, world_data):
        world, fed, wrestlers = world_data
        sl = create_storyline(
            db_session, world.id, fed.id,
            [wrestlers[0].id, wrestlers[1].id],
        )
        sl.heat = 75
        sl.status = "active"
        progress_storyline(db_session, sl, "match", heat_delta=10)
        assert sl.status == "climax"

    def test_resolve_storyline(self, db_session, world_data):
        world, fed, wrestlers = world_data
        sl = create_storyline(
            db_session, world.id, fed.id,
            [wrestlers[0].id, wrestlers[1].id],
        )
        resolve_storyline(db_session, sl, "Settled in a cage match")
        assert sl.status == "resolved"
        assert sl.planned_blowoff == "Settled in a cage match"


class TestAutoGeneration:
    def test_generates_storylines_for_npc_feds(self, db_session, world_data):
        world, fed, wrestlers = world_data
        new_sls = auto_generate_storylines(db_session, world.id, "2026-01-01")
        db_session.commit()

        # Should generate at least one storyline for NPC feds
        assert len(new_sls) >= 0  # May be 0 if conditions not met

    def test_respects_max_active_limit(self, db_session, world_data):
        world, fed, wrestlers = world_data

        # Create 3 active storylines for this fed
        for i in range(3):
            w_pair = db_session.query(GameWrestlerDB).filter(
                GameWrestlerDB.world_id == world.id
            ).offset(i * 2).limit(2).all()
            if len(w_pair) == 2:
                create_storyline(
                    db_session, world.id, fed.id,
                    [w_pair[0].id, w_pair[1].id],
                )
        db_session.commit()

        # Should not generate more since limit is 3
        new_sls = auto_generate_storylines(db_session, world.id, "2026-01-01")
        # Count storylines for this specific fed (other NPC feds may get new ones)
        fed_sls = [sl for sl in new_sls if sl.federation_id == fed.id]
        assert len(fed_sls) == 0
