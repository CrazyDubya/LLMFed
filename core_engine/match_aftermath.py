"""
Match aftermath processing — the cascading effects of every match result.

Handles: title changes, win/loss records, popularity/morale shifts,
wrestler relationships/chemistry, history entries, and storyline triggers.
"""

import random
import logging
from sqlalchemy.orm import Session

from models.game_models import (
    MatchDB, MatchParticipantDB, GameWrestlerDB, WrestlerStatsDB,
    ChampionshipDB, ChampionshipHistoryDB, WrestlerHistoryDB,
    WrestlerRelationshipDB, GameNarrativeLogDB, TagTeamDB,
)

logger = logging.getLogger(__name__)


def process_match_aftermath(db: Session, match: MatchDB, game_date: str):
    """Process all consequences of a completed match."""
    if not match.is_completed or not match.winner_id:
        return

    participants = db.query(MatchParticipantDB).filter(
        MatchParticipantDB.match_id == match.id,
        MatchParticipantDB.role == "competitor",
    ).all()

    if len(participants) < 2:
        return

    winners = [p for p in participants if p.is_winner]
    losers = [p for p in participants if not p.is_winner]

    # 1. Title change handling
    if match.is_title_match and match.championship_id:
        _handle_title_result(db, match, winners, losers, game_date)

    # 2. Popularity & morale shifts
    _update_popularity_morale(db, match, winners, losers)

    # 3. Win/loss streak tracking
    _update_streaks(db, winners, losers)

    # 4. Record last booked date
    for p in participants:
        w = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == p.wrestler_id).first()
        if w:
            w.last_booked_date = game_date

    # 5. Wrestler history entries
    _record_history(db, match, winners, losers, game_date)

    # 6. Update wrestler relationships / chemistry
    _update_relationships(db, match, participants, game_date)

    # 7. Update tag team records
    _update_tag_team_records(db, match, participants)

    # 8. Alignment momentum shifts
    _update_alignment_momentum(db, match, winners, losers, game_date)

    # 9. Career highlights (Group 5) and specialization growth (Group 6)
    _post_match_lifecycle(db, match, participants, game_date)

    # 10. Botch consequences — trust degradation, injury, history entries
    _process_botch_consequences(db, match, game_date)

    # 11. Going-into-business consequences — discipline, locker room heat, trust destruction
    _process_shoot_consequences(db, match, game_date)


def _handle_title_result(db: Session, match: MatchDB,
                         winners: list, losers: list, game_date: str):
    """Handle championship title change or successful defense."""
    champ = db.query(ChampionshipDB).filter(
        ChampionshipDB.id == match.championship_id
    ).first()
    if not champ:
        return

    winner_id = winners[0].wrestler_id if winners else None
    if not winner_id:
        return

    winner = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == winner_id).first()
    winner_name = winner.name if winner else "Unknown"

    if champ.current_holder_id == winner_id:
        # Successful title defense
        champ.defenses += 1
        db.add(GameNarrativeLogDB(
            world_id=match.world_id,
            game_date=game_date, tick=0,
            event_type="title_defense",
            description=f"{winner_name} successfully defends the {champ.name} ({champ.defenses} defenses)",
            involved_entities=[winner_id, champ.id],
            importance=7,
        ))
    else:
        # Title change!
        old_holder_id = champ.current_holder_id
        old_holder = db.query(GameWrestlerDB).filter(
            GameWrestlerDB.id == old_holder_id
        ).first() if old_holder_id else None

        # End old reign
        if old_holder_id:
            old_reign = db.query(ChampionshipHistoryDB).filter(
                ChampionshipHistoryDB.championship_id == champ.id,
                ChampionshipHistoryDB.wrestler_id == old_holder_id,
                ChampionshipHistoryDB.reign_end == None,
            ).first()
            if old_reign:
                old_reign.reign_end = game_date
                old_reign.how_lost = match.finish_type or "pinfall"

        # Start new reign
        db.add(ChampionshipHistoryDB(
            championship_id=champ.id,
            wrestler_id=winner_id,
            reign_start=game_date,
            defenses=0,
            how_won=match.finish_type or "pinfall",
        ))

        champ.current_holder_id = winner_id
        champ.current_reign_start = game_date
        champ.defenses = 0

        # Title change popularity/morale bonuses
        if winner:
            winner.popularity = min(100, winner.popularity + 10)
            winner.morale = min(100, winner.morale + 10)

        if old_holder:
            old_holder.popularity = max(0, old_holder.popularity - 5)
            old_holder.morale = max(0, old_holder.morale - 8)

        # History entries
        db.add(WrestlerHistoryDB(
            wrestler_id=winner_id, game_date=game_date,
            event_type="title_win",
            description=f"Won the {champ.name}",
            details={"championship_id": champ.id, "finish": match.finish_type},
        ))
        if old_holder_id:
            db.add(WrestlerHistoryDB(
                wrestler_id=old_holder_id, game_date=game_date,
                event_type="title_loss",
                description=f"Lost the {champ.name} to {winner_name}",
                details={"championship_id": champ.id},
            ))

        old_name = old_holder.name if old_holder else "the previous champion"
        db.add(GameNarrativeLogDB(
            world_id=match.world_id,
            game_date=game_date, tick=0,
            event_type="title_change",
            description=f"NEW CHAMPION! {winner_name} defeats {old_name} for the {champ.name}!",
            involved_entities=[winner_id, champ.id],
            importance=9,
        ))


