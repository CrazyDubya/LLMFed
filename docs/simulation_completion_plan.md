# Simulation Completion Plan: Get It All Together

Plan to close the gaps and make the wrestling card simulation complete end-to-end.

---

## Phase 1: Wire Week → Full Card Flow (High Impact)

**Problem:** `run_week_from_template` runs plain `Card`s via `run_card`. No opening, promo, backstage, commercial, closing—just matches.

**Solution:** Convert each week-built Card to FullCard and run via `run_full_card`.

| Step | Action |
|------|--------|
| 1.1 | In `run_week_from_template`, after `fill_week_matches`, for each card: `full_card = build_full_card(card, card_type_from_show_type(card.show_type))` |
| 1.2 | Call `orch.run_card(full_card, ...)` (run_card accepts FullCard → run_full_card) |
| 1.3 | Helper: `card_type_from_show_type(show_type)` → house→HOUSE, tv→MAJOR_TV, ppv→PPV |

**Files:** `simulation/orchestrator.py`, `simulation/week_builder.py` (optional helper)

**Dependency:** None.

---

## Phase 2: FanReaction and Favorites/Hated Wiring (Medium Impact)

**Problem:** `FanEngagement.generate_fan_reaction` exists but isn't called. `favorite_agent_ids`/`hated_agent_ids` are in hints but crowd behavior doesn't explicitly use them.

**Solution:** Wire FanReaction into crowd context; pass favorites/hated into prompt so crowd bias is explicit.

| Step | Action |
|------|--------|
| 2.1 | In engine `_build_context` for role=crowd, add `favorite_agent_ids` and `hated_agent_ids` from hints to state |
| 2.2 | In `PromptBuilder` preamble for crowd, add: "The crowd loves [favorites] and hates [hated]. React accordingly." (when present) |
| 2.3 | Optional: After each participant action, call `FanEngagement.generate_fan_reaction(event, agent_popularity)` and inject result into next crowd tick or use to weight available crowd actions |

**Files:** `core_engine/engine.py`, `core_engine/prompt_builder.py`, optionally `core_engine/fan_engagement.py`

**Dependency:** None.

---

## Phase 3: Commercial / Intermission Behavior (Lower Impact)

**Problem:** Commercial segment runs one announcer tick; crowd doesn't behave differently; no "break" feel.

**Solution:** Light behavior: commercial = announcer only, no crowd tick; intermission = crowd sees "intermission" (no ring), backstage/promoter run.

| Step | Action |
|------|--------|
| 3.1 | Commercial: SEGMENT_ROLES already has ["announcer"]. Ensure crowd does NOT run during commercial (POV says TV only). Current flow: run_one_segment_tick runs only roles in SEGMENT_ROLES, so crowd won't run. Verify. |
| 3.2 | Add `segment_type` to crowd/announcer context: "commercial break" vs "intermission" vs "match" so tone can differ |
| 3.3 | Optional: Skip match ticks during commercial (if we ever interleave commercial *during* a match)—defer |

**Files:** `models/card_structure.py` (verify SEGMENT_ROLES), `core_engine/engine.py` (_build_segment_context)

**Dependency:** None.

---

## Phase 4: Day-Before Prep Tick (Optional)

**Problem:** `prep_date` is in hints; no separate "day before" tick.

**Solution:** Before running the first card of a week (or before each card), optionally run one promoter+backstage tick with context "Card tomorrow: [name]. Travel squad: [ids]. Venue: [venue]."

| Step | Action |
|------|--------|
| 4.1 | Add `run_day_before_prep(card, federation_id)` that runs one tick for promoter+backstage with segment_type="prep" and hints including prep_date, travel_squad_ids |
| 4.2 | Add "prep" to SEGMENT_ROLES: ["backstage", "promoter"] |
| 4.3 | In run_week_from_template or run_card, call run_day_before_prep when card has prep_date and flag `run_prep=True` |

**Files:** `core_engine/engine.py`, `models/card_structure.py`, `simulation/orchestrator.py`

**Dependency:** None.

---

## Phase 5: Day-After Fallout Tick (Optional)

**Problem:** Fatigue increments; no promoter/backstage "day after" reaction.

**Solution:** After each card, optionally run one promoter+backstage tick with match results, "plan next week."

| Step | Action |
|------|--------|
| 5.1 | Add `run_day_after_fallout(card, federation_id, last_match_results)` |
| 5.2 | Runs promoter+backstage with match_result summary, card_run_state |
| 5.3 | Wire into run_card / run_full_card when flag `run_fallout=True` |

