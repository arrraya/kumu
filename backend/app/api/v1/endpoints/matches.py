from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.db import models
from app.schemas import match as match_schemas
from app.services.player_team_matcher import (
    PlayerTeamMatcher,
    Player as MatcherPlayer,
    Team as MatcherTeam,
)
import app.services.player_service as player_service

router = APIRouter()
matcher = PlayerTeamMatcher()


def _sanitize_metrics(metrics: dict) -> dict:
    """Replace None metric values with 0 so the matcher can do arithmetic.

    The pipeline intentionally stores None for metrics it cannot compute
    (contract E.5). Coverage reporting is what keeps that visible; here we
    only need numeric safety.
    """
    clean = {}
    for category, values in (metrics or {}).items():
        if isinstance(values, dict):
            clean[category] = {k: (0.0 if v is None else v) for k, v in values.items()}
    return clean


def _to_matcher_player(db_player) -> MatcherPlayer:
    """Adapt a DB player row to the matcher's Player object."""
    p = MatcherPlayer(
        player_id=str(db_player.id),
        name=db_player.name or "",
        age=db_player.age or 26,
        position=db_player.position or "",
    )
    p.market_value = float(db_player.market_value or 0)
    p.metrics = _sanitize_metrics(db_player.metrics)
    p.performance_history = db_player.performance_history or []
    p.performance_index = db_player.performance_index or None
    return p


def _to_matcher_team(db_team) -> MatcherTeam:
    """Adapt a DB team row to the matcher's Team object."""
    t = MatcherTeam(
        team_id=str(db_team.id),
        name=db_team.name or "",
        league=db_team.league or "",
        budget=float(db_team.budget or 0),
    )
    t.formation = db_team.formation or "4-3-3"
    t.playing_style = db_team.playing_style or {}
    reqs = db_team.requirements or {}
    t.position_needs = reqs.get("positions", [])
    t.performance_requirements = reqs.get("performance", {})
    t.expected_index = reqs.get("expected_index")
    return t


@router.post("/calculate", response_model=List[match_schemas.Match])
async def calculate_matches(
    request: match_schemas.MatchCalculationRequest,
    db: Session = Depends(get_db),
):
    """Calculate player-team compatibility using the real matching algorithm."""
    player = player_service.get_player(db, int(request.player_id))
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # National sides exist as teams so their squads are real, but nobody signs
    # for a country: transfer destinations are clubs only.
    query = db.query(models.Team).filter(
        (models.Team.team_type == "club") | (models.Team.team_type.is_(None))
    )
    if request.team_ids:
        query = query.filter(models.Team.id.in_([int(t) for t in request.team_ids]))
    teams = query.all()
    if not teams:
        raise HTTPException(status_code=404, detail="No teams available for matching")

    matcher_player = _to_matcher_player(player)

    matches = []
    for team in teams:
        matcher_team = _to_matcher_team(team)
        result = matcher.calculate_match_score(matcher_player, matcher_team)
        breakdown = result["breakdown"]

        match = match_schemas.Match(
            team=match_schemas.MatchTeam(
                id=str(team.id),
                name=team.name,
                league=team.league or "",
                logo="",
            ),
            score=match_schemas.MatchScore(
                overall=result["overall_score"],
                tactical=breakdown["tactical_fit"],
                performance=breakdown["performance_match"],
                financial=breakdown["financial_fit"],
                growth=breakdown["growth_potential"],
            ),
            offer=match_schemas.MatchOffer(
                minimum=player.market_value * 0.8,
                maximum=player.market_value * 1.2,
                recommended=player.market_value,
            ),
            recommendation=matcher.generate_recommendation(
                matcher_player, matcher_team, result
            ),
        )

        if match.score.overall >= request.min_score:
            matches.append(match)

    matches.sort(key=lambda x: x.score.overall, reverse=True)
    return matches[:10]
