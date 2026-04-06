"""
Stable (faction) service — creation, membership, and the internal drama engine.

Stables are where wrestling's richest storylines live.  The internal politics
system tracks loyalty, influence, and cohesion.  When tensions rise, the
engine auto-seeds betrayal and power-struggle storylines — the same dynamics
that made the nWo, Evolution, and The Bloodline must-watch TV.
"""

import random
import logging
from sqlalchemy.orm import Session

from models.game_models import (
    StableDB, StableMemberDB, GameWrestlerDB, GameNarrativeLogDB,
    StorylineDB, StorylineParticipantDB, ManagerDB,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRUD — Create / Read / Update / Dissolve
# ---------------------------------------------------------------------------

def create_stable(
    db: Session,
    world_id: str,
    federation_id: str,
    name: str,
    leader_id: str,
    founding_member_ids: list,
    alignment: str = "heel",
    short_name: str = None,
    catchphrase: str = None,
    group_finisher_name: str = None,
    manager_id: str = None,
    game_date: str = None,
) -> StableDB:
    """Form a new stable with founding members."""
    stable = StableDB(
        world_id=world_id,
        federation_id=federation_id,
        name=name,
        short_name=short_name,
        alignment=alignment,
        catchphrase=catchphrase,
        group_finisher_name=group_finisher_name,
        manager_id=manager_id,
        formed_date=game_date,
        heat=30,
        prestige=20,
        cohesion=80,
    )
    db.add(stable)
    db.flush()  # Get the stable.id

    # Add founding members
    all_member_ids = set(founding_member_ids) | {leader_id}
    for wid in all_member_ids:
        role = "leader" if wid == leader_id else "member"
        loyalty = 85 if wid == leader_id else 70
        influence = 80 if wid == leader_id else 30
        member = StableMemberDB(
            stable_id=stable.id,
            wrestler_id=wid,
            role=role,
            loyalty=loyalty,
            influence=influence,
            joined_date=game_date,
        )
        db.add(member)

    # Narrative log
    wrestler_names = _get_wrestler_names(db, list(all_member_ids))
    leader_name = wrestler_names.get(leader_id, "Unknown")
    db.add(GameNarrativeLogDB(
        world_id=world_id,
        game_date=game_date or "",
        tick=0,
        event_type="stable_formed",
        description=f"{name} has formed! Led by {leader_name}, the group includes {', '.join(wrestler_names.values())}.",
        importance=8,
    ))

    db.commit()
    logger.info("Stable '%s' formed with %d members in world %s", name, len(all_member_ids), world_id)
    return stable


def add_member(
    db: Session,
    stable_id: str,
    wrestler_id: str,
    role: str = "recruit",
    game_date: str = None,
) -> StableMemberDB:
    """Add a wrestler to an existing stable.  New members start as recruits
    with modest loyalty — they need to prove themselves."""
    member = StableMemberDB(
        stable_id=stable_id,
        wrestler_id=wrestler_id,
        role=role,
        loyalty=50 if role == "recruit" else 65,
        influence=15 if role == "recruit" else 30,
        joined_date=game_date,
    )
    db.add(member)

    stable = db.query(StableDB).filter_by(id=stable_id).first()
    if stable:
        wrestler = db.query(GameWrestlerDB).filter_by(id=wrestler_id).first()
        w_name = wrestler.name if wrestler else "Unknown"
        db.add(GameNarrativeLogDB(
            world_id=stable.world_id,
            game_date=game_date or "",
            tick=0,
            event_type="stable_member_added",
            description=f"{w_name} has joined {stable.name} as a {role}!",
            importance=6,
        ))

    db.commit()
    return member


def remove_member(
    db: Session,
    stable_id: str,
    wrestler_id: str,
    game_date: str = None,
    was_expelled: bool = False,
) -> bool:
    """Remove a wrestler from a stable.  If the leader is removed, the
    highest-influence remaining member becomes the new leader."""
    member = db.query(StableMemberDB).filter_by(
        stable_id=stable_id, wrestler_id=wrestler_id, is_active=True
    ).first()
    if not member:
        return False

    was_leader = member.role == "leader"
    member.is_active = False
    member.left_date = game_date

    stable = db.query(StableDB).filter_by(id=stable_id).first()
    if stable:
        wrestler = db.query(GameWrestlerDB).filter_by(id=wrestler_id).first()
        w_name = wrestler.name if wrestler else "Unknown"
        verb = "was expelled from" if was_expelled else "has left"
        db.add(GameNarrativeLogDB(
            world_id=stable.world_id,
            game_date=game_date or "",
            tick=0,
            event_type="stable_member_removed",
            description=f"{w_name} {verb} {stable.name}!",
            importance=7,
        ))

        # If leader left, promote the highest-influence remaining member
        if was_leader:
            _auto_promote_leader(db, stable, game_date)

        # Check if the stable still has enough active members
        active_count = db.query(StableMemberDB).filter_by(
            stable_id=stable_id, is_active=True
        ).count()
        if active_count < 2:
            dissolve_stable(db, stable_id, game_date, reason="too few members")

    db.commit()
    return True


def promote_member(
    db: Session,
    stable_id: str,
    wrestler_id: str,
    new_role: str,
) -> bool:
    """Change a member's role within the stable."""
    member = db.query(StableMemberDB).filter_by(
        stable_id=stable_id, wrestler_id=wrestler_id, is_active=True
    ).first()
    if not member:
        return False

    old_role = member.role
    member.role = new_role

    # If promoting to leader, demote current leader to lieutenant
    if new_role == "leader" and old_role != "leader":
        current_leader = db.query(StableMemberDB).filter(
            StableMemberDB.stable_id == stable_id,
            StableMemberDB.role == "leader",
            StableMemberDB.is_active == True,  # noqa: E712
            StableMemberDB.wrestler_id != wrestler_id,
        ).first()
        if current_leader:
            current_leader.role = "lieutenant"
            # Demoted leader loses loyalty
            current_leader.loyalty = max(0, current_leader.loyalty - 20)

    db.commit()
    return True


def dissolve_stable(
    db: Session,
    stable_id: str,
    game_date: str = None,
    reason: str = "disbanded",
) -> bool:
    """Dissolve a stable — all members are released."""
    stable = db.query(StableDB).filter_by(id=stable_id, is_active=True).first()
    if not stable:
        return False

    stable.is_active = False
    stable.dissolved_date = game_date

    members = db.query(StableMemberDB).filter_by(
        stable_id=stable_id, is_active=True
    ).all()
    for m in members:
        m.is_active = False
        m.left_date = game_date

    db.add(GameNarrativeLogDB(
        world_id=stable.world_id,
        game_date=game_date or "",
        tick=0,
        event_type="stable_dissolved",
        description=f"{stable.name} has disbanded! ({reason})",
        importance=8,
    ))

    db.commit()
    logger.info("Stable '%s' dissolved: %s", stable.name, reason)
    return True


def get_stable_with_members(db: Session, stable_id: str) -> dict:
    """Fetch a stable and its active members with wrestler names."""
    stable = db.query(StableDB).filter_by(id=stable_id).first()
    if not stable:
        return {}

    members = db.query(StableMemberDB).filter_by(
        stable_id=stable_id, is_active=True
    ).all()

    wrestler_ids = [m.wrestler_id for m in members]
    wrestler_names = _get_wrestler_names(db, wrestler_ids)

    manager_name = None
    if stable.manager_id:
        mgr = db.query(ManagerDB).filter_by(id=stable.manager_id).first()
        manager_name = mgr.name if mgr else None

    return {
        "stable": stable,
        "manager_name": manager_name,
        "members": [
            {
                "wrestler_id": m.wrestler_id,
                "wrestler_name": wrestler_names.get(m.wrestler_id, "Unknown"),
                "role": m.role,
                "loyalty": m.loyalty,
                "influence": m.influence,
                "joined_date": m.joined_date,
                "is_active": m.is_active,
            }
            for m in members
        ],
    }


def list_stables(db: Session, world_id: str, federation_id: str = None, active_only: bool = True) -> list:
    """List all stables in a world, optionally filtered by federation."""
    q = db.query(StableDB).filter_by(world_id=world_id)
    if federation_id:
        q = q.filter_by(federation_id=federation_id)
    if active_only:
        q = q.filter_by(is_active=True)
    return q.all()


def get_wrestler_stable(db: Session, wrestler_id: str) -> dict:
    """Get the active stable membership for a wrestler, if any."""
    member = db.query(StableMemberDB).filter_by(
        wrestler_id=wrestler_id, is_active=True
    ).first()
    if not member:
        return {}
    stable = db.query(StableDB).filter_by(id=member.stable_id, is_active=True).first()
    if not stable:
        return {}
    return {"stable": stable, "member": member}


# ---------------------------------------------------------------------------
# Internal Drama Engine — called daily from world_ticker
# ---------------------------------------------------------------------------

def tick_stable_dynamics(db: Session, stable: StableDB, game_date: str = None):
    """Process one day of internal faction politics.

    This is the heart of the faction system — loyalty drifts, influence
    jockeys, and when things get bad enough, storylines auto-generate.
    """
    members = db.query(StableMemberDB).filter_by(
        stable_id=stable.id, is_active=True
    ).all()
    if len(members) < 2:
        return

    leader = next((m for m in members if m.role == "leader"), None)

    for member in members:
        wrestler = db.query(GameWrestlerDB).filter_by(id=member.wrestler_id).first()
        if not wrestler:
            continue

        # --- Loyalty drift ---
        # Winners gain loyalty, losers while stablemates win lose it
        if wrestler.win_streak > 0:
            member.loyalty = min(100, member.loyalty + random.randint(1, 3))
        elif wrestler.win_streak < 0 and wrestler.win_streak <= -2:
            member.loyalty = max(0, member.loyalty - random.randint(2, 5))

        # Recruits slowly gain loyalty as they prove themselves
        if member.role == "recruit" and member.loyalty >= 65:
            member.role = "member"

        # --- Influence jockeying ---
        # High-charisma wrestlers slowly gain influence
        if wrestler.popularity > 70:
            member.influence = min(100, member.influence + random.randint(0, 2))

        # Low-card members with high influence create tension
        if member.role == "member" and member.influence > 60 and leader:
            if member.influence > leader.influence - 10:
                # This member is getting too big for the stable
                member.loyalty = max(0, member.loyalty - random.randint(1, 4))

    # --- Cohesion calculation ---
    avg_loyalty = sum(m.loyalty for m in members) / len(members) if members else 80
    stable.cohesion = int(avg_loyalty)

    # --- Auto-generate storylines from tension ---
    if stable.cohesion < 40:
        _check_power_struggle(db, stable, members, game_date)
    if stable.cohesion < 20:
        _check_betrayal_seed(db, stable, members, game_date)

    db.commit()


def process_match_result_for_stables(
    db: Session,
    winner_id: str,
    loser_id: str,
    world_id: str,
    game_date: str = None,
):
    """Called after a match to update stable dynamics based on results.

    When a stable member wins, the whole faction benefits.
    When they lose — especially the leader — cracks form.
    """
    # Check if winner is in a stable
    winner_member = db.query(StableMemberDB).filter_by(
        wrestler_id=winner_id, is_active=True
    ).first()
    if winner_member:
        stable = db.query(StableDB).filter_by(id=winner_member.stable_id, is_active=True).first()
        if stable:
            stable.heat = min(100, stable.heat + 2)
            stable.prestige = min(100, stable.prestige + 1)
            # All members get a small loyalty boost
            stablemates = db.query(StableMemberDB).filter_by(
                stable_id=stable.id, is_active=True
            ).all()
            for m in stablemates:
                m.loyalty = min(100, m.loyalty + 1)

    # Check if loser is in a stable
    loser_member = db.query(StableMemberDB).filter_by(
        wrestler_id=loser_id, is_active=True
    ).first()
    if loser_member:
        stable = db.query(StableDB).filter_by(id=loser_member.stable_id, is_active=True).first()
        if stable:
            # Leader losing clean is devastating
            if loser_member.role == "leader":
                stablemates = db.query(StableMemberDB).filter_by(
                    stable_id=stable.id, is_active=True
                ).all()
                for m in stablemates:
                    if m.wrestler_id != loser_id:
                        m.loyalty = max(0, m.loyalty - random.randint(2, 5))
            else:
                loser_member.loyalty = max(0, loser_member.loyalty - 1)

    db.commit()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_wrestler_names(db: Session, wrestler_ids: list) -> dict:
    """Fetch a {wrestler_id: name} mapping."""
    if not wrestler_ids:
        return {}
    wrestlers = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id.in_(wrestler_ids)
    ).all()
    return {w.id: w.name for w in wrestlers}


