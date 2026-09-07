"""Tests for the maintenance service — data lifecycle management."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base, NarrativeLogDB, EngineRequestDB
from game_service.maintenance_service import (
    archive_narrative_logs,
    archive_engine_requests,
    run_full_maintenance,
    get_table_stats,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _add_narrative_logs(db, count):
    for i in range(count):
        db.add(
            NarrativeLogDB(
                tick_id=f"tick_{i}",
                time_index=i,
                agent_id=f"agent_{i % 3}",
                role="participant",
                description=f"Event {i}",
            )
        )
    db.commit()


def _add_engine_requests(db, count, status="processed"):
    for i in range(count):
        db.add(
            EngineRequestDB(
                request_id=f"req_{i}_{status}",
                agent_id=f"agent_{i % 3}",
                due_tick=i,
                context_json="{}",
                status=status,
            )
        )
    db.commit()


class TestArchiveNarrativeLogs:
    def test_no_deletion_under_retention(self, db_session):
        _add_narrative_logs(db_session, 50)
        deleted = archive_narrative_logs(db_session, retention_count=100)
        assert deleted == 0
        assert db_session.query(NarrativeLogDB).count() == 50

    def test_deletes_oldest_beyond_retention(self, db_session):
        _add_narrative_logs(db_session, 100)
        deleted = archive_narrative_logs(db_session, retention_count=30)
        assert deleted == 70
        assert db_session.query(NarrativeLogDB).count() == 30

    def test_exact_retention_no_delete(self, db_session):
        _add_narrative_logs(db_session, 50)
        deleted = archive_narrative_logs(db_session, retention_count=50)
        assert deleted == 0


class TestArchiveEngineRequests:
    def test_no_deletion_under_retention(self, db_session):
        _add_engine_requests(db_session, 20)
        deleted = archive_engine_requests(db_session, retention_count=100)
        assert deleted == 0

    def test_deletes_oldest_beyond_retention(self, db_session):
        _add_engine_requests(db_session, 80)
        deleted = archive_engine_requests(db_session, retention_count=20)
        assert deleted == 60
        assert (
            db_session.query(EngineRequestDB)
            .filter(EngineRequestDB.status == "processed")
            .count()
            == 20
        )

    def test_only_deletes_processed(self, db_session):
        _add_engine_requests(db_session, 50, status="processed")
        _add_engine_requests(db_session, 10, status="pending")
        deleted = archive_engine_requests(db_session, retention_count=10)
        assert deleted == 40
        # Pending requests untouched
        assert (
            db_session.query(EngineRequestDB)
            .filter(EngineRequestDB.status == "pending")
            .count()
            == 10
        )


class TestRunFullMaintenance:
    def test_full_maintenance(self, db_session):
        _add_narrative_logs(db_session, 200)
        _add_engine_requests(db_session, 100)

        results = run_full_maintenance(
            db_session,
            narrative_retention=50,
            engine_request_retention=30,
        )
        assert results["narrative_logs_deleted"] == 150
        assert results["engine_requests_deleted"] == 70

    def test_full_maintenance_no_work(self, db_session):
        results = run_full_maintenance(db_session)
        assert results["narrative_logs_deleted"] == 0
        assert results["engine_requests_deleted"] == 0


class TestTableStats:
    def test_returns_counts(self, db_session):
        _add_narrative_logs(db_session, 10)
        _add_engine_requests(db_session, 5)
        stats = get_table_stats(db_session)
        assert stats["narrative_logs"] == 10
        assert stats["engine_requests"] == 5
