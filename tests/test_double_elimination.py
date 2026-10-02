"""Double-elimination topology, asynchronous progression and compatibility."""

from collections import Counter
from dataclasses import asdict
import json
import random

import pytest

from game_service.tournament_service import (
    MatchStatus, TournamentBracket, TournamentFormat, TournamentMatch,
    TournamentParticipant, create_tournament, record_match_result,
)


COUNTS = [2, 3, 4, 5, 8, 13]


def create(n):
    return create_tournament("DE", TournamentFormat.DOUBLE_ELIMINATION,
                             [f"w{i}" for i in range(1, n + 1)])


def node(bracket, stage, number=1, match=1):
    return next(m for m in bracket.matches if
                (m.stage, m.round_number, m.match_number) == (stage, number, match))


def play(bracket, match, slot="a"):
    return record_match_result(bracket, match.match_id, getattr(match, f"participant_{slot}_id"))


@pytest.mark.parametrize("n", COUNTS)
def test_topology_has_unique_edges_slots_and_is_acyclic(n):
    bracket = create(n)
    matches = {m.match_id: m for m in bracket.matches}
    assert len(matches) == len(bracket.matches)
    stages = {m.stage for m in bracket.matches}
    assert {"winners", "grand_final", "reset_final"} <= stages
    if n > 2:
        assert "losers" in stages
    destinations = Counter()
    edges = []
    for match in bracket.matches:
        assert match.next_match_id == match.winner_next_match_id
        assert match.is_final == (match.stage in ("grand_final", "reset_final"))
        if match.stage == "winners":
            assert match.loser_next_match_id is not None
        if match.stage == "losers":
            assert match.loser_next_match_id is None
        for outcome in ("winner", "loser"):
            target = getattr(match, f"{outcome}_next_match_id")
            slot = getattr(match, f"{outcome}_next_slot")
            if target is None:
                assert slot is None
                continue
            assert target in matches
            assert slot in ("a", "b")
            destinations[target, slot] += 1
            edges.append((match.match_id, target))
    assert all(count == 1 for count in destinations.values())
    for match in bracket.matches:
        if match.stage != "winners" or match.round_number != 1:
            assert destinations[match.match_id, "a"] == 1
            assert destinations[match.match_id, "b"] == 1
    visited = set()
    while len(visited) < len(matches):
        ready = {mid for mid in matches if mid not in visited and
                 all(source in visited for source, target in edges if target == mid)}
        assert ready, "cycle"
        visited.update(ready)
    assert asdict(bracket)["matches"] == asdict(create(n))["matches"]


@pytest.mark.parametrize("n", COUNTS)
def test_seeds_byes_and_stats(n):
    bracket = create(n)
    size = 1 << (n - 1).bit_length()
    byes = [m for m in bracket.matches if m.stage == "winners" and m.status == MatchStatus.BYE]
    assert [m.winner_id for m in byes] == [f"w{i}" for i in range(1, size - n + 1)]
    for match in bracket.get_round_matches(1):
        if match.stage == "winners" and match.status != MatchStatus.BYE:
            assert match.participant_a_id == f"w{match.match_number}"
            assert match.participant_b_id == f"w{size + 1 - match.match_number}"
    assert all(p.wins == p.losses == 0 and not p.eliminated for p in bracket.participants)
    assert bracket.to_dict()["matches_completed"] == 0


def test_rankings_stably_seed_and_do_not_call_single_elimination(monkeypatch):
    def fail(*args):
        raise AssertionError("double elimination delegated to single elimination")
    monkeypatch.setattr("game_service.tournament_service._generate_single_elimination", fail)
    bracket = create_tournament("Ranked", TournamentFormat.DOUBLE_ELIMINATION,
                                ["a", "b", "c"], rankings={"a": 2, "b": 1, "c": 1})
    assert [p.wrestler_id for p in bracket.participants] == ["b", "c", "a"]
    assert node(bracket, "winners").winner_id == "b"


@pytest.mark.parametrize("n", COUNTS)
@pytest.mark.parametrize("reset", [False, True])
@pytest.mark.parametrize("reset_winner", ["a", "b"])
def test_full_tournament_randomized_schedule(n, reset, reset_winner):
    bracket = create(n)
    rng = random.Random(n)
    recorded_losses = Counter()
    recorded_wins = Counter()
    games = 0
    while not bracket.is_complete:
        pending = bracket.get_pending_matches()
        assert pending, "progression stalled"
        match = rng.choice(pending)
        assert not any(p.eliminated for p in bracket.participants
                       if p.wrestler_id in (match.participant_a_id, match.participant_b_id))
        slot = rng.choice(["a", "b"])
        if match.stage == "grand_final":
            slot = "b" if reset else "a"
        if match.stage == "reset_final":
            slot = reset_winner
        result = play(bracket, match, slot)
        games += 1
        recorded_wins[result["winner_id"]] += 1
        recorded_losses[result["loser_id"]] += 1
        for p in bracket.participants:
            assert p.losses == recorded_losses[p.wrestler_id]
            assert p.wins == recorded_wins[p.wrestler_id]
            assert p.eliminated == (p.losses == 2)
        if match.stage == "grand_final" and reset:
            assert not result["tournament_complete"]
            assert bracket.winner_id is None
            assert node(bracket, "reset_final").is_ready()
        assert games <= 2 * n - 1
    assert games == 2 * n - 2 + reset
    assert result["tournament_winner_id"] == bracket.winner_id
    assert not bracket.get_pending_matches()
    assert all(p.losses == 2 for p in bracket.participants if p.wrestler_id != bracket.winner_id)
    champion = next(p for p in bracket.participants if p.wrestler_id == bracket.winner_id)
    assert champion.losses == int(reset)
    assert not champion.eliminated
    final_reset = node(bracket, "reset_final")
    assert final_reset.status == (MatchStatus.COMPLETED if reset else MatchStatus.SKIPPED)


