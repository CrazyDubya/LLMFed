"""
Static data for match simulation — move pools, spot descriptions, and crowd reactions.

Separated from match_engine.py to keep the simulation logic clean.
"""

# ---------------------------------------------------------------------------
# Move databases
# ---------------------------------------------------------------------------

MOVES = {
    "power": [
        ("Powerbomb", 12, "power"), ("Suplex", 8, "power"),
        ("Bodyslam", 6, "power"), ("Clothesline", 7, "power"),
        ("Spinebuster", 10, "power"), ("Gorilla Press", 9, "power"),
        ("Big Boot", 7, "power"), ("Chokeslam", 11, "power"),
        ("Military Press Slam", 10, "power"), ("Sidewalk Slam", 7, "power"),
        ("Running Powerslam", 11, "power"), ("Samoan Drop", 8, "power"),
        ("Fallaway Slam", 9, "power"), ("Avalanche Splash", 10, "power"),
        ("Pop-Up Powerbomb", 13, "power"), ("Deadlift Suplex", 10, "power"),
    ],
    "technical": [
        ("Arm Drag", 4, "technical"), ("Suplex Combo", 9, "technical"),
        ("German Suplex", 10, "technical"), ("Snap Mare", 3, "technical"),
        ("Dragon Screw", 7, "technical"), ("Backbreaker", 8, "technical"),
        ("Neckbreaker", 7, "technical"), ("Brainbuster", 11, "technical"),
        ("Northern Lights Suplex", 9, "technical"), ("T-Bone Suplex", 8, "technical"),
        ("Belly-to-Belly Suplex", 8, "technical"), ("Fisherman Suplex", 9, "technical"),
        ("Tiger Suplex", 10, "technical"), ("Rolling Elbow", 7, "technical"),
        ("Cobra Clutch Slam", 9, "technical"), ("Bridging German", 11, "technical"),
    ],
    "aerial": [
        ("Dropkick", 6, "aerial"), ("Moonsault", 11, "aerial"),
        ("Diving Crossbody", 9, "aerial"), ("Hurricanrana", 8, "aerial"),
        ("450 Splash", 12, "aerial"), ("Springboard Elbow", 8, "aerial"),
        ("Frog Splash", 10, "aerial"), ("Shooting Star Press", 13, "aerial"),
        ("Corkscrew Plancha", 10, "aerial"), ("Springboard Cutter", 11, "aerial"),
        ("Tope Con Hilo", 9, "aerial"), ("Phoenix Splash", 14, "aerial"),
        ("Sasuke Special", 10, "aerial"), ("Spanish Fly", 12, "aerial"),
        ("Diving Elbow Drop", 9, "aerial"), ("Asai Moonsault", 11, "aerial"),
    ],
    "brawling": [
        ("Right Hand", 4, "brawling"), ("Uppercut", 5, "brawling"),
        ("Knee Strike", 7, "brawling"), ("Elbow Smash", 6, "brawling"),
        ("Headbutt", 5, "brawling"), ("Lariat", 9, "brawling"),
        ("Running Knee", 10, "brawling"), ("Discus Punch", 8, "brawling"),
        ("Throat Thrust", 5, "brawling"), ("Spinning Backfist", 8, "brawling"),
        ("Knife-Edge Chop", 4, "brawling"), ("Avalanche Corner Splash", 8, "brawling"),
        ("European Uppercut", 6, "brawling"), ("Rebound Lariat", 10, "brawling"),
        ("Enzuigiri", 7, "brawling"), ("Discus Elbow", 9, "brawling"),
    ],
    "submission": [
        ("Armbar", 6, "submission"), ("Figure Four", 8, "submission"),
        ("Sharpshooter", 9, "submission"), ("Crossface", 8, "submission"),
        ("Sleeper Hold", 5, "submission"), ("Ankle Lock", 9, "submission"),
        ("Kimura", 7, "submission"), ("Triangle Choke", 8, "submission"),
        ("Boston Crab", 7, "submission"), ("STF", 8, "submission"),
        ("Koji Clutch", 7, "submission"), ("Dragon Sleeper", 9, "submission"),
        ("Rings of Saturn", 8, "submission"), ("Octopus Hold", 7, "submission"),
        ("Cattle Mutilation", 9, "submission"), ("Rear Naked Choke", 8, "submission"),
    ],
}

