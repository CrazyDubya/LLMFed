# LLMFed: Wrestling World Architecture

## Vision

LLMFed is a **persistent living world** wrestling simulator where players assume roles
as **Promoters** or **Wrestlers** and shape the world through indirect control.

- **Promoter Mode**: Management sim / life sim / world builder. Create federations, book
  shows, manage rosters, develop storylines, set match cards, handle finances.
- **Wrestler Mode**: Character-driven RPG. Create a persona, train skills, cut promos,
  form alliances/rivalries, chase championships, build a legacy.
- **The World Lives**: LLMs and algorithms control NPCs, generate storylines, evolve
  feuds, simulate crowd reactions, and advance the world whether players are online or not.
- **Indirect Control**: Players influence outcomes through their role's tools — a promoter
  books the card but can't control what happens in the ring; a wrestler chooses training
  and promo style but can't guarantee a title shot.

## Game Modes

### Single Player
- **Start as Promoter**: Begin with a small indie federation. Book venues, sign wrestlers,
  create shows. All wrestlers are AI-controlled NPCs. Goal: grow from bingo halls to arenas.
- **Start as Wrestler**: Create a character with a gimmick. Start in the independents.
  Train, cut promos, accept bookings. The federation and other wrestlers are AI-controlled.

### Multiplayer
- **Multiple Promoters**: Competing federations in the same world. Bid for talent, compete
  for TV slots, run rival shows on the same night.
- **Multiple Wrestlers**: Players wrestle in the same or different federations. Form tag
  teams, factions, rivalries with each other or NPCs.
- **Mixed**: Some players are promoters, some wrestlers. A player-promoter books
  player-wrestlers alongside NPCs.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend (SPA)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │  Auth /   │  │ Promoter │  │ Wrestler │  │   World View   │  │
