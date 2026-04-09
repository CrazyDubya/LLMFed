"""
Social media service — simulates wrestler social media activity.

Generates in-character, shoot, and worked-shoot posts. Handles viral moments,
feud exchanges, and fan engagement tracking.
"""

import random
import logging
from sqlalchemy.orm import Session

from models.game_models import (
    GameWrestlerDB, SocialMediaPostDB, GimmickHistoryDB,
    WrestlerBackstoryDB, StorylineDB, StorylineParticipantDB,
    WrestlerRelationshipDB, WorldNewsDB,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template pools
# ---------------------------------------------------------------------------

KAYFABE_FACE_POSTS = [
    "Tonight I fight for every single one of you. Let's DO this! #NeverGiveUp",
    "Hard work beats talent when talent doesn't work hard. See you in the ring.",
    "To every kid watching at home — you CAN do this. Believe in yourself.",
    "Just finished the best training session of my life. I'm coming for that title.",
    "The people deserve a champion who fights for THEM. That's me.",
    "Win, lose, or draw — I leave everything in that ring. Every. Single. Night.",
]

KAYFABE_HEEL_POSTS = [
    "None of you deserve to breathe the same air as me. #BowDown",
    "Another day, another roster full of people who can't touch me.",
    "I don't need your cheers. I need your FEAR.",
    "Looking at the competition and honestly? I'm insulted.",
    "Your hero? I already beat them. Twice.",
    "The only thing more pathetic than this roster is the fans who cheer for them.",
]

SHOOT_POSTS = [
    "Great day at the gym. Grateful for this life.",
    "Nothing better than a day off with the family.",
    "Throwing it back to where it all started. Long way from {hometown}.",
    "Real talk — this industry tests you. But I love it.",
    "Watching the new generation come up. The future's bright.",
    "Rest day. My body needed this more than I want to admit.",
    "Appreciating the little things today. This business can take a lot from you.",
]

WORKED_SHOOT_POSTS = [
    "Funny how some people get opportunities and others don't. Just saying.",
    "I've been very patient. That patience is running out.",
    "Sometimes I wonder if anyone backstage is actually watching the show...",
    "...",
    "When you're ready to have a REAL conversation, you know where to find me.",
    "I wasn't supposed to say this but I genuinely don't care anymore.",
    "The best match on the card and we got 8 minutes. Interesting.",
]

PERSONAL_POSTS = [
    "Took the kids to the park today. Best part of my week.",
    "Happy anniversary to the love of my life. You make this all worth it.",
    "Lost someone special this week. Hug the people you love.",
    "New hobby alert: apparently I'm a terrible cook but I'm not giving up.",
    "Dog update: still the best part of coming home from the road.",
    "Reading recommendation from the road: currently on my third book this month.",
]

CHALLENGE_POSTS = [
    "Hey {target} — you've been real quiet since I called you out. Cat got your tongue?",
    "{target} ducking me on social media just like they duck me in the ring.",
    "Everywhere I go, people ask me the same thing: 'When are you gonna shut {target} up?' Soon.",
    "I see {target} posted another selfie. Must be nice having free time when you don't have MY schedule.",
]

RESPONSE_POSTS = [
    "LOL {target} is talking again. Wake me up when they actually win a match.",
    "{target} wants attention so bad. Fine. You got it. And you'll regret it.",
    "The difference between me and {target}? I let my record speak for itself.",
    "Cute post, {target}. Real cute. See you at the show.",
]


# ---------------------------------------------------------------------------
# Post generation
# ---------------------------------------------------------------------------

def generate_social_post(db: Session, wrestler_id: str, world_id: str,
                         game_date: str, context: str = None) -> SocialMediaPostDB:
    """Generate a social media post for a wrestler."""
    wrestler = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id == wrestler_id,
    ).first()
    if not wrestler:
        return None

    gimmick = db.query(GimmickHistoryDB).filter(
        GimmickHistoryDB.wrestler_id == wrestler_id,
        GimmickHistoryDB.is_active == True,
    ).first()

    backstory = db.query(WrestlerBackstoryDB).filter(
        WrestlerBackstoryDB.wrestler_id == wrestler_id,
    ).first()

    # Determine post type based on kayfabe commitment
    kayfabe_commit = wrestler.kayfabe_commitment or 50
    roll = random.random() * 100

    if roll < kayfabe_commit * 0.6:
        post_type = "kayfabe"
    elif roll < kayfabe_commit * 0.6 + 20:
        post_type = "personal"
    elif roll < kayfabe_commit * 0.6 + 35:
        post_type = "shoot"
    else:
        post_type = "worked_shoot"

    # Generate content
    content = _generate_post_content(wrestler, gimmick, backstory, post_type)

    # Platform selection
    platform = random.choices(
        ["twitter", "instagram", "tiktok", "youtube"],
        weights=[40, 30, 20, 10], k=1,
    )[0]

    # Engagement based on popularity and content type
    base_engagement = wrestler.popularity // 3
    if post_type == "worked_shoot":
        base_engagement += random.randint(10, 30)
    elif post_type == "shoot" and backstory:
        media_savvy = (backstory.real_personality or {}).get("media_savvy", 50)
        base_engagement += media_savvy // 10
    engagement = min(100, base_engagement + random.randint(-5, 15))

    # Controversy
    controversy = 0
    if post_type == "worked_shoot":
        controversy = random.randint(20, 60)
    elif post_type == "shoot":
        controversy = random.randint(0, 20)
    elif post_type == "kayfabe" and wrestler.alignment == "heel":
        controversy = random.randint(5, 25)

    # Kayfabe break level
    kayfabe_break = 0
    if post_type == "shoot":
        kayfabe_break = random.randint(30, 70)
    elif post_type == "worked_shoot":
        kayfabe_break = random.randint(40, 80)

    # Fan reaction
    if post_type == "worked_shoot":
        fan_reaction = random.choice(["confused", "mixed", "negative", "positive"])
    elif wrestler.alignment == "face":
        fan_reaction = "positive" if engagement > 30 else "mixed"
    elif wrestler.alignment == "heel":
        fan_reaction = "negative" if engagement > 30 else "mixed"
    else:
        fan_reaction = "mixed"

    post = SocialMediaPostDB(
        wrestler_id=wrestler_id,
        world_id=world_id,
        game_date=game_date,
        content=content,
        post_type=post_type,
        platform=platform,
        engagement_score=engagement,
        controversy_level=controversy,
        is_viral=False,
        fan_reaction=fan_reaction,
        kayfabe_break_level=kayfabe_break,
        popularity_impact=0,
    )
    db.add(post)
    db.flush()

    # Check if it goes viral
    if check_viral_moment(post):
        post.is_viral = True
        process_viral_fallout(db, post, game_date)

    return post