# ---------------------------------------------------------------------------
# Signature move pools by archetype — used when populating wrestlers
# ---------------------------------------------------------------------------

SIGNATURE_MOVE_POOLS = {
    "monster_heel": [
        ("Tombstone Piledriver", 14, "power"), ("Running Big Boot", 9, "power"),
        ("Release German Suplex", 10, "power"), ("Torture Rack", 10, "submission"),
        ("Snake Eyes", 7, "brawling"), ("Tree of Woe Stomp", 8, "brawling"),
    ],
    "underdog_face": [
        ("Sling Blade", 8, "technical"), ("Stunner", 12, "brawling"),
        ("Tornado DDT", 10, "aerial"), ("La Magistral Cradle", 7, "technical"),
        ("Diving Headbutt", 9, "aerial"), ("Thesz Press", 7, "brawling"),
    ],
    "cocky_technician": [
        ("Rolling Thunder", 9, "technical"), ("Regal Cutter", 10, "technical"),
        ("Perfect Plex", 10, "technical"), ("Bridging Suplex", 9, "technical"),
        ("Figure Eight", 10, "submission"), ("Standing Moonsault", 9, "aerial"),
    ],
    "silent_assassin": [
        ("Running Knee Strike", 11, "brawling"), ("Kinshasa", 12, "brawling"),
        ("Roundhouse Kick", 10, "brawling"), ("Buzzsaw Kick", 9, "brawling"),
        ("Snap DDT", 8, "technical"), ("Penalty Kick", 10, "brawling"),
    ],
    "cult_leader": [
        ("Sister Abigail", 12, "power"), ("Mandible Claw", 8, "submission"),
        ("Uranage Slam", 10, "power"), ("Running Senton", 9, "power"),
        ("Swinging Neckbreaker", 8, "technical"), ("Eye Rake Combo", 6, "brawling"),
    ],
    "comedy_act": [
        ("People's Elbow", 8, "brawling"), ("Worm", 6, "brawling"),
        ("Bionic Elbow", 7, "brawling"), ("Stink Face", 3, "brawling"),
        ("Atomic Drop", 6, "power"), ("Airplane Spin", 5, "power"),
    ],
    "anti_hero": [
        ("Stunner", 12, "brawling"), ("Pedigree", 13, "power"),
        ("Curb Stomp", 11, "brawling"), ("GTS", 12, "technical"),
        ("Package Piledriver", 13, "power"), ("V-Trigger", 10, "brawling"),
    ],
    "legacy": [
        ("Crossface Chicken Wing", 9, "submission"), ("Slingshot Suplex", 8, "technical"),
        ("Figure Four Leglock", 9, "submission"), ("Spinning Toe Hold", 7, "submission"),
        ("Flying Body Press", 9, "aerial"), ("Bionic Elbow", 7, "brawling"),
    ],
    "patriot": [
        ("Patriot Slam", 11, "power"), ("Patriot Lock", 9, "submission"),
        ("Red White and Blue Thunder Bomb", 12, "power"), ("Flying Shoulder Tackle", 8, "power"),
        ("Angle Slam", 10, "technical"), ("Running Bulldog", 7, "brawling"),
    ],
    "daredevil": [
        ("Swanton Bomb", 12, "aerial"), ("Springboard 450", 14, "aerial"),
        ("Double Rotation Moonsault", 14, "aerial"), ("Corkscrew Shooting Star", 15, "aerial"),
        ("Coast-to-Coast Dropkick", 12, "aerial"), ("Sky Twister Press", 13, "aerial"),
    ],
}

