"""
World management service - creating worlds, players, and managing game state.
"""

import logging
import random
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from models.game_models import (
    WorldDB,
    WorldStateDB,
    PlayerDB,
    GameFederationDB,
    GameWrestlerDB,
    WrestlerStatsDB,
    ContractDB,
    ChampionshipDB,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NPC wrestler generation data
# ---------------------------------------------------------------------------

WRESTLER_FIRST_NAMES = [
    "Stone",
    "The",
    "Big",
    "Iron",
    "Lightning",
    "Shadow",
    "Diamond",
    "Golden",
    "Razor",
    "Thunder",
    "Crimson",
    "Silver",
    "Black",
    "White",
    "Red",
    "Blue",
    "King",
    "Prince",
    "Duke",
    "Baron",
    "Count",
    "Lord",
    "Mad",
    "Wild",
]

WRESTLER_LAST_NAMES = [
    "Havoc",
    "Storm",
    "Wolf",
    "Dragon",
    "Phoenix",
    "Titan",
    "Cobra",
    "Viper",
    "Hawk",
    "Eagle",
    "Bull",
    "Bear",
    "Panther",
    "Jaguar",
    "Fury",
    "Blaze",
    "Cross",
    "Steele",
    "Hart",
    "Austin",
    "Rock",
    "Edge",
    "Kane",
    "Mysterio",
]

GIMMICKS = [
    "A trash-talking powerhouse who backs up every boast",
    "A silent assassin who lets his moves do the talking",
    "A flamboyant showman who lives for the spotlight",
    "A blue-collar brawler fighting for the working class",
    "A cunning tactician who always has a plan",
    "A high-flying daredevil with no fear",
    "A mysterious loner with a dark past",
    "A charismatic leader who inspires loyalty",
    "A ruthless competitor who will do anything to win",
    "A technical wizard who can counter any move",
    "A monster heel who destroys everything in his path",
    "A plucky underdog who never gives up",
    "A conniving villain who hides behind henchmen",
    "A street-smart brawler from the wrong side of the tracks",
    "A comedy character who's actually dangerous when provoked",
    "A supernatural entity that seems to defy human limits",
]

FEDERATION_NAMES = [
    ("Global Wrestling Alliance", "GWA"),
    ("National Wrestling Federation", "NWF"),
    ("Championship Wrestling International", "CWI"),
    ("Extreme Combat Wrestling", "ECW2"),
    ("Pacific Pro Wrestling", "PPW"),
    ("Southern Championship Wrestling", "SCW"),
    ("Midwest Wrestling League", "MWL"),
    ("Empire State Wrestling", "ESW"),
]

REGIONS = [
    "Northeast",
    "Southeast",
    "Midwest",
    "Southwest",
    "West Coast",
    "International",
]
STYLES = [
    "Sports Entertainment",
    "Strong Style",
    "Lucha Libre",
    "Technical",
    "Hardcore",
    "Old School",
]
WEIGHT_CLASSES = [
    "lightweight",
    "cruiserweight",
    "middleweight",
    "heavyweight",
    "super_heavyweight",
]

# Named venue pools by region — gives shows real character
VENUES = {
    "Northeast": {
        "club": [
            "The Hammerstein Ballroom",
            "The ECW Arena",
            "The Manhattan Center",
            "Webster Hall",
            "The Palladium",
        ],
        "arena": [
            "Madison Square Garden Theater",
            "Boardwalk Hall",
            "The Prudential Center",
            "Nassau Coliseum",
            "Barclays Center",
            "TD Garden",
        ],
        "stadium": ["MetLife Stadium", "Yankee Stadium", "Gillette Stadium"],
    },
    "Southeast": {
        "club": [
            "Center Stage Theater",
            "The Impact Zone",
            "The Sportatorium",
            "The Cajun Dome Club",
            "The Warehouse",
        ],
        "arena": [
            "The Omni",
            "Greensboro Coliseum",
            "The Civic Center",
            "Amway Center",
            "Bridgestone Arena",
            "FedExForum",
        ],
        "stadium": [
            "The Georgia Dome",
            "Raymond James Stadium",
            "Bank of America Stadium",
        ],
    },
    "Midwest": {
        "club": [
            "The Odeum",
            "Davis Arena",
            "The Rave",
            "Harley Race Arena",
            "The Coliseum Club",
        ],
        "arena": [
            "Allstate Arena",
            "Rupp Arena",
            "The Kiel Center",
            "Joe Louis Arena",
            "The Bradley Center",
            "Bankers Life Fieldhouse",
        ],
        "stadium": ["Soldier Field", "Ford Field", "Lucas Oil Stadium"],
    },
    "Southwest": {
        "club": [
            "The Bomb Factory",
            "The Aztec Theater",
            "The Pavilion",
            "South Side Ballroom",
            "The Pit",
        ],
        "arena": [
            "The Alamodome Theater",
            "American Airlines Center",
            "Dickies Arena",
            "The Toyota Center",
            "Desert Diamond Arena",
            "Moody Center",
        ],
        "stadium": ["AT&T Stadium", "NRG Stadium", "The Alamodome"],
    },
    "West Coast": {
        "club": [
            "The Grand Olympic Auditorium",
            "The Shrine Expo",
            "The Cow Palace Club",
            "The Hollywood Palladium",
            "The Showbox",
        ],
        "arena": [
            "The Staples Center",
            "Oracle Arena",
            "The Forum",
            "T-Mobile Arena",
            "Moda Center",
            "Climate Pledge Arena",
        ],
        "stadium": ["SoFi Stadium", "Levi's Stadium", "Allegiant Stadium"],
    },
    "International": {
        "club": [
            "The Budokan Hall",
            "York Hall",
            "Korakuen Hall",
            "Arena Mexico",
            "Wembley Arena Club",
        ],
        "arena": [
            "Tokyo Dome City Hall",
            "Manchester Arena",
            "The O2 Arena",
            "Osaka-Jo Hall",
            "Ryogoku Kokugikan",
            "Wembley Arena",
        ],
        "stadium": ["Tokyo Dome", "Wembley Stadium", "Melbourne Cricket Ground"],
    },
}


def pick_venue(region: str, capacity: int) -> str:
    """Pick a named venue appropriate for the capacity and region."""
    region_venues = VENUES.get(region, VENUES["Northeast"])
    if capacity <= 1500:
        tier = "club"
    elif capacity <= 15000:
        tier = "arena"
    else:
        tier = "stadium"
    pool = region_venues.get(tier, region_venues["arena"])
    return random.choice(pool)


def _random_stat(base: int = 50, variance: int = 25) -> int:
    """Generate a random stat with a normal distribution around base."""
    return max(1, min(100, base + random.randint(-variance, variance)))


def _generate_career_goals(age: int) -> list:
    """Generate career goals for a wrestler based on age."""
    goals = []

    if age < 25:
        goals.append(
            random.choice(
                [
                    "win_first_title",
                    "prove_myself",
                    "make_it_to_main_event",
                ]
            )
        )
    elif age < 32:
        goals.append(
            random.choice(
                [
                    "become_champion",
                    "main_event_ppv",
                    "build_legacy",
                    "become_top_draw",
                    "win_title_at_crown_jewel",
                ]
            )
        )
    else:
        goals.append(
            random.choice(
                [
                    "one_more_title_run",
                    "mentor_next_generation",
                    "retirement_match",
                    "cement_legacy",
                    "prove_doubters_wrong",
                ]
            )
        )

    # Secondary goal
    goals.append(
        random.choice(
            [
                "earn_respect",
                "get_rich",
                "have_5_star_match",
                "defeat_rival",
                "headline_biggest_show",
            ]
        )
    )

    return goals


def _pick_archetype(alignment: str, stats_dict: dict) -> str:
    """Pick a gimmick archetype based on alignment and dominant stats."""
    # Determine dominant style from stats
    style_scores = {
        "power": stats_dict.get("power", 50) + stats_dict.get("toughness", 50),
        "aerial": stats_dict.get("aerial", 50) + stats_dict.get("speed", 50),
        "technical": stats_dict.get("technical", 50) + stats_dict.get("submission", 50),
        "brawling": stats_dict.get("brawling", 50) + stats_dict.get("toughness", 50),
        "charisma": stats_dict.get("charisma", 50) + stats_dict.get("mic_skill", 50),
    }
    dominant = max(style_scores, key=style_scores.get)

    # Map dominant style + alignment to likely archetypes
    archetype_map = {
        ("power", "heel"): ["monster_heel", "cult_leader"],
        ("power", "face"): ["patriot", "legacy"],
        ("power", "tweener"): ["anti_hero", "silent_assassin"],
        ("aerial", "heel"): ["cocky_technician", "daredevil"],
        ("aerial", "face"): ["daredevil", "underdog_face"],
        ("aerial", "tweener"): ["daredevil", "anti_hero"],
        ("technical", "heel"): ["cocky_technician", "silent_assassin"],
        ("technical", "face"): ["legacy", "underdog_face"],
        ("technical", "tweener"): ["anti_hero", "cocky_technician"],
        ("brawling", "heel"): ["monster_heel", "cult_leader"],
        ("brawling", "face"): ["patriot", "underdog_face"],
        ("brawling", "tweener"): ["anti_hero", "silent_assassin"],
        ("charisma", "heel"): ["cult_leader", "cocky_technician"],
        ("charisma", "face"): ["comedy_act", "underdog_face"],
        ("charisma", "tweener"): ["anti_hero", "comedy_act"],
    }
    options = archetype_map.get((dominant, alignment), ["anti_hero"])
    return random.choice(options)


def _generate_npc_wrestler(world_id: str) -> tuple:
    """Generate a random NPC wrestler with stats."""
    name = f"{random.choice(WRESTLER_FIRST_NAMES)} {random.choice(WRESTLER_LAST_NAMES)}"
    age = random.randint(20, 42)
    exp = max(0, age - 18 - random.randint(0, 5))

    from game_service.wrestler_lifecycle_service import (
        generate_physical_attributes,
        update_career_phase,
    )

    phys = generate_physical_attributes()
    peak_age = random.randint(26, 32)

    # Generate stats first so we can derive archetype
    exp_bonus = min(exp * 2, 30)
    stats_raw = {
        "power": _random_stat(45 + exp_bonus // 2),
        "speed": _random_stat(55 - age // 4),
        "technical": _random_stat(40 + exp_bonus),
        "aerial": _random_stat(50 - age // 3),
        "brawling": _random_stat(45 + exp_bonus // 2),
        "submission": _random_stat(40 + exp_bonus // 2),
        "stamina": _random_stat(55 - age // 5),
        "toughness": _random_stat(50 + exp_bonus // 3),
        "charisma": _random_stat(50),
        "mic_skill": _random_stat(45),
        "psychology": _random_stat(35 + exp_bonus),
        "selling": _random_stat(40 + exp_bonus // 2),
        "backstage_politics": _random_stat(40),
        "loyalty": _random_stat(50),
        "work_ethic": _random_stat(60),
        "injury_prone": _random_stat(30, 15),
    }

    alignment = random.choice(["face", "heel", "tweener"])
    charisma_style = random.choice(
        ["cocky", "humble", "intense", "funny", "mysterious"]
    )

    # Pick archetype and generate archetype-specific finisher + signatures
    archetype = _pick_archetype(alignment, stats_raw)

    from core_engine.match_engine import ARCHETYPE_FINISHERS, SIGNATURE_MOVE_POOLS

    finisher_pool = ARCHETYPE_FINISHERS.get(archetype, ARCHETYPE_FINISHERS["anti_hero"])
    finisher_name, finisher_type = random.choice(finisher_pool)

    sig_pool = SIGNATURE_MOVE_POOLS.get(archetype, SIGNATURE_MOVE_POOLS["anti_hero"])
    signature_moves = [
        list(sig) for sig in random.sample(sig_pool, min(3, len(sig_pool)))
    ]

    wrestler = GameWrestlerDB(
        world_id=world_id,
        name=name,
        is_npc=True,
        gimmick=random.choice(GIMMICKS),
        alignment=alignment,
        popularity=random.randint(20, 80),
        condition=random.randint(80, 100),
        morale=random.randint(50, 90),
        age=age,
        experience_years=exp,
        weight_class=random.choice(WEIGHT_CLASSES),
        finisher_name=finisher_name,
        finisher_type=finisher_type,
        signature_moves=signature_moves,
        personality_traits={
            "aggression": random.randint(20, 90),
            "charisma_style": charisma_style,
            "risk_tolerance": random.randint(20, 90),
            "archetype": archetype,
        },
        career_goals=_generate_career_goals(age),
        # Group 1: Aging
        birth_date=f"{2026 - age}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
        peak_age=peak_age,
        # Group 6: Physical Identity
        height_cm=phys["height_cm"],
        weight_kg=phys["weight_kg"],
        body_type=phys["body_type"],
    )
    update_career_phase(wrestler)

    stats = WrestlerStatsDB(**stats_raw)

    return wrestler, stats


# ---------------------------------------------------------------------------
# World creation
# ---------------------------------------------------------------------------


def create_world(
    db: Session,
    name: str,
    description: str = None,
    is_multiplayer: bool = False,
    max_players: int = 1,
    world_config: dict = None,
) -> WorldDB:
    """Create a new game world with NPC federations and wrestlers."""
    world = WorldDB(
        name=name,
        description=description,
        is_multiplayer=is_multiplayer,
        max_players=max_players,
        world_config=world_config or {},
    )
    db.add(world)
    db.flush()  # Get world.id

    # Initialize world state
    for key, value in [
        ("economy_health", 75),
        ("industry_popularity", 60),
        ("total_fans", 1000000),
        ("tv_market_value", 50000),
    ]:
        db.add(WorldStateDB(world_id=world.id, key=key, value=value))

    # Create NPC federations
    num_feds = random.randint(3, 5)
    fed_choices = random.sample(FEDERATION_NAMES, min(num_feds, len(FEDERATION_NAMES)))
    federations = []

    for fed_name, short_name in fed_choices:
        fed = GameFederationDB(
            world_id=world.id,
            name=fed_name,
            short_name=short_name,
            description=f"A {random.choice(STYLES).lower()} promotion based in the {random.choice(REGIONS)}.",
            is_npc=True,
            prestige=random.randint(30, 80),
            budget=random.uniform(50000, 500000),
            home_region=random.choice(REGIONS),
            style=random.choice(STYLES),
            ai_personality={
                "booking_style": random.choice(
                    ["workrate", "entertainment", "hardcore", "storyline"]
                ),
                "risk_tolerance": random.randint(20, 80),
                "talent_priority": random.choice(["homegrown", "free_agents", "mixed"]),
            },
        )
        db.add(fed)
        db.flush()
        federations.append(fed)

        # Create a championship per federation
        db.add(
            ChampionshipDB(
                world_id=world.id,
                federation_id=fed.id,
                name=f"{short_name} World Championship",
                prestige=fed.prestige,
            )
        )

    # Generate NPC wrestlers and assign to federations
    num_wrestlers = random.randint(30, 50)
    free_agents = []
    for _ in range(num_wrestlers):
        wrestler, stats = _generate_npc_wrestler(world.id)
        db.add(wrestler)
        db.flush()
        stats.wrestler_id = wrestler.id
        db.add(stats)

        # 80% chance of being signed to a federation
        if random.random() < 0.8 and federations:
            fed = random.choice(federations)
            # Contract length: 26-78 weeks (6-18 months)
            contract_weeks = random.randint(26, 78)
            start = datetime.strptime(world.current_game_date, "%Y-%m-%d")
            end_date = (start + timedelta(weeks=contract_weeks)).strftime("%Y-%m-%d")
            db.add(
                ContractDB(
                    world_id=world.id,
                    wrestler_id=wrestler.id,
                    federation_id=fed.id,
                    status="active",
                    salary_weekly=random.uniform(500, 10000),
                    start_date=world.current_game_date,
                    end_date=end_date,
                    is_exclusive=random.random() < 0.7,
                )
            )
        else:
            free_agents.append(wrestler)

    # Create structured goal records for each wrestler (Group 2)
    from game_service.wrestler_lifecycle_service import create_wrestler_goals

    all_wrestlers = (
        db.query(GameWrestlerDB)
        .filter(
            GameWrestlerDB.world_id == world.id,
        )
        .all()
    )
    for w in all_wrestlers:
        create_wrestler_goals(db, w, world.current_game_date)

    # Generate booking visions and PPV calendars for each federation
    from game_service.booking_vision_service import generate_federation_vision
    from game_service.ppv_calendar_service import generate_ppv_calendar

    db.flush()  # Ensure all contracts are persisted

    for fed in federations:
        # Get the fed's roster
        fed_contracts = (
            db.query(ContractDB)
            .filter(
                ContractDB.federation_id == fed.id,
                ContractDB.status == "active",
            )
            .all()
        )
        fed_roster = []
        for c in fed_contracts:
            w = (
                db.query(GameWrestlerDB)
                .filter(GameWrestlerDB.id == c.wrestler_id)
                .first()
            )
            if w:
                fed_roster.append(w)

        if fed_roster:
            # Generate booking vision (push tiers, title pipeline, planned feuds)
            generate_federation_vision(db, fed, fed_roster)
            # Generate PPV calendar for the year
            generate_ppv_calendar(db, fed, world.current_game_date)

    db.commit()
    db.refresh(world)
    logger.info(
        f"Created world '{name}' with {len(federations)} federations and {num_wrestlers} wrestlers"
    )
    return world


# ---------------------------------------------------------------------------
# Player management
# ---------------------------------------------------------------------------


def create_player(
    db: Session, user_id: str, world_id: str, player_type: str, **kwargs
) -> PlayerDB:
    """Create a player in a world (promoter or wrestler)."""
    world = db.query(WorldDB).filter(WorldDB.id == world_id).first()
    if not world:
        raise ValueError("World not found")

    # Check player limit
    existing_count = (
        db.query(PlayerDB)
        .filter(PlayerDB.world_id == world_id, PlayerDB.is_active == True)
        .count()
    )
    if existing_count >= world.max_players:
        raise ValueError("World is full")

    # Check user doesn't already have a player in this world
    existing = (
        db.query(PlayerDB)
        .filter(PlayerDB.user_id == user_id, PlayerDB.world_id == world_id)
        .first()
    )
    if existing:
        raise ValueError("You already have a character in this world")

    player = PlayerDB(
        user_id=user_id,
        world_id=world_id,
        player_type=player_type,
    )

    if player_type == "promoter":
        fed = _create_player_federation(db, world_id, kwargs)
        player.federation_id = fed.id
    elif player_type == "wrestler":
        wrestler = _create_player_wrestler(db, world_id, kwargs)
        player.wrestler_id = wrestler.id
    else:
        raise ValueError(f"Invalid player type: {player_type}")

    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def _create_player_federation(
    db: Session, world_id: str, kwargs: dict
) -> GameFederationDB:
    """Create a player-owned federation."""
    name = kwargs.get("federation_name", "My Wrestling Federation")
    fed = GameFederationDB(
        world_id=world_id,
        name=name,
        short_name=kwargs.get("federation_short_name", name[:3].upper()),
        description=kwargs.get(
            "federation_description", "A new independent promotion."
        ),
        is_npc=False,
        prestige=20,  # Start small
        budget=50000.0,
        home_region=kwargs.get("home_region", "Northeast"),
        style=kwargs.get("style", "Sports Entertainment"),
    )
    db.add(fed)
    db.flush()

    # Create a starting championship
    db.add(
        ChampionshipDB(
            world_id=world_id,
            federation_id=fed.id,
            name=f"{fed.short_name} Championship",
            prestige=20,
        )
    )

    return fed


def _create_player_wrestler(db: Session, world_id: str, kwargs: dict) -> GameWrestlerDB:
    """Create a player-controlled wrestler."""
    name = kwargs.get("wrestler_name", "The Rookie")
    style = kwargs.get("wrestler_style", "allrounder")

    wrestler = GameWrestlerDB(
        world_id=world_id,
        name=name,
        is_npc=False,
        gimmick=kwargs.get(
            "wrestler_gimmick", "A hungry newcomer looking to make a name."
        ),
        alignment=kwargs.get("wrestler_alignment", "face"),
        popularity=25,  # Start low
        age=22,
        experience_years=0,
        weight_class=kwargs.get("weight_class", "heavyweight"),
        finisher_name=kwargs.get("finisher_name", "The Debut"),
        finisher_type=kwargs.get("finisher_type", "power"),
        personality_traits={
            "player_controlled": True,
            "style_preference": style,
        },
    )
    db.add(wrestler)
    db.flush()

    # Stats based on chosen style
    style_bonuses = {
        "technical": {"technical": 20, "submission": 15, "psychology": 10},
        "brawler": {"brawling": 20, "toughness": 15, "power": 10},
        "highflyer": {"aerial": 20, "speed": 15, "selling": 10},
        "powerhouse": {"power": 20, "toughness": 15, "brawling": 10},
        "allrounder": {"psychology": 10, "stamina": 10, "charisma": 10},
        "showman": {"charisma": 20, "mic_skill": 15, "psychology": 10},
    }
    bonuses = style_bonuses.get(style, {})

    stats = WrestlerStatsDB(
        wrestler_id=wrestler.id,
        power=40 + bonuses.get("power", 0),
        speed=45 + bonuses.get("speed", 0),
        technical=35 + bonuses.get("technical", 0),
        aerial=35 + bonuses.get("aerial", 0),
        brawling=35 + bonuses.get("brawling", 0),
        submission=30 + bonuses.get("submission", 0),
        stamina=45 + bonuses.get("stamina", 0),
        toughness=40 + bonuses.get("toughness", 0),
        charisma=40 + bonuses.get("charisma", 0),
        mic_skill=35 + bonuses.get("mic_skill", 0),
        psychology=30 + bonuses.get("psychology", 0),
        selling=35 + bonuses.get("selling", 0),
        backstage_politics=20,
        loyalty=70,
        work_ethic=75,
        injury_prone=25,
    )
    db.add(stats)

    return wrestler


# ---------------------------------------------------------------------------
# World queries
# ---------------------------------------------------------------------------


def get_world(db: Session, world_id: str) -> WorldDB:
    """Get a world by ID."""
    world = db.query(WorldDB).filter(WorldDB.id == world_id).first()
    if not world:
        raise ValueError("World not found")
    return world


def get_player(db: Session, player_id: str) -> PlayerDB:
    """Get a player by ID."""
    player = db.query(PlayerDB).filter(PlayerDB.id == player_id).first()
    if not player:
        raise ValueError("Player not found")
    return player


def get_player_for_user(db: Session, user_id: str, world_id: str) -> PlayerDB:
    """Get a user's player in a specific world."""
    player = (
        db.query(PlayerDB)
        .filter(PlayerDB.user_id == user_id, PlayerDB.world_id == world_id)
        .first()
    )
    if not player:
        raise ValueError("No player found in this world")
    return player


def get_federation(db: Session, federation_id: str) -> GameFederationDB:
    """Get a federation by ID."""
    fed = (
        db.query(GameFederationDB).filter(GameFederationDB.id == federation_id).first()
    )
    if not fed:
        raise ValueError("Federation not found")
    return fed


def get_roster(db: Session, federation_id: str) -> list:
    """Get all wrestlers contracted to a federation."""
    contracts = (
        db.query(ContractDB)
        .filter(
            ContractDB.federation_id == federation_id,
            ContractDB.status == "active",
        )
        .all()
    )
    wrestler_ids = [c.wrestler_id for c in contracts]
    if not wrestler_ids:
        return []
    return db.query(GameWrestlerDB).filter(GameWrestlerDB.id.in_(wrestler_ids)).all()


def get_free_agents(db: Session, world_id: str) -> list:
    """Get wrestlers not under any active contract."""
    contracted_ids = (
        db.query(ContractDB.wrestler_id)
        .filter(ContractDB.status == "active")
        .scalar_subquery()
    )
    return (
        db.query(GameWrestlerDB)
        .filter(
            GameWrestlerDB.world_id == world_id,
            GameWrestlerDB.is_active == True,
            ~GameWrestlerDB.id.in_(contracted_ids),
        )
        .all()
    )


def get_world_federations(db: Session, world_id: str) -> list:
    """Get all federations in a world."""
    return (
        db.query(GameFederationDB)
        .filter(
            GameFederationDB.world_id == world_id,
            GameFederationDB.is_active == True,
        )
        .all()
    )


def get_world_wrestlers(db: Session, world_id: str, limit: int = 100) -> list:
    """Get wrestlers in a world."""
    return (
        db.query(GameWrestlerDB)
        .filter(
            GameWrestlerDB.world_id == world_id,
            GameWrestlerDB.is_active == True,
        )
        .limit(limit)
        .all()
    )


def get_wrestler_with_stats(db: Session, wrestler_id: str) -> tuple:
    """Get a wrestler with their stats."""
    wrestler = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wrestler_id).first()
    if not wrestler:
        raise ValueError("Wrestler not found")
    stats = (
        db.query(WrestlerStatsDB)
        .filter(WrestlerStatsDB.wrestler_id == wrestler_id)
        .first()
    )
    return wrestler, stats