def test_destination_slots_do_not_depend_on_result_order():
    bracket = create(4)
    play(bracket, node(bracket, "winners", match=2), "b")
    upper_final = node(bracket, "winners", number=2)
    lower = node(bracket, "losers")
    assert upper_final.participant_a_id is None
    assert upper_final.participant_b_id == "w3"
    assert lower.participant_a_id is None
    assert lower.participant_b_id == "w2"
    assert not lower.is_ready()
    play(bracket, node(bracket, "winners", match=1))
    assert upper_final.participant_a_id == "w1"
    assert lower.participant_a_id == "w4"
    assert lower.is_ready() and upper_final.is_ready()
    play(bracket, upper_final)
    loser = next(p for p in bracket.participants if p.wrestler_id == "w3")
    assert loser.losses == 1 and not loser.eliminated
    assert bracket.current_round == 2  # lower round 1 still waiting to be played
    play(bracket, lower)
    assert bracket.current_round == 3
    play(bracket, node(bracket, "losers", number=2))
    assert loser.losses == 2 and loser.eliminated


def test_partially_fed_match_is_not_a_bye():
    bracket = create(5)
    waiting = node(bracket, "losers", number=2, match=1)
    assert waiting.participant_a_resolved
    assert waiting.participant_a_id is None
    assert not waiting.participant_b_resolved
    assert waiting.status == MatchStatus.PENDING
    before = asdict(bracket)
    with pytest.raises(ValueError):
        record_match_result(bracket, waiting.match_id, None)
    assert asdict(bracket) == before


@pytest.mark.parametrize("corruption", ["missing", "occupied", "slot"])
def test_invalid_edges_do_not_partially_mutate_results(corruption):
    bracket = create(4)
    match = node(bracket, "winners")
    if corruption == "missing":
        match.loser_next_match_id = "missing"
    elif corruption == "slot":
        match.loser_next_slot = "c"
    else:
        node(bracket, "losers").participant_a_id = "intruder"
    before = asdict(bracket)
    with pytest.raises(ValueError, match="destination"):
        play(bracket, match)
    assert asdict(bracket) == before


def test_unready_inactive_duplicate_and_in_progress_results():
    bracket = create(4)
    match = node(bracket, "winners")
    match.status = MatchStatus.IN_PROGRESS
    play(bracket, match)
    before = asdict(bracket)
    with pytest.raises(ValueError, match="already completed"):
        play(bracket, match)
    assert before == asdict(bracket)
    waiting = node(bracket, "winners", number=2)
    with pytest.raises(ValueError, match="not ready"):
        play(bracket, waiting)
    reset = node(bracket, "reset_final")
    reset.participant_a_id, reset.participant_b_id = "w1", "w2"
    reset.participant_a_resolved = reset.participant_b_resolved = True
    assert not reset.is_ready()
    with pytest.raises(ValueError, match="not ready"):
        play(bracket, reset)


def test_serialized_mid_tournament_can_resume():
    bracket = create(5)
    play(bracket, bracket.get_pending_matches()[0])
    data = json.loads(json.dumps(asdict(bracket)))
    data["format"] = TournamentFormat(data["format"])
    data["matches"] = [TournamentMatch(**m) for m in data["matches"]]
    data["participants"] = [TournamentParticipant(**p) for p in data["participants"]]
    restored = TournamentBracket(**data)
    while not restored.is_complete:
        play(restored, restored.get_pending_matches()[-1])
    assert all(p.losses == 2 for p in restored.participants if p.eliminated)


@pytest.mark.parametrize("n", COUNTS)
def test_single_elimination_still_completes(n):
    bracket = create_tournament("SE", TournamentFormat.SINGLE_ELIMINATION,
                                [f"w{i}" for i in range(n)])
    games = 0
    while not bracket.is_complete:
        play(bracket, bracket.get_pending_matches()[-1])
        games += 1
        assert games <= n - 1
    assert games == n - 1
    assert sum(p.eliminated for p in bracket.participants) == n - 1


def test_duplicate_participants_rejected():
    with pytest.raises(ValueError, match="unique"):
        create_tournament("DE", TournamentFormat.DOUBLE_ELIMINATION, ["w", "w"])


def test_eight_player_losers_rounds_have_expected_crossovers():
    bracket = create(8)
    for number in range(1, 5):
        source = node(bracket, "winners", match=number)
        assert source.loser_next_match_id == f"losers-1-{(number + 1) // 2}"
        assert source.loser_next_slot == "ab"[(number - 1) % 2]
    for number in (1, 2):
        incoming = node(bracket, "winners", number=2, match=number)
        assert incoming.loser_next_match_id == f"losers-2-{3 - number}"
        assert incoming.loser_next_slot == "b"
        consolidation = node(bracket, "losers", number=2, match=number)
        assert consolidation.winner_next_match_id == "losers-3-1"
        assert consolidation.winner_next_slot == "ab"[number - 1]
    assert node(bracket, "winners", number=3).loser_next_match_id == "losers-4-1"
    assert node(bracket, "losers", number=3).winner_next_match_id == "losers-4-1"
    assert node(bracket, "losers", number=4).winner_next_match_id == "grand_final-1-1"
