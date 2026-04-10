"""Tests for the fan service — dynamic audience simulation."""

import pytest
from game_service.fan_service import (
    FanArchetype,
    FanSegment,
    FanBase,
    create_initial_fan_base,
    process_show_impact,
    predict_attendance,
)


class TestFanSegment:
    def test_defaults(self):
        seg = FanSegment(archetype=FanArchetype.CASUAL, population=1000)
        assert seg.population == 1000
        assert seg.satisfaction == 50.0
        assert seg.effective_population == 500.0  # 1000 * 50/100

    def test_effective_population_scales(self):
        seg = FanSegment(archetype=FanArchetype.HARDCORE, population=1000, satisfaction=80)
        assert seg.effective_population == 800.0

    def test_to_dict(self):
        seg = FanSegment(archetype=FanArchetype.SMARK, population=500)
        d = seg.to_dict()
        assert d["archetype"] == "smark"
        assert d["population"] == 500


class TestFanBase:
    def test_total_population(self):
        fb = FanBase(federation_id="f1")
        fb.segments[FanArchetype.CASUAL] = FanSegment(
            archetype=FanArchetype.CASUAL, population=1000
        )
        fb.segments[FanArchetype.HARDCORE] = FanSegment(
            archetype=FanArchetype.HARDCORE, population=500
        )
        assert fb.total_population == 1500

    def test_overall_satisfaction_weighted(self):
        fb = FanBase(federation_id="f1")
        fb.segments[FanArchetype.CASUAL] = FanSegment(
            archetype=FanArchetype.CASUAL, population=1000, satisfaction=80
        )
        fb.segments[FanArchetype.HARDCORE] = FanSegment(
            archetype=FanArchetype.HARDCORE, population=1000, satisfaction=40
        )
        # Weighted average: (80*1000 + 40*1000) / 2000 = 60
        assert fb.overall_satisfaction == 60.0

    def test_to_dict(self):
        fb = create_initial_fan_base("f1", "small")
        d = fb.to_dict()
        assert d["federation_id"] == "f1"
        assert d["total_population"] > 0
        assert "segments" in d
        assert "casual" in d["segments"]


class TestCreateInitialFanBase:
    def test_creates_all_archetypes(self):
        fb = create_initial_fan_base("f1")
        assert len(fb.segments) == 5
        assert FanArchetype.CASUAL in fb.segments
        assert FanArchetype.HARDCORE in fb.segments
        assert FanArchetype.FAMILY in fb.segments
        assert FanArchetype.SMARK in fb.segments
        assert FanArchetype.LAPSED in fb.segments

    def test_size_affects_population(self):
        small = create_initial_fan_base("f1", "small")
        large = create_initial_fan_base("f2", "large")
        assert large.total_population > small.total_population

    def test_casual_is_largest_segment(self):
        fb = create_initial_fan_base("f1")
        casual_pop = fb.segments[FanArchetype.CASUAL].population
        for archetype, seg in fb.segments.items():
            if archetype != FanArchetype.CASUAL:
                assert casual_pop >= seg.population


class TestProcessShowImpact:
    def test_great_show_increases_satisfaction(self):
        fb = create_initial_fan_base("f1")
        initial_sat = fb.overall_satisfaction
        process_show_impact(fb, {
            "match_quality": 4.5,
            "storyline_quality": 85,
            "star_power": 90,
            "spectacle": 80,
            "surprise": 70,
        })
        assert fb.overall_satisfaction > initial_sat

    def test_bad_show_decreases_satisfaction(self):
        fb = create_initial_fan_base("f1")
        # Set initial satisfaction high
        for seg in fb.segments.values():
            seg.satisfaction = 80.0
        initial_sat = fb.overall_satisfaction
        process_show_impact(fb, {
            "match_quality": 1.0,
            "storyline_quality": 15,
            "star_power": 20,
            "spectacle": 10,
            "surprise": 5,
        })
        assert fb.overall_satisfaction < initial_sat

    def test_returns_merch_revenue(self):
        fb = create_initial_fan_base("f1")
        result = process_show_impact(fb, {
            "match_quality": 3.0,
            "storyline_quality": 50,
            "star_power": 50,
            "spectacle": 50,
            "surprise": 50,
        })
        assert result["merch_revenue_this_show"] >= 0
        assert fb.total_merch_revenue > 0

    def test_shows_processed_increments(self):
        fb = create_initial_fan_base("f1")
        process_show_impact(fb, {"match_quality": 3.0})
        process_show_impact(fb, {"match_quality": 3.0})
        assert fb.shows_processed == 2

    def test_churn_on_low_satisfaction(self):
        fb = create_initial_fan_base("f1")
        # Tank satisfaction
        for seg in fb.segments.values():
            seg.satisfaction = 10.0
            seg.loyalty = 10.0
        initial_pop = fb.total_population
        process_show_impact(fb, {
            "match_quality": 0.5,
            "storyline_quality": 5,
            "star_power": 10,
            "spectacle": 5,
            "surprise": 5,
        })
        assert fb.total_population < initial_pop


class TestPredictAttendance:
    def test_weekly_show(self):
        fb = create_initial_fan_base("f1")
        result = predict_attendance(fb, 5000, "weekly", 50)
        assert 0 < result["predicted_attendance"] <= 5000
        assert result["venue_capacity"] == 5000

    def test_ppv_higher_than_weekly(self):
        fb = create_initial_fan_base("f1")
        weekly = predict_attendance(fb, 10000, "weekly", 50)
        ppv = predict_attendance(fb, 10000, "ppv", 50)
        assert ppv["predicted_attendance"] > weekly["predicted_attendance"]

    def test_sellout_detection(self):
        fb = create_initial_fan_base("f1", "national")
        for seg in fb.segments.values():
            seg.satisfaction = 95
            seg.buzz = 90
        result = predict_attendance(fb, 100, "ppv", 95)
        assert result["is_sellout"] is True

    def test_minimum_attendance(self):
        fb = FanBase(federation_id="f1")
        fb.segments[FanArchetype.LAPSED] = FanSegment(
            archetype=FanArchetype.LAPSED, population=10, satisfaction=5
        )
        result = predict_attendance(fb, 1000, "weekly", 10)
        assert result["predicted_attendance"] >= 100  # 10% of capacity min
