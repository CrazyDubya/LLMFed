import pytest
from core_engine.engine import TickScheduler

def test_next_tick_increments():
    sched = TickScheduler()
    assert sched.next_tick() == 1
    assert sched.next_tick() == 2
    assert sched.next_tick() == 3
