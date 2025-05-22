import pytest
from core_engine.heat import (
    calculate_match_heat,
    calculate_segment_heat,
    update_wrestler_heat,
    update_feud_heat,
)

class Dummy:
    def __init__(self, current_heat=0):
        self.current_heat = current_heat


def test_calculate_match_heat_default():
    assert calculate_match_heat({}) == 0
    assert calculate_match_heat({"heat": 5}) == 5


def test_calculate_segment_heat_default():
    assert calculate_segment_heat({}) == 0
    assert calculate_segment_heat({"heat": 3}) == 3


def test_update_wrestler_heat():
    w = Dummy(current_heat=10)
    new = update_wrestler_heat(w, 5)
    assert new == 15
    assert w.current_heat == 15


def test_update_feud_heat():
    feud = {"heat": 7}
    new = update_feud_heat(feud, -2)
    assert new == 5
    assert feud["heat"] == 5
