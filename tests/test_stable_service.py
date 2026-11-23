"""
Tests for the stable/faction service — CRUD, internal drama engine,
and match result integration.
"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    WorldDB, GameFederationDB, GameWrestlerDB, StableMemberDB,
    ContractDB, StorylineDB, MatchDB, MatchParticipantDB, ShowDB, ShowSegmentDB,
)
from core_engine.match_aftermath import process_match_aftermath
from game_service.wrestler_lifecycle_service import load_conditioning_data
from game_service.stable_service import (
    create_stable, add_member, remove_member, promote_member,
    dissolve_stable, get_stable_with_members, list_stables,
    get_wrestler_stable, tick_stable_dynamics,
    process_match_result_for_stables,
)


@pytest.fixture
def db():
    """Create an in-memory SQLite database for testing.

    Autoflush is off to match the production ``SessionLocal``.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def world(db):
    w = WorldDB(id="world-1", name="Test World", current_game_date="2026-01-01", current_tick=0)
    db.add(w)
    db.commit()
    return w


@pytest.fixture
def federation(db, world):
    f = GameFederationDB(id="fed-1", world_id=world.id, name="Test Fed", is_npc=True)
    db.add(f)
    db.commit()
    return f


@pytest.fixture
def wrestlers(db, world, federation):
    ws = []
    for i, name in enumerate(["Alpha", "Beta", "Gamma", "Delta"]):
        w = GameWrestlerDB(
            id=f"w-{i}", world_id=world.id, name=name,
            alignment="heel", popularity=50 + i * 10, condition=90,
            morale=70, age=28, weight_class="heavyweight",
            win_streak=0,
        )
        db.add(w)
        c = ContractDB(
            id=f"c-{i}", world_id=world.id,
            federation_id=federation.id, wrestler_id=w.id,
            status="active", salary_weekly=2000,
            start_date="2026-01-01",
        )
        db.add(c)
        ws.append(w)
    db.commit()
    return ws


# ---------------------------------------------------------------------------
# CRUD Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("member", [False, True])
def test_match_result_sql_count(db, world, federation, wrestlers, member):
    if member:
        create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
            game_date="2026-01-01",
        )
    winner_id, loser_id, world_id = wrestlers[0].id, wrestlers[3].id, world.id
    statements = []
    commits = []

    def record_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    def record_commit(session):
        commits.append(True)

    event.listen(db.bind, "before_cursor_execute", record_sql)
    event.listen(db, "after_commit", record_commit)
    try:
        process_match_result_for_stables(db, winner_id, loser_id, world_id)
    finally:
        event.remove(db.bind, "before_cursor_execute", record_sql)
        event.remove(db, "after_commit", record_commit)
    selects = [s for s in statements if s.startswith("SELECT")]
    assert len(selects) == (3 if member else 1)
    assert len(commits) == int(member)


def test_match_result_empty_participants(db):
    statements = []

    def record_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db.bind, "before_cursor_execute", record_sql)
    try:
        process_match_result_for_stables(db, None, None, "missing")
    finally:
        event.remove(db.bind, "before_cursor_execute", record_sql)
    assert statements == []


def test_match_result_missing_participants(db):
    process_match_result_for_stables(db, "missing-winner", "missing-loser", "missing")
    assert not db.dirty


def test_draw_flushes_results_for_conditioning(db, world, federation, wrestlers):
    world_id, federation_id = world.id, federation.id
    wrestler_ids = [w.id for w in wrestlers[:2]]
    game_date = "2026-01-01"
    show = ShowDB(
        id="draw-show", world_id=world_id, federation_id=federation_id,
        name="Thursday Show", game_date=game_date,
    )
    match = MatchDB(id="draw-match", world_id=world_id)
    participants = [
        MatchParticipantDB(match_id=match.id, wrestler_id=wid)
        for wid in wrestler_ids
    ]
    db.add_all([show, match, *participants, ShowSegmentDB(
        show_id=show.id, match_id=match.id, position=0, segment_type="match",
    )])
    db.commit()

    match.is_completed = True
    match.winner_id = None
    match.finish_type = "draw"
    for participant in participants:
        participant.performance_rating = 3.5
    process_match_aftermath(db, match, game_date)
    assert match in db.dirty
    assert load_conditioning_data(db, world_id, game_date)[1] == {}

    losers = db.query(MatchParticipantDB).filter(
        MatchParticipantDB.match_id == match.id,
        MatchParticipantDB.is_winner.is_(False),
    ).all()
    assert len(losers) == 2
    for loser in losers:
        process_match_result_for_stables(db, None, loser.wrestler_id, world_id, game_date)

    assert load_conditioning_data(db, world_id, game_date)[1] == {
        wid: 1 for wid in wrestler_ids
    }
    assert db.query(MatchParticipantDB.performance_rating).filter(
        MatchParticipantDB.match_id == match.id,
    ).all() == [(3.5,), (3.5,)]


