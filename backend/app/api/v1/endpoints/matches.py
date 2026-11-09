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
from app.core import security

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
        # Absent age travels as None. It used to be laundered into 26 here
        # and the matcher only recovered by recognising that exact number as
        # its own sentinel - which meant a player who really is 26 was
        # treated as having no age at all.
        age=db_player.age,
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
    org_ids: list = Depends(security.readable_org_ids),
):
    """Calculate player-team compatibility using the real matching algorithm."""
    player = player_service.get_player(db, int(request.player_id), org_ids)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    # National sides exist as teams so their squads are real, but nobody signs
    # for a country: transfer destinations are clubs only.
    # Scoped like every other read. This query used to list every club in the
    # database, so one client would have seen another client's private clubs as
    # possible destinations — a leak the tenancy audit missed because the raw
    # listing endpoints were fixed and this one builds its own query.
    query = db.query(models.Team).filter(
        (models.Team.team_type == "club") | (models.Team.team_type.is_(None)),
        models.Team.organization_id.in_(list(org_ids)),
    )
    if request.team_ids:
        query = query.filter(models.Team.id.in_([int(t) for t in request.team_ids]))
    teams = query.all()
    if not teams:
        raise HTTPException(status_code=404, detail="No teams available for matching")

    matcher_player = _to_matcher_player(player)

    # A client may upload a player with no valuation, which the contract allows.
    # The offer range used to multiply that None and 500 the whole request. It
    # now falls back to the same index-based estimate the report uses, so the
    # two never disagree about what the player is worth.
    from app.services.scouting_report_generator import ScoutingReportGenerator

    from app.core import markets

    reference_value = ScoutingReportGenerator()._market_value({
        "market_value": player.market_value,
        "performance_index": player.performance_index,
        "market_anchor": markets.anchor_for(markets.player_market(db, player.id), db),
    })

    matches = []
    for team in teams:
        matcher_team = _to_matcher_team(team)
        result = matcher.calculate_match_score(matcher_player, matcher_team, org_ids)
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
                minimum=reference_value * 0.8,
                maximum=reference_value * 1.2,
                recommended=reference_value,
            ),
            recommendation=matcher.generate_recommendation(
                matcher_player, matcher_team, result
            ),
        )

        if match.score.overall >= request.min_score:
            matches.append(match)

    matches.sort(key=lambda x: x.score.overall, reverse=True)
    return matches[:10]


