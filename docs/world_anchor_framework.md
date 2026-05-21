# World Anchor Framework: 4-Year Spine and Marquee Show

The simulator is anchored on **one random coherent marquee annual show two years in the future**. The entire engine is designed backward from that event (what must come together to make it possible and meaningful) and forward from it (how the world realizes its benefits over the following two years). This document solidifies the framework so the engine provides **continuity, richness, and engagement** without hard-coding outcomes—the **promoter’s decisions** determine whether the federation achieves that reality.

---

## 1. The Anchor: One Marquee Annual Show

- **Name**: The federation’s marquee annual event (e.g. *Grandstand*, *Summit*, *Crown Jewel*). Configurable per federation; the **date** is fixed relative to world start.
- **Placement**: **Exactly two years** from the federation’s **world start date**.
- **Role**: The anchor is the **singular reference point** for:
  - **Backward design**: What storylines, roster, titles, and heat must build over 24 months.
  - **Forward design**: What payoff and aftermath look like for the next 24 months (title reigns, career arcs, new feuds, audience growth).

The engine is **fine-tuned but not overtuned**: it provides the structure (calendar, stakes, milestones) so that when run “for real,” the **promoter’s choices** (booking, pushes, storylines, contracts) determine whether the federation actually achieves that marquee reality (sellout, main-event quality, lasting impact). The gamification lives in **decision-impact**, not in scripted outcomes.

---

## 2. The 4-Year World

| Phase        | Duration   | Role |
|-------------|------------|------|
| **Build-up** | Years 0–1  | 24 months of weekly/PPV product building toward the anchor. Roster, contracts, storylines, titles, heat, and momentum accumulate. |
| **Anchor**   | Year 2     | The marquee annual show. Climax of long-term arcs; title changes; career-defining moments. |
| **Aftermath**| Years 2–3  | 24 months after the anchor. New champions, new feuds, audience and business effects. The “did we achieve it?” payoff. |

- **World start**: Federation’s canonical “day 1” (e.g. first Monday of a given year).
- **Anchor date**: World start + 2 years (e.g. first Sunday of that month).
- **World end**: World start + 4 years (optional; can run open-ended, but the **spine** is 4 years for design).

Every card, storyline, and contract exists relative to this spine. The engine can answer: *weeks until marquee*, *phase* (build_up | anchor | aftermath), *years from anchor*.

---

## 3. Backward: What Must Come Together Over Two Years

To make the anchor show **coherent and achievable**, the engine must support (and the promoter must use):

| Piece | Purpose |
|-------|--------|
| **Roster** | Stable of wrestlers, staff (announcers, refs, managers, valets). Contracts, turnover, star-building. |
| **Contracts** | Who is under contract through the anchor? Expirations, re-signings, debuts. |
| **Titles** | Lineage and prestige. Who holds what by anchor night? #1 contender logic. |
| **Storylines** | Long-term feuds and alliances. Heat, payoff timing, multi-year arcs. |
| **Heat & momentum** | Per-wrestler and per-feud. Build toward anchor main events. |
| **Audience / demographics** | Fan types, engagement. Crowd size and reaction at anchor. |
| **Cards & calendar** | House, TV, PPV, seasonal climaxes. PPVs as stepping stones to the marquee. |
| **Memories & continuity** | Agents and audience remember past events. Callbacks at the anchor. |

The **scheduler, storyline director, and character evolution** all contribute: they create the **possibility** of a coherent card two years out. The promoter’s booking (who gets pushed, who headlines, which storylines get time) determines whether that possibility becomes **reality**. The engine does not force success; it exposes **stakes and consequences**.

---

## 4. Forward: Two Years of Payoff and Consequences

After the anchor:

| Dimension | How the engine supports it |
|-----------|----------------------------|
| **Title changes** | New champions; reign length and prestige; challengers. |
| **Career arcs** | Wins/losses, momentum, heat. Who “won” the anchor; who is rebuilt. |
| **New storylines** | Feuds born from anchor outcomes; betrayals, alliances. |
| **Business / audience** | Crowd growth or decline; engagement metrics. |
| **Roster churn** | Contract ends, retirements, new signings. |

