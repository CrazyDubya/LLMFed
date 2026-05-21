# Conducting Cards and Events: Promoter, Federation, World, Wrestlers

Design for how cards and events flow through Week → Month → Season → Annual, and how the **promoter**, **federation**, **larger world**, and **specific wrestlers** fit into conducting this calendar.

---

## 1. Hierarchy

```
Year (federation year; world anchor spine)
  └── Season (3–4 months; build to seasonal climax)
        └── Month (4–5 weeks; build to PPV)
              └── Week (Mon–Sun; house/TV/PPV slots)
                    └── Card (one show: house, TV, or PPV)
                          └── Events: matches, promos, backstage, commercial, closing
```

- **Card**: A single show (house, TV, or PPV). Contains matches and segments. Conducted by the promoter.
- **Week**: 4–7 cards (or fewer). House loop A/B, TV, PPV. Each card has a travel squad (specific wrestlers).
- **Month**: 4–5 weeks. Last week = PPV week. Build-up weeks lead to PPV; fallout week(s) after.
- **Season**: 3–4 months. Optional seasonal climax (e.g. Survivor Series). Connects to world anchor.
- **Year**: Federation year. Anchored by the **marquee annual show** (world anchor).

---

## 2. Promoter

The **promoter** conducts cards and plans the calendar. They operate at multiple levels:

| Level | Promoter Role |
|-------|---------------|
| **Card** | Book matches, assign promo cutters, set tone. Receives: travel squad, venue, card_run_state, last_match_result. |
| **Week** | Ensure week flows (TV builds storylines; house loops rehearse; PPV week culminates). Day-before prep, day-after fallout. |
| **Month** | Build toward PPV. Week 1–3: build-up (storylines, title picture, heat). PPV week: payoff. Post-PPV: fallout, new arcs. |
| **Season** | Build toward seasonal climax (if any) and annual marquee. Roster evolution, tenure mix, injuries, trapdoors. |
| **Annual** | Achieve (or fail) the conceptual card at the marquee show. World anchor provides stakes. |

**Context flow**: Promoter hints include `world_anchor` (annual), `month_context` (where in month), `season_context` (where in season), `run_state` (ripples, trapdoors), `tier9_recall` (canonical records).

---

## 3. Federation

The **federation** owns:

- **Calendar**: Weeks, months, seasons, years.
- **Roster**: Wrestlers, contracts (full_time, part_time, ppv_appearance), tenure (veteran, rising, newcomer).
- **Venues**: Where cards happen; capacity, PPV-capable.
- **Titles**: Lineage, current champions.
- **Storylines**: Active feuds, payoff_phase (build_up, anchor, aftermath).
- **Tier 9 immutables**: Card dates, attendance, match results, title changes.

The federation is the scope for `recall()`, `build_month`, travel squad, and fatigue.

---

## 4. Larger World

The **larger world** is the 4-year spine (world anchor):

- **World anchor**: Marquee annual show (e.g. Grandstand) at `anchor_date` (e.g. world_start + 2 years).
- **Phases**: `build_up` (toward anchor), `anchor` (marquee month), `aftermath` (beyond anchor).
- **Conceptual vs run**: Conceptual = plan; run = reality. Trapdoors, ripples, branches.

Promoter guidance includes `weeks_until_marquee`, `anchor_event`, `conceptual_card` (main event target, title matches, storyline payoffs).

---

## 5. Specific Wrestlers

**Wrestlers** are the actors. At each level:

| Level | Wrestler Context |
|-------|------------------|
| **Card** | Travel squad for this show. Who is available (not injured, not over-fatigued). Who cuts promos. Match participants. |
| **Week** | Loop A vs B (house). TV roster vs house roster. Fatigue: who worked last night, who rested. |
| **Month** | Tenure mix (veteran main event, rising title matches, newcomer openers). Out injured, just returned. |
| **Season/Annual** | Roster evolution. Who got over, who got cut (chaff). Contract status. |

**Roster pools**: TV roster, house roster (loop A/B), PPV roster. Derived from contract + tenure + fatigue.

---

## 6. Conducting a Card

When the promoter **conducts a card**:

1. **Day before** (optional): Prep tick. Context: card tomorrow, travel squad, venue.
2. **Card run**: Full segment flow (opening → promo → matches → commercial → backstage → closing).
3. **Day after**: Fatigue increment, next-day coverage (optional), fallout tick (optional).
4. **Tier 9**: Record immutables (card date, attendance, match results, title changes).

Hints at card level: venue, audience (favorites/hated), viewing_context, card_run_state, travel_squad_ids, prep_date, show_type.

---

## 7. Conducting a Week

When the promoter **conducts a week**:

- For each card (by date): run day-before (optional), run card, run day-after (optional).
- Pass `last_match_result` and `card_run_state` across cards (or reset per card).
- Week context: which week of the month (1–4), build-up vs PPV week vs fallout.

---

## 8. Conducting a Month

When the promoter **conducts a month**:

- **Month context**: `month_week_index` (1–4), `is_ppv_week`, `phase` (build_up_to_ppv | ppv_week | post_ppv_fallout).
- For each week: build week from template, fill matches, run cards.
- PPV week: last week; Sunday card = PPV. Use ppv_template.
- Build-up: Storylines point toward PPV. Fallout: New champions, new feuds.

---

## 9. Conducting a Season and Annual

- **Season**: 3–4 months. Optional seasonal climax (e.g. Survivor Series). Month context includes `season_month_index`.
- **Annual**: World anchor. Marquee show = climax of the year (or year 2 in the spine). `years_from_anchor`, `weeks_until_marquee`.

---

## 10. Events (Beyond Matches)

| Event Type | When | Who |
|------------|------|-----|
| **Match** | During card | Participants, ref, announcer, crowd |
| **Promo** | During card | Announcer, crowd, backstage, promoter, optional wrestler |
| **Day-before prep** | Day before card | Backstage, promoter |
| **Day-after fallout** | Day after card | Backstage, promoter |
| **Next-day coverage** | card_date + 1 | Coverage record (no LLM; data hook) |
| **Real-time coverage** | During show | Future: live blog bubble |

---

## 11. Implementation Summary

| Component | Status |
|-----------|--------|
| Card → Week → Month | Done (build_week_from_template, build_month) |
| build_season | Done (simulation/month_builder.py) |
| run_card, run_week_from_template | Done |
| run_month, run_season | Done (simulation/orchestrator.py) |
| Month/season context in hints | Done (build_month_context, promoter preamble) |
| Promoter guidance (world anchor, conceptual) | Done |
| Travel squad, fatigue, roster pools | Done |
| Tier 9 immutables, recall | Done |
| Ripples, trapdoors | Done |
| PPV attached to month’s last week | Extended |