@pytest.mark.parametrize("inactive_stable", [False, True])
def test_match_result_flushes_without_stable_changes(db, world, federation, wrestlers, inactive_stable):
    world_id = world.id
    winner_id = None
    if inactive_stable:
        winner_id = wrestlers[0].id
        stable = create_stable(
            db, world_id, federation.id, "The Pack", leader_id=winner_id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
        )
        stable.is_active = False
        db.commit()
    world.name = "Pending change"

    process_match_result_for_stables(db, winner_id, None, world_id)

    assert db.query(WorldDB.name).filter_by(id=world_id).scalar() == "Pending change"
    assert db.in_transaction()


class TestStableCRUD:
    def test_create_stable(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id,
            name="The Wolfpack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
            alignment="heel",
            game_date="2026-01-01",
        )
        assert stable.name == "The Wolfpack"
        assert stable.alignment == "heel"
        assert stable.is_active is True

        # Check members
        members = db.query(StableMemberDB).filter_by(stable_id=stable.id, is_active=True).all()
        assert len(members) == 3

        leader = next(m for m in members if m.role == "leader")
        assert leader.wrestler_id == wrestlers[0].id
        assert leader.loyalty >= 80

    def test_add_member(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[wrestlers[0].id, wrestlers[1].id],
            game_date="2026-01-01",
        )
        new_member = add_member(db, stable.id, wrestlers[2].id, role="recruit", game_date="2026-01-05")
        assert new_member.role == "recruit"
        assert new_member.loyalty == 50  # Recruits start lower

    def test_remove_member(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
            game_date="2026-01-01",
        )
        result = remove_member(db, stable.id, wrestlers[2].id, game_date="2026-01-10")
        assert result is True

        active = db.query(StableMemberDB).filter_by(stable_id=stable.id, is_active=True).all()
        assert len(active) == 2

    def test_remove_leader_auto_promotes(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
            game_date="2026-01-01",
        )
        # Give one member high influence
        member = db.query(StableMemberDB).filter_by(
            stable_id=stable.id, wrestler_id=wrestlers[1].id
        ).first()
        member.influence = 90
        db.commit()

        remove_member(db, stable.id, wrestlers[0].id, game_date="2026-01-10")

        new_leader = db.query(StableMemberDB).filter_by(
            stable_id=stable.id, role="leader", is_active=True
        ).first()
        assert new_leader is not None
        assert new_leader.wrestler_id == wrestlers[1].id

    def test_remove_top_influence_leader_promotes_remaining_member(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
            game_date="2026-01-01",
        )

        remove_member(db, stable.id, wrestlers[0].id, game_date="2026-01-10")

        new_leader = db.query(StableMemberDB).filter_by(
            stable_id=stable.id, role="leader", is_active=True
        ).first()
        assert new_leader is not None
        assert new_leader.wrestler_id in {wrestlers[1].id, wrestlers[2].id}

    def test_removal_leaving_one_member_dissolves_stable(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Duo",
            leader_id=wrestlers[0].id,
            founding_member_ids=[wrestlers[1].id],
            game_date="2026-01-01",
        )

        remove_member(db, stable.id, wrestlers[1].id, game_date="2026-01-10")

        db.refresh(stable)
        assert stable.is_active is False
        assert stable.dissolved_date == "2026-01-10"
        active = db.query(StableMemberDB).filter_by(stable_id=stable.id, is_active=True).count()
        assert active == 0

    def test_dissolve_stable(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
            game_date="2026-01-01",
        )
        dissolve_stable(db, stable.id, game_date="2026-02-01")

        db.refresh(stable)
        assert stable.is_active is False
        active = db.query(StableMemberDB).filter_by(stable_id=stable.id, is_active=True).all()
        assert len(active) == 0

    def test_promote_member(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
            game_date="2026-01-01",
        )
        result = promote_member(db, stable.id, wrestlers[1].id, "enforcer")
        assert result is True

        member = db.query(StableMemberDB).filter_by(
            stable_id=stable.id, wrestler_id=wrestlers[1].id
        ).first()
        assert member.role == "enforcer"

    def test_list_stables(self, db, world, federation, wrestlers):
        create_stable(
            db, world.id, federation.id, "Pack A",
            leader_id=wrestlers[0].id,
            founding_member_ids=[wrestlers[0].id, wrestlers[1].id],
        )
        create_stable(
            db, world.id, federation.id, "Pack B",
            leader_id=wrestlers[2].id,
            founding_member_ids=[wrestlers[2].id, wrestlers[3].id],
        )
        stables = list_stables(db, world.id)
        assert len(stables) == 2

    def test_get_wrestler_stable(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[wrestlers[0].id, wrestlers[1].id],
        )
        result = get_wrestler_stable(db, wrestlers[0].id)
        assert result["stable"].id == stable.id
        assert result["member"].role == "leader"

        # Wrestler not in a stable
        result = get_wrestler_stable(db, wrestlers[3].id)
        assert result == {}

    def test_get_stable_with_members(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
        )
        data = get_stable_with_members(db, stable.id)
        assert data["stable"].name == "The Pack"
        assert len(data["members"]) == 3
        leader = next(m for m in data["members"] if m["role"] == "leader")
        assert leader["wrestler_name"] == "Alpha"


