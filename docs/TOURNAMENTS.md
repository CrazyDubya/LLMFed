# Tournament progression

## Double elimination

`create_tournament(..., TournamentFormat.DOUBLE_ELIMINATION, ...)` builds an
in-memory DAG. No database or API migration is required. Existing tournament
creation, result recording, pending-match and standings interfaces are retained.

### Seeding and topology policy

- Rankings sort ascending, with caller order breaking ties. Seeds are assigned
  after sorting, exactly as for single elimination.
- Pad to the next power of two. Preserve existing first-vs-last pairings and
  adjacent winner merges; highest seeds receive first-round byes. This does not
  introduce a different, conventional seed-spreading layout.
- Winners-round-one losers pair into the first losers round. Subsequent losers
  rounds alternate incoming winners-bracket losers and consolidation matches.
  Incoming drops use reversed winners-match order to separate immediate
  rematches where possible; rematches later in the event remain possible.
- Winners-bracket champion enters grand-final slot `a`; losers-bracket champion
  enters slot `b`. With two entrants, the first loser is already the losers-side
  finalist, so there is no unnecessary losers-bracket match.
- The reset final is pre-generated and inactive. It activates only if slot `b`
  wins the grand final. Grand-final winner routes to reset slot `a`, loser to
  slot `b`. Either may win the reset. If slot `a` wins the grand final, the reset
  becomes `SKIPPED`, and the tournament completes immediately.
- Match IDs are deterministic **within a bracket**, using stage, round and match
  number. Use `(tournament_id, match_id)` when combining multiple tournaments.

### State and routing contract

`winner_next_match_id` / `winner_next_slot` and `loser_next_match_id` /
`loser_next_slot` identify outgoing edges. Slots are `a` or `b`.
`next_match_id` mirrors the winner destination for compatibility; double
elimination uses the explicit fields as authority. Other formats retain their
legacy routing behavior.

Each input has a resolved flag, distinguishing an empty bye input from a pending
predecessor. Both inputs must resolve before a match is playable or a bye can
propagate. `BYE` nodes forward their sole participant (or an empty output) without
recording a competitive result, win or loss. `matches_completed` counts played
matches only for double elimination; `matches_total` includes byes and the
conditional reset. First losses route to the losers side; second losses eliminate.

`round_number` is local to `stage`. `get_round_matches(n)` can therefore include
multiple stages. `current_round` reports the earliest unfinished active DAG
wave, and `total_rounds` is the longest path including the optional reset.
Readiness never depends on this global counter: use `get_pending_matches()` to
schedule matches across stages. `is_final` marks the grand-final/conditional-reset
path, not a guarantee that recording that match completes the tournament. Use
`tournament_complete` or `bracket.is_complete` for completion.

Result application validates on a copy before committing state, preserving
existing match/participant object references and leaving state unchanged on
routing errors. This is an in-memory operation, not a thread-safety or persistent
transaction guarantee. Dataclass fields are JSON-serializable via `asdict`;
restore the bracket's format enum and nested dataclasses before resuming.

Older double-elimination brackets generated using the single-elimination fallback
must be regenerated; their missing losers topology cannot be inferred from the
new fields' defaults. Single-elimination brackets retain their existing behavior.

## Verification

`python -m pytest tests/test_tournament_service.py tests/test_double_elimination.py -q`

Tests cover fields of 2, 3, 4, 5, 8 and 13 entrants, deterministic topology and
seeding, empty inputs, routing slots, overlapping stages, loss counts, both
championship paths, invalid-result rollback, serialization/resume, and existing
single-elimination progression.
