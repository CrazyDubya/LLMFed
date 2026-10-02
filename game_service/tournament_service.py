"""
Tournament Service — bracket generation, advancement, and special event formats.

Supports single elimination, double elimination, round-robin, Royal Rumble,
and gauntlet match formats with automatic bracket advancement and seeding.
"""

import logging
import random
import math
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
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
    BYE = "bye"
    SKIPPED = "skipped"


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

    # Explicit DAG edges for double elimination; next_match_id remains the
    # compatible winner-destination mirror. Slots are "a" or "b".
    winner_next_match_id: Optional[str] = None
    winner_next_slot: Optional[str] = None
    loser_next_match_id: Optional[str] = None
    loser_next_slot: Optional[str] = None
    stage: str = ""
    participant_a_resolved: bool = True
    participant_b_resolved: bool = True
    active: bool = True

    def is_ready(self) -> bool:
        """Both participants are set and match hasn't been played."""
        return (
            self.active
            and self.participant_a_resolved
            and self.participant_b_resolved
            and self.participant_a_id is not None
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

    if len(set(wrestler_ids)) != len(wrestler_ids):
        raise ValueError("Tournament participants must be unique")

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
        _generate_double_elimination(bracket)

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


def _generate_double_elimination(bracket: TournamentBracket) -> None:
    """Build a seeded winners/losers DAG with a pre-generated reset final.

    Preserve SE's first-vs-last pairings and adjacent winner merges. Highest
    seeds receive byes. Losers rounds alternate consolidation and WB drops;
    reversed drops avoid immediate rematches where the field permits it.
    """
    n = len(bracket.participants)
    rounds = (n - 1).bit_length()
    size = 1 << rounds

    def make_round(stage: str, number: int, count: int) -> List[TournamentMatch]:
        matches = [TournamentMatch(
            match_id=f"{stage}-{number}-{i + 1}",
            stage=stage, round_number=number, match_number=i + 1,
            participant_a_resolved=False, participant_b_resolved=False,
        ) for i in range(count)]
        bracket.matches.extend(matches)
        return matches

    def link(source: TournamentMatch, outcome: str,
             target: TournamentMatch, slot: str) -> None:
        setattr(source, f"{outcome}_next_match_id", target.match_id)
        setattr(source, f"{outcome}_next_slot", slot)
        if outcome == "winner":
            source.next_match_id = target.match_id

    winners = [make_round("winners", r, size >> r)
               for r in range(1, rounds + 1)]
    for current, following in zip(winners, winners[1:]):
        for i, match in enumerate(current):
            link(match, "winner", following[i // 2], "ab"[i % 2])

    final = make_round("grand_final", 1, 1)[0]
    final.is_final = True
    reset = make_round("reset_final", 1, 1)[0]
    reset.is_final = True
    reset.active = False
    link(final, "winner", reset, "a")
    link(final, "loser", reset, "b")
    link(winners[-1][0], "winner", final, "a")

    if rounds == 1:
        # With two entrants the WB loser is already the LB champion.
        link(winners[0][0], "loser", final, "b")
    else:
        lower = make_round("losers", 1, size // 4)
        for i, match in enumerate(winners[0]):
            link(match, "loser", lower[i // 2], "ab"[i % 2])
        for r in range(2, rounds + 1):
            incoming = make_round("losers", 2 * r - 2, len(winners[r - 1]))
            for i, match in enumerate(lower):
                link(match, "winner", incoming[i], "a")
            for i, match in enumerate(reversed(winners[r - 1])):
                link(match, "loser", incoming[i], "b")
            lower = incoming
            if r < rounds:
                lower = make_round("losers", 2 * r - 1, len(incoming) // 2)
                for i, match in enumerate(incoming):
                    link(match, "winner", lower[i // 2], "ab"[i % 2])
        link(lower[0], "winner", final, "b")

    # round_number is stage-local. total_rounds counts maximum dependency
    # waves, including the optional reset; current_round is the earliest
    # unfinished active wave, not a scheduling barrier.
    for i, match in enumerate(winners[0]):
        match.participant_a_id = bracket.participants[i].wrestler_id
        other = size - 1 - i
        if other < n:
            match.participant_b_id = bracket.participants[other].wrestler_id
        match.participant_a_resolved = match.participant_b_resolved = True
    _resolve_double_elimination_byes(bracket)
    _update_double_elimination_round(bracket)


def _route_outcome(bracket: TournamentBracket, match: TournamentMatch,
                   outcome: str, participant_id: Optional[str]) -> None:
    """Resolve one explicit destination, including an empty bye output."""
    target_id = getattr(match, f"{outcome}_next_match_id")
    slot = getattr(match, f"{outcome}_next_slot")
    if target_id is None and slot is None:
        return
    target = next((m for m in bracket.matches if m.match_id == target_id), None)
    if target is None or slot not in ("a", "b"):
        raise ValueError("Invalid progression destination")
    field_name = f"participant_{slot}_id"
    resolved_name = f"participant_{slot}_resolved"
    if target.status != MatchStatus.PENDING:
        raise ValueError("Progression destination is already settled")
    if getattr(target, resolved_name) or getattr(target, field_name) is not None:
        raise ValueError("Progression destination slot is already occupied or resolved")
    other = target.participant_b_id if slot == "a" else target.participant_a_id
    if participant_id is not None and participant_id == other:
        raise ValueError("Progression would pair a participant with themselves")
    setattr(target, field_name, participant_id)
    setattr(target, resolved_name, True)


def _resolve_double_elimination_byes(bracket: TournamentBracket) -> None:
    """Propagate empty inputs only after both predecessors are resolved."""
    changed = True
    while changed:
        changed = False
        for match in bracket.matches:
            if (not match.active or match.status != MatchStatus.PENDING
                    or not match.participant_a_resolved or not match.participant_b_resolved
                    or (match.participant_a_id is not None and match.participant_b_id is not None)):
                continue
            match.winner_id = match.participant_a_id or match.participant_b_id
            match.status = MatchStatus.BYE
            _route_outcome(bracket, match, "winner", match.winner_id)
            _route_outcome(bracket, match, "loser", None)
            changed = True


def _update_double_elimination_round(bracket: TournamentBracket) -> None:
    """Report the earliest unfinished dependency wave, never gate readiness."""
    depths: Dict[str, int] = {}
    predecessors: Dict[str, List[str]] = {m.match_id: [] for m in bracket.matches}
    for match in bracket.matches:
        for target in (match.winner_next_match_id, match.loser_next_match_id):
            if target is not None:
                predecessors[target].append(match.match_id)
    remaining = list(bracket.matches)
    while remaining:
        ready = [m for m in remaining if all(p in depths for p in predecessors[m.match_id])]
        if not ready:
            raise ValueError("Tournament progression contains a cycle")
        for match in ready:
            depths[match.match_id] = 1 + max(
                (depths[p] for p in predecessors[match.match_id]), default=0)
            remaining.remove(match)
    bracket.total_rounds = max(depths.values())
    pending = [depths[m.match_id] for m in bracket.matches
               if m.active and m.status in (MatchStatus.PENDING, MatchStatus.IN_PROGRESS)]
    bracket.current_round = min(pending) if pending else max(
        depths[m.match_id] for m in bracket.matches if m.status == MatchStatus.COMPLETED)


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

    if bracket.format == TournamentFormat.DOUBLE_ELIMINATION:
        return _record_double_elimination_result(bracket, match, winner_id)

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


def _record_double_elimination_result(
    bracket: TournamentBracket, match: TournamentMatch, winner_id: str,
) -> Dict[str, Any]:
    """Apply the DAG transactionally so invalid edges cannot partially record a result."""
    if (not match.active or not match.participant_a_resolved
            or not match.participant_b_resolved
            or match.participant_a_id is None or match.participant_b_id is None
            or match.status not in (MatchStatus.PENDING, MatchStatus.IN_PROGRESS)):
        raise ValueError("Match is not ready for a result")
    if bracket.is_complete:
        raise ValueError("Tournament already completed")

    updated = deepcopy(bracket)
    played = next(m for m in updated.matches if m.match_id == match.match_id)
    played.winner_id = winner_id
    played.loser_id = (played.participant_b_id if winner_id == played.participant_a_id
                       else played.participant_a_id)
    played.status = MatchStatus.COMPLETED
    for participant in updated.participants:
        if participant.wrestler_id == played.winner_id:
            participant.wins += 1
        elif participant.wrestler_id == played.loser_id:
            participant.losses += 1
            participant.eliminated = participant.losses == 2

    complete = played.stage == "reset_final"
    if played.stage == "grand_final":
        reset = next(m for m in updated.matches if m.stage == "reset_final")
        complete = winner_id == played.participant_a_id  # undefeated WB champion
        if complete:
            reset.status = MatchStatus.SKIPPED
        else:
            reset.active = True
    if not complete:
        _route_outcome(updated, played, "winner", played.winner_id)
        _route_outcome(updated, played, "loser", played.loser_id)
        _resolve_double_elimination_byes(updated)
    else:
        updated.winner_id = winner_id
        updated.is_complete = True
    _update_double_elimination_round(updated)

    # Preserve references held by callers while committing the validated state.
    for original, new in zip(bracket.matches, updated.matches):
        original.__dict__.update(new.__dict__)
    for original, new in zip(bracket.participants, updated.participants):
        original.__dict__.update(new.__dict__)
    bracket.current_round = updated.current_round
    bracket.winner_id = updated.winner_id
    bracket.is_complete = updated.is_complete
    result = {
        "match_id": match.match_id, "winner_id": winner_id,
        "loser_id": match.loser_id, "round": match.round_number,
        "is_final": match.is_final, "tournament_complete": complete,
    }
    if complete:
        result["tournament_winner_id"] = winner_id
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
