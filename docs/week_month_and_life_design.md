# Week, Month, Day-Around-Card, and Personal vs Kayfabe

Design for: day before/after a card, week structure (house/TV/PPV), roster splits and travel, how week and month fit together, and personal (off-camera) life vs on-camera kayfabe.

---

## 1. Scope

| Concept | Purpose |
|--------|---------|
| **Day before a card** | Travel, prep, promo day, arrival; who is where. |
| **Day after a card** | Travel home, rest, media, critics; fallout. |
| **Week structure** | How many house shows, TV shows, PPV; which days; roster per show. |
| **Roster split** | Who travels to house vs TV vs PPV; loops (A/B); why (fatigue, tier, contract). |
| **Week + month** | Month = 4–5 weeks; PPV week; build-up and fallout. |
| **Personal vs kayfabe** | Off-camera life (rest, travel, fatigue, real motives); on-camera gimmick; POV rules. |

---

## 2. Day Before a Card

**Intent:** The day before a show is travel/prep/promo day, not “nothing.”

| Element | Description |
|--------|-------------|
| **Travel** | Roster (or travel squad) is “on the road” to the venue city. Optional: `TravelLeg` (from_venue_id, to_venue_id, date, agent_ids[]) for logistics. |
| **Prep day** | Promoter/backstage can run a lightweight “prep” tick: set tone, injury check, last-minute swerves. No ring. |
| **Promo day** | Optional: taped or social promos for tomorrow’s card; could feed into crowd/announcer context. |
| **Who is “active”** | Only the **travel squad** for that card is “on the road”; others are off (rest, other loop, or off-camera). |

**Data / hooks:**

- **Card** (or **ScheduledShow**) gets optional `prep_date` (day before) and `card_date` (show day).
- **Day-before context** for promoter/backstage: “Card tomorrow: [name]. Travel squad: [ids]. Venue: [venue]. Last show result: [last_match_result].”
- No need to simulate every hour; “day before” = one optional prep tick or a simple flag that the next card is tomorrow.

**Implementation order:** After week/schedule and travel squad exist; then add optional prep tick or day-before hint.

---

## 3. Day After a Card

**Intent:** Day after is rest, travel home, media, critics.

| Element | Description |
|--------|-------------|
| **Travel home** | Squad returns (or moves to next city for a loop). |
| **Rest / fatigue** | Wrestlers who worked last night have higher fatigue (see §7). |
| **Media** | Critics write next-day recaps (CoverageScope.NEXT_DAY); optional “morning after” narrative. |
| **Fallout** | Promoter/backstage “day after” tick: react to ratings, injuries, heat; plan next week. |

**Data / hooks:**

- **Card** (or show) has `card_date`; “day after” = `card_date + 1`.
- **Fatigue** (per agent): incremented after working a card; decay over rest days (§7).
- **Coverage**: Next-day stories already in `models/media.py`; can be triggered by “day after” (batch or on-demand).

**Implementation order:** Fatigue model first; then optional “day after” promoter/backstage tick; wire next-day coverage to card_date + 1.

---

## 4. Week Structure

**Intent:** A week has a fixed shape: which days have which show type (house, TV, PPV), and how many.

### 4.1 Show types and typical counts

| Show type | Typical per week | Day(s) | Roster |
|-----------|-------------------|--------|--------|
| **House** | 2–4 | Tue–Sun (not Monday if Monday is TV) | Travel squad (loop A or B) |
| **TV** | 1–2 | e.g. Monday + Friday | TV roster |
| **PPV** | 0 or 1 | Usually Sunday (month-end week) | PPV roster (superset of TV + specials) |

Example **major league** week:

- Monday: TV (Raw).
- Tuesday: House (loop A).
- Wednesday: House (loop B).
- Thursday: House (loop A).
- Friday: TV (SmackDown) or house.
- Saturday: House or dark before PPV.
- Sunday: PPV (if month-end) or house.

Example **smaller fed** week:

- Friday: TV (one show).
- Sat–Sun: House loop (same crew both nights).

### 4.2 Week template (data)

A **WeekTemplate** (or federation config) defines:

