"""
Fan Service — dynamic fan base and audience simulation.

Models persistent fan segments with distinct preferences, satisfaction tracking,
churn modeling, and merch purchasing behavior. Fan sentiment feeds back into
booking decisions and viewership predictions.

Fan Archetypes:
- Casual: watches big events, prefers star power and simple storylines
- Hardcore: watches everything, values in-ring quality and work rate
- Family: prefers face characters, clean finishes, and wholesome entertainment
- Smark: appreciates technical wrestling, wants "smart" booking, vocal online
- Lapsed: former fans who left due to bad booking, hard to win back
"""

import logging
import random
from dataclasses import dataclass, field
from typing import Dict, Any, List
from enum import Enum

logger = logging.getLogger(__name__)


class FanArchetype(str, Enum):
    CASUAL = "casual"
    HARDCORE = "hardcore"
    FAMILY = "family"
    SMARK = "smark"
    LAPSED = "lapsed"


# What each archetype values (weights for satisfaction calculation)
ARCHETYPE_PREFERENCES = {
    FanArchetype.CASUAL: {
        "star_power": 0.35,
        "storyline_quality": 0.25,
        "match_quality": 0.10,
        "spectacle": 0.20,
        "surprise": 0.10,
    },
    FanArchetype.HARDCORE: {
        "star_power": 0.10,
        "storyline_quality": 0.20,
        "match_quality": 0.40,
        "spectacle": 0.10,
        "surprise": 0.20,
    },
    FanArchetype.FAMILY: {
        "star_power": 0.20,
        "storyline_quality": 0.30,
        "match_quality": 0.10,
        "spectacle": 0.25,
        "surprise": 0.15,
    },
    FanArchetype.SMARK: {
        "star_power": 0.05,
        "storyline_quality": 0.30,
        "match_quality": 0.35,
        "spectacle": 0.05,
        "surprise": 0.25,
    },
    FanArchetype.LAPSED: {
        "star_power": 0.25,
        "storyline_quality": 0.35,
        "match_quality": 0.15,
        "spectacle": 0.15,
        "surprise": 0.10,
    },
}

# How easily each archetype churns (higher = more likely to leave)
CHURN_SENSITIVITY = {
    FanArchetype.CASUAL: 0.15,
    FanArchetype.HARDCORE: 0.05,
    FanArchetype.FAMILY: 0.10,
    FanArchetype.SMARK: 0.12,
    FanArchetype.LAPSED: 0.25,
}

# Merch spending multiplier per archetype
MERCH_MULTIPLIER = {
    FanArchetype.CASUAL: 0.8,
    FanArchetype.HARDCORE: 1.5,
    FanArchetype.FAMILY: 1.2,
    FanArchetype.SMARK: 1.0,
    FanArchetype.LAPSED: 0.3,
}


@dataclass
class FanSegment:
    """A segment of the fan base with shared preferences."""

    archetype: FanArchetype
    population: int = 0
    satisfaction: float = 50.0  # 0-100
    loyalty: float = 50.0  # 0-100, how resistant to churning
    buzz: float = 0.0  # 0-100, social media excitement
    merch_spend_per_capita: float = 10.0  # Base $ per fan per show
    favorite_wrestlers: List[str] = field(default_factory=list)
    disliked_wrestlers: List[str] = field(default_factory=list)

    @property
    def effective_population(self) -> float:
        """Population weighted by satisfaction (unhappy fans don't attend)."""
        return self.population * (self.satisfaction / 100)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "archetype": self.archetype.value,
            "population": self.population,
            "satisfaction": round(self.satisfaction, 1),
            "loyalty": round(self.loyalty, 1),
            "buzz": round(self.buzz, 1),
            "effective_population": round(self.effective_population),
            "merch_spend_per_capita": round(self.merch_spend_per_capita, 2),
        }


@dataclass
class FanBase:
    """Complete fan base for a federation."""

    federation_id: str
    segments: Dict[FanArchetype, FanSegment] = field(default_factory=dict)
    total_merch_revenue: float = 0.0
    shows_processed: int = 0

    @property
    def total_population(self) -> int:
        return sum(s.population for s in self.segments.values())

    @property
    def total_effective(self) -> float:
        return sum(s.effective_population for s in self.segments.values())

    @property
    def overall_satisfaction(self) -> float:
        total_pop = self.total_population
        if total_pop == 0:
            return 50.0
        return (
            sum(s.satisfaction * s.population for s in self.segments.values())
            / total_pop
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "federation_id": self.federation_id,
            "total_population": self.total_population,
            "total_effective": round(self.total_effective),
            "overall_satisfaction": round(self.overall_satisfaction, 1),
            "total_merch_revenue": round(self.total_merch_revenue, 2),
            "shows_processed": self.shows_processed,
            "segments": {k.value: v.to_dict() for k, v in self.segments.items()},
        }