The **same systems** (storylines, stats, heat, contracts) that built toward the anchor now drive the aftermath. Continuity comes from **one timeline**: one anchor, one 4-year spine, with promoter decisions shaping whether the federation “achieved” the marquee and how the next two years play out.

---

## 5. Promoter Achievement (Gamification of the Simulation)

- **Engine responsibility**: Provide the **world** (calendar, roster, storylines, titles, heat, segments, POVs) and the **tools** (scheduling, evolution, narrative, fan engagement) so that:
  - A coherent **anchor card** is *possible* (right number of matches, talent, stakes).
  - **Achievement** is not guaranteed: poor booking, lost talent, cold storylines can lead to a weak anchor or failed payoff.
- **Promoter responsibility**: Make decisions (booking, pushes, storylines, contracts) that **impact**:
  - Whether the anchor is a “sellout” (audience, heat).
  - Whether main events feel earned (momentum, storyline payoff).
  - Whether the two years after realize benefits (new stars, sustained heat, business growth).

The engine is **fine-tuned** to this 4-year spine (stakes, milestones, continuity) but **not overtuned** to a single script: the promoter can succeed or fail within the same world. Richness and engagement come from **anchoring** the simulation on one random coherent card two years in the future and designing backward and forward from it.

---

## 6. Implementation: World Anchor in the Engine

- **WorldAnchor** (or equivalent): Holds `world_start_date`, `anchor_event_name`, `anchor_date` (world_start + 2 years), optional `world_end_date` (world_start + 4 years). Federation-scoped.
- **Phase**: For any `card_date`, compute `phase`: `build_up` | `anchor` | `aftermath` and **weeks_until_marquee** / **weeks_since_marquee** (for stakes and narrative).
- **Milestones**: Optional list of anchor-related milestones (e.g. “main event set”, “title picture locked”, “sellout threshold”) used for pacing and promoter feedback—not for forcing outcomes.
- **One random coherent card**: The “anchor card” is the **target** card for the marquee date: a full card (segments, matches, storylines) that the engine can **generate** or **evaluate** against the world state. Building that card (and whether it’s “achieved”) is the gamified goal; the engine provides the spine and the tools.

This framework encapsulates the simulator **outward from the match**: from a single match to a card, to a week, month, season, year, and finally to a **4-year world** centered on one marquee annual show two years in the future, with backward and forward design ensuring continuity, richness, and promoter-driven engagement.

---

## 7. Implementation (Engine)

| Component | Location | Purpose |
|-----------|----------|---------|
| **WorldAnchor** | `models/world_anchor.py` | Pydantic model: world_start_date, anchor_event_name, anchor_date (default +2 years), phase_for(), weeks_until_marquee(), years_from_anchor(). |
| **WorldPhase** | `models/world_anchor.py` | Enum: build_up, anchor, aftermath. |
| **AnchorMilestone** | `models/world_anchor.py` | Optional pacing milestones (roster_set, title_picture, main_event_set, heat_peak, payoff_arcs). |
| **build_default_anchor()** | `models/world_anchor.py` | First Monday of start_year, anchor = first Sunday of same month +2 years. |
| **WorldAnchorDB** | `models/db_models.py` | Persist anchor per federation (world_start_date, anchor_event_name, anchor_date). |
| **Hints** | `simulation/orchestrator.py` | _build_hints() adds `world_anchor`: phase, anchor_event, weeks_until_marquee, weeks_since_marquee, years_from_anchor (so promoter/LLM context sees stakes and continuity). |

The engine does **not** script outcomes; it exposes the spine so that when run for real, the promoter’s decisions determine whether the federation achieves the marquee reality.

---

## 8. Depth: Roster, Tenure, Injuries, Surprises, Betrayals

The anchor show is **not** “everyone on the roster today, same roster in 2 years.” The 4-year plan has **depth** so the marquee card feels earned and the simulation is rich.

### 8.1 Roster Over Time (Who Is on the Show When)

- **Different join points**: Wrestlers (and staff) **join at different times** over the 4 years. Contract `start_date` is the **debut/join date** with this federation. So:
  - Some are there from **world start** (year 0).
  - Some **debut or sign** in year 1 (rising stars by anchor night).
  - Some **debut or sign** in year 2 (newcomers; maybe call-ups, surprise signings).
  - Some **leave** (contract end, release, retirement) before or after the anchor.
