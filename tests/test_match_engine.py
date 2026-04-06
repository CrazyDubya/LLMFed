"""Tests for the match simulation engine."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    WorldDB, GameWrestlerDB, WrestlerStatsDB, MatchDB, MatchParticipantDB,
    MatchEventDB, GameFederationDB, ShowDB, ShowSegmentDB, ChampionshipDB,
)
from core_engine.match_engine import (
    MatchSimulator, MatchParticipantState, MatchResult, simulate_match_from_db,
)
from game_service.world_service import create_world


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_participant(name, wrestler_id="w1", style="allrounder", **overrides):
    """Create a MatchParticipantState for testing."""
    base_stats = {
        "power": 50, "technical": 50, "aerial": 50, "brawling": 50,
        "submission": 50, "stamina": 50, "toughness": 50, "speed": 50,
        "charisma": 50, "psychology": 50, "selling": 50,
    }
    base_stats.update(overrides.pop("stats", {}))
    defaults = {
        "wrestler_id": wrestler_id,
        "name": name,
        "health": 100.0,
        "momentum": 50.0,
        "stamina": 100.0,
        "finisher_available": False,
        "finisher_used": False,
        "stats": base_stats,
        "finisher_name": "The Finisher",
        "alignment": "face",
    }
    defaults.update(overrides)
    return MatchParticipantState(**defaults)


class TestMatchSimulator:
    def test_basic_match_produces_result(self):
        p1 = _make_participant("Hero", "w1", alignment="face")
        p2 = _make_participant("Villain", "w2", alignment="heel")
        sim = MatchSimulator(planned_winner_id="w1")
        result = sim.simulate([p1, p2])

        assert isinstance(result, MatchResult)
        assert result.duration_ticks > 0
        assert len(result.spots) > 0
        assert result.match_rating >= 0.0
        assert result.crowd_heat >= 0

    def test_planned_winner_usually_wins(self):
        """Planned winner should win most of the time (barring upsets)."""
        wins = 0
        trials = 50
        for _ in range(trials):
            p1 = _make_participant("Hero", "w1")
            p2 = _make_participant("Villain", "w2")
            sim = MatchSimulator(planned_winner_id="w1")
            result = sim.simulate([p1, p2])
            if result.winner_id == "w1":
                wins += 1
        # Should win at least 70% of the time (planned winner has strong advantage)
        assert wins >= trials * 0.7

    def test_match_has_finish(self):
        p1 = _make_participant("A", "w1")
        p2 = _make_participant("B", "w2")
        sim = MatchSimulator(planned_winner_id="w1")
        result = sim.simulate([p1, p2])

        # Most matches should have a finish (pinfall/submission) not time limit draw
        assert result.finish_type in ("pinfall", "submission", "time_limit_draw")

    def test_submission_finish(self):
        """Planned submission finish should produce submission wins."""
        sub_wins = 0
        for _ in range(30):
            p1 = _make_participant("Sub Master", "w1", stats={"submission": 90})
            p2 = _make_participant("Victim", "w2")
            sim = MatchSimulator(planned_winner_id="w1", planned_finish="submission")
            result = sim.simulate([p1, p2])
            if result.winner_id == "w1" and result.finish_type == "submission":
                sub_wins += 1
        assert sub_wins > 0  # At least some submission wins

    def test_main_event_longer_than_opener(self):
        """Main events should tend to be longer."""
        opener_lengths = []
        main_lengths = []
        for _ in range(20):
            p1 = _make_participant("A", "w1")
            p2 = _make_participant("B", "w2")
            sim = MatchSimulator(planned_winner_id="w1", card_position="opener")
            result = sim.simulate([p1, p2])
            opener_lengths.append(result.duration_ticks)

            p1 = _make_participant("A", "w1")
            p2 = _make_participant("B", "w2")
            sim = MatchSimulator(planned_winner_id="w1", card_position="main_event")
            result = sim.simulate([p1, p2])
            main_lengths.append(result.duration_ticks)

        avg_opener = sum(opener_lengths) / len(opener_lengths)
        avg_main = sum(main_lengths) / len(main_lengths)
        assert avg_main > avg_opener

    def test_title_match_rating_boost(self):
        """Title matches should tend to have higher ratings."""
        normal_ratings = []
        title_ratings = []
        for _ in range(30):
            p1 = _make_participant("A", "w1", stats={"psychology": 70, "selling": 70})
            p2 = _make_participant("B", "w2", stats={"psychology": 70, "selling": 70})
            sim = MatchSimulator(planned_winner_id="w1", is_title_match=False)
            result = sim.simulate([p1, p2])
            normal_ratings.append(result.match_rating)

            p1 = _make_participant("A", "w1", stats={"psychology": 70, "selling": 70})
            p2 = _make_participant("B", "w2", stats={"psychology": 70, "selling": 70})
            sim = MatchSimulator(planned_winner_id="w1", is_title_match=True)
            result = sim.simulate([p1, p2])
            title_ratings.append(result.match_rating)

        avg_normal = sum(normal_ratings) / len(normal_ratings)
        avg_title = sum(title_ratings) / len(title_ratings)
        assert avg_title > avg_normal

    def test_high_stats_produce_better_ratings(self):
        """Wrestlers with better psychology/selling should produce higher rated matches."""
        low_ratings = []
        high_ratings = []
        for _ in range(30):
            p1 = _make_participant("Low", "w1", stats={"psychology": 20, "selling": 20})
            p2 = _make_participant("Low2", "w2", stats={"psychology": 20, "selling": 20})
            sim = MatchSimulator(planned_winner_id="w1")
            result = sim.simulate([p1, p2])
            low_ratings.append(result.match_rating)

            p1 = _make_participant("High", "w1", stats={"psychology": 90, "selling": 90})
            p2 = _make_participant("High2", "w2", stats={"psychology": 90, "selling": 90})
            sim = MatchSimulator(planned_winner_id="w1")
            result = sim.simulate([p1, p2])
            high_ratings.append(result.match_rating)

        assert sum(high_ratings) / len(high_ratings) > sum(low_ratings) / len(low_ratings)

    def test_not_enough_participants(self):
        p1 = _make_participant("Solo", "w1")
        sim = MatchSimulator()
        result = sim.simulate([p1])
        assert result.winner_id is None
        assert "cancelled" in result.narrative_summary.lower()

    def test_spots_have_descriptions(self):
        p1 = _make_participant("A", "w1")
        p2 = _make_participant("B", "w2")
        sim = MatchSimulator(planned_winner_id="w1")
        result = sim.simulate([p1, p2])

        for spot in result.spots:
            assert spot.description != ""
            assert spot.move_name != ""

    def test_momentum_and_health_change(self):
        """Participants' health and stamina should decrease during the match."""
        p1 = _make_participant("A", "w1")
        p2 = _make_participant("B", "w2")
        sim = MatchSimulator(planned_winner_id="w1")
        sim.simulate([p1, p2])

        # Both should have taken damage
        assert p1.health < 100 or p2.health < 100
        assert p1.stamina < 100 and p2.stamina < 100


