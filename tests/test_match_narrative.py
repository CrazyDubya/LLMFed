"""Tests for match narrative engine — LLM commentary and chemistry system."""

import pytest
from unittest.mock import patch

from core_engine.match_narrative import (
    ChemistryRecord,
    ChemistryTracker,
    narrate_finisher,
    narrate_near_fall,
    narrate_reversal,
    narrate_match_finish,
    narrate_match_psychology,
)


class TestChemistryRecord:
    def test_new_record_defaults(self):
        rec = ChemistryRecord(wrestler_a_id="w1", wrestler_b_id="w2")
        assert rec.match_count == 0
        assert rec.average_rating == 0.0
        assert rec.familiarity_bonus == 0.0

    def test_record_match_increases_count(self):
        rec = ChemistryRecord(wrestler_a_id="w1", wrestler_b_id="w2")
        rec.record_match(3.5, "2025-01-15")
        assert rec.match_count == 1
        assert rec.average_rating == 3.5
        assert rec.best_rating == 3.5
        assert rec.last_match_date == "2025-01-15"

    def test_familiarity_builds_then_decays(self):
        rec = ChemistryRecord(wrestler_a_id="w1", wrestler_b_id="w2")
        bonuses = []
        for i in range(15):
            rec.record_match(3.0)
            bonuses.append(rec.familiarity_bonus)
        # Should build in first 5 matches
        assert bonuses[4] > bonuses[0]
        # Should peak around match 10
        assert bonuses[9] >= bonuses[4]
        # Should decay after 10+
        assert bonuses[14] < bonuses[9]

    def test_best_rating_tracked(self):
        rec = ChemistryRecord(wrestler_a_id="w1", wrestler_b_id="w2")
        rec.record_match(3.0)
        rec.record_match(4.5)
        rec.record_match(2.0)
        assert rec.best_rating == 4.5

    def test_to_dict(self):
        rec = ChemistryRecord(wrestler_a_id="w1", wrestler_b_id="w2")
        rec.record_match(4.0, "2025-06-01")
        d = rec.to_dict()
        assert d["match_count"] == 1
        assert d["average_rating"] == 4.0
        assert d["wrestler_a_id"] == "w1"


class TestChemistryTracker:
    def test_get_creates_new_record(self):
        tracker = ChemistryTracker()
        rec = tracker.get("w1", "w2")
        assert rec.match_count == 0

    def test_canonical_key_order(self):
        tracker = ChemistryTracker()
        rec1 = tracker.get("w2", "w1")
        rec2 = tracker.get("w1", "w2")
        assert rec1 is rec2

    def test_record_match(self):
        tracker = ChemistryTracker()
        rec = tracker.record_match("w1", "w2", 4.0, "2025-01-01")
        assert rec.match_count == 1
        assert rec.average_rating == 4.0

    def test_all_records(self):
        tracker = ChemistryTracker()
        tracker.record_match("w1", "w2", 3.0)
        tracker.record_match("w3", "w4", 4.0)
        assert len(tracker.all_records()) == 2


class TestNarrateFinisher:
    def test_returns_string(self):
        result = narrate_finisher("John Cena", "The Rock", "Attitude Adjustment")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_contains_wrestler_names_in_template(self):
        # With LLM disabled, should use template that includes names
        with patch("core_engine.match_narrative.USE_LLM", False):
            result = narrate_finisher("Stone Cold", "The Rock", "Stone Cold Stunner")
        assert "Stone Cold" in result or "Stunner" in result


class TestNarateNearFall:
    def test_returns_string(self):
        result = narrate_near_fall("HHH", "Undertaker", kickout_count=2)
        assert isinstance(result, str)
        assert len(result) > 0


class TestNarrateReversal:
    def test_returns_string(self):
        result = narrate_reversal("Edge", "Cena", "Powerbomb", "Spear")
        assert isinstance(result, str)

    def test_comeback_context(self):
        with patch("core_engine.match_narrative.USE_LLM", False):
            result = narrate_reversal(
                "Edge", "Cena", "Powerbomb", "Spear", reverser_health=15.0
            )
        assert isinstance(result, str)


class TestNarrateMatchFinish:
    def test_returns_string(self):
        result = narrate_match_finish(
            "John Cena", "The Rock", "pinfall", "Attitude Adjustment", 4.5
        )
        assert isinstance(result, str)

    def test_upset(self):
        with patch("core_engine.match_narrative.USE_LLM", False):
            result = narrate_match_finish(
                "Jobber", "Champion", "pinfall", is_upset=True
            )
        assert isinstance(result, str)


class TestNarrateMatchPsychology:
    def test_early_match(self):
        result = narrate_match_psychology({
            "tick": 3, "target_length": 20,
            "attacker_health": 90, "defender_health": 90,
            "crowd_heat": 30,
        })
        assert result == "feeling_out"

    def test_mid_match(self):
        result = narrate_match_psychology({
            "tick": 10, "target_length": 20,
            "attacker_health": 70, "defender_health": 60,
            "crowd_heat": 50,
        })
        assert result == "build_heat"

    def test_late_match_low_health(self):
        result = narrate_match_psychology({
            "tick": 16, "target_length": 20,
            "attacker_health": 50, "defender_health": 30,
            "crowd_heat": 80,
        })
        assert result == "go_home"

    def test_late_match_both_healthy(self):
        result = narrate_match_psychology({
            "tick": 14, "target_length": 20,
            "attacker_health": 60, "defender_health": 60,
            "crowd_heat": 70,
        })
        assert result == "false_finish"