- **Roster at a date**: For any given date (e.g. anchor date), the “active roster” is: agents with an active contract whose `start_date` ≤ date and (`end_date` is null or `end_date` ≥ date). So the **anchor card** is built from whoever is **on the roster that night**—a mix of people who joined 2 years ago, 1 year ago, 6 months ago, etc.

### 8.2 Veteran / Rising / Newcomer (Tenure Mix)

So the marquee show has a **mix**, not one flat roster:

| Tier | Meaning (relative to anchor) | Example |
|------|------------------------------|--------|
| **Veteran** | With the federation since early (e.g. contract start &lt; world_start + 12 months). Established names, long-term storylines. |
| **Rising** | Joined mid–build (e.g. 12–24 months before anchor). Built over time; ready for main event or title. |
| **Newcomer** | Joined recently (e.g. last 12 months before anchor, or debut in aftermath). Fresh feuds, surprise factor. |

The engine supports **tenure tier** (from contract start vs anchor date) so that:
- Booking can target “veteran main event,” “rising star title match,” “newcomer opener.”
- Storylines can reference “years of history” vs “just arrived.”
- The anchor card can be **crafted** so that not everyone was there 2 years ago—some are newcomers or surprise debuts.

### 8.3 Injuries

- **Injuries** take talent **off the board** for a period: `out_from`, `out_until`, `injury_type`, optional `return_surprise`.
- Who is **available** at a given date? Active roster **minus** anyone injured (date in [out_from, out_until]).
- **Comebacks**: Return from injury can be a **story beat** (return pop, feud with whoever “took them out”). Optional flag: `return_surprise` for unadvertised returns.
- So by anchor night: some are **just back**, some are **out** (card changes), some never got injured. Depth comes from planning injuries and returns over the 4 years.

### 8.4 Surprises (Debut, Return, Swerve)

- **Surprise debut**: Newcomer’s first appearance can be a “surprise” (contract start = anchor or big PPV).
- **Surprise return**: Injury return or “gone” star returns (use injury/absence + `return_surprise` or a dedicated return event).
- **Swerve**: Storyline beat (e.g. betrayal, alignment flip) that the engine can tag so narrative and crowd reaction can reflect it.
- The engine supports **event types** (debut, return, betrayal, etc.) so that at each step we can **craft story**—not every show is the same; surprises and swerves are first-class.

### 8.5 Betrayals (and Story at Each Step)

- **Betrayal** is already a **storyline type** (alliance → betrayal). Over 4 years:
  - Long-term allies; betrayal **payoff at anchor** (e.g. one turns on the other in the main event or in the build-up).
  - Betrayals **after** the anchor drive the next 2 years (new feuds, new alliances).
- **Story at each step**: Each wrestler and each storyline has a **trajectory**:
  - When they joined, when they got hurt, when they returned.
  - Which feuds are building, which pay off at anchor, which start in aftermath.
  - Optional **payoff_phase** on storylines: build_up (escalating) | anchor (climax) | aftermath (consequences). So we *plan* that certain arcs climax at the marquee and others in the years after.

### 8.6 How This Makes the 4-Year Plan Exciting (Not Bland)

- **Roster**: Veterans, rising stars, newcomers on the **same** anchor show—because they joined at different points. Not “everyone was there day 1.”
- **Injuries**: Cards change; comebacks are moments; “will they be back for the marquee?” is a real question.
- **Surprises**: Debuts and returns can be **scheduled** (or emergent) so the 2-year show has surprise factor.
- **Betrayals**: Long-term storylines that **pay off** at anchor or in aftermath; relationship flips that the engine and narrative can use.
- **Crafting at each step**: The simulator supports **who joins when**, **who’s out when**, **which storylines climax when**. The promoter (or scenario) can plan a **rich** 4 years so the anchor card is coherent and exciting, and the aftermath continues the story.

### 8.7 Implementation (Depth)

