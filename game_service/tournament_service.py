"""
Tournament Service — bracket generation, advancement, and special event formats.

Supports single elimination, double elimination, round-robin, Royal Rumble,
and gauntlet match formats with automatic bracket advancement and seeding.
"""

import logging
import random
import math
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class TournamentFormat(str, Enum):
    SINGLE_ELIMINATION = "single_elimination"
    DOUBLE_ELIMINATION = "double_elimination"
    ROUND_ROBIN = "round_robin"
    ROYAL_RUMBLE = "royal_rumble"
    GAUNTLET = "gauntlet"


class MatchStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class TournamentParticipant:
    """A wrestler entered in the tournament."""
    wrestler_id: str
    name: str
    seed: int = 0
    ranking: int = 0
    eliminated: bool = False
    wins: int = 0
    losses: int = 0
    points: float = 0.0  # For round-robin
    entry_number: int = 0  # For Royal Rumble


@dataclass
class TournamentMatch:
    """A single match within the tournament bracket."""
    match_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    round_number: int = 0
    match_number: int = 0
    participant_a_id: Optional[str] = None
    participant_b_id: Optional[str] = None
    winner_id: Optional[str] = None
    loser_id: Optional[str] = None
    status: MatchStatus = MatchStatus.PENDING
    next_match_id: Optional[str] = None  # Winner advances to this match
    stipulation: Optional[str] = None
    is_final: bool = False

    def is_ready(self) -> bool:
        """Both participants are set and match hasn't been played."""
        return (
            self.participant_a_id is not None
            and self.participant_b_id is not None
            and self.status == MatchStatus.PENDING
        )


@dataclass
class TournamentBracket:
    """Complete tournament bracket with all rounds and matches."""
    tournament_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    format: TournamentFormat = TournamentFormat.SINGLE_ELIMINATION
    participants: List[TournamentParticipant] = field(default_factory=list)
    matches: List[TournamentMatch] = field(default_factory=list)
    current_round: int = 1
    total_rounds: int = 0
    winner_id: Optional[str] = None
    stakes: str = ""  # e.g., "World Championship shot", "Contract"
    is_complete: bool = False

    def get_pending_matches(self) -> List[TournamentMatch]:
        return [m for m in self.matches if m.is_ready()]

    def get_round_matches(self, round_num: int) -> List[TournamentMatch]:
        return [m for m in self.matches if m.round_number == round_num]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tournament_id": self.tournament_id,
            "name": self.name,
            "format": self.format.value,
            "participant_count": len(self.participants),
            "total_rounds": self.total_rounds,
            "current_round": self.current_round,
            "matches_total": len(self.matches),
            "matches_completed": sum(1 for m in self.matches if m.status == MatchStatus.COMPLETED),
            "winner_id": self.winner_id,
            "stakes": self.stakes,
            "is_complete": self.is_complete,
        }


# ---------------------------------------------------------------------------
# Bracket generation
# ---------------------------------------------------------------------------

def create_tournament(
    name: str,
    format: TournamentFormat,
    wrestler_ids: List[str],
    wrestler_names: Dict[str, str] = None,
    rankings: Dict[str, int] = None,
    stakes: str = "",
) -> TournamentBracket:
    """Create a tournament with seeded participants and generated bracket."""
    if len(wrestler_ids) < 2:
        raise ValueError("Tournament requires at least 2 participants")

    wrestler_names = wrestler_names or {}
    rankings = rankings or {}

    # Create participants with seeding
    participants = []
    for i, wid in enumerate(wrestler_ids):
        participants.append(TournamentParticipant(
            wrestler_id=wid,
            name=wrestler_names.get(wid, f"Wrestler {i+1}"),
            seed=i + 1,
            ranking=rankings.get(wid, 999),
        ))

    # Sort by ranking for seeding
    participants.sort(key=lambda p: p.ranking)
    for i, p in enumerate(participants):
        p.seed = i + 1

    bracket = TournamentBracket(
        name=name,
        format=format,
        participants=participants,
        stakes=stakes,
    )

    if format == TournamentFormat.SINGLE_ELIMINATION:
        _generate_single_elimination(bracket)
    elif format == TournamentFormat.ROUND_ROBIN:
        _generate_round_robin(bracket)
    elif format == TournamentFormat.ROYAL_RUMBLE:
        _generate_royal_rumble(bracket)
    elif format == TournamentFormat.GAUNTLET:
        _generate_gauntlet(bracket)
    elif format == TournamentFormat.DOUBLE_ELIMINATION:
        _generate_single_elimination(bracket)  # Simplified: use SE structure

    return bracket


