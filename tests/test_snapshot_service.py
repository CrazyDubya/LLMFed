"""Tests for snapshot service — world state save/load."""

import gzip
import json
import pytest
import tempfile
import os

from game_service.snapshot_service import (
    create_snapshot,
    restore_snapshot,
    export_snapshot_to_file,
    import_snapshot_from_file,
    _serialize_row,
)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.db_models import Base
from models.core_models import WorldDB


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
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
    def test_restore_creates_branch(self, db_session, world_with_data):
        snapshot = create_snapshot(db_session, world_with_data.id)
        result = restore_snapshot(db_session, snapshot["data"], create_new_world=True)
        assert result["is_branch"] is True
        assert result["world_id"] != world_with_data.id
        assert result["original_world_id"] == world_with_data.id


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
