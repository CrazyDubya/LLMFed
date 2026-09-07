"""
News generation service — creates kayfabe and dirt sheet news from world events.

Generates headlines and articles from show results, title changes, injuries,
signings, and weekly industry roundups.
"""

import random
import logging
from sqlalchemy.orm import Session

from models.game_models import (
    WorldNewsDB,
    ShowDB,
    GameFederationDB,
    GameWrestlerDB,
    GameNarrativeLogDB,
    SocialMediaPostDB,
    LifeEventDB,
)

logger = logging.getLogger(__name__)


def generate_show_news(
    db: Session, show: ShowDB, match_ratings: list, fed: GameFederationDB = None
):
    """Generate news headlines from a completed show."""
    fed_name = (fed.short_name or fed.name) if fed else "Unknown Promotion"
    rating = show.overall_rating or 0
    attendance = show.attendance or 0

    # Main show results headline
    if rating >= 4.0:
        headline = f"{fed_name} delivers a CLASSIC with {show.name}!"
        body = (
            f"{show.name} received rave reviews with an overall rating of "
            f"{rating:.1f} stars. {attendance} fans were in attendance at {show.venue}."
        )
    elif rating >= 3.0:
        headline = f"{fed_name}'s {show.name} delivers solid action"
        body = (
            f"{show.name} was a solid night of wrestling, earning a {rating:.1f} "
            f"star rating. {attendance} fans filled {show.venue}."
        )
    else:
        headline = f"{fed_name}'s {show.name} falls flat"
        body = (
            f"{show.name} struggled to connect with the audience, earning just "
            f"{rating:.1f} stars. Only {attendance} fans attended at {show.venue}."
        )

    db.add(
        WorldNewsDB(
            world_id=show.world_id,
            headline=headline,
            body=body,
            category="show_results",
            game_date=show.game_date,
            is_kayfabe=True,
            source=f"{fed_name} Report",
        )
    )

    # Check for title changes in recent narrative events
    title_events = (
        db.query(GameNarrativeLogDB)
        .filter(
            GameNarrativeLogDB.world_id == show.world_id,
            GameNarrativeLogDB.game_date == show.game_date,
            GameNarrativeLogDB.event_type == "title_change",
        )
        .all()
    )

    for event in title_events:
        db.add(
            WorldNewsDB(
                world_id=show.world_id,
                headline=event.description,
                body=f"In a shocking development at {show.name}, {event.description.lower()}",
                category="title_change",
                game_date=show.game_date,
                is_kayfabe=True,
                source="Breaking News",
            )
        )

    # Check for heel/face turns
    turn_events = (
        db.query(GameNarrativeLogDB)
        .filter(
            GameNarrativeLogDB.world_id == show.world_id,
            GameNarrativeLogDB.game_date == show.game_date,
            GameNarrativeLogDB.event_type.in_(["heel_turn", "face_turn"]),
        )
        .all()
    )

    for event in turn_events:
        db.add(
            WorldNewsDB(
                world_id=show.world_id,
                headline=event.description,
                body=f"The wrestling world was rocked tonight: {event.description}",
                category="alignment_turn",
                game_date=show.game_date,
                is_kayfabe=True,
                source="Wrestling Insider",
            )
        )


def generate_injury_news(
    db: Session, world_id: str, wrestler: GameWrestlerDB, weeks_out: int, game_date: str
):
    """Generate news about a wrestler injury."""
    db.add(
        WorldNewsDB(
            world_id=world_id,
            headline=f"INJURY REPORT: {wrestler.name} sidelined for {weeks_out} weeks",
            body=(
                f"{wrestler.name} has been placed on the shelf after sustaining an injury. "
                f"The expected recovery timeline is approximately {weeks_out} weeks."
            ),
            category="injury",
            game_date=game_date,
            is_kayfabe=True,
            source="Medical Update",
        )
    )


def generate_signing_news(
    db: Session, world_id: str, wrestler_name: str, fed_name: str, game_date: str
):
    """Generate news about a talent signing."""
    db.add(
        WorldNewsDB(
            world_id=world_id,
            headline=f"BREAKING: {wrestler_name} signs with {fed_name}!",
            body=(
                f"In a move that sends shockwaves through the industry, {wrestler_name} "
                f"has officially signed with {fed_name}."
            ),
            category="signing",
            game_date=game_date,
            is_kayfabe=False,
            source="Wrestling Observer",
        )
    )