class TestSimulateMatchFromDB:
    def test_simulates_and_persists(self, db_session):
        world = create_world(db_session, "Match Test World")

        # Get two wrestlers
        wrestlers = db_session.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == world.id
        ).limit(2).all()
        assert len(wrestlers) == 2

        # Create a match
        match = MatchDB(
            world_id=world.id,
            match_type="singles",
            winner_id=wrestlers[0].id,
            finish_type="pinfall",
        )
        db_session.add(match)
        db_session.flush()

        # Add participants
        for w in wrestlers:
            db_session.add(MatchParticipantDB(
                match_id=match.id,
                wrestler_id=w.id,
                role="competitor",
            ))
        db_session.commit()

        # Simulate
        result = simulate_match_from_db(db_session, match)
        db_session.commit()

        assert result.duration_ticks > 0
        assert match.is_completed is True
        assert match.match_rating is not None
        assert match.match_rating > 0

        # Match events were persisted
        events = db_session.query(MatchEventDB).filter(
            MatchEventDB.match_id == match.id
        ).all()
        assert len(events) > 0

        # Simulation log stored
        assert len(match.simulation_log) > 0

    def test_title_match_flag(self, db_session):
        world = create_world(db_session, "Title Match World")
        wrestlers = db_session.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == world.id
        ).limit(2).all()

        match = MatchDB(
            world_id=world.id,
            match_type="singles",
            is_title_match=True,
            winner_id=wrestlers[0].id,
        )
        db_session.add(match)
        db_session.flush()

        for w in wrestlers:
            db_session.add(MatchParticipantDB(
                match_id=match.id, wrestler_id=w.id, role="competitor",
            ))
        db_session.commit()

        result = simulate_match_from_db(db_session, match)
        db_session.commit()

        assert match.is_completed is True
        assert result.match_rating > 0

    def test_wrestler_condition_affected(self, db_session):
        world = create_world(db_session, "Condition World")
        wrestlers = db_session.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == world.id
        ).limit(2).all()

        # Set both to full condition
        for w in wrestlers:
            w.condition = 100
        db_session.commit()

        match = MatchDB(
            world_id=world.id, match_type="singles",
            winner_id=wrestlers[0].id,
        )
        db_session.add(match)
        db_session.flush()

        for w in wrestlers:
            db_session.add(MatchParticipantDB(
                match_id=match.id, wrestler_id=w.id, role="competitor",
            ))
        db_session.commit()

        simulate_match_from_db(db_session, match)
        db_session.commit()

        # At least one wrestler should have lost some condition
        db_session.refresh(wrestlers[0])
        db_session.refresh(wrestlers[1])
        assert wrestlers[0].condition < 100 or wrestlers[1].condition < 100


