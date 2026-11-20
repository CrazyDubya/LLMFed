"""Tests for analytics service."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agent_service.database import get_db_sync
from api_gateway.main import app
from api_gateway.security import get_current_user, TokenData
from models.db_models import Base
from models.core_models import WorldDB
from models.wrestler_models import GameWrestlerDB
from models.show_models import MatchDB, MatchParticipantDB, ShowDB
from models.wrestler_models import ContractDB
from models.federation_models import GameFederationDB
from game_service.analytics_service import world_summary


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
    engine.dispose()


@pytest.fixture
def analytics_client(db_session):
    overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db_sync] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: TokenData(user_id="analytics-user")
    try:
        yield TestClient(app, base_url="http://localhost")
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides)


@pytest.fixture
def world_with_matches(db_session):
    world = WorldDB(name="Analytics World")
    db_session.add(world)
    db_session.flush()
    winner = GameWrestlerDB(world_id=world.id, name="The Champion")
    loser = GameWrestlerDB(world_id=world.id, name="The Challenger")
    db_session.add_all([winner, loser])
    db_session.flush()
    match = MatchDB(
        world_id=world.id, winner_id=winner.id, is_completed=True,
        match_rating=4.5, crowd_heat=85,
    )
    db_session.add(match)
    db_session.flush()
    db_session.add_all([
        MatchParticipantDB(match_id=match.id, wrestler_id=winner.id, is_winner=True),
        MatchParticipantDB(match_id=match.id, wrestler_id=loser.id),
    ])
    db_session.commit()
    return world, winner, loser, match


class TestAnalyticsRoutes:
    def test_federation_health_uses_world_scoped_metrics(self, analytics_client, db_session, world_with_matches):
        world, wrestler, _, _ = world_with_matches
        other_world = WorldDB(name="Other World")
        federation = GameFederationDB(world_id=world.id, name="Analytics Federation", budget=12345.67)
        db_session.add_all([other_world, federation])
        db_session.flush()
        for data_world in (world, other_world):
            db_session.add_all([
                ContractDB(
                    world_id=data_world.id, federation_id=federation.id, wrestler_id=wrestler.id,
                    start_date="2026-01-01", status="active",
                ),
                ShowDB(
                    world_id=data_world.id, federation_id=federation.id, name="Weekly Show",
                    game_date="2026-01-01", is_completed=True, gate_revenue=1000,
                ),
            ])
        db_session.commit()

        response = analytics_client.get(
            f"/game/analytics/world/{world.id}/federation/{federation.id}"
        )

        assert response.status_code == 200
        assert response.json()["balance"] == 12345.67
        assert response.json()["roster_count"] == 1
        assert response.json()["shows_completed"] == 1
        assert response.json()["total_gate_revenue"] == 1000

    @pytest.mark.parametrize(("resource", "model"), [
        ("wrestler", GameWrestlerDB),
        ("federation", GameFederationDB),
    ])
    def test_analytics_rejects_cross_world_resource(self, analytics_client, db_session, resource, model):
        owner = WorldDB(name="Owner World")
        other = WorldDB(name="Other World")
        db_session.add_all([owner, other])
        db_session.flush()
        entity = model(world_id=owner.id, name="Owner World Entity")
        db_session.add(entity)
        db_session.commit()

        response = analytics_client.get(f"/game/analytics/world/{other.id}/{resource}/{entity.id}")

        assert response.status_code == 404
        assert response.json()["message"] == f"{resource.title()} not found"

    def test_leaderboard_with_matches(self, analytics_client, world_with_matches):
        world, winner, loser, _ = world_with_matches
        response = analytics_client.get(f"/game/analytics/world/{world.id}/leaderboard")
        assert response.status_code == 200
        assert response.json() == [
            {"wrestler_id": winner.id, "name": winner.name, "total_matches": 1,
             "wins": 1, "win_rate": 1.0, "avg_match_rating": 4.5},
            {"wrestler_id": loser.id, "name": loser.name, "total_matches": 1,
             "wins": 0, "win_rate": 0.0, "avg_match_rating": 4.5},
        ]

    @pytest.mark.parametrize("result", ["win", "loss"])
    def test_wrestler_with_matches(self, analytics_client, world_with_matches, result):
        world, winner, loser, match = world_with_matches
        wrestler = winner if result == "win" else loser
        response = analytics_client.get(
            f"/game/analytics/world/{world.id}/wrestler/{wrestler.id}"
        )
        assert response.status_code == 200
        body = response.json()
        assert body["name"] == wrestler.name
        assert body["total_matches"] == 1
        assert body["wins"] == (result == "win")
        assert body["losses"] == (result == "loss")
        assert body["avg_match_rating"] == 4.5
        assert body["recent_matches"] == [{
            "match_id": match.id, "match_type": "singles", "result": result,
            "rating": 4.5, "crowd_heat": 85,
        }]

    def test_empty_leaderboard(self, analytics_client, db_session):
        world = WorldDB(name="No matches")
        db_session.add(world)
        db_session.flush()
        wrestler = GameWrestlerDB(world_id=world.id, name="Debutant")
        db_session.add(wrestler)
        db_session.commit()
        response = analytics_client.get(f"/game/analytics/world/{world.id}/leaderboard")
        assert response.status_code == 200
        assert response.json() == []
        response = analytics_client.get(
            f"/game/analytics/world/{world.id}/wrestler/{wrestler.id}"
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Debutant"
        assert response.json()["total_matches"] == 0
        assert response.json()["recent_matches"] == []

    @pytest.mark.parametrize("resource", ["wrestler", "federation"])
    def test_analytics_rejects_missing_resource(self, analytics_client, world_with_matches, resource):
        world, _, _, _ = world_with_matches
        response = analytics_client.get(f"/game/analytics/world/{world.id}/{resource}/missing")
        assert response.status_code == 404
        assert response.json()["message"] == f"{resource.title()} not found"

    def test_invalid_leaderboard_limit(self, analytics_client):
        response = analytics_client.get("/game/analytics/world/missing/leaderboard?limit=0")
        assert response.status_code == 422


def test_fed_roster_uses_wrestler_name(db_session, world_with_matches, monkeypatch):
    from typer.testing import CliRunner
    from cli.main import app as cli_app

    world, winner, _, _ = world_with_matches
    federation = GameFederationDB(world_id=world.id, name="Analytics Federation")
    db_session.add(federation)
    db_session.flush()
    db_session.add(ContractDB(
        world_id=world.id, federation_id=federation.id, wrestler_id=winner.id,
        start_date="2026-01-01", status="active",
    ))
    db_session.commit()
    monkeypatch.setattr("cli.main._get_db", lambda: db_session)
    result = CliRunner().invoke(cli_app, ["fed", "roster", federation.id])
    assert result.exit_code == 0, result.exception
    assert winner.name in result.stdout


class TestWorldSummary:
    def test_returns_summary(self, db_session):
        world = WorldDB(name="Analytics World")
        db_session.add(world)
        db_session.commit()
        db_session.refresh(world)

        result = world_summary(db_session, world.id)
        assert result["name"] == "Analytics World"
        assert result["federations"] == 0
        assert result["wrestlers"] == 0
        assert result["total_matches"] == 0

    def test_nonexistent_world(self, db_session):
        result = world_summary(db_session, "fake-id")
        assert result.get("error") == "World not found"
