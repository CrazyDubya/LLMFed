# World Bubbles: Venues, Critics, Media, Viewing, Fan Preferences

The card happens **in a place**. Fans watch **somewhere**. Critics and newsrooms write **next day** and **in real time**. Concessions, gate, PPV money, pubs and living rooms—microcosms that rise and pop as needed. This doc specifies the structures so the world can "have it all."

---

## 1. The Place: Venues and Stadiums

Every card is at a **venue**. The venue defines where the show is, how big it is, whether it's special, and how money flows.

| Concept | Description |
|--------|-------------|
| **Venue** | Named place: arena, stadium, ballroom, bingo hall. Has location, capacity, venue_type. |
| **venue_type** | `arena` (regular), `stadium` (marquee, big gate), `tv_only` (no live crowd), `special` (historic, one-off). |
| **Capacity** | Max attendance; affects gate revenue and crowd mix. |
| **Concessions** | Whether food/drink is sold; concession revenue can be modeled (house cut vs vendor). |
| **PPV capable** | Venue can host a PPV broadcast (production trucks, feed); not every building is. |
| **Gate / revenue** | Ticket sales (gate), PPV buys, merch at venue. Federation makes money here. |

**Card ↔ Venue**: A card (or week’s show) is held at one venue. Venue choice affects crowd size, prestige, and whether the show is "special" (e.g. Madison Square Garden, Wembley).

---

## 2. Critics and Media

**Critics** exist. They write **next day** (recaps, ratings, "what we learned"), **in real time** (live blogs, live reactions), and sometimes **on blogs** (opinion, hot takes).

| Concept | Description |
|--------|-------------|
| **MediaOutlet** | Source of coverage: blog, newspaper, TV, podcast. Has name, type, reach. |
| **Critic** | Byline/agent tied to an outlet. Can have bias (favorite wrestler, hated gimmick), style (smark, casual, kayfabe). |
| **Coverage / Story** | A piece of media: recap, live blog, editorial. Has scope (real_time, next_day, weekly_recap), target (card, match, angle), author/critic, published_at. |
| **Next-day** | Recap and ratings published the day after the show. |
| **Real-time** | Live blog or live reaction during the show. |
| **Blog** | Opinion, hot takes, "dirtsheet" style; can be in-world or meta. |

Newsrooms are **bubbles**: they activate when a show happens (real-time) or the next morning (next-day). They don’t need to exist every tick; they rise when needed and pop when the story is filed.

---

## 3. Fan Reactions, Favorites, Hated

Fans **react** (already: FanReaction, chants, intensity). They also have **favorites** and **hated** wrestlers (or stables, angles).

| Concept | Description |
|--------|-------------|
| **Fan preferences** | Per segment or per demographic: favorite_agent_ids, hated_agent_ids (or bias_for / bias_against). |
| **Reaction bias** | Crowd reaction weighted by favorites/hated: cheer the face they love, boo the heel they hate (or the worker they just dislike). |
| **Superfans** | Stronger preferences; more likely to chant, start "fight forever," or turn on a match. |

Staff already has `bias_toward` (e.g. announcer favorite). Audience segments can carry **favorite_agent_ids** and **hated_agent_ids** so the crowd isn’t neutral—they have favorites and hated.

---

## 4. Concessions and Money at the Venue

At the **place**:

| Concept | Description |
|--------|-------------|
| **Concessions** | Available or not; optional revenue share (house cut). |
| **Gate** | Ticket revenue = f(attendance, ticket_tier, venue). |
| **PPV** | When the card is PPV, revenue from buys (in-world: domestic/international, price tier). |
| **Merch** | At-venue merch sales; optional. |

Venue can have flags: `concessions_available`, `ppv_capable`. Revenue can be modeled later; the **structures** (venue, gate_model, ppv_model) exist so "they make money, PPV is shown" is representable.

---

## 5. Viewing Microcosms: Pubs, Living Rooms, Newsrooms

People don’t only watch in the arena. They watch in **microcosms**:

| Microcosm | Description |
|-----------|-------------|
| **Arena / venue** | Live crowd; one segment per section or one aggregate crowd. |
| **Living room** | At-home viewer (TV or stream); demos (family, superfan alone). |
| **Pub / bar** | Watch party; group reaction, noise, "everyone cheers the babyface." |
| **Watch party** | Informal group (friend’s house, dorm); similar to pub. |
| **Newsroom** | Where critics/journalists "are" when writing real-time or next-day; a bubble that activates for the show. |

These are **viewing contexts**. They can be modeled as **ViewingContext**: type (arena_section, living_room, pub, watch_party, newsroom), optional venue_id (for pub at a physical place), optional demo (who’s in the room). Bubbles: a pub "exists" when there’s a show on; a newsroom "exists" when a critic is filing. Much can be implied (e.g. "pub" = one entity per region) or explicit (named pub, named critic).

---

## 6. What Exists So the World Can "Have It All"

- **Venue** (place): name, location, capacity, venue_type, concessions_available, ppv_capable; card → venue_id.
- **Critic / MediaOutlet**: outlet type (blog, newspaper, tv, podcast), name; optional critic agent/bylines.
- **Story / Coverage**: scope (real_time, next_day, recap), target (card_id, match_id), author, published_at; so "next day" and "in real time" are first-class.
- **ViewingContext**: type (arena, living_room, pub, watch_party, newsroom); optional venue_id; bubbles that rise and pop.
- **Fan preferences**: favorite_agent_ids, hated_agent_ids on AudienceSegment or a small FanPreferences model; so fans have favorites and hated.
- **Concessions / gate / PPV**: flags and optional revenue models on Venue and Card; so "they make money, PPV is shown" is in the data.

Implementation can be phased: first the **models and docs** (so prompts and guidance can reference "the venue," "the critic's next-day piece," "fans in the pub"), then wiring (orchestrator, APIs, persistence). The point is: **enough must exist** for the simulation to behave as if it's all there—critics write the next day, fans have favorites and hated, the card is in a place, and pubs/living rooms/newsrooms are bubbles that rise and pop as needed.

---

## 7. Prompts and guidance

When building context for LLMs (promoter, crowd, backstage, announcer):

- **Venue**: Include `venue_id`, venue name, venue_type, capacity, and whether it's PPV/special so the model knows *where* the card is and why it might be a big night.
- **Critics / next-day**: For post-show or recap prompts, include that "critics will file next-day recaps" or "the newsroom is covering this show"; optional `Coverage` scope (real_time, next_day) for narrative hooks.
- **Fan preferences**: Pass `favorite_agent_ids` and `hated_agent_ids` (from AudienceSegment or FanPreferences) into crowd/announcer context so reactions are biased (cheer favorites, boo hated).
- **Viewing context**: When simulating "where" the audience is (arena vs living room vs pub), pass `ViewingContext` type so tone can differ (pub = rowdy, living_room = family/solo, newsroom = critic filing).

---

## 8. Match-in-the-middle: what a match receives

When the orchestrator runs a match (including the **match in the middle** of a card), it builds hints via `_build_hints(federation_id, match, card)` and passes them to the engine. Every tick, the prompt includes these hints. As of the "match glue" implementation, a match receives:

| Hint | Description |
|------|-------------|
| **venue** | The place: name, location, capacity, venue_type, concessions_available, ppv_capable (from VenueDB if card.venue_id set). |
| **audience** | Crowd mix (superfan_pct, etc.) and **favorite_agent_ids** / **hated_agent_ids** for reaction bias (from AudienceSegmentDB by card_id, or defaults). |
| **viewing_context** | Where the audience is watching; default `"arena"` for live card. |
| **card_name**, **is_ppv** | Card identity and PPV flag. |
| **storyline** | If match has storyline_id: title, type, heat, participants. |
| **title_match** | If title match: title_name, tier, champion_id. |
| **world_anchor**, **promoter_guidance**, **anchor_stakes** | When card has a date: 4-year spine, guidance, stakes. |

To inspect what the middle match gets: run `python scripts/run_middle_match.py` (optionally `--run` to execute a few ticks). See `simulation/orchestrator.py` `_build_hints` and `agent_service/venue_crud.py` for venue loading.