def _update_popularity_morale(db: Session, match: MatchDB,
                              winners: list, losers: list):
    """Shift popularity and morale based on match result."""
    rating = match.match_rating or 3.0
    rating_factor = rating / 5.0  # 0.0 - 1.0

    for wp in winners:
        w = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wp.wrestler_id).first()
        if not w:
            continue
        pop_gain = int(2 + 3 * rating_factor)  # 2-5
        morale_gain = random.randint(3, 5)

        # Clean finish bonus
        if match.finish_type in ("pinfall", "submission"):
            pop_gain += 2

        w.popularity = min(100, w.popularity + pop_gain)
        w.morale = min(100, w.morale + morale_gain)

    for lp in losers:
        w = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == lp.wrestler_id).first()
        if not w:
            continue
        # Good matches soften the loss
        pop_loss = max(1, int(3 - 2 * rating_factor))  # 1-3
        morale_loss = random.randint(2, 4)

        w.popularity = max(0, w.popularity - pop_loss)
        w.morale = max(0, w.morale - morale_loss)


def _update_streaks(db: Session, winners: list, losers: list):
    """Update win/loss streak counters."""
    for wp in winners:
        w = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wp.wrestler_id).first()
        if w:
            w.win_streak = max(0, w.win_streak) + 1  # Reset if was negative

    for lp in losers:
        w = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == lp.wrestler_id).first()
        if w:
            w.win_streak = min(0, w.win_streak) - 1  # Reset if was positive


def _record_history(db: Session, match: MatchDB, winners: list, losers: list,
                    game_date: str):
    """Create wrestler history entries for match results."""
    for wp in winners:
        w = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wp.wrestler_id).first()
        if w:
            db.add(WrestlerHistoryDB(
                wrestler_id=wp.wrestler_id, game_date=game_date,
                event_type="match_win",
                description=f"Defeated opponent via {match.finish_type or 'pinfall'} ({match.match_rating or 0:.1f} stars)",
                details={"match_id": match.id, "rating": match.match_rating},
            ))

    for lp in losers:
        w = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == lp.wrestler_id).first()
        if w:
            db.add(WrestlerHistoryDB(
                wrestler_id=lp.wrestler_id, game_date=game_date,
                event_type="match_loss",
                description=f"Lost via {match.finish_type or 'pinfall'} ({match.match_rating or 0:.1f} stars)",
                details={"match_id": match.id, "rating": match.match_rating},
            ))


