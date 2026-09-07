"""Tests for tournament service — bracket generation and advancement."""

import pytest
from game_service.tournament_service import (
    TournamentFormat,
    MatchStatus,
    create_tournament,
    record_match_result,
    get_standings,
)


def _wrestler_ids(n):
    return [f"w{i}" for i in range(1, n + 1)]


def _wrestler_names(ids):
    return {wid: f"Wrestler {wid}" for wid in ids}


class TestSingleElimination:
    def test_create_4_man_bracket(self):
        ids = _wrestler_ids(4)
        bracket = create_tournament(
            "Test Cup", TournamentFormat.SINGLE_ELIMINATION, ids
        )
        assert bracket.total_rounds == 2
        assert len(bracket.participants) == 4
        # 4 participants → 2 first-round matches + 1 final = 3
        assert len(bracket.matches) == 3
        assert bracket.is_complete is False

    def test_create_8_man_bracket(self):
        ids = _wrestler_ids(8)
        bracket = create_tournament("8-Man", TournamentFormat.SINGLE_ELIMINATION, ids)
        assert bracket.total_rounds == 3
        assert len(bracket.matches) == 7  # 4 + 2 + 1

    def test_3_man_bracket_has_bye(self):
        ids = _wrestler_ids(3)
        bracket = create_tournament("3-Man", TournamentFormat.SINGLE_ELIMINATION, ids)
        assert bracket.total_rounds == 2
        # One first-round match should be auto-completed (bye)
        completed = [m for m in bracket.matches if m.status == MatchStatus.COMPLETED]
        assert len(completed) >= 1

    def test_full_tournament_flow(self):
        ids = _wrestler_ids(4)
        names = _wrestler_names(ids)
        bracket = create_tournament(
            "King of the Ring",
            TournamentFormat.SINGLE_ELIMINATION,
            ids,
            wrestler_names=names,
            stakes="Title Shot",
        )
        assert bracket.stakes == "Title Shot"

        # Play first round
        pending = bracket.get_pending_matches()
        assert len(pending) == 2

        r1 = record_match_result(
            bracket, pending[0].match_id, pending[0].participant_a_id
        )
        assert r1["is_final"] is False
        r2 = record_match_result(
            bracket, pending[1].match_id, pending[1].participant_a_id
        )
        assert r2["is_final"] is False

        # Play final
        final_matches = bracket.get_pending_matches()
        assert len(final_matches) == 1
        final = final_matches[0]
        result = record_match_result(bracket, final.match_id, final.participant_a_id)
        assert result["tournament_complete"] is True
        assert bracket.winner_id is not None
        assert bracket.is_complete is True

    def test_already_completed_match_raises(self):
        ids = _wrestler_ids(4)
        bracket = create_tournament("Test", TournamentFormat.SINGLE_ELIMINATION, ids)
        pending = bracket.get_pending_matches()
        match = pending[0]
        record_match_result(bracket, match.match_id, match.participant_a_id)
        with pytest.raises(ValueError, match="already completed"):
            record_match_result(bracket, match.match_id, match.participant_a_id)

    def test_invalid_winner_raises(self):
        ids = _wrestler_ids(4)
        bracket = create_tournament("Test", TournamentFormat.SINGLE_ELIMINATION, ids)
        match = bracket.get_pending_matches()[0]
        with pytest.raises(ValueError, match="not a participant"):
            record_match_result(bracket, match.match_id, "nonexistent")


class TestRoundRobin:
    def test_create_4_man_round_robin(self):
        ids = _wrestler_ids(4)
        bracket = create_tournament("Round Robin", TournamentFormat.ROUND_ROBIN, ids)
        # C(4,2) = 6 matches
        assert len(bracket.matches) == 6
        assert all(m.is_ready() for m in bracket.matches)

    def test_standings_after_results(self):
        ids = _wrestler_ids(3)
        names = _wrestler_names(ids)
        bracket = create_tournament("RR", TournamentFormat.ROUND_ROBIN, ids, names)
        # 3 matches: w1 vs w2, w1 vs w3, w2 vs w3
        for match in bracket.matches:
            record_match_result(bracket, match.match_id, match.participant_a_id)

        standings = get_standings(bracket)
        assert len(standings) == 3
        assert standings[0]["wins"] >= standings[1]["wins"]


class TestRoyalRumble:
    def test_create_rumble(self):
        ids = _wrestler_ids(10)
        bracket = create_tournament("Rumble", TournamentFormat.ROYAL_RUMBLE, ids)
        assert len(bracket.matches) == 1
        assert bracket.matches[0].stipulation == "royal_rumble"
        # Entry numbers should be assigned
        entries = [p.entry_number for p in bracket.participants]
        assert len(set(entries)) == 10  # All unique


class TestGauntlet:
    def test_create_gauntlet(self):
        ids = _wrestler_ids(5)
        bracket = create_tournament("Gauntlet", TournamentFormat.GAUNTLET, ids)
        assert len(bracket.matches) == 4  # n-1 matches
        assert bracket.matches[-1].is_final is True
        assert all(m.stipulation == "gauntlet" for m in bracket.matches)


class TestBracketInfo:
    def test_to_dict(self):
        ids = _wrestler_ids(4)
        bracket = create_tournament("Test", TournamentFormat.SINGLE_ELIMINATION, ids)
        d = bracket.to_dict()
        assert d["name"] == "Test"
        assert d["format"] == "single_elimination"
        assert d["participant_count"] == 4
        assert d["is_complete"] is False