def generate_weekly_dirt_sheet(db: Session, world_id: str, game_date: str):
    """Generate a weekly behind-the-scenes dirt sheet report."""
    from models.game_models import GameFederationDB, ContractDB

    feds = (
        db.query(GameFederationDB)
        .filter(
            GameFederationDB.world_id == world_id,
            GameFederationDB.is_active == True,
        )
        .all()
    )

    dirt_items = []

    for fed in feds:
        fed_name = fed.short_name or fed.name

        # Financial health
        if fed.budget < 20000:
            dirt_items.append(
                f"Sources say {fed_name} is having serious financial difficulties "
                f"and may need to release talent soon."
            )
        elif fed.budget > 500000:
            dirt_items.append(
                f"{fed_name} is flush with cash and reportedly looking to "
                f"make some big signings."
            )

        # Momentum
        momentum = fed.momentum or 50
        if momentum > 75:
            dirt_items.append(
                f"{fed_name} is red hot right now. Everything they touch turns to gold."
            )
        elif momentum < 25:
            dirt_items.append(
                f"Backstage sources say morale is low at {fed_name}. "
                f"Several talents are said to be unhappy."
            )

        # Low morale wrestlers
        contracts = (
            db.query(ContractDB)
            .filter(
                ContractDB.federation_id == fed.id,
                ContractDB.status == "active",
            )
            .all()
        )
        wrestler_ids = [c.wrestler_id for c in contracts]
        unhappy = (
            db.query(GameWrestlerDB)
            .filter(
                GameWrestlerDB.id.in_(wrestler_ids),
                GameWrestlerDB.morale < 30,
                GameWrestlerDB.is_active == True,
            )
            .all()
            if wrestler_ids
            else []
        )

        if len(unhappy) >= 2:
            names = ", ".join(w.name for w in unhappy[:3])
            dirt_items.append(
                f"Multiple {fed_name} talents ({names}) are reportedly unhappy backstage."
            )

    if not dirt_items:
        dirt_items.append(
            "It's been a quiet week behind the scenes in the wrestling world."
        )

    # Pick up to 4 items for the weekly roundup
    selected = random.sample(dirt_items, min(4, len(dirt_items)))
    body = "\n\n".join(f"- {item}" for item in selected)

    db.add(
        WorldNewsDB(
            world_id=world_id,
            headline="Weekly Dirt Sheet: Behind the Curtain",
            body=body,
            category="dirt_sheet",
            game_date=game_date,
            is_kayfabe=False,
            source="Wrestling Observer Newsletter",
        )
    )


def generate_social_media_news(db: Session, world_id: str, game_date: str):
    """Generate news from viral social media posts."""
    viral_posts = (
        db.query(SocialMediaPostDB)
        .filter(
            SocialMediaPostDB.world_id == world_id,
            SocialMediaPostDB.game_date == game_date,
            SocialMediaPostDB.is_viral == True,
        )
        .all()
    )

    for post in viral_posts:
        wrestler = (
            db.query(GameWrestlerDB)
            .filter(
                GameWrestlerDB.id == post.wrestler_id,
            )
            .first()
        )
        if not wrestler:
            continue

        name = wrestler.name
        if post.post_type == "shoot":
            headline = f"VIRAL: {name}'s shoot post breaks the internet!"
            body = (
                f"{name} posted what appears to be a genuine, unscripted message "
                f"on {post.platform} that has the wrestling world buzzing. "
                f"The post has generated massive engagement and debate among fans."
            )
        elif post.post_type == "worked_shoot":
            headline = f"Is {name}'s viral post a work or a shoot? Fans debate"
            body = (
                f"A cryptic post from {name} on {post.platform} has fans "
                f"divided on whether it's a storyline tease or a genuine grievance. "
                f"The ambiguity has only fueled more discussion."
            )
        else:
            headline = f"{name}'s {post.platform} post goes viral"
            body = (
                f"{name} is trending after a {post.platform} post caught fire. "
                f"Fan reaction has been {post.fan_reaction}."
            )

        db.add(
            WorldNewsDB(
                world_id=world_id,
                headline=headline,
                body=body,
                category="social_media",
                game_date=game_date,
                is_kayfabe=False,
                source="Social Media Report",
                related_entities=[wrestler.id],
            )
        )


def generate_life_event_news(db: Session, world_id: str, game_date: str):
    """Generate news from public life events."""
    public_events = (
        db.query(LifeEventDB)
        .filter(
            LifeEventDB.world_id == world_id,
            LifeEventDB.game_date == game_date,
            LifeEventDB.is_public == True,
        )
        .all()
    )

    for event in public_events:
        wrestler = (
            db.query(GameWrestlerDB)
            .filter(
                GameWrestlerDB.id == event.wrestler_id,
            )
            .first()
        )
        if not wrestler:
            continue

        name = wrestler.name
        positive_types = {
            "marriage",
            "child_born",
            "personal_achievement",
            "charity_work",
            "family_reconciliation",
        }
        if event.event_type in positive_types:
            headline = f"Congratulations! {name} shares personal good news"
            source = "Wrestling Insider"
        else:
            headline = f"Sources say {name} dealing with personal issues"
            source = "Wrestling Observer"

        db.add(
            WorldNewsDB(
                world_id=world_id,
                headline=headline,
                body=event.description,
                category="personal",
                game_date=game_date,
                is_kayfabe=False,
                source=source,
                related_entities=[wrestler.id],
            )
        )


def generate_gimmick_change_news(
    db: Session,
    world_id: str,
    wrestler: GameWrestlerDB,
    old_gimmick: str,
    new_gimmick: str,
    game_date: str,
):
    """Generate news about a wrestler's gimmick change/repackaging."""
    db.add(
        WorldNewsDB(
            world_id=world_id,
            headline=f"REPACKAGE: {wrestler.name} debuts new character!",
            body=(
                f"{wrestler.name} has been repackaged with a new gimmick. "
                f'The previous "{old_gimmick}" character has been retired. '
                f"Fans will see the new persona on the next show."
            ),
            category="repackage",
            game_date=game_date,
            is_kayfabe=False,
            source="Wrestling Observer",
            related_entities=[wrestler.id],
        )
    )
