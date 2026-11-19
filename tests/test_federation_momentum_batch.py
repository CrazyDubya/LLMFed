"""Daily momentum reads stay bounded and retain roster/show semantics."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from models.db_models import Base
from models.game_models import ContractDB, GameFederationDB, GameWrestlerDB, ShowDB
from game_service.inter_federation_service import update_federation_momentum


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def contract(fed, wrestler, status='active'):
    return ContractDB(world_id='world', federation_id=fed, wrestler_id=wrestler,
                      start_date='2026-01-01', status=status)


@pytest.mark.parametrize('count', [0, 1, 12])
def test_momentum_select_budget(db, count):
    for i in range(count):
        db.add(GameFederationDB(id=f'f{i}', world_id='world', name=f'Fed {i}'))
        db.add(GameWrestlerDB(id=f'w{i}', world_id='world', name=f'Wrestler {i}'))
        db.add(contract(f'f{i}', f'w{i}'))
    db.flush()
    selects = []

    def record(conn, cursor, statement, *args):
        if statement.startswith('SELECT'):
            selects.append(statement)
    event.listen(db.bind, 'before_cursor_execute', record)
    try:
        update_federation_momentum(db, SimpleNamespace(id='world'), [], None, '2026-01-01')
    finally:
        event.remove(db.bind, 'before_cursor_execute', record)
    assert len(selects) == 4


def test_momentum_show_order_and_roster_semantics(db):
    expected = {'first': 52, 'zero': 50, 'low': 49, 'duplicate': 50,
                'shared': 48, 'missing': 50, 'empty': 50, 'boundary': 50,
                'inactive': 70, 'other': 70}
    for name in expected:
        db.add(GameFederationDB(
            id=name, world_id='elsewhere' if name == 'other' else 'world', name=name,
            momentum=70 if name in ('inactive', 'other') else 50,
            is_active=name != 'inactive',
        ))
    for wid, morale in [('sad', 0), ('happy', 90), ('boundary', 40)]:
        db.add(GameWrestlerDB(id=wid, world_id='world', name=wid, morale=morale))
    db.add_all([contract('duplicate', 'sad'), contract('duplicate', 'sad'),
                contract('duplicate', 'happy'), contract('shared', 'sad'),
                contract('shared', 'happy', 'expired'), contract('missing', 'absent'),
                contract('boundary', 'boundary')])
    for index, (sid, fed, rating) in enumerate([
        ('z-first', 'first', 4.5), ('a-second', 'first', 1.0),
        ('z-zero', 'zero', 0.0), ('a-later', 'zero', 4.5), ('low', 'low', 1.0),
    ]):
        db.add(ShowDB(id=sid, world_id='world', federation_id=fed, name=sid,
                      created_at=datetime(2026, 1, 1) + timedelta(seconds=index),
                      game_date='2026-01-01', is_completed=True, overall_rating=rating))
    db.add_all([
        ShowDB(world_id='world', federation_id='empty', name='unfinished',
               game_date='2026-01-01', is_completed=False, overall_rating=5),
        ShowDB(world_id='world', federation_id='empty', name='yesterday',
               game_date='2025-12-31', is_completed=True, overall_rating=5),
    ])
    db.flush()
    # SQLite's federation index visits equal keys in rowid (insertion) order, not UUID order.
    plan = db.execute(text('EXPLAIN QUERY PLAN SELECT * FROM shows '
                           'WHERE federation_id = :fed AND is_completed '
                           'AND game_date = :date LIMIT 1'),
                      {'fed': 'first', 'date': '2026-01-01'}).all()
    assert 'ix_shows_federation_id' in str(plan)
    assert db.query(ShowDB).filter_by(federation_id='first', is_completed=True,
                                    game_date='2026-01-01').first().id == 'z-first'
    update_federation_momentum(db, SimpleNamespace(id='world'), [], None, '2026-01-01')
    assert {f.id: f.momentum for f in db.query(GameFederationDB)} == expected


@pytest.mark.parametrize('earlier_id,seconds', [('z-earlier', 1), ('a-earlier', 0)])
def test_momentum_show_timestamp_order_and_id_tiebreak(db, earlier_id, seconds):
    db.add(GameFederationDB(id='fed', world_id='world', name='Fed', momentum=50))
    timestamp = datetime(2026, 1, 1)
    db.add(ShowDB(id='m-later', world_id='world', federation_id='fed', name='Later',
                  game_date='2026-01-01', is_completed=True, overall_rating=1,
                  created_at=timestamp + timedelta(seconds=seconds)))
    db.add(ShowDB(id=earlier_id, world_id='world', federation_id='fed', name='Earlier',
                  game_date='2026-01-01', is_completed=True, overall_rating=4.5,
                  created_at=timestamp))
    db.flush()
    update_federation_momentum(db, SimpleNamespace(id='world'), [], None, '2026-01-01')
    assert db.get(GameFederationDB, 'fed').momentum == 52
