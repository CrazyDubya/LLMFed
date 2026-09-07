"""
Tests for the manager/valet service — creation, bonding, promos, and interference.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.game_models import (
    WorldDB,
    GameFederationDB,
    GameWrestlerDB,
)
from game_service.manager_service import (
    create_manager,
    assign_manager,
    remove_manager,
    get_manager_clients,
    get_wrestler_manager,
    list_managers,
    list_manager_bonds,
    generate_manager_promo,
    calculate_interference_chance,
    attempt_interference,
    calculate_manager_bonus,
)


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
    f = GameFederationDB(id="fed-1", world_id=world.id, name="Test Fed", is_npc=True)
    db.add(f)
    db.commit()
    return f


@pytest.fixture
def wrestlers(db, world):
    ws = []
    for i, name in enumerate(["Alpha", "Beta"]):
        w = GameWrestlerDB(
            id=f"w-{i}",
            world_id=world.id,
            name=name,
            alignment="heel",
            popularity=60 + i * 10,
            condition=90,
            morale=70,
            age=28,
            weight_class="heavyweight",
        )
        db.add(w)
        ws.append(w)
    db.commit()
    return ws


# ---------------------------------------------------------------------------
# Manager CRUD
# ---------------------------------------------------------------------------


class TestManagerCRUD:
    def test_create_manager(self, db, world, federation):
        mgr = create_manager(
            db,
            world.id,
            name="Paul Bearer",
            alignment="heel",
            archetype="scheming_manager",
            federation_id=federation.id,
            catchphrase="Oh yesss!",
        )
        assert mgr.name == "Paul Bearer"
        assert mgr.archetype == "scheming_manager"
        assert mgr.alignment == "heel"
        assert 50 <= mgr.charisma <= 85
        assert 50 <= mgr.mic_skill <= 85
        assert mgr.is_active is True

    def test_list_managers(self, db, world, federation):
        create_manager(db, world.id, "Mgr A", federation_id=federation.id)
        create_manager(db, world.id, "Mgr B", federation_id=federation.id)
        mgrs = list_managers(db, world.id)
        assert len(mgrs) == 2

    def test_assign_manager(self, db, world, federation, wrestlers):
        mgr = create_manager(db, world.id, "The Advocate", federation_id=federation.id)
        bond = assign_manager(
            db,
            world.id,
            mgr.id,
            wrestlers[0].id,
            role="advocate",
            specialization="promo_boost",
            game_date="2026-01-01",
        )
        assert bond.role == "advocate"
        assert bond.specialization == "promo_boost"
        assert bond.is_active is True
        assert bond.effectiveness == 50

    def test_remove_manager(self, db, world, federation, wrestlers):
        mgr = create_manager(db, world.id, "The Advocate", federation_id=federation.id)
        bond = assign_manager(
            db, world.id, mgr.id, wrestlers[0].id, game_date="2026-01-01"
        )
        result = remove_manager(db, bond.id, game_date="2026-02-01")
        assert result is True

        db.refresh(bond)
        assert bond.is_active is False
        assert bond.contract_ended == "2026-02-01"

    def test_remove_nonexistent_bond(self, db):
        assert remove_manager(db, "fake-id") is False

    def test_get_manager_clients(self, db, world, federation, wrestlers):
        mgr = create_manager(db, world.id, "The Agent", federation_id=federation.id)
        assign_manager(db, world.id, mgr.id, wrestlers[0].id)
        assign_manager(db, world.id, mgr.id, wrestlers[1].id)

        clients = get_manager_clients(db, mgr.id)
        assert len(clients) == 2
        names = {c["client_name"] for c in clients}
        assert "Alpha" in names
        assert "Beta" in names

    def test_get_wrestler_manager(self, db, world, federation, wrestlers):
        mgr = create_manager(db, world.id, "Bobby", federation_id=federation.id)
        assign_manager(db, world.id, mgr.id, wrestlers[0].id)

        result = get_wrestler_manager(db, wrestlers[0].id)
        assert result["manager_name"] == "Bobby"

        # Wrestler without manager
        result = get_wrestler_manager(db, wrestlers[1].id)
        assert result == {}

    def test_list_manager_bonds(self, db, world, federation, wrestlers):
        mgr = create_manager(db, world.id, "Agent", federation_id=federation.id)
        assign_manager(db, world.id, mgr.id, wrestlers[0].id)

        bonds = list_manager_bonds(db, world.id)
        assert len(bonds) == 1
        assert bonds[0]["manager_name"] == "Agent"
        assert bonds[0]["client_name"] == "Alpha"


# ---------------------------------------------------------------------------
# Manager Promos
# ---------------------------------------------------------------------------


class TestManagerPromos:
    def test_generate_promo_scheming(self, db, world, federation, wrestlers):
        mgr = create_manager(
            db,
            world.id,
            "Sneaky Steve",
            archetype="scheming_manager",
            federation_id=federation.id,
        )
        assign_manager(db, world.id, mgr.id, wrestlers[0].id)

        result = generate_manager_promo(db, mgr.id, wrestlers[0].id)
        assert result["content"]  # Not empty
        # Client name may or may not appear depending on template choice
        assert result["client_name"] == "Alpha"
        assert result["manager_name"] == "Sneaky Steve"
        assert result["quality_rating"] > 0
        assert result["heat_generated"] > 0

    def test_generate_promo_with_target(self, db, world, federation, wrestlers):
        mgr = create_manager(
            db,
            world.id,
            "Agent Smith",
            archetype="corporate_suit",
            federation_id=federation.id,
        )
        assign_manager(db, world.id, mgr.id, wrestlers[0].id)

        result = generate_manager_promo(db, mgr.id, wrestlers[0].id, wrestlers[1].id)
        assert result["target_name"] == "Beta"
        assert "Beta" in result["content"]

    def test_all_archetypes_produce_content(self, db, world, federation, wrestlers):
        for archetype in [
            "scheming_manager",
            "corporate_suit",
            "flamboyant_mouthpiece",
            "enforcer_type",
            "old_school",
        ]:
            mgr = create_manager(
                db,
                world.id,
                f"Manager_{archetype}",
                archetype=archetype,
                federation_id=federation.id,
            )
            assign_manager(db, world.id, mgr.id, wrestlers[0].id)
            result = generate_manager_promo(db, mgr.id, wrestlers[0].id)
            assert result["content"], f"No content for archetype {archetype}"
            assert result["quality_rating"] > 0

    def test_nonexistent_manager_returns_empty(self, db):
        result = generate_manager_promo(db, "fake-id", "also-fake")
        assert result["content"] == ""
        assert result["quality"] == 0


# ---------------------------------------------------------------------------
# Interference
# ---------------------------------------------------------------------------


class TestInterference:
    def test_interference_chance_in_range(self, db, world, federation):
        mgr = create_manager(
            db, world.id, "Interference Expert", federation_id=federation.id
        )
        chance = calculate_interference_chance(db, mgr.id)
        assert 0.05 <= chance <= 0.8

    def test_interference_chance_nonexistent(self, db):
        assert calculate_interference_chance(db, "fake") == 0.0

    def test_attempt_interference_produces_description(self, db, world, federation):
        mgr = create_manager(db, world.id, "Sneaky", federation_id=federation.id)
        result = attempt_interference(db, mgr.id)
        assert isinstance(result["success"], bool)
        assert result["description"]  # Has a narrative description

    def test_attempt_interference_nonexistent(self, db):
        result = attempt_interference(db, "fake")
        assert result["success"] is False
        assert result["description"] == ""


# ---------------------------------------------------------------------------
# Bonus Calculation
# ---------------------------------------------------------------------------


class TestManagerBonus:
    def test_bonus_with_manager(self, db, world, federation, wrestlers):
        mgr = create_manager(db, world.id, "Boost Master", federation_id=federation.id)
        assign_manager(db, world.id, mgr.id, wrestlers[0].id)

        bonus = calculate_manager_bonus(db, wrestlers[0].id)
        assert bonus["has_manager"] is True
        assert bonus["charisma_bonus"] >= 0
        assert bonus["heat_bonus"] >= 0

    def test_bonus_without_manager(self, db, wrestlers):
        bonus = calculate_manager_bonus(db, wrestlers[0].id)
        assert bonus["has_manager"] is False
        assert bonus["charisma_bonus"] == 0
        assert bonus["heat_bonus"] == 0