def _generate_single_elimination(bracket: TournamentBracket) -> None:
    """Generate a single-elimination bracket with byes for non-power-of-2."""
    n = len(bracket.participants)
    total_rounds = math.ceil(math.log2(n))
    bracket.total_rounds = total_rounds

    # Pad to next power of 2 with byes
    bracket_size = 2 ** total_rounds
    seeded = list(bracket.participants)

    # Standard bracket seeding (1 vs last, 2 vs second-last, etc.)
    first_round_matches = bracket_size // 2

    matches_by_round: Dict[int, List[TournamentMatch]] = {}

    # Generate all rounds
    for round_num in range(1, total_rounds + 1):
        num_matches = bracket_size // (2 ** round_num)
        round_matches = []
        for match_num in range(num_matches):
            match = TournamentMatch(
                round_number=round_num,
                match_number=match_num + 1,
                is_final=(round_num == total_rounds),
            )
            round_matches.append(match)
            bracket.matches.append(match)
        matches_by_round[round_num] = round_matches

    # Link matches: winner of match N in round R goes to match N//2 in round R+1
    for round_num in range(1, total_rounds):
        current = matches_by_round[round_num]
        next_round = matches_by_round[round_num + 1]
        for i, match in enumerate(current):
            match.next_match_id = next_round[i // 2].match_id

    # Populate first round with seeded participants
    first_round = matches_by_round[1]
    for i, match in enumerate(first_round):
        idx_a = i
        idx_b = first_round_matches * 2 - 1 - i

        if idx_a < n:
            match.participant_a_id = seeded[idx_a].wrestler_id
        if idx_b < n:
            match.participant_b_id = seeded[idx_b].wrestler_id

        # Handle byes (only one participant)
        if match.participant_a_id and not match.participant_b_id:
            match.winner_id = match.participant_a_id
            match.status = MatchStatus.COMPLETED
            _advance_winner(bracket, match)
        elif match.participant_b_id and not match.participant_a_id:
            match.winner_id = match.participant_b_id
            match.status = MatchStatus.COMPLETED
            _advance_winner(bracket, match)


def _generate_round_robin(bracket: TournamentBracket) -> None:
    """Generate a full round-robin schedule."""
    participants = bracket.participants
    n = len(participants)
    bracket.total_rounds = n - 1 if n % 2 == 0 else n

    round_num = 0
    match_num = 0
    for i in range(n):
        for j in range(i + 1, n):
            round_num = (match_num // (n // 2)) + 1 if n > 2 else match_num + 1
            match_num += 1
            bracket.matches.append(TournamentMatch(
                round_number=round_num,
                match_number=match_num,
                participant_a_id=participants[i].wrestler_id,
                participant_b_id=participants[j].wrestler_id,
            ))


def _generate_royal_rumble(bracket: TournamentBracket) -> None:
    """Generate a Royal Rumble — timed entry elimination."""
    participants = list(bracket.participants)
    random.shuffle(participants)
    for i, p in enumerate(participants):
        p.entry_number = i + 1

    bracket.total_rounds = 1
    # Rumble is a single "match" with multiple eliminations tracked elsewhere
    bracket.matches.append(TournamentMatch(
        round_number=1,
        match_number=1,
        participant_a_id=participants[0].wrestler_id if participants else None,
        participant_b_id=participants[1].wrestler_id if len(participants) > 1 else None,
        stipulation="royal_rumble",
        is_final=True,
    ))


def _generate_gauntlet(bracket: TournamentBracket) -> None:
    """Generate a gauntlet match — one wrestler faces all others sequentially."""
    participants = list(bracket.participants)
    random.shuffle(participants)
    bracket.total_rounds = len(participants) - 1

    for i in range(len(participants) - 1):
        bracket.matches.append(TournamentMatch(
            round_number=i + 1,
            match_number=1,
            participant_a_id=participants[i].wrestler_id,
            participant_b_id=participants[i + 1].wrestler_id,
            stipulation="gauntlet",
            is_final=(i == len(participants) - 2),
        ))


# ---------------------------------------------------------------------------
# Match result recording and bracket advancement
# ---------------------------------------------------------------------------

def _advance_winner(bracket: TournamentBracket, match: TournamentMatch) -> None:
    """Place the winner of a match into the next round."""
    if not match.next_match_id or not match.winner_id:
        return

    next_match = next(
        (m for m in bracket.matches if m.match_id == match.next_match_id), None
    )
    if next_match is None:
        return

    if next_match.participant_a_id is None:
        next_match.participant_a_id = match.winner_id
    elif next_match.participant_b_id is None:
        next_match.participant_b_id = match.winner_id


def record_match_result(
    bracket: TournamentBracket,
    match_id: str,
    winner_id: str,
) -> Dict[str, Any]:
    """Record the result of a tournament match and advance the bracket.

    Returns info about what happened (advancement, tournament completion, etc.)
    """
    match = next((m for m in bracket.matches if m.match_id == match_id), None)
    if match is None:
        raise ValueError(f"Match '{match_id}' not found in tournament")

    if match.status == MatchStatus.COMPLETED:
        raise ValueError("Match already completed")

    if winner_id not in (match.participant_a_id, match.participant_b_id):
        raise ValueError(f"Winner '{winner_id}' is not a participant in this match")

    # Record result
    match.winner_id = winner_id
    match.loser_id = (
        match.participant_b_id
        if winner_id == match.participant_a_id
        else match.participant_a_id
    )
    match.status = MatchStatus.COMPLETED

    # Update participant records
    for p in bracket.participants:
        if p.wrestler_id == winner_id:
            p.wins += 1
            if bracket.format == TournamentFormat.ROUND_ROBIN:
                p.points += 3  # 3 points for a win
        elif p.wrestler_id == match.loser_id:
            p.losses += 1
            if bracket.format == TournamentFormat.SINGLE_ELIMINATION:
                p.eliminated = True

    # Advance winner
    _advance_winner(bracket, match)

    # Check for tournament completion
    result = {
        "match_id": match_id,
        "winner_id": winner_id,
        "loser_id": match.loser_id,
        "round": match.round_number,
        "is_final": match.is_final,
        "tournament_complete": False,
    }

    if match.is_final:
        bracket.winner_id = winner_id
        bracket.is_complete = True
        result["tournament_complete"] = True
        result["tournament_winner_id"] = winner_id
        logger.info("Tournament '%s' completed! Winner: %s", bracket.name, winner_id)

    # Update current round
    completed_in_round = sum(
        1 for m in bracket.matches
        if m.round_number == bracket.current_round and m.status == MatchStatus.COMPLETED
    )
    total_in_round = sum(
        1 for m in bracket.matches if m.round_number == bracket.current_round
    )
    if completed_in_round >= total_in_round and not bracket.is_complete:
        bracket.current_round += 1

    return result


def get_standings(bracket: TournamentBracket) -> List[Dict[str, Any]]:
    """Get current tournament standings (especially useful for round-robin)."""
    standings = []
    for p in bracket.participants:
        standings.append({
            "wrestler_id": p.wrestler_id,
            "name": p.name,
            "seed": p.seed,
            "wins": p.wins,
            "losses": p.losses,
            "points": p.points,
            "eliminated": p.eliminated,
        })

    if bracket.format == TournamentFormat.ROUND_ROBIN:
        standings.sort(key=lambda s: (-s["points"], -s["wins"], s["losses"]))
    else:
        standings.sort(key=lambda s: (s["eliminated"], -s["wins"], s["seed"]))

    return standings
