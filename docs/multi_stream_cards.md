# Multi-Stream Cards: POVs, Segments, and Card Types

Design for full cards with temporal streams, POV-filtered information, segments/breaks, and card-type hierarchy.

---

## 1. Temporal Streams (POVs)

Each stream has its own **point of view** and **information pool**. They run simultaneously with selective information sharing.

| Stream | Who | Sees | Does Not See | Pace |
|--------|-----|------|--------------|------|
| **TV Audience** | Announcer, broadcast | Ring action, promos (produced), replays, commercials | Backstage, promoter decisions, wrestler personal | Tick-aligned with match; commercial breaks |
| **Crowd** | Crowd agent | Live ring action, live promos, dark matches | Backstage, TV edits, commercials | Every tick during ring; intermission |
| **Backstage** | Backstage agent | Wrestler prep, conflict, injury, alliance, betrayal, promoter notes | Live ring (delayed), TV cuts | Every 12 ticks; between segments |
| **Promoter** | Promoter agent | Everything (orchestrator view), booking, storylines, outcomes | — | Pre/post match; every 20 ticks in-match; segment transitions |

### Information Flow Rules

| From | To TV | To Crowd | To Backstage | To Promoter |
|------|-------|----------|--------------|-------------|
| **Ring action** | ✓ (broadcast) | ✓ (live) | ✗ (or delayed summary) | ✓ |
| **Backstage** | ✗ (unless cut to) | ✗ | ✓ | ✓ |
| **Promoter** | Via announcer hints | Via crowd heat | Via backstage notes | ✓ |
| **Wrestler personal** | Via gimmick only | Via gimmick only | ✓ (backstage knows) | ✓ |
| **Wrestler collaboration** | Via ring action | Via ring action | ✓ (planning) | ✓ |

### Wrestler Dual Life

- **Gimmick/Persona**: What TV and crowd see (in-ring character).
- **Personal/Professional**: What backstage sees (real motives, alliances, injuries).
- **Promoter** knows both; uses them for booking.

---

## 2. Card Types (Hierarchy)

| Type | Stakes | Production | Example |
|------|--------|------------|---------|
| **house** | Low | Minimal, crowd-only | House show, loop |
| **minor_tv** | Low–mid | Basic TV, small audience | Main Event, NXT Level Up |
| **major_tv** | Mid–high | Full production | Raw, Dynamite, SmackDown |
| **ppv** | High | Full, monthly culmination | Clash at the Castle |
| **marquee_season** | Very high | Seasonal climax | Survivor Series, Royal Rumble |
| **marquee_year** | Highest | Annual climax | WrestleMania |

### Card Type Attributes

| Type | Segments | Commercials | Dark Match | Intermission |
|------|----------|-------------|------------|--------------|
| house | Simple (match–match) | No | Sometimes | Yes |
| minor_tv | Basic (intro, matches) | Yes | Rare | No |
| major_tv | Full (open, promos, matches, close) | Yes | Sometimes post | No |
| ppv | Full + preshow | No (paid) | No | No |
| marquee_season | Full + special segments | No | No | No |
| marquee_year | Full + spectacle | No | No | No |

---

## 3. Segments and Breaks

A **segment** is a unit of the card: match, promo, backstage, commercial, etc.

| Segment Type | TV Sees | Crowd Sees | Backstage | Duration |
|--------------|---------|------------|-----------|----------|
| **opening** | ✓ | ✓ | Summary | 1 "block" |
| **match** | ✓ (or commercial cut) | ✓ | Delayed/no | N ticks |
| **promo** | ✓ | ✓ | ✓ (who cut it) | 1 block |
| **backstage** | Only if cut to | ✗ | ✓ | 1 block |
| **commercial** | Break | Intermission/hype | — | 1 block |
| **intermission** | ✗ | ✓ (between matches) | ✓ | 1 block |
| **dark_match** | ✗ | ✓ | ✓ | N ticks |
| **closing** | ✓ | ✓ | Summary | 1 block |
| **preshow** | Optional | ✗ | ✓ | 1+ blocks |