def _auto_promote_leader(db: Session, stable: StableDB, game_date: str = None):
    """When the leader leaves, the highest-influence member takes over."""
    remaining = db.query(StableMemberDB).filter_by(
        stable_id=stable.id, is_active=True
    ).order_by(StableMemberDB.influence.desc()).first()
    if remaining:
        remaining.role = "leader"
        wrestler = db.query(GameWrestlerDB).filter_by(id=remaining.wrestler_id).first()
        w_name = wrestler.name if wrestler else "Unknown"
        db.add(GameNarrativeLogDB(
            world_id=stable.world_id,
            game_date=game_date or "",
            tick=0,
            event_type="stable_new_leader",
            description=f"{w_name} has taken over as leader of {stable.name}!",
            importance=7,
        ))


def _check_power_struggle(db: Session, stable: StableDB, members: list, game_date: str = None):
    """When cohesion is low, check if a power struggle storyline should fire."""
    # Don't create if one already exists for this stable
    existing = db.query(StorylineDB).filter(
        StorylineDB.world_id == stable.world_id,
        StorylineDB.federation_id == stable.federation_id,
        StorylineDB.storyline_type == "power_struggle",
        StorylineDB.status.in_(["brewing", "active"]),
        StorylineDB.name.contains(stable.name),
    ).first()
    if existing:
        return

    leader = next((m for m in members if m.role == "leader"), None)
    challenger = max(
        (m for m in members if m.role != "leader" and m.influence > 50),
        key=lambda m: m.influence,
        default=None,
    )
    if not leader or not challenger:
        return

    names = _get_wrestler_names(db, [leader.wrestler_id, challenger.wrestler_id])
    leader_name = names.get(leader.wrestler_id, "the leader")
    challenger_name = names.get(challenger.wrestler_id, "a challenger")

    storyline = StorylineDB(
        world_id=stable.world_id,
        federation_id=stable.federation_id,
        name=f"Power Struggle in {stable.name}",
        storyline_type="power_struggle",
        status="brewing",
        description=f"Tensions inside {stable.name} — {challenger_name} is challenging {leader_name} for control.",
        heat=45,
        kayfabe_level=90,
        start_date=game_date,
    )
    db.add(storyline)
    db.flush()

    for wid, role in [(leader.wrestler_id, "protagonist"), (challenger.wrestler_id, "antagonist")]:
        db.add(StorylineParticipantDB(
            storyline_id=storyline.id,
            wrestler_id=wid,
            role=role,
        ))

    db.add(GameNarrativeLogDB(
        world_id=stable.world_id,
        game_date=game_date or "",
        tick=0,
        event_type="power_struggle",
        description=f"Cracks are showing in {stable.name}! {challenger_name} appears to be eyeing leadership.",
        importance=7,
    ))
    logger.info("Power struggle storyline created in '%s'", stable.name)


