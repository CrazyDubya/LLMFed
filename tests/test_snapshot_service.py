"""Tests for snapshot service — world state save/load."""

import gzip
import json
import pytest
import tempfile
import os
from datetime import datetime

from game_service.snapshot_service import (
    create_snapshot,
    restore_snapshot,
    export_snapshot_to_file,
    import_snapshot_from_file,
    _serialize_row,
)

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from models.db_models import Base
from models.core_models import WorldDB


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    # Import all models to register them with Base
    import models.core_models  # noqa
    import models.wrestler_models  # noqa
    import models.show_models  # noqa
    import models.social_models  # noqa
    import models.federation_models  # noqa
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def world_with_data(db_session):
    """Create a minimal world for snapshot testing."""
    world = WorldDB(name="Test World")
    db_session.add(world)
    db_session.commit()
    db_session.refresh(world)
    return world


class TestSerializeRow:
    def test_serialize_world(self, db_session, world_with_data):
        data = _serialize_row(world_with_data)
        assert data["name"] == "Test World"
        assert "id" in data


class TestCreateSnapshot:
    def test_creates_snapshot(self, db_session, world_with_data):
        snapshot = create_snapshot(db_session, world_with_data.id, "Test snapshot")
        assert "metadata" in snapshot
        assert "data" in snapshot
        assert snapshot["size_bytes"] > 0
        meta = snapshot["metadata"]
        assert meta["world_id"] == world_with_data.id
        assert meta["description"] == "Test snapshot"
        assert meta["snapshot_type"] == "manual"

    def test_snapshot_is_valid_gzip(self, db_session, world_with_data):
        snapshot = create_snapshot(db_session, world_with_data.id)
        raw = gzip.decompress(snapshot["data"])
        state = json.loads(raw)
        assert "world" in state
        assert "tables" in state

    def test_nonexistent_world_raises(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            create_snapshot(db_session, "nonexistent-id")


class TestRestoreSnapshot:
    @pytest.mark.parametrize("via_http", [False, True], ids=["service", "http"])
    def test_branch_remaps_world_config(self, db_session, world_with_data, via_http):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from agent_service.database import get_db_sync
        from api_gateway.routes.snapshot_routes import router
        from api_gateway.security import get_current_user, TokenData
        from models.game_models import GameFederationDB, GameWrestlerDB, PlayerDB, UserDB

        fed = GameFederationDB(world_id=world_with_data.id, name="Request Fed")
        wrestlers = [GameWrestlerDB(world_id=world_with_data.id, name=name) for name in ["A", "B"]]
        db_session.add_all([fed, *wrestlers])
        db_session.flush()
        config = {
            "pending_match_requests": [{
                "wrestler_id": wrestlers[0].id, "opponent_id": wrestlers[1].id,
                "federation_id": fed.id, "type": "open_challenge",
            }],
            "last_match_request_dates": {wrestlers[0].id: "2026-01-01"},
            "nested": {"world_id": world_with_data.id, "empty": [[], {}], "optional": None},
            "difficulty": "normal",
        }
        world_with_data.world_config = config
        db_session.commit()
        if via_http:
            user = UserDB(username="branch-owner", email="branch@example.test", password_hash="unused")
            db_session.add(user)
            db_session.flush()
            db_session.add(PlayerDB(user_id=user.id, world_id=world_with_data.id, player_type="promoter"))
            db_session.commit()
            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db_sync] = lambda: db_session
            app.dependency_overrides[get_current_user] = lambda: TokenData(user_id=user.id)
            with TestClient(app, base_url="http://localhost") as client:
                response = client.post("/game/snapshots", json={"world_id": world_with_data.id})
                assert response.status_code == 201, response.text
                response = client.post("/game/snapshots/restore", json={
                    "snapshot_id": response.json()["snapshot_id"], "create_new_world": True,
                })
                assert response.status_code == 200, response.text
                result = response.json()
        else:
            snapshot = create_snapshot(db_session, world_with_data.id)
            result = restore_snapshot(db_session, snapshot["data"])
        db_session.expire_all()
        branch_id = result["world_id"]
        branch = db_session.get(WorldDB, branch_id)
        new_ids = {w.name: w.id for w in db_session.query(GameWrestlerDB).filter_by(world_id=branch_id)}
        new_fed = db_session.query(GameFederationDB).filter_by(world_id=branch_id).one()
        assert set(new_ids.values()).isdisjoint(w.id for w in wrestlers)
        assert branch.world_config == {
            **config,
            "pending_match_requests": [{**config["pending_match_requests"][0],
                                        "wrestler_id": new_ids["A"], "opponent_id": new_ids["B"],
                                        "federation_id": new_fed.id}],
            "last_match_request_dates": {new_ids["A"]: "2026-01-01"},
            "nested": {**config["nested"], "world_id": branch_id},
        }
        assert db_session.get(WorldDB, world_with_data.id).world_config == config

    def test_branch_remaps_booking_vision_json(self, db_session, world_with_data):
        from models.game_models import BookingVisionDB, GameFederationDB, GameWrestlerDB

        fed = GameFederationDB(world_id=world_with_data.id, name="Vision Fed", short_name="VF")
        wrestler = GameWrestlerDB(world_id=world_with_data.id, name="Action Wrestler")
        db_session.add_all([fed, wrestler])
        db_session.flush()
        payload = {
            "wrestler_id": wrestler.id,
            "nested": [{"target": wrestler.id}, [], {}],
            "amount": 3, "enabled": True, "optional": None, "label": "unchanged",
        }
        vision = BookingVisionDB(
            world_id=world_with_data.id, federation_id=fed.id,
            crown_jewel_vision=payload, trajectories={wrestler.id: {"direction": "rising"}},
        )
        db_session.add(vision)
        db_session.commit()
        snapshot = create_snapshot(db_session, world_with_data.id)
        result = restore_snapshot(db_session, snapshot["data"])
        restored_wrestler = db_session.query(GameWrestlerDB).filter_by(world_id=result["world_id"]).one()
        restored_vision = db_session.query(BookingVisionDB).filter_by(world_id=result["world_id"]).one()
        assert restored_wrestler.id != wrestler.id
        assert restored_vision.crown_jewel_vision == {
            **payload, "wrestler_id": restored_wrestler.id,
            "nested": [{"target": restored_wrestler.id}, [], {}],
        }
        assert restored_vision.trajectories == {restored_wrestler.id: {"direction": "rising"}}
        assert vision.crown_jewel_vision == payload

    @pytest.mark.parametrize("branch", [True, False])
    def test_snapshot_excludes_account_bound_rows(self, db_session, world_with_data, branch):
        from models.game_models import UserDB, PlayerDB, PlayerActionDB

        db_session.execute(text("PRAGMA foreign_keys=ON"))
        user = UserDB(email="portable@example.com", username="portable", password_hash="unused")
        db_session.add(user)
        db_session.flush()
        player = PlayerDB(user_id=user.id, world_id=world_with_data.id, player_type="promoter")
        db_session.add(player)
        db_session.flush()
        action = PlayerActionDB(
            world_id=world_with_data.id, player_id=player.id, action_type="train", action_data={},
        )
        db_session.add(action)
        db_session.commit()
        snapshot = create_snapshot(db_session, world_with_data.id)
        tables = json.loads(gzip.decompress(snapshot["data"]))["tables"]
        assert "players" not in tables
        assert "player_actions" not in tables
        if branch:
            db_session.delete(action)
            db_session.delete(player)
            db_session.flush()
            db_session.delete(user)
            db_session.commit()
            assert db_session.query(UserDB).count() == 0
        result = restore_snapshot(db_session, snapshot["data"], create_new_world=branch)
        assert db_session.query(WorldDB).filter_by(id=result["world_id"]).one()
        assert db_session.query(PlayerDB).count() == (0 if branch else 1)
        assert db_session.query(PlayerActionDB).count() == (0 if branch else 1)

    @pytest.mark.parametrize("branch", [True, False])
    def test_restores_stats_segments_and_participants(self, db_session, world_with_data, branch):
        from models.game_models import (
            GameFederationDB, GameWrestlerDB, WrestlerStatsDB,
            ShowDB, ShowSegmentDB, MatchDB, MatchParticipantDB,
        )

        world_id = world_with_data.id
        fed = GameFederationDB(world_id=world_id, name="Fed", short_name="F")
        wrestler = GameWrestlerDB(world_id=world_id, name="Wrestler")
        match = MatchDB(world_id=world_id)
        db_session.add_all([fed, wrestler, match])
        db_session.flush()
        show = ShowDB(world_id=world_id, federation_id=fed.id, name="Show", game_date="2026-01-01")
        db_session.add(show)
        db_session.flush()
        db_session.add_all([
            WrestlerStatsDB(wrestler_id=wrestler.id, power=87),
            ShowSegmentDB(show_id=show.id, match_id=match.id, position=1, segment_type="match"),
            MatchParticipantDB(match_id=match.id, wrestler_id=wrestler.id),
        ])
        db_session.commit()

        snapshot = create_snapshot(db_session, world_id)
        result = restore_snapshot(db_session, snapshot["data"], create_new_world=branch)
        restored_id = result["world_id"]
        stats = db_session.query(WrestlerStatsDB).join(GameWrestlerDB).filter(
            GameWrestlerDB.world_id == restored_id).all()
        segments = db_session.query(ShowSegmentDB).join(ShowDB).filter(ShowDB.world_id == restored_id).all()
        participants = db_session.query(MatchParticipantDB).join(MatchDB).filter(
            MatchDB.world_id == restored_id).all()
        assert (len(stats), len(segments), len(participants)) == (1, 1, 1)
        assert stats[0].power == 87
        assert participants[0].wrestler_id == stats[0].wrestler_id
        assert participants[0].match_id == segments[0].match_id
        if branch:
            assert stats[0].wrestler_id != wrestler.id

    def test_serialization_errors_propagate(self, db_session, world_with_data, monkeypatch):
        from game_service import snapshot_service

        def broken_scope(*args):
            raise RuntimeError("broken scope")

        monkeypatch.setattr(snapshot_service, "_world_scope", broken_scope)
        with pytest.raises(RuntimeError, match="broken scope"):
            create_snapshot(db_session, world_with_data.id)

    def test_unconfigured_child_scope_names_table(self):
        from sqlalchemy import Column, Integer, MetaData, Table
        from game_service.snapshot_service import _world_scope

        table = Table("unconfigured_child", MetaData(), Column("id", Integer, primary_key=True))
        with pytest.raises(ValueError, match="No world-scoping parent configured for table 'unconfigured_child'"):
            _world_scope(table, "world-id")

    @pytest.mark.parametrize("branch", [True, False])
    def test_all_world_owned_tables_round_trip(self, db_session, world_with_data, branch):
        from sqlalchemy import Integer, Float, Boolean, String, DateTime
        from game_service.snapshot_service import _model_classes_by_table, _world_scope
        from models.game_models import UserDB

        db_session.execute(text("PRAGMA foreign_keys=ON"))
        user = UserDB(email="test@example.com", username="test", password_hash="unused")
        db_session.add(user)
        db_session.flush()
        models = _model_classes_by_table()
        ids = {"worlds": world_with_data.id, "users": user.id}
        for name, model in models.items():
            if name == "worlds":
                continue
            values = {}
            for col in model.__table__.columns:
                if col.foreign_keys:
                    parent = next(iter(col.foreign_keys)).column.table.name
                    values[col.name] = ids[parent]
                elif col.name == "world_id":
                    values[col.name] = world_with_data.id
                elif col.primary_key or col.nullable or col.default is not None:
                    continue
                elif isinstance(col.type, (Integer, Float, Boolean)):
                    values[col.name] = 1
                elif isinstance(col.type, String):
                    values[col.name] = "test"
                elif isinstance(col.type, DateTime):
                    values[col.name] = datetime(2026, 1, 1)
                else:
                    values[col.name] = {}
            row = model(**values)
            db_session.add(row)
            db_session.flush()
            ids[name] = row.id
        db_session.commit()
        snapshot = create_snapshot(db_session, world_with_data.id)
        assert all(count == 1 for count in snapshot["metadata"]["table_counts"].values())
        result = restore_snapshot(db_session, snapshot["data"], create_new_world=branch)
        for name, model in models.items():
            if name != "worlds":
                assert db_session.query(model).filter(
                    _world_scope(model.__table__, result["world_id"])).count() == 1, name
        assert db_session.query(UserDB).count() == 1

    def test_restore_creates_branch(self, db_session, world_with_data):
        snapshot = create_snapshot(db_session, world_with_data.id)
        result = restore_snapshot(db_session, snapshot["data"], create_new_world=True)
        assert result["is_branch"] is True
        assert result["world_id"] != world_with_data.id
        assert result["original_world_id"] == world_with_data.id

    def test_restore_actually_writes_data_with_valid_foreign_keys(self, db_session):
        """restore_snapshot must persist real rows, not just return metadata."""
        from models.wrestler_models import GameWrestlerDB, ContractDB
        from models.federation_models import GameFederationDB

        fed = GameFederationDB(world_id="w-src", name="Test Fed", short_name="TF")
        db_session.add(fed)
        db_session.flush()
        wrestler = GameWrestlerDB(world_id="w-src", name="Test Wrestler")
        db_session.add(wrestler)
        db_session.flush()
        contract = ContractDB(
            world_id="w-src", wrestler_id=wrestler.id, federation_id=fed.id,
            status="active", salary_weekly=1000.0, start_date="2026-01-01",
        )
        db_session.add(contract)
        world = WorldDB(id="w-src", name="Source World")
        db_session.add(world)
        db_session.commit()

        snapshot = create_snapshot(db_session, "w-src")
        result = restore_snapshot(db_session, snapshot["data"], create_new_world=True)
        db_session.commit()
        new_world_id = result["world_id"]

        restored_world = db_session.query(WorldDB).filter_by(id=new_world_id).first()
        assert restored_world is not None
        restored_fed = db_session.query(GameFederationDB).filter_by(world_id=new_world_id).first()
        restored_wrestler = db_session.query(GameWrestlerDB).filter_by(world_id=new_world_id).first()
        restored_contract = db_session.query(ContractDB).filter_by(world_id=new_world_id).first()
        assert restored_fed is not None
        assert restored_wrestler is not None
        assert restored_contract is not None
        # Foreign keys must point at the *restored* rows, not the originals
        assert restored_contract.federation_id == restored_fed.id
        assert restored_contract.wrestler_id == restored_wrestler.id
        assert restored_contract.federation_id != fed.id
        assert restored_contract.wrestler_id != wrestler.id


class TestExportImport:
    def test_round_trip(self, db_session, world_with_data):
        snapshot = create_snapshot(db_session, world_with_data.id, "export test")

        with tempfile.NamedTemporaryFile(suffix=".llmfed.gz", delete=False) as f:
            filepath = f.name

        try:
            export_snapshot_to_file(snapshot, filepath)
            assert os.path.exists(filepath)
            assert os.path.getsize(filepath) > 0

            data = import_snapshot_from_file(filepath)
            result = restore_snapshot(db_session, data, create_new_world=True)
            assert result["is_branch"] is True
        finally:
            os.unlink(filepath)