### Block vs Tick

- **Block**: Logical unit (e.g. one segment). Used for pacing.
- **Tick**: In-ring simulation unit. Matches run for N ticks; promos/open/close are 1 block each.

---

## 4. Full Card Structure

```
Card (card_type, name, date)
├── Segment 1: opening (1 block)
├── Segment 2: match (opener) — N ticks
├── Segment 3: commercial (major_tv) or intermission (house)
├── Segment 4: promo OR backstage
├── Segment 5: match (mid-card)
├── ...
├── Segment K: match (main event)
├── Segment K+1: closing (1 block)
└── [Optional] Segment K+2: dark_match (house, major_tv)
```

### Segment Model

```python
Segment:
  segment_id, card_id, segment_type, order
  match_id? (if type=match)
  participant_ids? (for promo/backstage)
  duration_blocks: int  # 1 for non-match, N for match
  pov_visible: List[Stream]  # Which POVs see this segment
```

---

## 5. POV-Filtered Context

When building `EventContext` for an agent:

- **Announcer**: `pov="tv"` — only ring + promo segments, no backstage.
- **Crowd**: `pov="crowd"` — live ring + promo, no backstage, no commercial cutaways.
- **Backstage**: `pov="backstage"` — backstage segments + delayed match summaries, no live ring.
- **Promoter**: `pov="promoter"` — full view (all segments, all outcomes).
- **Participant/Referee**: `pov="ring"` — ring-only (they're in the match).

### Context State by POV

| POV | state keys |
|-----|------------|
| ring | current_tick, position, opponent, momentum, heat |
| tv | ring state + card_type, segment_type, "commercial" flag |
| crowd | ring state + live_only, no commercial awareness |
| backstage | delayed_match_summary, backstage_notes, wrestler_personal |
| promoter | full_state, booking_notes, storyline, outcomes |

---

## 6. Implementation Order

1. ✅ **Models**: CardType enum, SegmentType enum, Segment, POV, FullCard (models/card_structure.py).
2. ✅ **Card builder**: `build_full_card(card, card_type)` (simulation/card_builder.py).
3. ✅ **POV context**: `_build_context` derives POV from role, adds `pov`, `segment_type`, `card_type` to state.
4. ✅ **Segment runner**: `run_full_card` iterates segments; match/dark_match → `run_match`; non-match segments (opening, promo, backstage, closing) run one tick via `engine.run_one_segment_tick`.
5. ✅ **CardRunState (glue)**: State accumulated across the card: `previous_segment_type`, `last_match_result` (winner_id, match_id, participant_ids), `segment_results`. Passed into hints as `card_run_state` so each segment and match knows what came before and what just happened.
6. ⏳ **Commercial/intermission**: Skip or throttle ticks for TV/crowd during break (future).

---

## 7. Full card run: before match, match, after match

- **Before the match**: Opening (and promo/preshow if present) run first. `run_one_segment_tick(segment_type, card_type, card_run_state, hints)` runs the roles that see that segment (from `SEGMENT_ROLES`: e.g. opening → announcer, crowd, backstage, promoter). Each agent gets context with `mode="segment"`, `segment_type`, `card_type`, `card_run_state` (previous_segment_type, last_match_result, segments_completed). Results are appended to `card_run_state.segment_results`; `previous_segment_type` is updated.
- **The match**: Match segments run `run_match` (pre_match → match ticks → post_match). Hints include `card_run_state` so promoter/backstage/crowd know we're after the opening (or after the previous match). After the match, `last_match_result` is set (winner_id, match_id, participant_ids) and appended to `segment_results`.
- **After the match**: Post_match phase runs (promoter reacts, backstage plans next). Then the next segment runs (e.g. commercial, backstage, or next match) with updated `card_run_state` (so e.g. "last match: X beat Y" is in context).
- **Glue**: `CardRunState` (models/card_structure.py), `SEGMENT_ROLES` (segment type → roles to run), `run_one_segment_tick` (core_engine/engine.py), and the loop in `run_full_card` (simulation/orchestrator.py).