**Files:** `core_engine/engine.py`, `simulation/orchestrator.py`

**Dependency:** None.

---

## Phase 6: Next-Day Coverage Trigger (Optional)

**Problem:** Coverage, Critic, MediaOutlet exist; no runtime trigger for next-day recaps.

**Solution:** After a card (or end of week), optionally create a Coverage row with scope=NEXT_DAY, target_card_id, published_at=card_date+1. No LLM call to write the article yet—just the data hook.

| Step | Action |
|------|--------|
| 6.1 | Add `create_next_day_coverage(db, card_id, federation_id, card_date)` → Coverage record |
| 6.2 | Call from orchestrator after card when `create_coverage=True` |
| 6.3 | CoverageDB or use existing models; add CoverageDB if needed |

**Files:** `agent_service/` (coverage_crud or similar), `models/db_models.py`, `simulation/orchestrator.py`

**Dependency:** None.

---

## Phase 7: Promo Segment with Wrestler (Enhancement)

**Problem:** Promo runs announcer, crowd, backstage, promoter. No "who cuts the promo."

**Solution:** Add optional `participant_ids` to Segment for promo; when present, include those wrestlers in the promo tick (they get a turn to "cut a promo").

| Step | Action |
|------|--------|
| 7.1 | Segment already has `participant_ids` for promo/backstage |
| 7.2 | When building FullCard from Card, promo segments could get participant_ids from a "promo lineup" (future: promoter picks who cuts promo) |
| 7.3 | In run_one_segment_tick for promo, if segment has participant_ids, run those participants with context "You are cutting a promo. React." |
| 7.4 | Extend SEGMENT_ROLES or add promo-specific logic: promo = announcer, crowd, backstage, promoter + optional participant_ids |

**Files:** `simulation/card_builder.py`, `core_engine/engine.py`, `models/card_structure.py`

**Dependency:** Card/segment needs a way to assign "who cuts the promo." Could be from storyline participants or a new field.

---

## Phase 8: Gate / Revenue (Implemented)

**Problem:** Venue has concessions_available, ppv_capable; no gate or PPV revenue.

**Solution:** `models/revenue.py` — RevenueResult, compute_card_revenue (gate, PPV, concessions). CardRevenueDB, revenue_crud. `compute_revenue=True` in run_card/run_full_card/run_week/run_week_from_template.

---

## Implementation Order

| Order | Phase | Effort | Impact |
|-------|-------|--------|--------|
| 1 | Phase 1: Week → FullCard flow | Small | High |
| 2 | Phase 2: FanReaction + favorites/hated | Small–Medium | Medium |
| 3 | Phase 3: Commercial/intermission verification | Small | Low |
| 4 | Phase 4: Day-before prep | Small | Low |
| 5 | Phase 5: Day-after fallout | Small | Low |
| 6 | Phase 6: Next-day coverage trigger | Small | Low |
| 7 | Phase 7: Promo with wrestler | Medium | Medium |
| 8 | Phase 8: Gate/revenue | Defer | — |

---

## Checklist (Get It All Together)

- [x] **Phase 1** — Week-built cards run as FullCards with segments
- [x] **Phase 2** — Crowd context includes favorites/hated; preamble updated; base hints for all segments
- [x] **Phase 3** — Commercial/intermission roles verified (commercial=announcer only; segment_type in state)
- [x] **Phase 4** — Optional day-before prep tick (run_prep=True; _run_day_before_prep)
- [x] **Phase 5** — Optional day-after fallout tick (run_fallout=True; _run_day_after_fallout)
- [x] **Phase 6** — Optional next-day coverage record creation (create_coverage=True; coverage_crud)
- [x] **Phase 7** — Promo segment can include wrestler(s) (card_builder assigns next match participants; engine runs promo cutters)
- [x] **Phase 8** — Gate/revenue (RevenueResult, compute_card_revenue, CardRevenueDB; compute_revenue=True)

---

## Summary

**Must-do for "complete":** Phase 1 (week → full card flow) and Phase 2 (favorites/hated in crowd).

**Nice-to-have:** Phases 3–7.

**Defer:** Phase 8.

This plan closes the main gaps so the simulation runs a full week with full cards (opening, promo, matches, commercial, backstage, closing), crowd bias, and optional day-before/day-after/next-day hooks.
