# Wrestling Concepts: Heat, Teams, Stables, Titles, Momentum, Storylines, Memories

Design notes for extending LLMFed with wrestling-specific concepts and long-term scaling.

## Move Engine

**`core_engine/move_engine.py`** — Wrestlers draw from 50+ real moves filtered by:

| Factor | Source | Example |
|--------|--------|---------|
| **Position** | Tick-derived cycle | standing → ground → corner → ropes → top_rope |
| **Style** | Gimmick keywords | powerhouse, technical, high_flyer, brawler, submission |
| **Momentum** | Match state | Specials need 20–28; finishers need 35–40 |
| **Opponent** | Future | Style-based counters |

**Move types:** common (strikes, grapples, takedowns), special (signatures), finisher (match-ending).

---

## Current State (Summary)

See also: `docs/roster_staff_audience.md` for roster, contracts, wrestler stats/personalities, staff (announcers, refs, valets, managers), and audience demographics (superfan, super_viewer, common_viewer, common_fan).

| Concept | Implemented | Notes |
|---------|-------------|-------|
| **Heat** | Partial | Per-wrestler `current_heat`, match-level `GameState.heat`; crowd `heat_adjustment`, ref pinfall, announcer, backstage affect it |
| **Momentum** | Partial | Per-wrestler `momentum`; increments on participant action, resets on pinfall |
| **Teams** | No | — |
| **Stables** | No | — |
| **Titles** | No | Mentioned in hints/demos only |
| **Storylines** | No | Hints only; ENHANCEMENT_PROPOSAL has NarrativeEngine/StorylineDirector (unbuilt) |
| **Memories** | No | ENHANCEMENT_PROPOSAL has AgentMemory (unbuilt) |

---

## 1. Heat

**Heat** = crowd/audience engagement with a wrestler or match.

- **Babyface heat**: Cheering, support. Losing streak can build sympathy heat.
- **Heel heat**: Booing, hatred. Gets crowd invested in seeing them lose.
- **Feud heat**: Intensity of a rivalry. Affects crowd reaction when those two face off.
- **Match heat**: In-ring energy during a match (current `GameState.heat`).

**Proposed model:**
- Per-wrestler: `current_heat` (0–100 or similar), `alignment` (babyface/heel/tweener)
- Per-feud: `feud_heat` (how hot the rivalry is)
- Match: aggregate of participants + feud + stipulation; decays over time if not fed

**Interactions:** Crowd reaction affects heat; heat affects who gets cheered/booed. Title matches, main events, PPV slots amplify heat.

---

## 2. Teams

**Tag teams** (and trios): Named partnerships with shared history.

- `Team`: `team_id`, `name`, `member_ids[]`, `federation_id`, `formed_date`, `disbanded_date?`
- Tag title eligibility, breakup angles (one turns on the other), reunions
- Team-specific momentum/heat (The Usos, FTR as units)

**Proposed model:** Team as first-class entity; agents can belong to 0 or 1 active team; matches can be `team vs team` or `team vs singles`.

---

## 3. Stables

**Stables** (factions): Groups with a shared identity (nWo, The Bloodline, Judgment Day).

- `Stable`: `stable_id`, `name`, `leader_id?`, `member_ids[]`, `federation_id`, `formed_date`, `disbanded_date?`
- Rivalries: stable vs stable (Bloodline vs Judgment Day)
- Betrayals: member leaves or turns on leader
- Faction feuds drive multi-man matches, war games, elimination matches

**Proposed model:** Stable as first-class entity; agents can belong to 0 or 1 stable; stables have internal roles (leader, enforcer, etc.).

---

## 4. Titles (Championships)

**Titles** = championships with lineage and prestige.

- `Title`: `title_id`, `name`, `federation_id`, `tier` (world, mid-card, tag, etc.)
- **Lineage**: ordered list of reigns: `(champion_id, start_date, end_date?, end_reason)`
- Current holder = most recent reign with no `end_date`
- Title matches: `is_title_match`, `title_id` on Match
- Prestige: can grow/shrink based on who held it, length of reigns, PPV main events

**Proposed model:** Title + Reign entities; Match links to `title_id` when applicable; engine/promoter know "champion vs challenger" context.