def _update_relationships(db: Session, match: MatchDB,
                          participants: list, game_date: str):
    """Update or create relationship records between all match participants."""
    wrestler_ids = [p.wrestler_id for p in participants]
    rating = match.match_rating or 3.0

    # Pre-fetch wrestler alignment data for rivalry_heat calculations
    wrestlers_by_id = {}
    for wid in wrestler_ids:
        w = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wid).first()
        if w:
            wrestlers_by_id[wid] = w

    for i in range(len(wrestler_ids)):
        for j in range(i + 1, len(wrestler_ids)):
            w1, w2 = sorted([wrestler_ids[i], wrestler_ids[j]])
            rel = db.query(WrestlerRelationshipDB).filter(
                WrestlerRelationshipDB.world_id == match.world_id,
                WrestlerRelationshipDB.wrestler1_id == w1,
                WrestlerRelationshipDB.wrestler2_id == w2,
            ).first()

            if rel:
                rel.matches_together += 1
                rel.total_rating += rating
                rel.chemistry_score = round(rel.total_rating / rel.matches_together, 2)
                rel.last_match_date = game_date
            else:
                rel = WrestlerRelationshipDB(
                    world_id=match.world_id,
                    wrestler1_id=w1, wrestler2_id=w2,
                    matches_together=1,
                    total_rating=rating,
                    chemistry_score=round(rating, 2),
                    last_match_date=game_date,
                    rivalry_heat=0,
                )
                db.add(rel)

            # --- rivalry_heat update ---
            heat_increase = 0

            # +5 for opposing alignments (face vs heel)
            wr1 = wrestlers_by_id.get(w1)
            wr2 = wrestlers_by_id.get(w2)
            if wr1 and wr2:
                alignments = {wr1.alignment, wr2.alignment}
                if alignments == {"face", "heel"}:
                    heat_increase += 5

            # +3 for title match
            if match.is_title_match:
                heat_increase += 3

            # +2 if an active storyline involves both wrestlers
            if wr1 and wr2:
                storyline_link = db.query(GameNarrativeLogDB).filter(
                    GameNarrativeLogDB.world_id == match.world_id,
                    GameNarrativeLogDB.involved_entities.contains(w1),
                    GameNarrativeLogDB.involved_entities.contains(w2),
                ).first()
                if storyline_link:
                    heat_increase += 2

            current_heat = rel.rivalry_heat or 0
            if heat_increase > 0:
                rel.rivalry_heat = min(100, current_heat + heat_increase)
            else:
                # Natural decay: reduce by 1, minimum 0
                rel.rivalry_heat = max(0, current_heat - 1)


def _update_tag_team_records(db: Session, match: MatchDB, participants: list):
    """Update tag team win/loss records if this was a tag match."""
    if match.match_type != "tag_team":
        return

    winners = {p.wrestler_id for p in participants if p.is_winner}
    losers = {p.wrestler_id for p in participants if not p.is_winner}

    # Find tag teams involved
    all_ids = [p.wrestler_id for p in participants]
    teams = db.query(TagTeamDB).filter(
        TagTeamDB.is_active == True,
        TagTeamDB.wrestler1_id.in_(all_ids),
        TagTeamDB.wrestler2_id.in_(all_ids),
    ).all()

    for team in teams:
        members = {team.wrestler1_id, team.wrestler2_id}
        if members <= winners:
            team.wins += 1
            team.team_chemistry = min(100, team.team_chemistry + 5)
        elif members <= losers:
            team.losses += 1
            team.team_chemistry = min(100, team.team_chemistry + 2)  # Still grow from working together


def _update_alignment_momentum(db: Session, match: MatchDB,
                               winners: list, losers: list, game_date: str):
    """Shift alignment momentum based on how the match played out."""
    # Clean wins push toward face, dirty finishes push toward heel
    is_clean = match.finish_type in ("pinfall", "submission")

    for wp in winners:
        w = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == wp.wrestler_id).first()
        if not w:
            continue
        if is_clean:
            w.alignment_momentum = min(100, (w.alignment_momentum or 0) + 2)
        else:
            w.alignment_momentum = max(-100, (w.alignment_momentum or 0) - 3)

        _check_alignment_turn(db, w, game_date, match.world_id)

    for lp in losers:
        w = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == lp.wrestler_id).first()
        if not w:
            continue
        # Losing can push either way - sympathy (face) or bitterness (heel)
        if w.morale and w.morale < 40:
            # Bitter from losing → heel drift
            w.alignment_momentum = max(-100, (w.alignment_momentum or 0) - 2)
        else:
            # Sympathetic underdog → face drift
            w.alignment_momentum = min(100, (w.alignment_momentum or 0) + 1)

        _check_alignment_turn(db, w, game_date, match.world_id)