def _generate_post_content(wrestler, gimmick, backstory, post_type):
    """Generate post content based on type and persona."""
    hometown = wrestler.hometown or "the road"

    # Template-based fallback
    if post_type == "kayfabe":
        if wrestler.alignment == "heel":
            fallback = random.choice(KAYFABE_HEEL_POSTS)
        else:
            fallback = random.choice(KAYFABE_FACE_POSTS)
    elif post_type == "shoot":
        template = random.choice(SHOOT_POSTS)
        fallback = template.format(hometown=hometown)
    elif post_type == "worked_shoot":
        fallback = random.choice(WORKED_SHOOT_POSTS)
    elif post_type == "personal":
        fallback = random.choice(PERSONAL_POSTS)
    else:
        fallback = "..."

    # Try LLM-enhanced post if enabled
    import os
    if os.getenv("LLMFED_USE_LLM", "").lower() in ("1", "true", "yes"):
        try:
            from llm_abstraction.provider import get_llm
            archetype = gimmick.archetype if gimmick else "wrestler"
            prompt = (
                f"Write a short social media post (1-2 sentences, under 280 chars) "
                f"for {wrestler.name}, a {wrestler.alignment or 'face'} wrestler "
                f"with a {archetype} persona. Post type: {post_type}. "
                f"No hashtags unless it fits the character."
            )
            response = get_llm().generate(prompt, max_tokens=80)
            if response and response.content and len(response.content.strip()) > 10:
                return response.content.strip()
        except Exception:
            pass

    return fallback


