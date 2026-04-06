"""
Tests for the wrestler persona duality system.

Covers: backstory generation, gimmick creation/evolution, life events,
social media posts, persona-aware promos, kayfabe collision detection.
"""

import pytest
import random
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# We test with in-memory SQLite
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    GameWrestlerDB, WrestlerStatsDB, WrestlerBackstoryDB,
    GimmickHistoryDB, LifeEventDB, SocialMediaPostDB,
    WrestlerRelationshipDB, GameFederationDB, ContractDB,
    WorldDB, StorylineDB, StorylineParticipantDB, PromoDB,
    WorldNewsDB,
)


@pytest.fixture
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def world(db_session):
    """Create a test world."""
    w = WorldDB(
        id="world1",
        name="Test World",
        current_game_date="2026-03-01",
        current_tick=1,
    )
    db_session.add(w)
    db_session.flush()
    return w


@pytest.fixture
def federation(db_session, world):
    """Create a test federation."""
    fed = GameFederationDB(
        id="fed1",
        world_id=world.id,
        name="Test Wrestling Federation",
        short_name="TWF",
        kayfabe_strictness=50,
        allows_worked_shoots=True,
        social_media_policy="guided",
    )
    db_session.add(fed)
    db_session.flush()
    return fed


@pytest.fixture
def wrestler(db_session, world):
    """Create a test wrestler."""
    w = GameWrestlerDB(
        id="w1",
        world_id=world.id,
        name="Thunder McSlam",
        real_name="John Smith",
        gimmick="A powerhouse brawler",
        alignment="face",
        popularity=60,
        morale=70,
        age=28,
        hometown="Dallas, TX",
        catchphrase="Feel the thunder!",
        finisher_name="Thunder Driver",
        finisher_type="power",
        personality_traits={"aggression": 70, "charisma_style": "intense"},
        kayfabe_commitment=60,
        character_depth=40,
    )
    db_session.add(w)
    stats = WrestlerStatsDB(
        wrestler_id=w.id,
        power=75, speed=50, technical=40, aerial=30,
        brawling=80, submission=30, stamina=70, toughness=75,
        charisma=65, mic_skill=55, psychology=50, selling=45,
    )
    db_session.add(stats)
    db_session.flush()
    return w


@pytest.fixture
def wrestler2(db_session, world):
    """Create a second test wrestler."""
    w = GameWrestlerDB(
        id="w2",
        world_id=world.id,
        name="Dark Phantom",
        real_name="Mike Jones",
        gimmick="A mysterious heel",
        alignment="heel",
        popularity=55,
        morale=65,
        age=30,
        hometown="Chicago, IL",
        kayfabe_commitment=80,
        character_depth=50,
    )
    db_session.add(w)
    stats = WrestlerStatsDB(
        wrestler_id=w.id,
        power=60, speed=65, technical=70, aerial=40,
        brawling=50, submission=60, stamina=65, toughness=60,
        charisma=70, mic_skill=75, psychology=65, selling=60,
    )
    db_session.add(stats)
    db_session.flush()
    return w


# ===================================================================
# Backstory tests
# ===================================================================

class TestBackstoryGeneration:
    def test_generate_backstory(self, db_session, wrestler):
        from game_service.persona_service import generate_backstory
        backstory = generate_backstory(db_session, wrestler)

        assert backstory is not None
        assert backstory.wrestler_id == wrestler.id
        assert backstory.origin_story is not None
        assert len(backstory.origin_story) > 10
        assert backstory.family_situation in [
            "single", "married", "married_with_kids", "divorced",
            "divorced_with_kids", "long_term_relationship",
            "estranged_family", "close_family",
        ]
        assert backstory.wrestling_motivation is not None
        assert backstory.real_personality is not None
        assert "temperament" in backstory.real_personality
        assert "ambition" in backstory.real_personality
        assert 0 <= backstory.personal_life_stability <= 100

    def test_backstory_persists(self, db_session, wrestler):
        from game_service.persona_service import generate_backstory
        generate_backstory(db_session, wrestler)
        db_session.flush()

        loaded = db_session.query(WrestlerBackstoryDB).filter(
            WrestlerBackstoryDB.wrestler_id == wrestler.id,
        ).first()
        assert loaded is not None
        assert loaded.origin_story is not None


