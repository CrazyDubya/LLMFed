"""
Manager/valet service — creation, bonding, promos, and match interference.

Managers are dedicated non-competitor characters (though they CAN bump).
They provide charisma/heat bonuses to clients, cut promos on their behalf,
and create interference opportunities during matches.  Every great era in
wrestling was defined by its managers: Heenan, Heyman, Cornette, Blassie.
"""

import random
import logging
from sqlalchemy.orm import Session

from models.game_models import (
    ManagerDB, ManagerClientDB, GameWrestlerDB, GameNarrativeLogDB,
    StorylineDB, StorylineParticipantDB,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Manager archetype promo templates
# ---------------------------------------------------------------------------

MANAGER_PROMO_TEMPLATES = {
    "scheming_manager": {
        "openers": [
            "Now, now, settle down. My client doesn't need to waste his time on any of you.",
            "I've arranged a little... surprise for tonight.",
            "*adjusts glasses* Let me explain something to you simple people.",
            "My client and I have been discussing strategy, and we've come to a decision.",
        ],
        "body": [
            "You see, {client} is not just any competitor. {client} is MY competitor. And that means {client} is untouchable.",
            "Every move, every match, every championship — it's all part of MY plan.",
            "While you fools cheer for your heroes, {client} is three steps ahead.",
            "Nobody outsmarts me. And by extension, nobody outsmarts {client}.",
        ],
        "closers": [
            "And that, ladies and gentlemen, is simply... good business.",
            "Mark my words — {client} WILL be champion. I guarantee it.",
            "*smirks* You've been warned.",
            "Don't say I didn't tell you so.",
        ],
    },
    "corporate_suit": {
        "openers": [
            "Let me be perfectly clear about the current situation.",
            "On behalf of my client, I have a formal statement to make.",
            "The numbers don't lie, and neither do I.",
            "I've reviewed the contracts, the analytics, and the data.",
        ],
        "body": [
            "{client} is the most valuable asset in this entire company, and it's not even close.",
            "From a business perspective, {client} represents the future of this industry.",
            "Every metric — merchandise, ratings, social media — {client} is number one.",
            "The board has reviewed {client}'s performance and the results speak for themselves.",
        ],
        "closers": [
            "This is non-negotiable. {client} gets what {client} deserves.",
            "The contract is ironclad. Deal with it.",
            "We'll see you in court — or in the ring. Your choice.",
            "Thank you. No further questions.",
        ],
    },
    "flamboyant_mouthpiece": {
        "openers": [
            "Ladies and gentlemen! Boys and girls! Feast your EYES!",
            "OH WHAT A NIGHT this is going to be!",
            "Allow me to introduce the GREATEST competitor on God's green earth!",
            "You want to talk about star power? About CHARISMA? About DESTINY?",
        ],
        "body": [
            "{client} is not just a wrestler — {client} is a PHENOMENON!",
            "There is NOBODY — and I mean NOBODY — who can stand in the same ring as {client}!",
            "When {client} walks into the arena, the ground SHAKES and the heavens PART!",
            "You people should be THANKING {client} for even showing up tonight!",
        ],
        "closers": [
            "And THAT is the gospel according to ME!",
            "Can I get an AMEN?!",
            "Remember this night, people — you witnessed GREATNESS!",
            "*drops mic, poses dramatically*",
        ],
    },
    "enforcer_type": {
        "openers": [
            "...",
            "Listen up. I'm only gonna say this once.",
            "*cracks knuckles*",
            "You want to get to my guy? You go through me first.",
        ],
        "body": [
            "Nobody touches {client}. Period.",
            "Last guy who tried something funny with {client}? He's still in rehab.",
            "{client} focuses on winning. I focus on making sure nobody gets in the way.",
            "I don't do speeches. I do damage.",
        ],
        "closers": [
            "We're done talking.",
            "*stares down the competition*",
            "Try something. I dare you.",
            "Consider this your only warning.",
        ],
    },
    "old_school": {
        "openers": [
            "I've been in this business for 30 years, and let me tell you something.",
            "Back in my day, we respected the business. And {client} respects the business.",
            "I've managed champions in every territory from New York to Tokyo.",
            "When I saw {client} for the first time, I knew — I KNEW — this was special.",
        ],
        "body": [
            "I've seen 'em come and go. The flash in the pans. The one-hit wonders. {client} is the real deal.",
            "{client} reminds me of the greats — the absolute greats of this industry.",
            "I've trained {client} in the lost art of professional wrestling. The REAL professional wrestling.",
            "Every generation produces one transcendent talent. This generation? It's {client}.",
        ],
        "closers": [
            "Take it from an old man who knows — {client} is going straight to the top.",
            "And that's not just my opinion. That's 30 years of experience talking.",
            "When they write the history books, {client} will have a whole chapter.",
            "*tips hat* Class dismissed.",
        ],
    },
}


# ---------------------------------------------------------------------------
# CRUD — Create / Read / Bond / Unbond
# ---------------------------------------------------------------------------

def create_manager(
    db: Session,
    world_id: str,
    name: str,
    alignment: str = "heel",
    archetype: str = "scheming_manager",
    federation_id: str = None,
    real_name: str = None,
    gender: str = "male",
    personality_traits: list = None,
    catchphrase: str = None,
) -> ManagerDB:
    """Create a new manager character."""
    manager = ManagerDB(
        world_id=world_id,
        federation_id=federation_id,
        name=name,
        real_name=real_name,
        gender=gender,
        alignment=alignment,
        archetype=archetype,
        personality_traits=personality_traits or [],
        catchphrase=catchphrase,
        charisma=random.randint(50, 85),
        mic_skill=random.randint(50, 85),
        cunning=random.randint(40, 75),
        interference_skill=random.randint(30, 70),
    )
    db.add(manager)
    db.commit()
    logger.info("Manager '%s' (%s) created in world %s", name, archetype, world_id)
    return manager


def assign_manager(
    db: Session,
    world_id: str,
    manager_id: str,
    client_wrestler_id: str,
    role: str = "manager",
    specialization: str = "all_around",
    game_date: str = None,
) -> ManagerClientDB:
    """Create a persistent manager-to-client bond."""
    manager = db.query(ManagerDB).filter_by(id=manager_id).first()
    wrestler = db.query(GameWrestlerDB).filter_by(id=client_wrestler_id).first()

    # Calculate initial bonuses based on manager stats and specialization
    charisma_bonus, heat_bonus = _calculate_bonuses(manager, specialization)

    bond = ManagerClientDB(
        world_id=world_id,
        manager_id=manager_id,
        client_wrestler_id=client_wrestler_id,
        role=role,
        specialization=specialization,
        effectiveness=50,
        charisma_bonus=charisma_bonus,
        heat_bonus=heat_bonus,
        contract_started=game_date,
    )
    db.add(bond)

    if manager and wrestler:
        db.add(GameNarrativeLogDB(
            world_id=world_id,
            game_date=game_date or "",
            tick=0,
            event_type="manager_assigned",
            description=f"{manager.name} has been announced as the new {role} for {wrestler.name}!",
            importance=6,
        ))

    db.commit()
    logger.info("Manager '%s' assigned to wrestler '%s'",
                manager.name if manager else manager_id,
                wrestler.name if wrestler else client_wrestler_id)
    return bond


def remove_manager(
    db: Session,
    bond_id: str,
    game_date: str = None,
    was_fired: bool = False,
) -> bool:
    """End a manager-client relationship."""
    bond = db.query(ManagerClientDB).filter_by(id=bond_id, is_active=True).first()
    if not bond:
        return False

    bond.is_active = False
    bond.contract_ended = game_date

    manager = db.query(ManagerDB).filter_by(id=bond.manager_id).first()
    wrestler = db.query(GameWrestlerDB).filter_by(id=bond.client_wrestler_id).first()
    if manager and wrestler:
        verb = "has been fired by" if was_fired else "has parted ways with"
        db.add(GameNarrativeLogDB(
            world_id=bond.world_id,
            game_date=game_date or "",
            tick=0,
            event_type="manager_removed",
            description=f"{manager.name} {verb} {wrestler.name}!",
            importance=6,
        ))

    db.commit()
    return True


def get_manager_clients(db: Session, manager_id: str) -> list:
    """Get all active clients for a manager."""
    bonds = db.query(ManagerClientDB).filter_by(
        manager_id=manager_id, is_active=True
    ).all()
    result = []
    for bond in bonds:
        wrestler = db.query(GameWrestlerDB).filter_by(id=bond.client_wrestler_id).first()
        result.append({
            "bond": bond,
            "client_name": wrestler.name if wrestler else "Unknown",
        })
    return result


def get_wrestler_manager(db: Session, wrestler_id: str) -> dict:
    """Get the active manager for a wrestler, if any."""
    bond = db.query(ManagerClientDB).filter_by(
        client_wrestler_id=wrestler_id, is_active=True
    ).first()
    if not bond:
        return {}
    manager = db.query(ManagerDB).filter_by(id=bond.manager_id).first()
    return {
        "bond": bond,
        "manager": manager,
        "manager_name": manager.name if manager else "Unknown",
    }


def list_managers(db: Session, world_id: str, federation_id: str = None, active_only: bool = True) -> list:
    """List all managers in a world."""
    q = db.query(ManagerDB).filter_by(world_id=world_id)
    if federation_id:
        q = q.filter_by(federation_id=federation_id)
    if active_only:
        q = q.filter_by(is_active=True)
    return q.all()


def list_manager_bonds(db: Session, world_id: str, active_only: bool = True) -> list:
    """List all manager-client bonds in a world with names."""
    q = db.query(ManagerClientDB).filter_by(world_id=world_id)
    if active_only:
        q = q.filter_by(is_active=True)
    bonds = q.all()
    result = []
    for bond in bonds:
        manager = db.query(ManagerDB).filter_by(id=bond.manager_id).first()
        wrestler = db.query(GameWrestlerDB).filter_by(id=bond.client_wrestler_id).first()
        result.append({
            "bond": bond,
            "manager_name": manager.name if manager else "Unknown",
            "client_name": wrestler.name if wrestler else "Unknown",
        })
    return result


# ---------------------------------------------------------------------------
# Manager promos — the heart of what a manager does
# ---------------------------------------------------------------------------

def generate_manager_promo(
    db: Session,
    manager_id: str,
    client_wrestler_id: str,
    target_wrestler_id: str = None,
    promo_type: str = "in_ring",
) -> dict:
    """Generate a promo where the manager speaks on behalf of their client.

    Uses the manager's archetype to shape voice and content.
    """
    manager = db.query(ManagerDB).filter_by(id=manager_id).first()
    client = db.query(GameWrestlerDB).filter_by(id=client_wrestler_id).first()
    target = db.query(GameWrestlerDB).filter_by(id=target_wrestler_id).first() if target_wrestler_id else None

    if not manager or not client:
        return {"content": "", "quality": 0, "heat": 0}

    archetype = manager.archetype
    templates = MANAGER_PROMO_TEMPLATES.get(archetype, MANAGER_PROMO_TEMPLATES["scheming_manager"])

    # Build the promo
    opener = random.choice(templates["openers"]).replace("{client}", client.name)
    body = random.choice(templates["body"]).replace("{client}", client.name)
    closer = random.choice(templates["closers"]).replace("{client}", client.name)

    # Add target reference if applicable
    target_line = ""
    if target:
        target_lines = [
            f"And as for {target.name}? {target.name} is nothing but a stepping stone on {client.name}'s path to glory.",
            f"{target.name} should be watching their back. My client has {target.name} in their sights.",
            f"Let me address {target.name} directly — you are out of your league.",
            f"{target.name}, if you're smart, you'll stay out of {client.name}'s way.",
        ]
        target_line = " " + random.choice(target_lines)

    content = f"{opener} {body}{target_line} {closer}"

    # Quality based on manager stats
    quality = (manager.mic_skill * 0.5 + manager.charisma * 0.3 + manager.cunning * 0.2) / 100.0
    quality = min(1.0, quality * random.uniform(0.8, 1.2))
    quality_rating = round(quality * 5, 1)  # 0-5 star rating

    # Heat generation
    heat = int(manager.charisma * 0.4 + manager.mic_skill * 0.3 + random.randint(5, 20))
    heat = min(100, heat)

    return {
        "content": content,
        "manager_name": manager.name,
        "client_name": client.name,
        "target_name": target.name if target else None,
        "promo_type": promo_type,
        "quality_rating": quality_rating,
        "heat_generated": heat,
        "archetype": archetype,
    }


# ---------------------------------------------------------------------------
# Match interference — managers affect match outcomes
# ---------------------------------------------------------------------------

def calculate_interference_chance(db: Session, manager_id: str) -> float:
    """Calculate the probability that a manager will successfully interfere
    in a match.  Returns 0.0 - 1.0."""
    manager = db.query(ManagerDB).filter_by(id=manager_id).first()
    if not manager:
        return 0.0

    # Base chance from interference_skill
    base = manager.interference_skill / 100.0
    # Cunning adds a bonus
    cunning_bonus = manager.cunning / 200.0
    # Random factor
    chance = base * 0.6 + cunning_bonus * 0.3 + random.uniform(0, 0.1)
    return min(0.8, max(0.05, chance))  # Cap at 80%, floor at 5%


def attempt_interference(
    db: Session,
    manager_id: str,
    match_id: str = None,
    game_date: str = None,
) -> dict:
    """Attempt manager interference in a match.  Returns whether it succeeded
    and a narrative description."""
    manager = db.query(ManagerDB).filter_by(id=manager_id).first()
    if not manager:
        return {"success": False, "description": ""}

    chance = calculate_interference_chance(db, manager_id)
    success = random.random() < chance

    if success:
        interference_types = [
            f"{manager.name} distracts the referee with an argument!",
            f"{manager.name} slides a foreign object into the ring!",
            f"{manager.name} grabs the opponent's ankle from outside the ring!",
            f"{manager.name} causes a distraction on the apron!",
            f"{manager.name} throws a towel over the referee's head!",
        ]
        caught_descriptions = [
            f"The referee catches {manager.name} in the act!",
            f"{manager.name}'s interference backfires!",
        ]
        # Small chance of getting caught even on "success"
        if random.random() < 0.15:
            description = random.choice(caught_descriptions)
            return {"success": False, "description": description, "caught": True}
        description = random.choice(interference_types)
    else:
        fail_descriptions = [
            f"{manager.name} tries to interfere but the referee is watching!",
            f"{manager.name}'s distraction attempt fails miserably!",
            f"The referee ejects {manager.name} from ringside!",
        ]
        description = random.choice(fail_descriptions)

    return {"success": success, "description": description, "caught": not success}


# ---------------------------------------------------------------------------
# Bonus calculation
# ---------------------------------------------------------------------------

def calculate_manager_bonus(db: Session, wrestler_id: str) -> dict:
    """Calculate the total manager bonuses for a wrestler."""
    bond = db.query(ManagerClientDB).filter_by(
        client_wrestler_id=wrestler_id, is_active=True
    ).first()
    if not bond:
        return {"charisma_bonus": 0, "heat_bonus": 0, "has_manager": False}

    return {
        "charisma_bonus": bond.charisma_bonus,
        "heat_bonus": bond.heat_bonus,
        "has_manager": True,
        "manager_id": bond.manager_id,
        "specialization": bond.specialization,
    }


def _calculate_bonuses(manager: ManagerDB, specialization: str) -> tuple:
    """Calculate charisma and heat bonuses based on manager stats and specialization."""
    if not manager:
        return (5, 5)

    base_charisma = int(manager.charisma / 10)  # 0-10 base
    base_heat = int(manager.mic_skill / 10)     # 0-10 base

    # Specialization adjustments
    if specialization == "promo_boost":
        base_charisma = min(20, base_charisma + 5)
    elif specialization == "interference":
        base_heat = min(20, base_heat + 5)
    elif specialization == "distraction":
        base_heat = min(20, base_heat + 3)
        base_charisma = min(20, base_charisma + 2)
    elif specialization == "negotiation":
        base_charisma = min(20, base_charisma + 3)
    # all_around keeps the base values

    return (min(20, base_charisma), min(20, base_heat))