def create_initial_fan_base(
    federation_id: str,
    federation_size: str = "medium",
) -> FanBase:
    """Create a fan base for a new federation based on its size tier."""
    size_multipliers = {
        "small": 0.3,
        "medium": 1.0,
        "large": 2.5,
        "national": 5.0,
    }
    mult = size_multipliers.get(federation_size, 1.0)

    fan_base = FanBase(federation_id=federation_id)

    # Distribution: casual 40%, hardcore 20%, family 20%, smark 15%, lapsed 5%
    distributions = {
        FanArchetype.CASUAL: int(4000 * mult),
        FanArchetype.HARDCORE: int(2000 * mult),
        FanArchetype.FAMILY: int(2000 * mult),
        FanArchetype.SMARK: int(1500 * mult),
        FanArchetype.LAPSED: int(500 * mult),
    }

    for archetype, pop in distributions.items():
        fan_base.segments[archetype] = FanSegment(
            archetype=archetype,
            population=pop,
            satisfaction=50.0 + random.uniform(-10, 10),
            loyalty=50.0 + random.uniform(-10, 10),
        )

    return fan_base


def process_show_impact(
    fan_base: FanBase,
    show_metrics: Dict[str, Any],
) -> Dict[str, Any]:
    """Update fan sentiment based on a completed show's metrics.

    show_metrics should include:
    - match_quality: 0-5 average star rating
    - storyline_quality: 0-100
    - star_power: 0-100 (combined drawing power of the card)
    - spectacle: 0-100 (special matches, pyro, production)
    - surprise: 0-100 (unexpected turns, upsets, debuts)
    - featured_wrestlers: list of wrestler_ids in main events

    Returns a summary of fan base changes.
    """
    changes = {}
    total_merch = 0.0

    # Normalize match quality to 0-100 scale
    mq = (show_metrics.get("match_quality", 2.5) / 5.0) * 100

    scores = {
        "star_power": show_metrics.get("star_power", 50),
        "storyline_quality": show_metrics.get("storyline_quality", 50),
        "match_quality": mq,
        "spectacle": show_metrics.get("spectacle", 50),
        "surprise": show_metrics.get("surprise", 30),
    }

    for archetype, segment in fan_base.segments.items():
        prefs = ARCHETYPE_PREFERENCES[archetype]
        # Weighted satisfaction score from show
        show_score = sum(scores.get(k, 50) * w for k, w in prefs.items())

        # Satisfaction moves toward show_score with momentum
        old_sat = segment.satisfaction
        segment.satisfaction = 0.7 * segment.satisfaction + 0.3 * show_score
        segment.satisfaction = max(0, min(100, segment.satisfaction))

        # Buzz spikes with surprise and quality
        segment.buzz = min(100, segment.buzz * 0.5 + show_score * 0.1)

        # Churn: unhappy fans leave
        churn_rate = CHURN_SENSITIVITY[archetype]
        if segment.satisfaction < 30:
            lost = int(segment.population * churn_rate * (1 - segment.loyalty / 100))
            segment.population = max(0, segment.population - lost)
        elif segment.satisfaction > 70:
            # Happy fans attract new fans (word of mouth)
            gained = int(segment.population * 0.02 * (segment.buzz / 100))
            segment.population += gained

        # Loyalty slowly shifts toward satisfaction
        segment.loyalty = 0.9 * segment.loyalty + 0.1 * segment.satisfaction

        # Merch revenue
        merch = (
            segment.effective_population
            * segment.merch_spend_per_capita
            * MERCH_MULTIPLIER[archetype]
            / 100  # Per-show fraction
        )
        total_merch += merch

        changes[archetype.value] = {
            "satisfaction_delta": round(segment.satisfaction - old_sat, 1),
            "population": segment.population,
            "buzz": round(segment.buzz, 1),
        }

    fan_base.total_merch_revenue += total_merch
    fan_base.shows_processed += 1

    return {
        "changes": changes,
        "merch_revenue_this_show": round(total_merch, 2),
        "total_population": fan_base.total_population,
        "overall_satisfaction": round(fan_base.overall_satisfaction, 1),
    }


def predict_attendance(
    fan_base: FanBase,
    venue_capacity: int,
    show_type: str = "weekly",
    card_star_power: float = 50.0,
) -> Dict[str, Any]:
    """Predict attendance for an upcoming show based on fan sentiment."""
    base = fan_base.total_effective

    # Show type multiplier
    type_mult = {
        "weekly": 0.3,
        "special": 0.5,
        "ppv": 0.8,
        "supershow": 1.0,
    }.get(show_type, 0.3)

    # Star power boost
    star_mult = 0.8 + (card_star_power / 100) * 0.4

    # Buzz boost
    avg_buzz = sum(s.buzz for s in fan_base.segments.values()) / max(
        len(fan_base.segments), 1
    )
    buzz_mult = 1.0 + (avg_buzz / 100) * 0.2

    predicted = int(base * type_mult * star_mult * buzz_mult)
    predicted = min(predicted, venue_capacity)
    predicted = max(predicted, int(venue_capacity * 0.1))  # Minimum 10% (comps)

    sellout = predicted >= venue_capacity * 0.95

    return {
        "predicted_attendance": predicted,
        "venue_capacity": venue_capacity,
        "fill_rate": round(predicted / venue_capacity, 2) if venue_capacity > 0 else 0,
        "is_sellout": sellout,
        "factors": {
            "effective_fan_base": round(base),
            "show_type_mult": type_mult,
            "star_power_mult": round(star_mult, 2),
            "buzz_mult": round(buzz_mult, 2),
        },
    }
