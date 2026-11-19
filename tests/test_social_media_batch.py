"""Daily social post lookups should not scale with the number of posters."""
import random
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from models.db_models import Base
from models.game_models import (
    GameWrestlerDB, SocialMediaPostDB, GameFederationDB, ContractDB,
    WrestlerBackstoryDB, GimmickHistoryDB,
)
from game_service import social_media_service as social


@pytest.mark.parametrize('count', [0, 1, 12])
def test_daily_post_select_budget(monkeypatch, count):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    monkeypatch.delenv('LLMFED_USE_LLM', raising=False)
    monkeypatch.setattr(social.random, 'random', lambda: 0.0)
    monkeypatch.setattr(social, 'check_viral_moment', lambda post: False)
    with Session(engine) as db:
        db.add_all([GameWrestlerDB(id=f'w{i}', world_id='world', name=f'Wrestler {i}',
                                  popularity=50, is_active=True) for i in range(count)])
        db.commit()
        selects = []

        def record(conn, cursor, statement, *args):
            if statement.startswith('SELECT'):
                selects.append(statement)

        event.listen(engine, 'before_cursor_execute', record)
        social.tick_social_media(db, 'world', '2026-01-01')
        event.remove(engine, 'before_cursor_execute', record)
        assert len(selects) <= 6
        posts = db.query(SocialMediaPostDB).all()
        assert len(posts) == count
        assert all(post.post_type == 'kayfabe' for post in posts)
    engine.dispose()


def test_missing_wrestler_returns_none():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        assert social.generate_social_post(db, 'missing', 'world', '2026-01-01') is None
        assert db.query(SocialMediaPostDB).count() == 0
    engine.dispose()


@pytest.mark.parametrize('policy,allows_worked_shoots', [
    ('strict_kayfabe', True), ('guided', True), ('guided', False),
])
def test_daily_posts_match_standalone_generation(monkeypatch, policy, allows_worked_shoots):
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    monkeypatch.delenv('LLMFED_USE_LLM', raising=False)
    monkeypatch.setattr(social, 'check_viral_moment', lambda post: False)
    with Session(engine) as db:
        fed = GameFederationDB(id='fed', world_id='world', name='Fed',
                               social_media_policy=policy, allows_worked_shoots=allows_worked_shoots)
        db.add(fed)
        for i in range(100):
            wid = f'w{i}'
            db.add(GameWrestlerDB(id=wid, world_id='world', name=wid, popularity=80,
                                 alignment='heel', hometown='Home', kayfabe_commitment=10))
            db.add(ContractDB(world_id='world', wrestler_id=wid, federation_id='fed',
                              start_date='2026-01-01'))
            db.add(WrestlerBackstoryDB(wrestler_id=wid, real_personality={'media_savvy': 90}))
            db.add(GimmickHistoryDB(wrestler_id=wid, gimmick_name='Persona', is_active=True))
        db.commit()
        initial_rng = random.getstate()
        try:
            random.seed(42)
            for wrestler in db.query(GameWrestlerDB).all():
                if random.random() < 0.13:
                    social.generate_social_post(db, wrestler.id, 'world', '2026-01-01')
            expected_rng = random.getstate()
            columns = [c.name for c in SocialMediaPostDB.__table__.columns
                       if c.name not in ('id', 'created_at')]

            def outputs():
                return [tuple(getattr(post, c) for c in columns)
                        for post in db.query(SocialMediaPostDB).all()]

            expected = outputs()
            db.query(SocialMediaPostDB).delete(synchronize_session=False)
            random.seed(42)
            social.tick_social_media(db, 'world', '2026-01-01')
            assert outputs() == expected
            assert random.getstate() == expected_rng
        finally:
            random.setstate(initial_rng)
    engine.dispose()
