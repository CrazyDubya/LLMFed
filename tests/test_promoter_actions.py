"""
Tests for promoter action processing — form_stable, assign_manager,
create_storyline, and advance_storyline through the world ticker.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    WorldDB,
    GameFederationDB,
    GameWrestlerDB,
    ContractDB,
    PlayerDB,
    PlayerActionDB,
    StableDB,
    StableMemberDB,
    ManagerDB,
    ManagerClientDB,
    StorylineDB,
)
from game_service.world_ticker import WorldTicker


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def world(db):
    w = WorldDB(
        id="world-1", name="Test World", current_game_date="2026-01-01", current_tick=0
    )
    db.add(w)
    db.commit()
    return w


@pytest.fixture
def federation(db, world):
    f = GameFederationDB(
        id="fed-1",
        world_id=world.id,
        name="Test Fed",
        is_npc=False,
        prestige=50,
        budget=100000,
    )
    db.add(f)
    db.commit()
    return f


@pytest.fixture
def wrestlers(db, world, federation):
    ws = []
    for i, name in enumerate(["Alpha", "Beta", "Gamma", "Delta"]):
        w = GameWrestlerDB(
            id=f"w-{i}",
            world_id=world.id,
            name=name,
            alignment="heel",
            popularity=50 + i * 10,
            condition=90,
            morale=70,
            age=28,
            weight_class="heavyweight",
        )
        db.add(w)
        c = ContractDB(
            id=f"c-{i}",
            world_id=world.id,
            federation_id=federation.id,
            wrestler_id=w.id,
            status="active",
            salary_weekly=2000,
            start_date="2026-01-01",
        )
        db.add(c)
        ws.append(w)
    db.commit()
    return ws


@pytest.fixture
def player(db, world, federation):
    p = PlayerDB(
        id="player-1",
        user_id="user-1",
        world_id=world.id,
        player_type="promoter",
        federation_id=federation.id,
    )
    db.add(p)
    db.commit()
    return p


class TestPromoterActions:
    def _submit_and_process(self, db, world, player, action_type, action_data):
        """Submit an action and process it through the ticker."""
        action = PlayerActionDB(
            world_id=world.id,
            player_id=player.id,
            action_type=action_type,
            action_data=action_data,
        )
        db.add(action)
        db.commit()

        ticker = WorldTicker(db, world.id)
        ticker._process_player_actions()
        db.commit()
        db.refresh(action)
        return action

    def test_form_stable_action(self, db, world, federation, wrestlers, player):
        action = self._submit_and_process(
            db,
            world,
            player,
            "form_stable",
            {
                "name": "The Wolfpack",
                "leader_id": wrestlers[0].id,
                "founding_member_ids": [w.id for w in wrestlers[:3]],
                "alignment": "heel",
            },
        )
        assert action.status == "completed"
        assert action.result["name"] == "The Wolfpack"

        stable = db.query(StableDB).filter_by(name="The Wolfpack").first()
        assert stable is not None
        assert stable.is_active is True
        members = (
            db.query(StableMemberDB)
            .filter_by(stable_id=stable.id, is_active=True)
            .all()
        )
        assert len(members) == 3

    def test_join_stable_action(self, db, world, federation, wrestlers, player):
        # First form a stable
        self._submit_and_process(
            db,
            world,
            player,
            "form_stable",
            {
                "name": "The Pack",
                "leader_id": wrestlers[0].id,
                "founding_member_ids": [wrestlers[0].id, wrestlers[1].id],
            },
        )
        stable = db.query(StableDB).filter_by(name="The Pack").first()

        # Now join
        action = self._submit_and_process(
            db,
            world,
            player,
            "join_stable",
            {
                "stable_id": stable.id,
                "wrestler_id": wrestlers[2].id,
                "role": "recruit",
            },
        )
        assert action.status == "completed"
        members = (
            db.query(StableMemberDB)
            .filter_by(stable_id=stable.id, is_active=True)
            .all()
        )
        assert len(members) == 3

    def test_leave_stable_action(self, db, world, federation, wrestlers, player):
        self._submit_and_process(
            db,
            world,
            player,
            "form_stable",
            {
                "name": "The Pack",
                "leader_id": wrestlers[0].id,
                "founding_member_ids": [w.id for w in wrestlers[:3]],
            },
        )
        stable = db.query(StableDB).filter_by(name="The Pack").first()

        action = self._submit_and_process(
            db,
            world,
            player,
            "leave_stable",
            {
                "stable_id": stable.id,
                "wrestler_id": wrestlers[2].id,
            },
        )
        assert action.status == "completed"
        active = (
            db.query(StableMemberDB)
            .filter_by(stable_id=stable.id, is_active=True)
            .all()
        )
        assert len(active) == 2

    def test_dissolve_stable_action(self, db, world, federation, wrestlers, player):
        self._submit_and_process(
            db,
            world,
            player,
            "form_stable",
            {
                "name": "The Pack",
                "leader_id": wrestlers[0].id,
                "founding_member_ids": [w.id for w in wrestlers[:3]],
            },
        )
        stable = db.query(StableDB).filter_by(name="The Pack").first()

        action = self._submit_and_process(
            db,
            world,
            player,
            "dissolve_stable",
            {
                "stable_id": stable.id,
            },
        )
        assert action.status == "completed"
        db.refresh(stable)
        assert stable.is_active is False

    def test_create_manager_action(self, db, world, federation, player):
        action = self._submit_and_process(
            db,
            world,
            player,
            "create_manager",
            {
                "name": "Paul Bearer",
                "alignment": "heel",
                "archetype": "scheming_manager",
                "federation_id": federation.id,
            },
        )
        assert action.status == "completed"
        assert action.result["name"] == "Paul Bearer"

        mgr = db.query(ManagerDB).filter_by(name="Paul Bearer").first()
        assert mgr is not None

    def test_assign_manager_action(self, db, world, federation, wrestlers, player):
        # Create manager first
        self._submit_and_process(
            db,
            world,
            player,
            "create_manager",
            {
                "name": "The Advocate",
                "federation_id": federation.id,
            },
        )
        mgr = db.query(ManagerDB).filter_by(name="The Advocate").first()

        action = self._submit_and_process(
            db,
            world,
            player,
            "assign_manager",
            {
                "manager_id": mgr.id,
                "client_wrestler_id": wrestlers[0].id,
            },
        )
        assert action.status == "completed"

        bond = (
            db.query(ManagerClientDB)
            .filter_by(manager_id=mgr.id, client_wrestler_id=wrestlers[0].id)
            .first()
        )
        assert bond is not None
        assert bond.is_active is True

    def test_remove_manager_action(self, db, world, federation, wrestlers, player):
        self._submit_and_process(
            db,
            world,
            player,
            "create_manager",
            {
                "name": "Agent",
                "federation_id": federation.id,
            },
        )
        mgr = db.query(ManagerDB).filter_by(name="Agent").first()
        self._submit_and_process(
            db,
            world,
            player,
            "assign_manager",
            {
                "manager_id": mgr.id,
                "client_wrestler_id": wrestlers[0].id,
            },
        )
        bond = db.query(ManagerClientDB).filter_by(manager_id=mgr.id).first()

        action = self._submit_and_process(
            db,
            world,
            player,
            "remove_manager",
            {
                "bond_id": bond.id,
            },
        )
        assert action.status == "completed"
        db.refresh(bond)
        assert bond.is_active is False

    def test_create_storyline_action(self, db, world, federation, wrestlers, player):
        action = self._submit_and_process(
            db,
            world,
            player,
            "create_storyline",
            {
                "wrestler_ids": [wrestlers[0].id, wrestlers[1].id],
                "storyline_type": "feud",
                "name": "The Rivalry",
            },
        )
        assert action.status == "completed"
        assert action.result["name"] == "The Rivalry"

        sl = db.query(StorylineDB).filter_by(name="The Rivalry").first()
        assert sl is not None
        assert sl.status == "brewing"

    def test_advance_storyline_action(self, db, world, federation, wrestlers, player):
        self._submit_and_process(
            db,
            world,
            player,
            "create_storyline",
            {
                "wrestler_ids": [wrestlers[0].id, wrestlers[1].id],
                "storyline_type": "feud",
            },
        )
        sl = db.query(StorylineDB).filter_by(storyline_type="feud").first()
        old_heat = sl.heat

        action = self._submit_and_process(
            db,
            world,
            player,
            "advance_storyline",
            {
                "storyline_id": sl.id,
                "status": "active",
                "heat_boost": 20,
            },
        )
        assert action.status == "completed"
        db.refresh(sl)
        assert sl.status == "active"
        assert sl.heat == old_heat + 20
