"""Agency reuses its roster and loads gimmicks only when an actor acts."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from game_service import character_agent as agency
from game_service.character_prompts import ARCHETYPE_PERSONALITIES
from models.db_models import Base
from models.game_models import GameWrestlerDB, GimmickHistoryDB


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as session:
        yield session
    engine.dispose()


@pytest.mark.parametrize('count,acts', [(0, True), (1, True), (12, True), (12, False)])
def test_agency_select_budget(db, monkeypatch, count, acts):
    db.add_all([GameWrestlerDB(id=f'w{i}', world_id='world', name=f'Actor {i}',
                               popularity=60, is_active=True, is_injured=False)
                for i in range(count)])
    db.flush()
    monkeypatch.setattr(agency, 'USE_LLM', False)
    monkeypatch.setattr(agency.random, 'random', lambda: 0 if acts else 1)
    monkeypatch.setattr(agency.random, 'choice', lambda choices: choices[0])
    selects = []

    def record(conn, cursor, statement, *args):
        if statement.startswith('SELECT'):
            selects.append(statement)

    event.listen(db.bind, 'before_cursor_execute', record)
    try:
        events = agency.tick_character_agency(db, 'world', '2026-01-01')
    finally:
        event.remove(db.bind, 'before_cursor_execute', record)
    assert len(events) == (count if acts else 0)
    assert len(selects) == (2 + count if count and acts else 1)
    assert sum('FROM game_wrestlers' in sql for sql in selects) == 1


@pytest.mark.parametrize('earlier_id,seconds', [('z-earlier', 1), ('a-earlier', 0)])
def test_agency_gimmick_order_and_fallback(db, monkeypatch, earlier_id, seconds):
    db.add(GameWrestlerDB(id='actor', world_id='world', name='Actor', popularity=60,
                          is_active=True, is_injured=False))
    timestamp = datetime(2026, 1, 1)
    db.add_all([
        GimmickHistoryDB(id='m-later', wrestler_id='actor', gimmick_name='Later',
                         archetype='monster_heel', created_at=timestamp + timedelta(seconds=seconds)),
        GimmickHistoryDB(id=earlier_id, wrestler_id='actor', gimmick_name='Earlier',
                         archetype='underdog_face', created_at=timestamp),
        GimmickHistoryDB(id='inactive', wrestler_id='actor', gimmick_name='Old',
                         archetype='monster_heel', created_at=timestamp - timedelta(days=1),
                         is_active=False),
    ])
    db.flush()
    monkeypatch.setattr(agency.random, 'random', lambda: 0)
    monkeypatch.setattr(agency.random, 'choice', lambda choices: choices[0])
    monkeypatch.setattr(agency, 'USE_LLM', True)
    prompts = []
    selects = []

    def record(conn, cursor, statement, *args):
        if statement.startswith('SELECT') and 'FROM gimmick_history' in statement:
            selects.append(statement)

    class BrokenLLM:
        def generate(self, *args, **kwargs):
            prompts.append(kwargs['system_message'])
            raise RuntimeError('unavailable')

    monkeypatch.setattr(agency, '_get_llm', lambda: BrokenLLM())
    event.listen(db.bind, 'before_cursor_execute', record)
    try:
        events = agency.tick_character_agency(db, 'world', '2026-01-01')
    finally:
        event.remove(db.bind, 'before_cursor_execute', record)
    expected = agency.FALLBACK_DECISIONS['underdog_face'][0].replace('_', ' ')
    assert events == [f'Actor: {expected} — Actor acts on instinct.']
    assert len(prompts) == 1
    assert ARCHETYPE_PERSONALITIES['underdog_face'] in prompts[0]
    assert ARCHETYPE_PERSONALITIES['monster_heel'] not in prompts[0]
    assert len(selects) == 1


def test_public_decide_missing_wrestler(db):
    assert agency.character_decide(db, 'missing', '') == {
        'action': 'noop', 'reasoning': 'Wrestler not found',
    }
