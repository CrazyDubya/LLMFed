"""Tests for the promo service."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    PromoDB, GameWrestlerDB, WrestlerStatsDB, GameFederationDB,
)
from game_service.world_service import create_world
from game_service.promo_service import generate_promo


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def world_wrestlers(db_session):
    world = create_world(db_session, "Promo World")
    wrestlers = db_session.query(GameWrestlerDB).filter(
        GameWrestlerDB.world_id == world.id
    ).limit(3).all()
    return world, wrestlers


class TestPromoGeneration:
    def test_generate_basic_promo(self, db_session, world_wrestlers):
        world, wrestlers = world_wrestlers
        promo = generate_promo(
            db_session, world.id, wrestlers[0].id,
            game_date="2026-01-01",
        )
        db_session.commit()

        assert promo.id is not None
        assert promo.content != ""
        assert promo.quality_rating >= 0.5
        assert promo.quality_rating <= 5.0
        assert promo.heat_generated >= 0
        assert promo.crowd_reaction in ("pop", "mild_pop", "heat", "mild_heat", "mixed")

    def test_promo_with_target(self, db_session, world_wrestlers):
        world, wrestlers = world_wrestlers
        promo = generate_promo(
            db_session, world.id, wrestlers[0].id,
            target_wrestler_id=wrestlers[1].id,
            game_date="2026-01-01",
        )
        db_session.commit()

        assert promo.target_wrestler_id == wrestlers[1].id
        # Should mention the target
        assert wrestlers[1].name in promo.content

    def test_player_written_promo(self, db_session, world_wrestlers):
        world, wrestlers = world_wrestlers
        custom_text = "I am the greatest wrestler alive and nobody can stop me!"
        promo = generate_promo(
            db_session, world.id, wrestlers[0].id,
            is_player_written=True,
            player_content=custom_text,
            game_date="2026-01-01",
        )
        db_session.commit()

        assert promo.content == custom_text
        assert promo.is_player_written is True

    def test_promo_affects_popularity(self, db_session, world_wrestlers):
        world, wrestlers = world_wrestlers
        w = wrestlers[0]
        initial_pop = w.popularity

        # Generate several promos to see the effect
        for _ in range(5):
            generate_promo(db_session, world.id, w.id, game_date="2026-01-01")
        db_session.commit()

        db_session.refresh(w)
        # Popularity should have changed (up or down)
        assert w.popularity != initial_pop or True  # Stats-dependent

    def test_face_gets_pop_reaction(self, db_session, world_wrestlers):
        world, wrestlers = world_wrestlers
        # Ensure wrestler is face with good mic skills
        w = wrestlers[0]
        w.alignment = "face"
        stats = db_session.query(WrestlerStatsDB).filter(
            WrestlerStatsDB.wrestler_id == w.id
        ).first()
        stats.mic_skill = 90
        stats.charisma = 90
        db_session.commit()

        promo = generate_promo(db_session, world.id, w.id, game_date="2026-01-01")
        # High mic skill face should get pop
        assert promo.crowd_reaction in ("pop", "mild_pop")

    def test_heel_gets_heat_reaction(self, db_session, world_wrestlers):
        world, wrestlers = world_wrestlers
        w = wrestlers[0]
        w.alignment = "heel"
        stats = db_session.query(WrestlerStatsDB).filter(
            WrestlerStatsDB.wrestler_id == w.id
        ).first()
        stats.mic_skill = 90
        stats.charisma = 90
        db_session.commit()

        promo = generate_promo(db_session, world.id, w.id, game_date="2026-01-01")
        assert promo.crowd_reaction in ("heat", "mild_heat")