@router.post("/search", response_model=match_schemas.TeamSearchResponse)
async def search_for_team(
    request: match_schemas.TeamSearchRequest,
    db: Session = Depends(get_db),
    org_ids: list = Depends(security.readable_org_ids),
):
    """Find players for a club, which is the question a scout actually has.

    /calculate takes one player and ranks clubs. This takes one club and
    ranks players. The inversion is not symmetric: ranking a population
    forces two decisions that scoring a single pair never had to make.

    The first is what to do with a player the brief cannot judge. Dropping
    him lets missing data erase a person; filling the gap is the defect this
    codebase keeps finding. Neither happens here: each result reports which
    criteria were assessed and a coverage figure, and the scout can sort on
    it. A player ranked seventh on three of five criteria is a different
    claim from one ranked seventh on all five, and the list says which.

    The second is what to do with a near miss. A filter that silently hides
    a player one year over the age limit is the opposite of a search, so a
    candidate who fails exactly one stated filter is kept, flagged, and
    placed after the clean matches.
    """
    team = (
        db.query(models.Team)
        .filter(models.Team.id == int(request.team_id),
                models.Team.organization_id.in_(list(org_ids)))
        .first()
    )
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    matcher_team = _to_matcher_team(team)

    # The brief: what the club asked for, or what it has declared it needs.
    positions = request.positions or list(matcher_team.position_needs or [])
    brief = [
        match_schemas.SearchCriterion(
            name="Position",
            assessed=bool(positions),
            detail=", ".join(positions) if positions
            else "No position stated and none declared by the club: all positions searched.",
        ),
        match_schemas.SearchCriterion(
            name="Budget",
            assessed=request.max_market_value is not None,
            detail=(f"Up to {request.max_market_value:,.0f}"
                    if request.max_market_value is not None else "No ceiling stated."),
        ),
        match_schemas.SearchCriterion(
            name="Level",
            assessed=request.min_performance_index is not None,
            detail=(f"Index {request.min_performance_index} or better"
                    if request.min_performance_index is not None else "No floor stated."),
        ),
        match_schemas.SearchCriterion(
            name="Age",
            assessed=request.max_age is not None,
            detail=(f"{request.max_age} or younger" if request.max_age is not None
                    else "No age limit stated."),
        ),
    ]

    # The population this club may read: the public reference set plus its own.
    #
    # Loaded whole and scored one by one, which is honest at 307 players and
    # will not survive a league subscription. The shape this wants at scale
    # is two stages: a cheap vectorised pass over the population to shortlist,
    # then this scoring on the few dozen that remain. Writing that now would
    # be optimising a question nobody has asked yet - but the day the
    # population stops fitting in memory, this loop is the thing that breaks,
    # and it breaks loudly rather than quietly, which is the right failure.
    population_q = db.query(models.Player).filter(
        models.Player.organization_id.in_(list(org_ids))
    )
    population = population_q.count()

    candidates = population_q.all()
    if positions:
        wanted = {p.upper() for p in positions}
        candidates = [p for p in candidates if (p.position or "").upper() in wanted]

    squad_ids = {
        m.player_id for m in db.query(models.SquadMembership).filter(
            models.SquadMembership.team_id == team.id,
            models.SquadMembership.left_at.is_(None),
        ).all()
    }
    candidates = [p for p in candidates if p.id not in squad_ids]

    results = []
    for db_player in candidates:
        # Each filter is evaluated rather than applied, so the ones a player
        # fails can be named instead of making him disappear.
        failed = []
        if request.max_market_value is not None:
            value = db_player.market_value
            if isinstance(value, (int, float)) and value > request.max_market_value:
                failed.append("over budget")
        if request.min_performance_index is not None:
            idx = (db_player.performance_index or {}).get("value")
            if isinstance(idx, (int, float)) and idx < request.min_performance_index:
                failed.append("below the level asked for")
        if request.max_age is not None:
            age = db_player.age
            if isinstance(age, (int, float)) and age > request.max_age:
                failed.append("over the age limit")

        if len(failed) > 1:
            continue
        if failed and not request.include_near_misses:
            continue

        matcher_player = _to_matcher_player(db_player)
        scored = matcher.calculate_match_score(matcher_player, matcher_team, org_ids)
        breakdown = scored["breakdown"]

        # Coverage is per player, not per brief: a budget ceiling means
        # nothing for a player the source carries no valuation for, and that
        # is the player's gap, not the club's.
        idx_value = (db_player.performance_index or {}).get("value")
        criteria = [
            match_schemas.SearchCriterion(
                name="Position",
                assessed=bool(db_player.position),
                detail=db_player.position or "Position not recorded for this player.",
            ),
            match_schemas.SearchCriterion(
                name="Budget",
                assessed=isinstance(db_player.market_value, (int, float))
                and db_player.market_value > 0,
                detail=None if isinstance(db_player.market_value, (int, float))
                and db_player.market_value > 0
                else "No valuation carried for this player.",
            ),
            match_schemas.SearchCriterion(
                name="Level",
                assessed=isinstance(idx_value, (int, float)),
                detail=None if isinstance(idx_value, (int, float))
                else "No performance index: too few matches to compute one.",
            ),
            match_schemas.SearchCriterion(
                name="Age",
                assessed=isinstance(db_player.age, (int, float)),
                detail=None if isinstance(db_player.age, (int, float))
                else "No date of birth in this source.",
            ),
        ]
        covered = sum(1 for c in criteria if c.assessed) / len(criteria)

        results.append(match_schemas.SearchResult(
            rank=0,
            player=match_schemas.SearchResultPlayer(
                id=str(db_player.id),
                name=db_player.name or "",
                position=db_player.position,
                nationality=db_player.nationality,
                current_team=db_player.current_team,
                age=db_player.age,
                market_value=db_player.market_value,
                performance_index=idx_value if isinstance(idx_value, (int, float)) else None,
            ),
            score=match_schemas.MatchScore(
                overall=scored["overall_score"],
                tactical=breakdown["tactical_fit"],
                performance=breakdown["performance_match"],
                financial=breakdown["financial_fit"],
                growth=breakdown["growth_potential"],
            ),
            criteria=criteria,
            coverage=round(covered, 3),
            near_miss=bool(failed),
            missed=failed[0] if failed else None,
        ))

    # Clean matches first, then near misses; score decides within each group.
    results.sort(key=lambda r: (r.near_miss, -r.score.overall))
    results = results[: request.limit]
    for i, r in enumerate(results, start=1):
        r.rank = i

    unassessed = [c.name.lower() for c in brief if not c.assessed]
    basis = (
        "Ranked %d of %d players the club may read%s. "
        "Coverage is stated per player: a rank earned on three criteria is "
        "not the same claim as a rank earned on four."
        % (len(results), population,
           ", after excluding its own squad" if squad_ids else "")
    )
    if unassessed:
        basis += " The brief stated no %s." % ", no ".join(unassessed)

    return match_schemas.TeamSearchResponse(
        team=match_schemas.MatchTeam(
            id=str(team.id), name=team.name or "",
            league=team.league or "", logo="",
        ),
        brief=brief,
        population=population,
        considered=len(candidates),
        results=results,
        basis=basis,
    )