def _check_alignment_turn(db: Session, wrestler: GameWrestlerDB,
                          game_date: str, world_id: str):
    """Check if alignment momentum has crossed the threshold for a turn."""
    momentum = wrestler.alignment_momentum or 0

    if wrestler.alignment == "face" and momentum <= -60:
        wrestler.alignment = "heel"
        wrestler.alignment_momentum = 0
        wrestler.popularity = min(100, wrestler.popularity + 5)  # Turns are exciting
        db.add(GameNarrativeLogDB(
            world_id=world_id, game_date=game_date, tick=0,
            event_type="heel_turn",
            description=f"SHOCKING HEEL TURN! {wrestler.name} has turned their back on the fans!",
            involved_entities=[wrestler.id], importance=9,
        ))
        db.add(WrestlerHistoryDB(
            wrestler_id=wrestler.id, game_date=game_date,
            event_type="heel_turn",
            description=f"{wrestler.name} turned heel",
        ))

    elif wrestler.alignment == "heel" and momentum >= 60:
        wrestler.alignment = "face"
        wrestler.alignment_momentum = 0
        wrestler.popularity = min(100, wrestler.popularity + 5)
        db.add(GameNarrativeLogDB(
            world_id=world_id, game_date=game_date, tick=0,
            event_type="face_turn",
            description=f"THE CROWD GOES WILD! {wrestler.name} has turned babyface!",
            involved_entities=[wrestler.id], importance=9,
        ))
        db.add(WrestlerHistoryDB(
            wrestler_id=wrestler.id, game_date=game_date,
            event_type="face_turn",
            description=f"{wrestler.name} turned face",
        ))


def get_chemistry_bonus(db: Session, world_id: str,
                        wrestler1_id: str, wrestler2_id: str) -> float:
    """Get chemistry bonus for a pair of wrestlers. Returns 0.0-1.0."""
    w1, w2 = sorted([wrestler1_id, wrestler2_id])
    rel = db.query(WrestlerRelationshipDB).filter(
        WrestlerRelationshipDB.world_id == world_id,
        WrestlerRelationshipDB.wrestler1_id == w1,
        WrestlerRelationshipDB.wrestler2_id == w2,
    ).first()

    if not rel or rel.matches_together < 3:
        return 0.0

    # Chemistry bonus scales with match count and quality
    return min(1.0, rel.chemistry_score * 0.2)


def _post_match_lifecycle(db: Session, match: MatchDB,
                         participants: list, game_date: str):
    """Post-match lifecycle hooks: career highlights and specialization growth."""
    try:
        from game_service.wrestler_lifecycle_service import (
            check_match_highlights, grow_specialization,
        )

        for p in participants:
            check_match_highlights(db, match, p.wrestler_id, game_date)

            # Grow specialization from stipulation matches
            if match.stipulation:
                stats = db.query(WrestlerStatsDB).filter(
                    WrestlerStatsDB.wrestler_id == p.wrestler_id
                ).first()
                if stats:
                    grow_specialization(stats, match.stipulation)
    except Exception as e:
        logger.warning(f"Lifecycle post-match hook failed: {e}")


def compute_win_loss(db: Session, wrestler_id: str) -> dict:
    """Compute win/loss/draw record from match participation."""
    wins = db.query(MatchParticipantDB).filter(
        MatchParticipantDB.wrestler_id == wrestler_id,
        MatchParticipantDB.role == "competitor",
        MatchParticipantDB.is_winner == True,
    ).count()

    total = db.query(MatchParticipantDB).join(MatchDB).filter(
        MatchParticipantDB.wrestler_id == wrestler_id,
        MatchParticipantDB.role == "competitor",
        MatchDB.is_completed == True,
    ).count()

    draws = db.query(MatchParticipantDB).join(MatchDB).filter(
        MatchParticipantDB.wrestler_id == wrestler_id,
        MatchParticipantDB.role == "competitor",
        MatchDB.is_completed == True,
        MatchDB.winner_id == None,
    ).count()

    losses = total - wins - draws
    return {"wins": wins, "losses": losses, "draws": draws}


# ---------------------------------------------------------------------------
# Botch consequences
# ---------------------------------------------------------------------------

