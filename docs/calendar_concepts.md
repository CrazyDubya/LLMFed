# Calendar and Timing Concepts

LLMFed builds from **match phases** (ring-time) to a **full federation calendar** (weeks, cards, PPVs).

## Match Phase Flow

Each match runs through three phases in order:

| Phase | When | Who Runs | Purpose |
|-------|------|----------|---------|
| **PRE_MATCH** | Before ring action | Promoter, Backstage | Promoter sets story/hints; backstage prepares |
| **MATCH** | Ring ticks | All roles (at different cadences) | In-ring action, commentary, crowd, ref |
| **POST_MATCH** | After match ends (finisher or max_ticks) | Promoter, Backstage | Promoter reacts to outcome; backstage plans next |

**Engine API:**
- `run_pre_match()` — Run promoter + backstage once. Call before `run_ticks` to seed hints.
- `run_ticks(n)` — Run match ticks. Returns `None` when finisher ends match.
- `run_post_match(match_result)` — Run promoter + backstage once after match. Receives outcome for context.
- `run_full_match(max_ticks)` — Runs pre_match → match ticks (until finisher or limit) → post_match in one call.

## Per-Role Tick Cadence (MATCH phase)

During the match, roles run at different frequencies:

| Role | Run every N ticks | Rationale |
|------|-------------------|-----------|
| **participant** | 1 (every tick) | Wrestlers act constantly |
| **referee** | 1 (every tick) | Ref watches the whole match |
| **announcer** | 4 | Commentary in bursts, not every move |
| **crowd** | 6 | Reacts in waves, not every strike |
| **backstage** | 12 | Off-camera, delayed; ~10–15 "seconds" |
| **promoter** | 20 | Off-scene; occasional in-match guidance |

Cadence is configured in `models/calendar.py` as `ROLE_TICK_CADENCE`.

## Calendar Hierarchy

```
Calendar (federation)
  └── Year (calendar year)
        └── Season (multiple per year)
              └── Month (multiple per season; culminates with PPV)
                    └── Week (Mon–Sun)
                          └── Card (show/event)
                                └── Match
                                      └── Phases (pre_match, match, post_match)
```

- **Year**: Federation year (e.g. 2025). Multiple seasons per year.
- **Season**: Group of months within a year (e.g. Q1, Q2; or TV seasons).
- **Month**: Calendar month (weeks, optional PPV). PPVs culminate each month's cycle.
- **Week**: Calendar week (start_date, end_date). Multiple weeks per month.
- **Card**: A show (e.g. Monday Night Raw, Dynamite). Contains one or more matches.
- **PPV**: A special Card that culminates each month (e.g. WrestleMania, SummerSlam).

## What a Card Looks Like

A **Card** is a show (e.g. Monday Night Raw, Dynamite, WrestleMania) with one or more matches.

```
Card
├── card_id: str
├── federation_id: str
├── name: str (e.g. "Monday Night Raw", "SummerSlam")
├── card_date: Optional[date]
├── week_id: Optional[str]
├── is_ppv: bool
└── matches: List[Match]
```

Each **Match** on a card goes through phases:

```
Match 1:  pre_match → match (ticks until finisher) → post_match
Match 2:  pre_match → match (ticks until finisher) → post_match
...
```

**Typical card structure:**
- Weekly TV: 3–5 matches (opener, mid-card, main event).
- PPV: 6–10 matches (culminates month-long storylines).

**Note:** Automated card building (e.g. `MatchScheduler`, `_create_optimal_match_card`) is described in `docs/ENHANCEMENT_PROPOSAL.md` as a future feature. It is not implemented in the codebase; no other branches contain card-building logic.

## Ring vs Beyond-Ring Time

- **Ring time**: `current_tick` during MATCH phase. Only participant and referee need every-tick fidelity.
- **Beyond ring**: Promoter and backstage run less often and can use slower models; they react as if they are not on-scene (10–15 "seconds" delay).

## Implementation Status

- [x] `EventPhase`, `ROLE_TICK_CADENCE`, `PRE_MATCH_ROLES`, `POST_MATCH_ROLES` in `models/calendar.py`
- [x] Engine uses cadence: skips roles when `(tick - 1) % cadence != 0`
- [x] Pre-match / post-match phases: `run_pre_match()`, `run_post_match()`, `run_full_match()`
- [x] Pydantic models: Match, Card, Week, PPV, Month, Season, Year, Calendar
- [ ] DB schema for Card, Week, Month, Season, Year (future)
- [x] End-to-end simulation: `SimulationOrchestrator`, `run_card`, `run_week`, POST `/simulation/run`, `scripts/run_simulation.py`
- [ ] Automated card-building / MatchScheduler (proposed in ENHANCEMENT_PROPOSAL only)
- [ ] Calendar API endpoints (future)
- [ ] Week template (house/TV/PPV per day), roster split, travel squad, day before/after, fatigue: see **`docs/week_month_and_life_design.md`**