# ---------------------------------------------------------------------------
# Daily tick
# ---------------------------------------------------------------------------

def tick_social_media(db: Session, world_id: str, game_date: str):
    """Daily social media tick. Each wrestler has a chance to post."""
    wrestlers = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.world_id == world_id,
        GameWrestlerDB.is_active == True,
    ).all()

    for wrestler in wrestlers:
        # Base posting chance: 8% per day (~1-2 posts per week per wrestler)
        chance = 0.08

        # More popular wrestlers post more
        if wrestler.popularity > 70:
            chance += 0.05
        elif wrestler.popularity < 30:
            chance -= 0.03

        # Higher social media following = more active
        if (wrestler.social_media_following or 0) > 50000:
            chance += 0.03

        if random.random() < chance:
            generate_social_post(db, wrestler.id, world_id, game_date)

    # Check for feud exchanges (active storylines generate social media beef)
    active_storylines = db.query(StorylineDB).filter(
        StorylineDB.world_id == world_id,
        StorylineDB.status.in_(["active", "climax"]),
    ).all()

    for storyline in active_storylines:
        # 10% chance of a social media exchange per active storyline per day
        if random.random() > 0.10:
            continue

        participants = db.query(StorylineParticipantDB).filter(
            StorylineParticipantDB.storyline_id == storyline.id,
        ).all()
        if len(participants) < 2:
            continue

        w1_id = participants[0].wrestler_id
        w2_id = participants[1].wrestler_id
        generate_feud_exchange(
            db, w1_id, w2_id, world_id, game_date, storyline.id,
        )


# ---------------------------------------------------------------------------
# Viral moments
# ---------------------------------------------------------------------------

def check_viral_moment(post: SocialMediaPostDB) -> bool:
    """Determine if a post goes viral."""
    chance = 0.02  # Base 2% chance

    if post.controversy_level > 50:
        chance += 0.10
    if post.engagement_score > 70:
        chance += 0.08
    if post.post_type == "worked_shoot":
        chance += 0.05
    if post.kayfabe_break_level > 60:
        chance += 0.05

    return random.random() < chance


def process_viral_fallout(db: Session, post: SocialMediaPostDB, game_date: str):
    """Handle the effects of a viral post.

    Viral posts now feed back into the gameplay loop:
    - Popularity changes (existing)
    - Storyline heat boosts when the post involves a rival
    - Narrative log events for high-controversy viral moments
    """
    wrestler = db.query(GameWrestlerDB).filter(
        GameWrestlerDB.id == post.wrestler_id,
    ).first()
    if not wrestler:
        return

    # Popularity impact
    if post.controversy_level > 50:
        # Controversial viral — could go either way
        pop_change = random.randint(-5, 10)
    else:
        pop_change = random.randint(3, 12)

    wrestler.popularity = max(0, min(100, wrestler.popularity + pop_change))
    wrestler.social_media_following = (wrestler.social_media_following or 1000) + random.randint(500, 5000)
    post.popularity_impact = pop_change

    # --- NEW: Storyline heat boost from viral posts ---
    # If the wrestler is in an active storyline, viral buzz heats the feud
    storyline_participants = db.query(StorylineParticipantDB).filter(
        StorylineParticipantDB.wrestler_id == wrestler.id,
    ).all()
    for sp in storyline_participants:
        storyline = db.query(StorylineDB).filter(
            StorylineDB.id == sp.storyline_id,
            StorylineDB.status.in_(["active", "climax", "brewing"]),
        ).first()
        if storyline:
            heat_boost = random.randint(3, 5)
            if post.controversy_level >= 40:
                heat_boost += 2
            storyline.heat = min(100, storyline.heat + heat_boost)
            logger.info("Viral post boosted storyline %s heat by +%d to %d",
                        storyline.id[:8], heat_boost, storyline.heat)

    # --- NEW: Narrative log for high-controversy viral moments ---
    if post.controversy_level >= 7:
        from models.game_models import GameNarrativeLogDB
        db.add(GameNarrativeLogDB(
            world_id=post.world_id,
            game_date=game_date,
            tick=0,
            event_type="social_media_viral",
            description=f"{wrestler.name}'s viral post is causing a stir backstage! "
                        f"(controversy: {post.controversy_level}, engagement: {post.engagement_score})",
            involved_entities=[wrestler.id],
            importance=6,
        ))

    # Generate news
    try:
        from game_service.news_service import generate_social_media_news
        generate_social_media_news(db, post.world_id, game_date)
    except Exception as e:
        logger.warning("Failed to generate social media news: %s", e)

    logger.info("Viral post by %s! Pop change: %+d", wrestler.name, pop_change)