| Component | Location | Purpose |
|-----------|----------|---------|
| **TenureTier** | `models/roster.py` | Enum: veteran, rising, newcomer (for anchor-card mix). |
| **Injury** | `models/roster.py` | out_from, out_until, return_surprise; `is_out_on(date)`. |
| **InjuryDB** | `models/db_models.py` | Persist injuries per agent/federation. |
| **StorylinePayoffPhase** | `models/wrestling.py` | build_up, anchor, aftermath (planned climax). |
| **Storyline.payoff_phase** | `models/wrestling.py`, `StorylineDB.payoff_phase` | Optional: which phase this arc climaxes in. |
| **get_roster_at_date** | `simulation/roster_timeline.py` | Active roster at date (contract start/end); fallback to agents by federation_id. |
| **get_available_at_date** | `simulation/roster_timeline.py` | Roster at date minus injured (who’s out on that date). |
| **tenure_tier_for** | `simulation/roster_timeline.py` | Compute veteran/rising/newcomer from join_date vs reference date. |
| **get_tenure_mix_at_date** | `simulation/roster_timeline.py` | { veteran: [ids], rising: [ids], newcomer: [ids] }. |
| **get_anchor_card_composition** | `simulation/roster_timeline.py` | Tenure mix, out_injured, just_returned for the marquee show. |

---

## 9. Two Temporals: Conceptual Timeline vs Run Timeline

The engine distinguishes **two temporal layers**. One is the **world built to achieve the card** (the plan, the target). The other is the **reality for the promoter in the moment of running it**—where they don’t have the pieces yet and must introduce them, sort chaff from wheat, and face chance, trapdoors, and ripples.

### 9.1 Conceptual Timeline (The Plan)

- **What it is**: The 4-year spine and the **target** marquee card. The “world built to achieve the card”: who *should* be veterans, rising, newcomers; which storylines *should* pay off at anchor; what the promoter is **aiming** for.
- **When it exists**: As a **design** or **intent**. The promoter (or scenario) can **plan** cards in conceptual terms: “In two years we want this main event, this title match, these feuds.” They can sketch debuts, pushes, and payoff phases.
- **What they don’t have yet**: In the conceptual layer, the pieces are **not** all real yet. Talent must still be **introduced** (debuts, signings). The roster must be **sorted from the chaff**—not everyone will get over; some will be released, some pushed. So the conceptual timeline is a **target**, not the run state.

### 9.2 Run Timeline (Reality in the Moment)

- **What it is**: The **actual** simulation state as it unfolds week by week, card by card. The promoter runs the engine **in the moment**. At any step they have only what has **already happened**: who has debuted, who is injured, who has heat, which storylines are hot or cold.
- **What they must do**: **Introduce** talent over time (debuts, signings). **Sort** who works and who doesn’t (chaff vs wheat). React to **random chance**, **injuries**, **cold starts**, **trapdoors** (change of mind, swerves). **Prune** or **pursue** branches (storylines, pushes) to try to achieve the 2-year card—or fail.
- **Gamification**: The run timeline is where the **gamification layer** lives. Random chance, what-ifs, multiple possible branches, trapdoors, and ripples all apply **here**. The promoter’s decisions interact with luck and consequences; the conceptual card is the **goal**, the run is the **reality**.

### 9.3 Gamification Layer: Chance, Branches, Pruning

- **Random chance**: Matches, injuries, crowd reaction, contract outcomes—the engine can inject variance so the run is not deterministic. **Lady luck** (good and ill): a breakout star, an untimely injury, a cold start.
- **Multiple branches**: Many possible paths lead toward (or away from) the anchor card. A push, a feud, a debut—each is a **branch**. Over time, some branches **thrive** (heat, momentum, payoff) and some **die** (cold, dropped, released). The promoter tries to **prune** dead branches and **nurture** the ones that get them toward the 2-year card.
- **What-ifs**: “What if we push X?” “What if Y gets injured?” The run timeline is one realized path; the conceptual timeline can encode **alternatives** or **targets**, but only the run produces the actual outcome.

### 9.4 Trapdoors (Change of Mind)