# ---------------------------------------------------------------------------
# Internal Drama Engine Tests
# ---------------------------------------------------------------------------

class TestStableDynamics:
    def test_tick_loyalty_drift(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
            game_date="2026-01-01",
        )
        # Wrestler with win streak gains loyalty
        wrestlers[1].win_streak = 3
        db.commit()

        member_before = db.query(StableMemberDB).filter_by(
            stable_id=stable.id, wrestler_id=wrestlers[1].id
        ).first()
        old_loyalty = member_before.loyalty

        tick_stable_dynamics(db, stable, "2026-01-02")

        db.refresh(member_before)
        assert member_before.loyalty >= old_loyalty  # Should increase or stay same

    def test_recruit_promotes_to_member(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[wrestlers[0].id, wrestlers[1].id],
        )
        recruit = add_member(db, stable.id, wrestlers[2].id, "recruit")
        recruit.loyalty = 70  # Above threshold
        db.commit()

        tick_stable_dynamics(db, stable, "2026-01-02")

        db.refresh(recruit)
        assert recruit.role == "member"  # Promoted from recruit

    def test_low_cohesion_triggers_power_struggle(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
            game_date="2026-01-01",
        )
        # Set everyone's loyalty very low to trigger power struggle
        members = db.query(StableMemberDB).filter_by(stable_id=stable.id).all()
        for m in members:
            m.loyalty = 30
        # Give a non-leader high influence
        non_leader = next(m for m in members if m.role != "leader")
        non_leader.influence = 70
        db.commit()

        tick_stable_dynamics(db, stable, "2026-01-15")

        # Should have created a power_struggle storyline
        ps = db.query(StorylineDB).filter_by(
            storyline_type="power_struggle",
        ).first()
        assert ps is not None
        assert stable.name in ps.name

    def test_match_result_boosts_stable(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
            game_date="2026-01-01",
        )
        old_heat = stable.heat

        process_match_result_for_stables(
            db, winner_id=wrestlers[0].id, loser_id=wrestlers[3].id,
            world_id=world.id, game_date="2026-01-05",
        )

        db.refresh(stable)
        assert stable.heat >= old_heat  # Heat should increase

    def test_leader_loss_damages_loyalty(self, db, world, federation, wrestlers):
        stable = create_stable(
            db, world.id, federation.id, "The Pack",
            leader_id=wrestlers[0].id,
            founding_member_ids=[w.id for w in wrestlers[:3]],
            game_date="2026-01-01",
        )
        members = db.query(StableMemberDB).filter_by(
            stable_id=stable.id, is_active=True
        ).all()
        old_loyalties = {m.wrestler_id: m.loyalty for m in members}

        process_match_result_for_stables(
            db, winner_id=wrestlers[3].id, loser_id=wrestlers[0].id,
            world_id=world.id, game_date="2026-01-05",
        )

        for m in members:
            db.refresh(m)
        # Non-leader members should lose loyalty when leader loses
        for m in members:
            if m.wrestler_id != wrestlers[0].id:
                assert m.loyalty <= old_loyalties[m.wrestler_id]