# ===================================================================
# Gimmick tests
# ===================================================================

class TestGimmickGeneration:
    def test_generate_initial_gimmick(self, db_session, wrestler):
        from game_service.persona_service import generate_initial_gimmick
        gimmick = generate_initial_gimmick(db_session, wrestler, "2026-03-01")

        assert gimmick is not None
        assert gimmick.wrestler_id == wrestler.id
        assert gimmick.is_active is True
        assert gimmick.archetype in [
            "monster_heel", "underdog_face", "cocky_technician",
            "silent_assassin", "cult_leader", "comedy_act",
            "anti_hero", "legacy", "patriot", "daredevil",
        ]
        assert gimmick.staleness == 0
        assert gimmick.depth_score > 0
        assert gimmick.voice_style is not None

    def test_gimmick_staleness_increases(self, db_session, wrestler):
        from game_service.persona_service import (
            generate_initial_gimmick, tick_gimmick_staleness,
        )
        gimmick = generate_initial_gimmick(db_session, wrestler, "2026-03-01")
        initial_staleness = gimmick.staleness

        tick_gimmick_staleness(db_session, wrestler, "2026-03-08")
        assert gimmick.staleness >= initial_staleness

    def test_repackaging_pressure(self, db_session, wrestler):
        from game_service.persona_service import (
            generate_initial_gimmick, check_repackaging_pressure,
        )
        gimmick = generate_initial_gimmick(db_session, wrestler, "2026-03-01")
        gimmick.staleness = 80
        gimmick.effectiveness = 20
        gimmick.fan_investment = 10

        pressure = check_repackaging_pressure(db_session, wrestler)
        assert pressure["pressure"] >= 60
        assert pressure["reason"] != "none"

    def test_execute_gimmick_change(self, db_session, wrestler):
        from game_service.persona_service import (
            generate_initial_gimmick, execute_gimmick_change,
        )
        old_gimmick = generate_initial_gimmick(db_session, wrestler, "2026-03-01")
        old_archetype = old_gimmick.archetype

        new_gimmick = execute_gimmick_change(
            db_session, wrestler, "2026-06-01", "stale_gimmick",
        )

        assert old_gimmick.is_active is False
        assert old_gimmick.end_date == "2026-06-01"
        assert new_gimmick.is_active is True
        assert new_gimmick.archetype != old_archetype
        assert new_gimmick.staleness == 0
        assert wrestler.gimmick_changes >= 1

    def test_evolve_gimmick_depth(self, db_session, wrestler):
        from game_service.persona_service import (
            generate_initial_gimmick, evolve_gimmick,
        )
        gimmick = generate_initial_gimmick(db_session, wrestler, "2026-03-01")
        initial_depth = gimmick.depth_score

        wrestler.last_booked_date = "2026-03-08"
        evolve_gimmick(db_session, wrestler, "2026-03-08")
        assert gimmick.depth_score >= initial_depth


# ===================================================================
# Life event tests
# ===================================================================

class TestLifeEvents:
    def test_generate_life_event_low_probability(self, db_session, wrestler, world):
        from game_service.persona_service import generate_backstory, generate_life_event
        generate_backstory(db_session, wrestler)

        # With 3% chance, most calls return None
        results = [
            generate_life_event(db_session, wrestler.id, world.id, "2026-03-01")
            for _ in range(20)
        ]
        none_count = sum(1 for r in results if r is None)
        assert none_count > 10  # Most should be None

    def test_generate_life_event_forced(self, db_session, wrestler, world):
        from game_service.persona_service import generate_backstory
        generate_backstory(db_session, wrestler)

        # Directly seed a life event
        event = LifeEventDB(
            wrestler_id=wrestler.id,
            world_id=world.id,
            game_date="2026-03-01",
            event_type="marriage",
            description="Thunder McSlam got married.",
            severity=4,
            is_public=True,
            morale_impact=15,
            performance_impact=0,
            storyline_potential=False,
        )
        db_session.add(event)
        db_session.flush()

        loaded = db_session.query(LifeEventDB).filter(
            LifeEventDB.wrestler_id == wrestler.id,
        ).first()
        assert loaded is not None
        assert loaded.event_type == "marriage"

    def test_process_life_event_effects(self, db_session, wrestler, world):
        from game_service.persona_service import (
            generate_backstory, process_life_event_effects,
        )
        generate_backstory(db_session, wrestler)
        initial_morale = wrestler.morale

        event = LifeEventDB(
            wrestler_id=wrestler.id,
            world_id=world.id,
            game_date="2026-03-01",
            event_type="death_in_family",
            description="Lost a family member.",
            severity=9,
            morale_impact=-25,
            performance_impact=-10,
            is_active=True,
        )
        db_session.add(event)
        db_session.flush()

        process_life_event_effects(db_session, event)
        assert wrestler.morale < initial_morale


