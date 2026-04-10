"""Tests for analytics service."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.db_models import Base
from models.core_models import WorldDB
from game_service.analytics_service import world_summary


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
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