- `week_template_id`, `federation_id`, `name` (e.g. "Standard", "PPV week").
- **Slots**: list of `(day_of_week, show_type, optional_venue_type)`.
  - `day_of_week`: 0=Mon … 6=Sun.
  - `show_type`: house | tv | ppv | dark | off.
  - Optional: `venue_type` (arena, stadium) or “default”.

So “PPV week” might have: Mon TV, Tue house, Wed house, Thu house, Fri TV, Sat dark, Sun PPV. “Normal week” might have: Mon TV, Tue–Thu house (loop A/B alternating), Fri TV, Sat–Sun house.

**Week instance** (existing `Week` extended or linked):

- `week_id`, `start_date`, `end_date`, `month_id`, `federation_id`.
- **Cards**: list of Card, each with `card_date` and `show_type` (house/tv/ppv).
- Optional: `week_template_id` or inline slots so we know “Monday = TV, Tuesday = house”, etc.

**Derivation:** From `Week.start_date` and the template, we can compute `card_date` per slot (e.g. Monday = start_date, Sunday = start_date + 6).

### 4.3 How many house shows?

- **Not fixed globally**; per federation and per week template.
- Template says “Tuesday = house, Wednesday = house, …” so the *count* is “number of house slots” in that template (e.g. 4).
- Different templates: “heavy loop” (5 house), “light” (2 house), “PPV week” (fewer house, one PPV).

---

## 5. Roster Split: Who Travels Where, Why, How

**Intent:** Only a portion of the roster is on each show. House shows use smaller, rotating crews; TV uses the “TV roster”; PPV uses the “PPV roster” (usually includes TV + part-time/legend).

### 5.1 Why split?

| Reason | Explanation |
|--------|-------------|
| **Fatigue** | Wrestlers can’t work every night; need rest days. |
| **Cost** | House shows are cheaper; smaller crew, smaller venues. |
| **Tiering** | Main-event talent on TV/PPV; mid-card and development on house loops. |
| **Contract** | `full_time` vs `part_time` vs `ppv_appearance`: who is obligated to TV, who only house, who only PPV. |
| **Storyline** | TV drives stories; house shows rehearse or run rematches; PPV pays off. |

### 5.2 Travel squad (per show)

For **one card** (one date, one venue):

- **Travel squad** = list of agent_ids that are “on” this show (wrestlers + optional ref/announcer/backstage).
- Used for: building the card (only these can be booked), fatigue (they “worked”), and day-before/day-after (they’re on the road).

**How to compute travel squad:**

1. **Show type** → roster pool:
   - **House**: house roster (subset of roster: e.g. mid-card, development, or “loop A” / “loop B”).
   - **TV**: TV roster (core talent: main-event + mid-card + story drivers).
   - **PPV**: PPV roster (TV roster + part-time/legend/specials; everyone who might appear).
2. **Contract type**: `ppv_appearance` only on PPV (and maybe one TV build-up); `full_time` on TV and house; `part_time` on house or selected TV.
3. **Loop A / B** (house only): Split house roster into two crews; alternate nights so no one works consecutive nights on the loop. So “Tuesday house” = loop A, “Wednesday house” = loop B, “Thursday house” = loop A, etc.
4. **Availability**: Minus injured (`get_available_at_date`), minus optional “rest day” (see fatigue §7).
5. **Cap**: Max squad size per show (e.g. 12 for house, 20 for TV, 30 for PPV) so we don’t book “everyone.”

### 5.3 Roster pools (federation-level)

Define (config or DB):

- **TV roster** (or “TV tier”): agent_ids that are regularly on TV. Derived from: tenure (veteran/rising), contract (full_time), storyline participation, or explicit list.
- **House roster**: Everyone else on the roster (or explicit list). Can be split into **loop A** and **loop B** for alternating nights.
- **PPV roster**: TV roster + `ppv_appearance` contracts + optional “special” list (legends, returns).

So:

- **House show** → travel squad = subset of (house roster, loop A or B), minus injured, minus rest, capped.
- **TV show** → travel squad = subset of (TV roster), minus injured, minus rest, capped.
- **PPV** → travel squad = subset of (PPV roster), minus injured, capped.