# ---------------------------------------------------------------------------
# Manager interference tests
# ---------------------------------------------------------------------------

class TestManagerInterference:
    def test_interference_can_occur_with_high_skill_manager(self):
        """A high-skill manager should produce interference in some matches."""
        from core_engine.match_engine import ManagerContext
        interference_count = 0
        for _ in range(100):
            mgr = ManagerContext(
                manager_id="mgr1", manager_name="Paul E.",
                client_wrestler_id="w1",
                interference_skill=95, cunning=95,
                specialization="interference",
            )
            sim = MatchSimulator(
                planned_winner_id="w1", managers=[mgr],
                card_position="main_event",
            )
            p1 = _make_participant("Face", "w1")
            p2 = _make_participant("Heel", "w2")
            result = sim.simulate([p1, p2])
            if result.interference_occurred:
                interference_count += 1
        assert interference_count > 0, "Interference never occurred in 100 matches"

    def test_no_interference_without_manager(self):
        """No managers means no interference."""
        for _ in range(30):
            sim = MatchSimulator(planned_winner_id="w1")
            p1 = _make_participant("A", "w1")
            p2 = _make_participant("B", "w2")
            result = sim.simulate([p1, p2])
            assert not result.interference_occurred

    def test_dq_finish_possible_from_interference(self):
        """Caught interference can produce DQ finish."""
        from core_engine.match_engine import ManagerContext
        dq_count = 0
        for _ in range(300):
            mgr = ManagerContext(
                manager_id="mgr1", manager_name="Sneaky",
                client_wrestler_id="w1",
                interference_skill=99, cunning=99,
            )
            sim = MatchSimulator(
                planned_winner_id="w1", managers=[mgr],
                card_position="main_event",
            )
            p1 = _make_participant("A", "w1")
            p2 = _make_participant("B", "w2")
            result = sim.simulate([p1, p2])
            if result.finish_type == "disqualification":
                dq_count += 1
        # DQ should happen at least once in 300 trials with max-skill manager
        assert dq_count > 0, "DQ never occurred"


# ---------------------------------------------------------------------------
# Rivalry heat tests
# ---------------------------------------------------------------------------

class TestRivalryHeat:
    def test_rivalry_heat_boosts_match_rating(self):
        """High rivalry heat should produce higher average ratings."""
        import random as rng
        ratings_no_rivalry = []
        ratings_high_rivalry = []
        rng.seed(42)
        for _ in range(50):
            sim = MatchSimulator(planned_winner_id="w1", rivalry_heat=0)
            p1 = _make_participant("A", "w1", stats={"psychology": 60, "selling": 60})
            p2 = _make_participant("B", "w2", stats={"psychology": 60, "selling": 60})
            result = sim.simulate([p1, p2])
            ratings_no_rivalry.append(result.match_rating)

        rng.seed(42)
        for _ in range(50):
            sim = MatchSimulator(planned_winner_id="w1", rivalry_heat=100)
            p1 = _make_participant("A", "w1", stats={"psychology": 60, "selling": 60})
            p2 = _make_participant("B", "w2", stats={"psychology": 60, "selling": 60})
            result = sim.simulate([p1, p2])
            ratings_high_rivalry.append(result.match_rating)

        avg_low = sum(ratings_no_rivalry) / len(ratings_no_rivalry)
        avg_high = sum(ratings_high_rivalry) / len(ratings_high_rivalry)
        assert avg_high > avg_low, f"Rivalry avg {avg_high:.2f} should be > no-rivalry {avg_low:.2f}"

    def test_rivalry_heat_boosts_crowd_heat(self):
        """High rivalry heat should produce higher crowd heat."""
        heats_low = []
        heats_high = []
        for _ in range(50):
            sim = MatchSimulator(planned_winner_id="w1", rivalry_heat=0, show_momentum=50)
            p1 = _make_participant("A", "w1")
            p2 = _make_participant("B", "w2")
            result = sim.simulate([p1, p2])
            heats_low.append(result.crowd_heat)

        for _ in range(50):
            sim = MatchSimulator(planned_winner_id="w1", rivalry_heat=100, show_momentum=50)
            p1 = _make_participant("A", "w1")
            p2 = _make_participant("B", "w2")
            result = sim.simulate([p1, p2])
            heats_high.append(result.crowd_heat)

        avg_low = sum(heats_low) / len(heats_low)
        avg_high = sum(heats_high) / len(heats_high)
        assert avg_high > avg_low