- **Trapdoors**: The promoter (or the sim) can **change direction**. Dropped storylines, swerves, new feuds, released talent, repackaged characters. A **trapdoor** is a point where the plan shifts: we *were* building to X, now we’re building to Y (or abandoning a branch). The run timeline records these; the conceptual timeline can be **updated** (new plan) or left as “what we once aimed for.”
- **Ripples**: A trapdoor **ripples**. Change the main event—now the title picture changes, the undercard gets different spotlight, someone’s push is cut or another’s is born. The engine can treat trapdoors as **events** that propagate effects (heat, momentum, storyline status).

### 9.5 Ripples and Effects (Injury, Cold Start, Lady Luck)

- **Injury**: A single event—someone is out. **Ripple**: Card changes, feuds pivot, someone else gets the spot (or the angle is dropped). Run timeline updates; conceptual plan may need to adapt (trapdoor) or absorb the hit.
- **Cold start**: A talent or angle doesn’t get over. **Ripple**: Push is cut, storyline is dropped or repackaged, roster is “sorted” (chaff). The run timeline reflects the cold start; the promoter prunes that branch.
- **Lady luck (good)**: Breakout performance, surprise pop, perfect timing. **Ripple**: New star, hotter feud, momentum. Run timeline gets a positive branch; promoter can lean in.
- **Lady luck (ill)**: Bad timing, injury before the big match, crowd turns. **Ripple**: Plan B, trapdoor, or failure to achieve the conceptual card. Run timeline records the setback.

So: **one timeline is the world built to achieve the card** (conceptual, target, plan). **The other is the reality for the promoter in the moment of running it**—where they must introduce and sort the pieces, face chance and trapdoors, and live with the ripples. The engine supports both; the gamification layer (random chance, branches, pruning, trapdoors, ripples) operates on the run timeline and determines whether the conceptual card is ever achieved.

### 9.6 Implementation (Two Temporals)

| Concept | Location | Purpose |
|---------|----------|---------|
| **TemporalLayer** | `models/temporals.py` | Enum: conceptual (plan) vs run (reality). |
| **BranchStatus** | `models/temporals.py` | alive, pruned, achieved, deferred (branch life in the run). |
| **RippleCause** | `models/temporals.py` | injury, cold_start, luck_good, luck_ill, trapdoor, debut, return, release. |
| **Ripple** | `models/temporals.py` | Effect that propagates (cause, at_date, agent_ids, storylines). |
| **Trapdoor** | `models/temporals.py` | Change of direction (from_branch, to_branch, reason, ripple_ids). |
| **RunState** | `models/temporals.py` | Snapshot of run timeline: branch_statuses, recent_ripples, recent_trapdoors. |
| **ConceptualCard** | `models/temporals.py` | Target card (main_event_target, title_matches_target, planned_storyline_payoffs). |

---

## 10. The One Card (Build)

The engine builds **one coherent FullCard** for the marquee show at anchor date.

### 10.1 Anchor Card Builder

- **`build_anchor_card(db, federation_id, anchor, conceptual_target)`** (`simulation/anchor_card_builder.py`): Builds a FullCard for the anchor date using:
  - `get_available_at_date` (roster minus injured)
  - `get_tenure_mix_at_date` (veteran/rising/newcomer)
  - Titles and storylines with `payoff_phase=anchor`
  - Optional `conceptual_target` (main_event_target, title_matches_target, planned_storyline_payoffs)
- Match ordering: main event (veterans) → title matches (veteran/rising vs champion) → storyline payoffs → filler.

### 10.2 Conceptual Card (Target)

- **GET /federations/{id}/conceptual_card**: Get target main event, title matches, planned storylines.
- **POST /federations/{id}/conceptual_card**: Set target. Body: `main_event_target`, `title_matches_target`, `planned_storyline_payoffs`.

### 10.3 Promoter Guidance

- **`build_promoter_guidance(world_anchor, conceptual_target, composition)`** (`core_engine/promoter_guidance.py`): Produces guidance text for promoter LLM.
- Orchestrator `_build_hints` injects `promoter_guidance`, `world_anchor`, `conceptual_card`, `anchor_stakes` when card has a date.
- PromptBuilder adds promoter preamble with guidance when role=promoter.

### 10.4 API

- **GET /federations/{id}/anchor_card**: Build the one coherent FullCard for the marquee show.
