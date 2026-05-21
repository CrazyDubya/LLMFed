"""Simulation package: end-to-end federation simulation."""

from simulation.orchestrator import (
    SimulationOrchestrator,
    run_card,
    run_week,
    run_week_from_template,
    run_month,
    run_season,
    build_demo_card,
    build_demo_card_three_matches,
    build_demo_full_card,
)
from simulation.card_builder import build_full_card
from simulation.anchor_card_builder import build_anchor_card
from simulation.week_builder import build_week_from_template, fill_week_matches
from simulation.month_builder import build_month, build_season
from simulation.travel_squad import (
    get_travel_squad,
    get_tv_roster,
    get_house_roster,
    get_ppv_roster,
)

__all__ = [
    "SimulationOrchestrator",
    "run_card",
    "run_week",
    "build_demo_card",
    "build_demo_card_three_matches",
    "build_demo_full_card",
    "build_full_card",
    "build_anchor_card",
    "build_week_from_template",
    "fill_week_matches",
    "run_week_from_template",
    "run_month",
    "run_season",
    "build_month",
    "build_season",
    "get_travel_squad",
    "get_tv_roster",
    "get_house_roster",
    "get_ppv_roster",
]