### 5.4 Who decides?

- **Promoter** (or scheduler) assigns “who is on which show” each week using the rules above.
- Automation: a **TravelSquadBuilder** (or extension of MatchScheduler) that, given (federation_id, card_date, show_type, week_template), returns agent_ids for that card. Then card building (e.g. anchor_card_builder, MatchScheduler) uses only those ids.

---

## 6. How Week and Month Come Together

**Intent:** Month = 4–5 weeks; one week is “PPV week”; others are “build-up” or “fallout.”

### 6.1 Month shape

- **Month**: `start_date`, `end_date`, `weeks: List[Week]`, `ppv: Optional[PPV]`.
- **Weeks**: Ordered; last week (or second-to-last) usually contains the PPV (e.g. last Sunday of month).
- **PPV**: One per month (or none); `card_date` = that Sunday (or configured day).

### 6.2 Week numbering and PPV week

- Week 1–4 (or 5): “Week 1” = first Monday–Sunday, etc.
- **PPV week**: The week whose date range contains `ppv.card_date`. That week’s template might be “PPV week” (fewer house shows, Sat dark, Sun PPV).
- **Build-up**: Weeks before PPV week; storylines point toward PPV (payoff_phase, title matches, feuds).
- **Fallout**: Week(s) after PPV; new champions, new feuds, “night after” promos.

### 6.3 Flows

- **Build a month**: Given federation, month (year, month_number), and templates: generate 4–5 Week instances; assign week_template (e.g. “Standard” for weeks 1–3, “PPV week” for last week); for each week, generate Cards from slots (house/TV/PPV) and assign travel squads.
- **Run a week**: For each card in the week (in order by card_date), run day-before (optional), run card (run_full_card), run day-after (optional fatigue + next-day coverage). Pass last_match_result / card_run_state across cards in the week.
- **Run a month**: Run each week in order; pass month-level context (e.g. “we’re in build-up to PPV” or “PPV just happened”) into hints.

---

## 7. Personal (Off-Camera) vs Kayfabe — and Fatigue

**Intent:** Wrestlers have a “real” side (personal, rest, fatigue, motives) and an “on-camera” side (gimmick, kayfabe). POV rules already say who sees what; we add off-camera state (fatigue, rest) that affects who works and how.

### 7.1 What already exists

- **WrestlerPersonality**: `gimmick_traits` (TV/crowd) vs `personal_traits` (backstage/promoter).
- **POV**: Backstage and promoter see personal; TV and crowd see gimmick.
- **CharacterEvolution**: Updates personal traits (e.g. confidence) after matches.

### 7.2 Off-camera life (extended)

| Concept | Description |
|--------|-------------|
| **Fatigue** | Per-agent, per-date (or rolling): “worked last night” → fatigue +1; rest day → fatigue decay. High fatigue → can’t work, or reduced likelihood of being booked. |
| **Rest day** | Agent has no show; fatigue decays. Travel squads are built so loop A/B alternate, giving rest. |
| **Travel** | “On the road” vs “home.” Optional: affects fatigue (travel day = light rest) or mood (personal_traits). |
| **Injury** | Already modeled (InjuryDB): out_from, out_until. Real vs kayfabe: injury_type (legitimate, storyline, kayfabe). |

### 7.3 Fatigue model (proposed)

- **Fatigue** (numeric, e.g. 0–100): Increases when agent works a card (e.g. +15 per match or +25 per card); decreases each rest day (e.g. −20 per day, floor 0).
- **Threshold**: If fatigue &gt; 70 (configurable), agent is “rested” (not available for next card) or only used in minimal role.
- **Travel squad builder** respects fatigue: don’t put someone on the squad if they’re over threshold or had no rest since last show.

Stored as: **AgentFatigue** (agent_id, federation_id, as_of_date, fatigue_level) or a single row per agent with last_updated and value; recomputed from “work history” (match_results / card participation) if preferred.

### 7.4 Kayfabe vs real