# Archetype-specific finisher pools (name, type)
ARCHETYPE_FINISHERS = {
    "monster_heel": [
        ("The Annihilation", "power"), ("Tomb of Darkness", "power"),
        ("The Extinction", "power"), ("Final Judgment", "power"),
    ],
    "underdog_face": [
        ("Heart of a Champion", "technical"), ("Against All Odds", "aerial"),
        ("The Comeback", "brawling"), ("Never Say Die", "technical"),
    ],
    "cocky_technician": [
        ("The Masterpiece", "technical"), ("Perfection", "submission"),
        ("Technical Knockout", "technical"), ("The Equation", "submission"),
    ],
    "silent_assassin": [
        ("The Kill Shot", "brawling"), ("Silent Night", "brawling"),
        ("Death Sentence", "brawling"), ("Zero Hour", "brawling"),
    ],
    "cult_leader": [
        ("The Sermon", "power"), ("Enlightenment", "submission"),
        ("The Awakening", "power"), ("Mass Hysteria", "power"),
    ],
    "comedy_act": [
        ("The Punchline", "brawling"), ("The Gag Reflex", "brawling"),
        ("Comedy of Errors", "brawling"), ("Lights Out Comedy", "power"),
    ],
    "anti_hero": [
        ("The Reckoning", "brawling"), ("One Final Beat", "power"),
        ("Bitter End", "power"), ("Anti-Establishment", "brawling"),
    ],
    "legacy": [
        ("The Dynasty", "technical"), ("Legacy Lock", "submission"),
        ("Generational Shift", "technical"), ("The Inheritance", "power"),
    ],
    "patriot": [
        ("The Patriot Act", "power"), ("Eagle's Landing", "aerial"),
        ("Freedom Strike", "brawling"), ("National Anthem", "submission"),
    ],
    "daredevil": [
        ("Terminal Velocity", "aerial"), ("The Death-Defier", "aerial"),
        ("Point of No Return", "aerial"), ("Leap of Faith", "aerial"),
    ],
}

# ---------------------------------------------------------------------------
# Match-type-specific spot pools
# ---------------------------------------------------------------------------

CAGE_SPOTS = [
    ("throws opponent into the cage wall", 8, "brawling"),
    ("grinds opponent's face against the steel", 6, "brawling"),
    ("catapults opponent into the cage", 9, "power"),
    ("climbs the cage and drops an elbow", 12, "aerial"),
    ("slams opponent off the cage wall", 10, "power"),
    ("attempts to escape over the top of the cage", 0, "escape"),
]

LADDER_SPOTS = [
    ("drives opponent through a ladder", 12, "power"),
    ("suplexes opponent onto a ladder", 11, "technical"),
    ("pushes opponent off the ladder", 13, "aerial"),
    ("sunset flip powerbomb off the ladder", 15, "power"),
    ("climbs the ladder and reaches for the prize", 0, "climb"),
    ("tips the ladder over with opponent on it", 14, "power"),
]

TABLE_SPOTS = [
    ("sets up a table at ringside", 0, "setup"),
    ("powerbombs opponent through the table", 16, "power"),
    ("superplexes opponent through a table", 18, "power"),
    ("spears opponent through a table", 15, "brawling"),
    ("elbow drops opponent through a table from the top", 17, "aerial"),
]

HELL_IN_A_CELL_SPOTS = [
    ("throws opponent into the cell wall", 9, "brawling"),
    ("slams opponent onto the steel steps", 10, "power"),
    ("climbs the outside of the cell", 0, "climb"),
    ("chokeslams opponent off the cell roof", 20, "power"),
    ("drives opponent through the announce table", 14, "brawling"),
    ("uses the cell door as a weapon", 8, "brawling"),
]

IRON_MAN_FALL_DESCRIPTIONS = [
    "scores a fall with a pinfall!", "scores a fall via submission!",
    "scores a fall after a devastating finisher!",
]

# ---------------------------------------------------------------------------
# Charisma style match spots
# ---------------------------------------------------------------------------

TAUNT_SPOTS = {
    "cocky": [
        "{name} flexes over their fallen opponent!", "{name} mocks the crowd with a strut!",
        "{name} slaps the taste out of {opponent}'s mouth and laughs!",
    ],
    "intense": [
        "{name} lets out a primal scream!", "{name} no-sells the last move and hulks up!",
        "{name} stares daggers through {opponent} — pure intensity!",
    ],
    "funny": [
        "{name} does a little dance for the crowd!", "{name} pretends to answer a phone call mid-match!",
        "{name} offers a handshake — then pulls it away! Classic!",
    ],
    "mysterious": [
        "{name} sits up like something out of a horror movie!",
        "{name} points to the sky ominously...", "{name} tilts their head — unsettling...",
    ],
    "humble": [
        "{name} fires up the crowd! They're feeding off the energy!",
        "{name} slaps the mat — they're not done yet!",
        "{name} bows to the crowd before delivering the next blow!",
    ],
}

# ---------------------------------------------------------------------------
# Venue atmosphere modifiers
# ---------------------------------------------------------------------------