# ---------------------------------------------------------------------------
# Show momentum tests
# ---------------------------------------------------------------------------

class TestShowMomentum:
    def test_high_show_momentum_boosts_crowd_heat(self):
        """Higher show momentum should produce higher crowd heat."""
        heats_low = []
        heats_high = []
        for _ in range(50):
            sim = MatchSimulator(planned_winner_id="w1", show_momentum=20)
            p1 = _make_participant("A", "w1")
            p2 = _make_participant("B", "w2")
            result = sim.simulate([p1, p2])
            heats_low.append(result.crowd_heat)

        for _ in range(50):
            sim = MatchSimulator(planned_winner_id="w1", show_momentum=90)
            p1 = _make_participant("A", "w1")
            p2 = _make_participant("B", "w2")
            result = sim.simulate([p1, p2])
            heats_high.append(result.crowd_heat)

        avg_low = sum(heats_low) / len(heats_low)
        avg_high = sum(heats_high) / len(heats_high)
        assert avg_high > avg_low, f"High momentum {avg_high:.1f} not > low {avg_low:.1f}"


# ---------------------------------------------------------------------------
# Post-match angle tests (DB-integrated)
# ---------------------------------------------------------------------------

class TestPostMatchAngle:
    def test_post_match_angle_with_heel_stable(self, db_session):
        """A heel stable winner should sometimes generate a faction beatdown."""
        from models.game_models import StableDB, StableMemberDB
        from core_engine.match_engine import _generate_post_match_angle

        world = create_world(db_session, "Angle Test World")
        wrestlers = db_session.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == world.id
        ).limit(3).all()
        assert len(wrestlers) >= 3

        fed = db_session.query(GameFederationDB).filter(
            GameFederationDB.world_id == world.id
        ).first()

        # Create a heel stable with wrestler 0 as leader and wrestler 2 as enforcer
        stable = StableDB(
            world_id=world.id, federation_id=fed.id,
            name="Evil Corp", alignment="heel", is_active=True,
        )
        db_session.add(stable)
        db_session.flush()

        for i, role in [(0, "leader"), (2, "enforcer")]:
            db_session.add(StableMemberDB(
                stable_id=stable.id, wrestler_id=wrestlers[i].id,
                role=role, is_active=True,
            ))
        db_session.commit()

        # Build a match result where wrestler 0 (heel stable leader) won vs wrestler 1
        match = MatchDB(
            world_id=world.id, match_type="singles",
            winner_id=wrestlers[0].id,
        )
        db_session.add(match)
        db_session.flush()

        result = MatchResult(
            winner_id=wrestlers[0].id,
            finish_type="pinfall",
        )

        # Run many trials — should get a beatdown angle eventually
        participant_states = [
            _make_participant(wrestlers[0].name, wrestlers[0].id, alignment="heel"),
            _make_participant(wrestlers[1].name, wrestlers[1].id, alignment="face"),
        ]

        angles = 0
        for _ in range(100):
            angle = _generate_post_match_angle(db_session, match, result, participant_states)
            if angle is not None:
                assert angle["type"] == "faction_beatdown"
                assert angle["stable_name"] == "Evil Corp"
                angles += 1
        assert angles > 0, "No post-match angles generated in 100 trials"

    def test_no_angle_without_stable(self, db_session):
        """Without stables, no post-match angles."""
        from core_engine.match_engine import _generate_post_match_angle

        world = create_world(db_session, "No Angle World")
        wrestlers = db_session.query(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == world.id
        ).limit(2).all()

        match = MatchDB(world_id=world.id, match_type="singles", winner_id=wrestlers[0].id)
        db_session.add(match)
        db_session.flush()

        result = MatchResult(winner_id=wrestlers[0].id)
        participant_states = [
            _make_participant(w.name, w.id) for w in wrestlers
        ]

        for _ in range(50):
            angle = _generate_post_match_angle(db_session, match, result, participant_states)
            assert angle is None, "Got angle without any stables"