def _process_botch_consequences(db: Session, match: MatchDB, game_date: str):
    """Handle the aftermath of botched moves.

    Dangerous botches (severity 3):
    - Victim may be injured
    - Trust between wrestlers degrades
    - History entry recorded for both wrestlers (memory for character agent)
    - Locker room standing drops for the botcher

    Bad botches (severity 2):
    - Minor trust degradation
    - History entry for the botcher
    """
    # The match result's botch_events are stored in simulation_log
    sim_log = match.simulation_log or []
    botch_events = [s for s in sim_log if s.get("is_botch")]
    if not botch_events:
        return

    for botch in botch_events:
        severity = botch.get("botch_severity", 0)
        if severity < 2:
            continue  # Minor stumbles don't have lasting consequences

        attacker_id = botch.get("attacker")
        victim_id = botch.get("defender")
        move_name = botch.get("move", "unknown move")

        attacker = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == attacker_id).first()
        victim = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == victim_id).first()
        if not attacker or not victim:
            continue

        # --- Trust degradation between these wrestlers ---
        rel = db.query(WrestlerRelationshipDB).filter(
            WrestlerRelationshipDB.world_id == match.world_id,
            WrestlerRelationshipDB.wrestler1_id.in_([attacker_id, victim_id]),
            WrestlerRelationshipDB.wrestler2_id.in_([attacker_id, victim_id]),
        ).first()
        if rel:
            trust_drop = 5 if severity == 2 else 15  # Dangerous botch = big trust hit
            rel.trust_level = max(0, (rel.trust_level or 50) - trust_drop)
            logger.info("Trust between %s and %s dropped by %d to %d (botch on %s)",
                        attacker.name, victim.name, trust_drop, rel.trust_level, move_name)

        # --- History entries: both wrestlers remember ---
        if severity >= 3:
            # Dangerous botch — victim remembers being hurt
            db.add(WrestlerHistoryDB(
                wrestler_id=victim_id,
                game_date=game_date,
                event_type="botch_victim",
                description=f"Was hurt by a botched {move_name} from {attacker.name}",
                details={"caused_by": attacker_id, "caused_by_name": attacker.name,
                         "move": move_name, "severity": severity, "match_id": match.id},
            ))
            # Attacker remembers hurting someone
            db.add(WrestlerHistoryDB(
                wrestler_id=attacker_id,
                game_date=game_date,
                event_type="botch_perpetrator",
                description=f"Botched {move_name} and hurt {victim.name}",
                details={"victim": victim_id, "victim_name": victim.name,
                         "move": move_name, "severity": severity, "match_id": match.id},
            ))

            # Injury check from dangerous botch
            stats = db.query(WrestlerStatsDB).filter(
                WrestlerStatsDB.wrestler_id == victim_id
            ).first()
            injury_risk = 0.25 + (stats.injury_prone if stats else 30) / 200
            if random.random() < injury_risk:
                weeks_out = random.randint(1, 8)
                from game_service.world_ticker import advance_game_date
                victim.is_injured = True
                victim.injury_return_date = advance_game_date(game_date, weeks_out * 7)
                victim.condition = max(0, victim.condition - random.randint(15, 35))

                db.add(GameNarrativeLogDB(
                    world_id=match.world_id,
                    game_date=game_date, tick=0,
                    event_type="botch_injury",
                    description=f"{victim.name} injured by botched {move_name} from {attacker.name}! Out {weeks_out} weeks.",
                    involved_entities=[victim_id, attacker_id],
                    importance=8,
                ))
                logger.info("BOTCH INJURY: %s hurt by %s's %s, out %d weeks",
                            victim.name, attacker.name, move_name, weeks_out)

            # Locker room standing drops for the botcher
            if attacker.locker_room_standing in ("leader", "respected"):
                attacker.locker_room_standing = "neutral"
            elif attacker.locker_room_standing == "neutral":
                attacker.locker_room_standing = "disliked"

        elif severity == 2:
            # Bad botch — attacker remembers
            db.add(WrestlerHistoryDB(
                wrestler_id=attacker_id,
                game_date=game_date,
                event_type="botch_perpetrator",
                description=f"Botched {move_name} against {victim.name}",
                details={"victim": victim_id, "victim_name": victim.name,
                         "move": move_name, "severity": severity, "match_id": match.id},
            ))


# ---------------------------------------------------------------------------
# Going-into-business consequences
# ---------------------------------------------------------------------------

