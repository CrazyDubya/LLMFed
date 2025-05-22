import pytest

from core_engine.rulebook import RuleBook
from core_engine.engine import AppliedAction


def test_validate_returns_applied_action():
    action_id = "test_action"
    description = "desc"
    meta = {"key": "value"}
    applied = RuleBook.validate(action_id, description, meta)
    assert isinstance(applied, AppliedAction)
    assert applied.action_id == action_id
    assert applied.description == description
    assert applied.effects == meta