VENUE_ATMOSPHERE = {
    "club": {"capacity_range": (200, 1500), "rating_mod": -0.2, "crowd_energy": 0.8,
             "description": "intimate venue"},
    "arena": {"capacity_range": (2000, 10000), "rating_mod": 0.0, "crowd_energy": 1.0,
              "description": "electric arena"},
    "large_arena": {"capacity_range": (10001, 25000), "rating_mod": 0.1, "crowd_energy": 1.1,
                    "description": "massive arena"},
    "stadium": {"capacity_range": (25001, 80000), "rating_mod": 0.2, "crowd_energy": 1.2,
                "description": "roaring stadium"},
}


def get_venue_tier(capacity: int) -> str:
    """Determine venue tier from capacity."""
    if capacity <= 1500:
        return "club"
    elif capacity <= 10000:
        return "arena"
    elif capacity <= 25000:
        return "large_arena"
    return "stadium"


# ---------------------------------------------------------------------------
# Crowd and narrative descriptions
# ---------------------------------------------------------------------------

CROWD_REACTIONS = [
    "The crowd erupts!", "Huge pop from the fans!", "The audience is on their feet!",
    "Mixed reaction from the crowd.", "The fans are booing loudly!",
    "Chants break out across the arena!", "Stunned silence from the crowd.",
    "The energy in the building is electric!", "The crowd is split down the middle!",
    "THIS IS AWESOME chants ring out!", "FIGHT FOREVER! FIGHT FOREVER!",
    "The crowd is going absolutely ballistic!", "You can barely hear yourself think!",
    "Dueling chants fill the arena!", "The fans throw streamers into the ring!",
    "A hush falls over the crowd...", "The building is shaking!",
    "Standing ovation from the crowd!", "The fans are in disbelief!",
]

REVERSAL_DESCRIPTIONS = [
    "ducks and counters with", "reverses into", "blocks and hits",
    "sidesteps and delivers", "catches the leg and transitions to",
]

NEAR_FALL_DESCRIPTIONS = [
    "Goes for the cover! ONE... TWO... kickout at the last moment!",
    "Hooks the leg! ONE... TWO... shoulder up just in time!",
    "Lateral press! ONE... TWO... NO! They stay alive!",
    "Quick pin attempt! ONE... TWO... power out!",
]

INTERFERENCE_SUCCESS = [
    "{mgr} distracts the referee while {attacker} uses a low blow on {defender}!",
    "{mgr} slides a chair into the ring — {attacker} uses it behind the ref's back!",
    "{mgr} grabs {defender}'s ankle from outside! {attacker} capitalizes!",
    "{mgr} throws powder in {defender}'s eyes while the ref argues with the crowd!",
    "{mgr} pulls down the top rope — {defender} tumbles to the outside!",
]

INTERFERENCE_CAUGHT = [
    "The referee catches {mgr} red-handed! The official ejects {mgr} from ringside!",
    "{mgr} tries to interfere but the referee sees it — DISQUALIFICATION!",
    "{defender} catches {mgr} trying to cheat — and decks {mgr} on the apron!",
]

INTERFERENCE_FAIL = [
    "{mgr} tries to distract the referee but gets caught — warning issued!",
    "{mgr} attempts to pass a weapon but {defender} sees it coming!",
    "The referee is wise to {mgr}'s tricks tonight!",
]

POST_MATCH_ATTACK = [
    "{attackers} storm the ring and lay out {victim} with a vicious beatdown!",
    "After the match, {attackers} blindside {victim} from behind!",
    "The bell has rung but {attackers} aren't done — {victim} takes a post-match assault!",
]

POST_MATCH_SAVE = [
    "{savers} charge to the ring and clear out the attackers!",
    "Here comes {savers} to make the save! The crowd goes wild!",
]

TAG_DESCRIPTIONS = [
    "tags in their partner",
    "reaches out and makes the tag",
    "dives and makes the hot tag",
    "slaps hands with their partner",
]

DOUBLE_TEAM_MOVES = [
    ("Double Suplex", 14), ("Double Clothesline", 10),
    ("Aided Powerbomb", 16), ("Tandem Neckbreaker", 12),
    ("Double Dropkick", 11), ("Combo Finisher", 18),
    ("Doomsday Device", 17), ("Magic Killer", 15),
    ("3D (Dudley Death Drop)", 16), ("Poetry in Motion", 13),
    ("Total Elimination", 15), ("Shatter Machine", 16),
    ("Hart Attack", 14), ("Rocket Launcher", 13),
]