# ===================================================================
# Social media tests
# ===================================================================

class TestSocialMedia:
    def test_generate_social_post(self, db_session, wrestler, world):
        from game_service.social_media_service import generate_social_post
        post = generate_social_post(db_session, wrestler.id, world.id, "2026-03-01")

        assert post is not None
        assert post.wrestler_id == wrestler.id
        assert post.content is not None
        assert len(post.content) > 0
        assert post.post_type in ["kayfabe", "shoot", "worked_shoot", "personal"]
        assert post.platform in ["twitter", "instagram", "tiktok", "youtube"]
        assert 0 <= post.engagement_score <= 100

    def test_feud_exchange(self, db_session, wrestler, wrestler2, world):
        from game_service.social_media_service import generate_feud_exchange
        posts = generate_feud_exchange(
            db_session, wrestler.id, wrestler2.id, world.id, "2026-03-01",
        )

        assert len(posts) == 2
        assert posts[0].wrestler_id == wrestler.id
        assert posts[1].wrestler_id == wrestler2.id
        assert posts[0].target_wrestler_id == wrestler2.id
        assert posts[1].target_wrestler_id == wrestler.id

    def test_viral_moment_detection(self):
        from game_service.social_media_service import check_viral_moment
        # High-controversy post should have higher viral chance
        post = MagicMock()
        post.controversy_level = 80
        post.engagement_score = 90
        post.post_type = "worked_shoot"
        post.kayfabe_break_level = 70

        # Run many times — should go viral at least once
        random.seed(42)
        results = [check_viral_moment(post) for _ in range(100)]
        assert any(results)


# ===================================================================
# Persona-aware promo tests
# ===================================================================

class TestPersonaPromos:
    def test_promo_with_gimmick(self, db_session, wrestler, world):
        from game_service.persona_service import generate_initial_gimmick
        from game_service.promo_service import generate_promo

        generate_initial_gimmick(db_session, wrestler, "2026-03-01")
        promo = generate_promo(
            db_session, world.id, wrestler.id,
            game_date="2026-03-01",
        )

        assert promo is not None
        assert promo.content is not None
        assert len(promo.content) > 10
        assert promo.quality_rating >= 0.5

    def test_promo_falls_back_without_gimmick(self, db_session, wrestler, world):
        from game_service.promo_service import generate_promo
        # No gimmick data — should use legacy templates
        promo = generate_promo(
            db_session, world.id, wrestler.id,
            game_date="2026-03-01",
        )

        assert promo is not None
        assert promo.content is not None

    def test_promo_with_target(self, db_session, wrestler, wrestler2, world):
        from game_service.persona_service import generate_initial_gimmick
        from game_service.promo_service import generate_promo

        generate_initial_gimmick(db_session, wrestler, "2026-03-01")
        promo = generate_promo(
            db_session, world.id, wrestler.id,
            target_wrestler_id=wrestler2.id,
            game_date="2026-03-01",
        )

        assert promo is not None
        assert promo.target_wrestler_id == wrestler2.id

    def test_promo_quality_improved_by_gimmick_depth(self, db_session, wrestler, world):
        from game_service.persona_service import generate_initial_gimmick
        from game_service.promo_service import generate_promo

        gimmick = generate_initial_gimmick(db_session, wrestler, "2026-03-01")
        gimmick.depth_score = 90
        gimmick.effectiveness = 85

        # Generate many promos and check average quality
        random.seed(42)
        qualities = []
        for _ in range(20):
            promo = generate_promo(
                db_session, world.id, wrestler.id,
                game_date="2026-03-01",
            )
            qualities.append(promo.quality_rating)

        avg_quality = sum(qualities) / len(qualities)
        assert avg_quality > 2.0  # Should be above average with deep gimmick