│  │  Lobby    │  │  Dashboard│ │ Dashboard│  │  (Spectator)   │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      │ REST + WebSocket
┌─────────────────────┴───────────────────────────────────────────┐
│                     FastAPI Backend                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Auth API  │  │ Game API │  │ World API│  │  WebSocket Hub │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────────┐
│                     Service Layer                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ User &   │  │ World    │  │ Match    │  │  Storyline     │  │
│  │ Player   │  │ Ticker   │  │ Simulator│  │  Engine        │  │
│  │ Service  │  │          │  │          │  │                │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ Booking  │  │ Training │  │ Economy  │  │  LLM / NPC     │  │
│  │ Service  │  │ Service  │  │ Service  │  │  Brain         │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────────┘  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
┌─────────────────────┴───────────────────────────────────────────┐
│                     PostgreSQL Database                           │
│  Users, Players, Wrestlers, Federations, Shows, Matches,         │
│  Championships, Storylines, Contracts, WorldState, NarrativeLog  │
└─────────────────────────────────────────────────────────────────┘
```

## PostgreSQL Schema

### Core Identity
- **users**: Account (email, password_hash, display_name)
- **players**: A user's game identity (player_type: promoter|wrestler, world_id)

### Wrestling World
- **worlds**: Game world instances (for single-player isolation or multiplayer shared)
- **world_state**: Key-value world state (current_date, economy, popularity, etc.)
- **federations**: Wrestling organizations (name, prestige, budget, tv_deal, home_region)
- **wrestlers**: Characters — NPC or player-controlled (name, gimmick, stats, alignment, popularity)
- **wrestler_stats**: Detailed attributes (power, speed, charisma, technical, stamina, psychology)
- **contracts**: Wrestler ↔ Federation employment (salary, duration, exclusivity)

### Shows & Matches
- **shows**: Scheduled events (federation, venue, date, show_type: weekly/ppv/special)
- **show_segments**: Ordered segments within a show (match, promo, backstage, interview)
- **matches**: Wrestling matches (match_type, stipulation, participants, winner, rating)
- **match_participants**: Join table (wrestler_id, match_id, role: competitor/manager/referee)
- **match_events**: Tick-by-tick in-ring events (move, reversal, highspot, finish)

### Storylines & Drama
- **storylines**: Active narrative arcs (feud, alliance, betrayal, championship_chase)
- **storyline_participants**: Who's involved in each storyline
- **promos**: In-character speeches/segments (wrestler, content, crowd_reaction, heat_generated)
- **championships**: Title belts (name, federation, prestige, current_holder)
- **championship_history**: Title reign history

### Player Actions
- **player_actions**: Queue of player decisions awaiting processing
- **booking_decisions**: Promoter's match card / segment bookings
- **training_sessions**: Wrestler's training choices and outcomes
- **promo_attempts**: Wrestler's promo scripts/approaches

### Narrative & History
- **narrative_logs**: World event log (what happened, when, who, where)
- **world_news**: Generated news articles about the wrestling world
- **wrestler_history**: Career milestones, match record, title reigns

## World Tick System

The world advances through **game days** (not real-time ticks). Each game day:

1. **Process player actions** from the queue
2. **AI decisions** for NPC promoters and wrestlers
3. **Simulate scheduled shows** (if any show is booked for today)
4. **Advance storylines** (LLM evaluates and evolves active feuds)
5. **Economy tick** (attendance, revenue, TV ratings, contracts)
6. **World events** (injuries, retirements, free agent signings, surprise debuts)
7. **Generate news** (LLM writes kayfabe news articles)
8. **Broadcast updates** via WebSocket to connected players

### Show Simulation Flow

When a show runs:
1. Promoter's booked card is loaded (or AI generates one for NPC feds)
2. Each segment simulates:
   - **Matches**: Multi-tick simulation using existing engine (LLM picks moves, referee
     calls, crowd reacts). Match quality determined by wrestler stats + chemistry + booking.
   - **Promos**: LLM generates promo content based on character gimmick + current feuds.
   - **Backstage**: Random events, contract negotiations, alliance shifts.
3. Results feed back into storylines, rankings, and popularity.

## Key Design Principles

1. **Everything is persistent** — every match, promo, and decision is logged
2. **AI fills the gaps** — NPCs make decisions when players don't
3. **Indirect control** — players set direction, the simulation plays out
4. **Emergent storytelling** — LLMs generate narrative from game state
5. **World doesn't wait** — background ticker advances time for all
6. **Stats matter but aren't everything** — charisma can beat power in the right storyline

## Technology Stack

- **Backend**: Python 3.10+, FastAPI, SQLAlchemy 2.0, Alembic
- **Database**: PostgreSQL 15+
- **Frontend**: React 18+ with TypeScript, Vite, TailwindCSS
- **Real-time**: WebSocket (FastAPI native)
- **LLM**: OpenAI API / Ollama (local) with provider abstraction
- **Background**: asyncio task loop for world ticker
- **Auth**: JWT with bcrypt password hashing

## Implementation Phases

### Phase 1: Foundation (Current)
- PostgreSQL schema + Alembic migrations
- New SQLAlchemy models for full game world
- User registration/login API
- Player creation (choose promoter or wrestler)
- World creation (single-player)

### Phase 2: Core Game Loop
- World ticker (game day advancement)
- Promoter tools: booking shows, signing wrestlers
- Wrestler tools: training, accepting bookings
- Match simulation (enhanced from current engine)
- NPC AI decision-making

### Phase 3: Web UI
- React SPA with auth flow
- Promoter dashboard (roster, shows, finances)
- Wrestler dashboard (stats, schedule, career)
- Show viewer (live match simulation display)
- World news feed

### Phase 4: Multiplayer
- Shared world instances
- Multiple players in same world
- Real-time updates via WebSocket
- Inter-federation competition
- Player-vs-player matches

### Phase 5: Polish
- Advanced storyline generation
- Championship tournament systems
- TV deal / media simulation
- Character relationship graph
- Historical stats and records