---

## 5. Momentum

**Momentum** = trajectory: hot streak vs cold streak.

- **Current:** Per-wrestler `momentum` (match-level), resets on pinfall
- **Proposed extension:**
  - `win_streak`, `loss_streak` (over matches, not ticks)
  - `momentum_tier`: hot / neutral / cold (derived from recent W/L + crowd reaction)
  - Feeds into booking: hot wrestler gets push; cold wrestler needs rehab or heel turn
  - Decay over time if not used (absence cools momentum)

---

## 6. Storylines

**Storylines** = narrative arcs: feuds, alliances, angles.

- `Storyline`: `storyline_id`, `title`, `type` (feud, alliance, betrayal, title chase), `participant_ids[]`, `status` (active, resolved, dropped), `heat`, `start_date`, `end_date?`
- Links to matches: Match can `advance_storyline_id`
- Promoter uses active storylines to set hints, book payoff matches
- Resolution: PPV blowoff, heel turn, double turn, alliance formed

**Proposed model:** Storyline as first-class entity; matches reference storyline; promoter hint builder reads active storylines.

---

## 7. Memories and 100-Year Scaling

**Problem:** Over 100 simulated years, we can’t store or recall every match, promo, or crowd reaction. We need bounded, tiered memory that preserves what matters and summarizes the rest.

### Who Remembers What?

| Actor | Scope | Bounded? | Notes |
|-------|-------|----------|-------|
| **Promoter** | Federation-wide, booking decisions | Yes | Recent detail; older = summaries. Drives hints. |
| **Wrestlers** | Personal history, feuds, key moments | Yes | Per-agent; only events they were in. |
| **Crowd** | “Right now” + recent highlights | Yes | Very short; reacts to current match + occasional callback. |
| **Federation history** | Canonical records | Yes | Title lineages, PPV results, records. Must never contradict itself. |
| **Announcers** | Current show + “legendary” callbacks | Yes | Real-time + curated history. |
| **Backstage** | Recent cards, active feuds | Yes | Limited window. |

### Archive Tiers (Federation History)

To scale to 100 years without bloat or inconsistency:

| Tier | Time Window | Granularity | Contents |
|------|-------------|-------------|----------|
| **Tier 0** | Last 4 weeks | Full | Match logs, narrative, tick-level detail. Queryable for “what happened last Raw?” |
| **Tier 1** | Last year | Match-level | Results, title changes, storyline resolutions, crowd heat. |
| **Tier 2** | 1–10 years | Season-level | Season summaries, champions, major feuds, PPV main events. |
| **Tier 3** | 10–100 years | Decade/milestone | Decade summaries, all-time records, legendary moments, Hall of Fame. |
| **Tier 9** | Forever | Immutables | Card dates, attendance, match card and results, title holder and changes. Append-only, never contradicted. |

### Invariants (Never Mess Up)

- **Title lineage**: Must be continuous. New reign = previous reign ends.
- **Records**: Win/loss, title reigns — canonical, append-only. No retroactive edits.
- **Legendary moments**: Promoted from Tier 1/2 by rules or heuristics (e.g. title change at WrestleMania, 5-star match, betrayal). Once “legendary,” always available.
- **Summarization**: When promoting Tier 0 → 1, compress narrative into structured summary. LLM or template: “Week of X: Card Y, Match Z ended with…, Title changed from A to B.”

### Implementation Sketch

- `HistoryStore` with tiered tables/partitions
- `summarize_and_archive()` runs periodically (e.g. end of week/season)
- `recall(actor, query, time_window)` returns relevant, bounded context for prompts
- Wrestler memory: `agent_memories` table, keyed by `agent_id`, with `importance` and `created_at`; evict low-importance old entries, keep feuds/betrayals/title wins

---

## Suggested Implementation Order

1. **Titles + lineage** — Foundation for “championship match” context, #1 contender logic
2. **Storylines** — Link matches to arcs; promoter hints from active storylines
3. **Heat extension** — Alignment, feud heat; wire into engine
4. **Teams** — Tag teams; then stables
5. **Momentum extension** — Win/loss streaks, momentum tier
6. **Memories** — Archive tiers, summarization, bounded recall for promoter/wrestlers/crowd