# ===================================================================
# Collision detection tests
# ===================================================================

class TestCollisionDetection:
    def test_crisis_during_push(self, db_session, wrestler, world):
        from game_service.persona_service import (
            generate_backstory, detect_collision_events,
        )
        generate_backstory(db_session, wrestler)
        wrestler.popularity = 80

        event = LifeEventDB(
            wrestler_id=wrestler.id, world_id=world.id,
            game_date="2026-03-01", event_type="death_in_family",
            description="Lost family member", severity=9,
            is_active=True, morale_impact=-25, performance_impact=-10,
        )
        db_session.add(event)
        db_session.flush()

        collisions = detect_collision_events(db_session, wrestler, "2026-03-01")
        types = [c["type"] for c in collisions]
        assert "crisis_during_push" in types

    def test_friends_as_rivals(self, db_session, wrestler, wrestler2, world):
        from game_service.persona_service import detect_collision_events

        rel = WrestlerRelationshipDB(
            world_id=world.id,
            wrestler1_id=wrestler.id,
            wrestler2_id=wrestler2.id,
            real_relationship="friends",
            kayfabe_alignment="rivals",
        )
        db_session.add(rel)
        db_session.flush()

        collisions = detect_collision_events(db_session, wrestler, "2026-03-01")
        types = [c["type"] for c in collisions]
        assert "friends_as_rivals" in types

    def test_facade_cracking(self, db_session, wrestler, world):
        from game_service.persona_service import (
            generate_backstory, detect_collision_events,
        )
        backstory = generate_backstory(db_session, wrestler)
        backstory.personal_life_stability = 20
        wrestler.kayfabe_commitment = 85

        collisions = detect_collision_events(db_session, wrestler, "2026-03-01")
        types = [c["type"] for c in collisions]
        assert "facade_cracking" in types


# ===================================================================
# Migration tests
# ===================================================================

class TestMigration:
    def test_migrate_existing_wrestlers(self, db_session, wrestler, world):
        from game_service.persona_service import migrate_existing_wrestlers

        count = migrate_existing_wrestlers(db_session, world.id)
        assert count >= 1

        backstory = db_session.query(WrestlerBackstoryDB).filter(
            WrestlerBackstoryDB.wrestler_id == wrestler.id,
        ).first()
        assert backstory is not None

        gimmick = db_session.query(GimmickHistoryDB).filter(
            GimmickHistoryDB.wrestler_id == wrestler.id,
            GimmickHistoryDB.is_active == True,
        ).first()
        assert gimmick is not None

    def test_migrate_is_idempotent(self, db_session, wrestler, world):
        from game_service.persona_service import migrate_existing_wrestlers

        count1 = migrate_existing_wrestlers(db_session, world.id)
        count2 = migrate_existing_wrestlers(db_session, world.id)
        assert count2 == 0  # Already migrated


# ===================================================================
# Kayfabe storyline tests
# ===================================================================

class TestKayfabeSpectrum:
    def test_create_storyline_with_kayfabe_level(self, db_session, world, federation, wrestler, wrestler2):
        from game_service.storyline_service import create_storyline

        sl = create_storyline(
            db_session, world.id, federation.id,
            [wrestler.id, wrestler2.id],
            storyline_type="feud",
            game_date="2026-03-01",
            kayfabe_level=30,
        )
        assert sl.kayfabe_level == 30

    def test_default_kayfabe_level(self, db_session, world, federation, wrestler, wrestler2):
        from game_service.storyline_service import create_storyline

        sl = create_storyline(
            db_session, world.id, federation.id,
            [wrestler.id, wrestler2.id],
            game_date="2026-03-01",
        )
        assert sl.kayfabe_level == 100  # Default pure kayfabe