def _check_betrayal_seed(db: Session, stable: StableDB, members: list, game_date: str = None):
    """When cohesion is critically low and a popular member's loyalty
    has bottomed out, auto-generate a betrayal storyline."""
    traitor = max(
        (m for m in members if m.loyalty <= 15),
        key=lambda m: m.influence,
        default=None,
    )
    if not traitor:
        return

    # Don't create duplicate betrayal storylines
    existing = db.query(StorylineDB).filter(
        StorylineDB.world_id == stable.world_id,
        StorylineDB.storyline_type == "betrayal",
        StorylineDB.status.in_(["brewing", "active"]),
        StorylineDB.name.contains(stable.name),
    ).first()
    if existing:
        return

    leader = next((m for m in members if m.role == "leader"), None)
    if not leader or leader.wrestler_id == traitor.wrestler_id:
        return

    names = _get_wrestler_names(db, [traitor.wrestler_id, leader.wrestler_id])
    traitor_name = names.get(traitor.wrestler_id, "a member")
    leader_name = names.get(leader.wrestler_id, "the leader")

    storyline = StorylineDB(
        world_id=stable.world_id,
        federation_id=stable.federation_id,
        name=f"Betrayal: {traitor_name} vs {stable.name}",
        storyline_type="betrayal",
        status="brewing",
        description=f"{traitor_name} has had enough of {leader_name}'s {stable.name}. A betrayal is imminent.",
        heat=60,
        kayfabe_level=95,
        start_date=game_date,
    )
    db.add(storyline)
    db.flush()

    db.add(StorylineParticipantDB(
        storyline_id=storyline.id,
        wrestler_id=traitor.wrestler_id,
        role="protagonist",
    ))
    db.add(StorylineParticipantDB(
        storyline_id=storyline.id,
        wrestler_id=leader.wrestler_id,
        role="antagonist",
    ))

    db.add(GameNarrativeLogDB(
        world_id=stable.world_id,
        game_date=game_date or "",
        tick=0,
        event_type="betrayal_brewing",
        description=f"Sources say {traitor_name} is planning to leave {stable.name} — and it won't be friendly.",
        importance=8,
    ))
    logger.info("Betrayal storyline seeded: %s leaving '%s'", traitor_name, stable.name)