# ---------------------------------------------------------------------------
# Buzz bonus for card draw
# ---------------------------------------------------------------------------

def get_viral_buzz_bonus(db: Session, world_id: str, game_date: str,
                         wrestler_ids: list) -> float:
    """Return a card draw multiplier bonus based on recent viral posts.

    Checks the last 7 game days for viral posts by wrestlers on the card.
    Each viral post adds 0.1 to the bonus (capped at 0.5).
    """
    from datetime import datetime, timedelta
    try:
        current = datetime.strptime(game_date, "%Y-%m-%d")
        week_ago = (current - timedelta(days=7)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return 0.0

    viral_count = db.query(SocialMediaPostDB).filter(
        SocialMediaPostDB.world_id == world_id,
        SocialMediaPostDB.is_viral == True,
        SocialMediaPostDB.game_date >= week_ago,
        SocialMediaPostDB.game_date <= game_date,
        SocialMediaPostDB.wrestler_id.in_(wrestler_ids),
    ).count()

    return min(0.5, viral_count * 0.1)


# ---------------------------------------------------------------------------
# Feud exchanges
# ---------------------------------------------------------------------------

def generate_feud_exchange(db: Session, wrestler1_id: str, wrestler2_id: str,
                           world_id: str, game_date: str,
                           storyline_id: str = None) -> list:
    """Create a back-and-forth social media exchange between feuding wrestlers."""
    w1 = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wrestler1_id).first()
    w2 = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wrestler2_id).first()
    if not w1 or not w2:
        return []

    posts = []
    platform = random.choice(["twitter", "twitter", "instagram"])

    # First salvo
    content1 = random.choice(CHALLENGE_POSTS).format(target=w2.name)
    post1 = SocialMediaPostDB(
        wrestler_id=w1.id, world_id=world_id, game_date=game_date,
        content=content1, post_type="kayfabe", platform=platform,
        engagement_score=random.randint(30, 70),
        controversy_level=random.randint(10, 40),
        storyline_id=storyline_id, target_wrestler_id=w2.id,
        fan_reaction="positive" if w1.alignment == "face" else "negative",
    )
    db.add(post1)
    posts.append(post1)

    # Response
    content2 = random.choice(RESPONSE_POSTS).format(target=w1.name)
    post2 = SocialMediaPostDB(
        wrestler_id=w2.id, world_id=world_id, game_date=game_date,
        content=content2, post_type="kayfabe", platform=platform,
        engagement_score=random.randint(30, 70),
        controversy_level=random.randint(10, 40),
        storyline_id=storyline_id, target_wrestler_id=w1.id,
        fan_reaction="positive" if w2.alignment == "face" else "negative",
    )
    db.add(post2)
    posts.append(post2)

    db.flush()
    return posts