def _process_shoot_consequences(db: Session, match: MatchDB, game_date: str):
    """Handle consequences when a wrestler goes into business for themselves.

    This is the nuclear option — a wrestler refused to do the planned job.
    Consequences are severe and long-lasting:
    - Trust with opponent DESTROYED
    - Locker room standing tanks
    - Federation may fine/suspend
    - History entry creates a permanent memory
    - Morale impact on the victim (humiliated, angry)
    - The shooter gets a temporary popularity boost (controversy sells)
    """
    sim_log = match.simulation_log or []
    shoot_spots = [s for s in sim_log if s.get("is_shoot")]
    if not shoot_spots:
        return

    shoot_spot = shoot_spots[0]
    shooter_id = shoot_spot.get("attacker")
    victim_id = shoot_spot.get("defender")

    shooter = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == shooter_id).first()
    victim = db.query(GameWrestlerDB).filter(GameWrestlerDB.id == victim_id).first()
    if not shooter or not victim:
        return

    # --- Trust DESTROYED between these wrestlers ---
    rel = db.query(WrestlerRelationshipDB).filter(
        WrestlerRelationshipDB.world_id == match.world_id,
        WrestlerRelationshipDB.wrestler1_id.in_([shooter_id, victim_id]),
        WrestlerRelationshipDB.wrestler2_id.in_([shooter_id, victim_id]),
    ).first()
    if rel:
        rel.trust_level = max(0, min(10, (rel.trust_level or 50) - 40))  # Near-zero
        rel.rivalry_heat = min(100, (rel.rivalry_heat or 0) + 30)  # Real heat
        rel.real_relationship = "enemies"  # This is personal now
        logger.info("SHOOT: Trust between %s and %s DESTROYED (now %d)",
                    shooter.name, victim.name, rel.trust_level)

    # --- Locker room standing tanks for the shooter ---
    shooter.locker_room_standing = "toxic"

    # --- Federation discipline ---
    from models.game_models import ContractDB, GameFederationDB
    contract = db.query(ContractDB).filter(
        ContractDB.wrestler_id == shooter_id,
        ContractDB.status == "active",
    ).first()
    if contract:
        fed = db.query(GameFederationDB).filter(
            GameFederationDB.id == contract.federation_id
        ).first()
        if fed:
            # Fine: 2 weeks salary
            fine = contract.salary_weekly * 2
            fed.budget += fine  # Federation collects the fine
            db.add(GameNarrativeLogDB(
                world_id=match.world_id,
                game_date=game_date, tick=0,
                event_type="discipline_fine",
                description=f"{shooter.name} fined ${fine:,.0f} for going into business for themselves!",
                involved_entities=[shooter_id, fed.id],
                importance=9,
            ))

            # Strict federations may also suspend
            if (fed.kayfabe_strictness or 50) > 60:
                from game_service.world_ticker import advance_game_date
                suspension_weeks = random.randint(2, 6)
                shooter.is_injured = True  # Use injury system for suspension
                shooter.injury_return_date = advance_game_date(game_date, suspension_weeks * 7)
                db.add(GameNarrativeLogDB(
                    world_id=match.world_id,
                    game_date=game_date, tick=0,
                    event_type="discipline_suspension",
                    description=f"{shooter.name} SUSPENDED for {suspension_weeks} weeks! Management is furious!",
                    involved_entities=[shooter_id, fed.id],
                    importance=9,
                ))

    # --- History entries: permanent memory for both wrestlers ---
    db.add(WrestlerHistoryDB(
        wrestler_id=shooter_id,
        game_date=game_date,
        event_type="went_into_business",
        description=f"Went into business for themselves against {victim.name} — refused to do the job",
        details={"victim": victim_id, "victim_name": victim.name,
                 "match_id": match.id, "was_title_match": match.is_title_match},
    ))
    db.add(WrestlerHistoryDB(
        wrestler_id=victim_id,
        game_date=game_date,
        event_type="business_victim",
        description=f"{shooter.name} went into business for themselves — refused to lose to you",
        details={"shooter": shooter_id, "shooter_name": shooter.name,
                 "match_id": match.id},
    ))

    # --- Morale impact ---
    victim.morale = max(0, victim.morale - random.randint(10, 20))
    shooter.morale = max(0, min(100, shooter.morale + random.randint(-5, 5)))  # Mixed feelings

    # --- Controversial popularity boost for shooter (controversy sells) ---
    shooter.popularity = min(100, shooter.popularity + random.randint(2, 8))

    # --- Narrative log for the world ---
    db.add(GameNarrativeLogDB(
        world_id=match.world_id,
        game_date=game_date, tick=0,
        event_type="went_into_business",
        description=(
            f"BACKSTAGE CHAOS: {shooter.name} went into business for themselves against {victim.name}! "
            f"The planned finish was thrown out the window. Management is LIVID."
        ),
        involved_entities=[shooter_id, victim_id],
        importance=10,  # Maximum importance — this is a defining event
    ))

    logger.info("SHOOT: %s went into business against %s!", shooter.name, victim.name)