- **On camera**: Gimmick, gimmick_traits, storyline, alignment (babyface/heel). What TV and crowd see.
- **Off camera**: Personal traits, fatigue, real injuries, contract status, backstage notes. What backstage and promoter see.
- **Critics**: Can be “kayfabe” (report as character) or “smark” (break fourth wall); already in media.Critic.style.

No extra “life simulator” required for v1; fatigue + rest + travel squad is enough to make “who works when” and “day before/after” feel real.

---

## 8. Implementation Order (Suggested)

| Step | What | Depends on |
|------|------|------------|
| 1 | **Week template** (show_type per day_of_week); extend Week or add WeekTemplate. | Calendar models. |
| 2 | **Roster pools** (TV roster, house roster, PPV roster; or derive from contract + tenure). | Contracts, tenure. |
| 3 | **Travel squad builder**: given (federation, date, show_type, template), return agent_ids. | Roster pools, get_available_at_date, loop A/B. |
| 4 | **Fatigue**: model (e.g. AgentFatigueDB), increment on card worked, decay on rest; travel squad excludes high-fatigue. | Match/card participation. |
| 5 | **Loop A/B** for house: split house roster, assign nights; travel squad for “Tuesday house” = loop A, etc. | Week template, travel squad. |
| 6 | **Day before**: optional prep_date on Card; one “prep” tick or hint “card tomorrow, squad = X.” | Travel squad, Card. |
| 7 | **Day after**: fatigue update, optional “day after” promoter tick; next-day coverage trigger. | Fatigue, Coverage. |
| 8 | **Month builder**: generate weeks from template, assign PPV to last week, generate cards + travel squads per card. | Week template, travel squad, PPV. |

---

## 9. Summary Table

| Concept | Design | Status |
|---------|--------|--------|
| Day before card | prep_date, optional prep tick, travel squad in context | Design |
| Day after card | Fatigue update, next-day coverage, optional fallout tick | Design |
| Week structure | WeekTemplate (slots: day_of_week, show_type); how many house/TV/PPV per week | Design |
| How many house shows | From template (e.g. 2–4 house slots per week) | Design |
| Roster split (house) | House roster, loop A/B, travel squad per show; only portion travels | Design |
| Roster split (TV/PPV) | TV roster, PPV roster; travel squad = subset by show type | Design |
| Week + month | Month = 4–5 weeks; PPV week; build-up/fallout; generate cards + squads | Design |
| Personal vs kayfabe | WrestlerPersonality + POV (existing); fatigue + rest = off-camera life | Design (fatigue new) |
| Fatigue | Per-agent, + on work, − on rest; travel squad excludes high fatigue | Design |

This doc is the single place for week/month, day-around-card, roster splits, and personal/kayfabe/fatigue; implementation can follow the order above and plug into existing calendar, roster_timeline, and card building.

---

## 10. Implementation Status

| Component | Status | Location |
|-----------|--------|----------|
| WeekTemplate, ShowSlot, ShowType | Done | `models/week_schedule.py` |
| WeekTemplateDB, AgentFatigueDB | Done | `models/db_models.py` |
| Card.show_type, prep_date, travel_squad_ids | Done | `models/calendar.py` |
| Roster pools (TV/house/PPV) | Done | `simulation/travel_squad.py`: get_tv_roster, get_house_roster, get_ppv_roster |
| Travel squad builder (loop A/B, fatigue) | Done | `simulation/travel_squad.py`: get_travel_squad |
| Fatigue (increment, get, decay in get_fatigue) | Done | `core_engine/fatigue.py` |
| Week builder from template | Done | `simulation/week_builder.py`: build_week_from_template |
| Month builder | Done | `simulation/month_builder.py`: build_month |
| Fatigue increment after card | Done | `simulation/orchestrator.py`: after run_card / run_full_card |
| Hints: travel_squad_ids, prep_date, show_type | Done | `simulation/orchestrator.py`: _build_hints |
| Day-before prep tick | Optional | Not implemented; hints include prep_date for context |
| Day-after promoter tick | Optional | Not implemented; fatigue + next-day coverage trigger on demand |
