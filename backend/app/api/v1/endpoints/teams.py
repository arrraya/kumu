from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.schemas import team as team_schemas
import app.services.team_service as team_service

router = APIRouter()


@router.get("/", response_model=List[team_schemas.Team])
def get_teams(
    skip: int = 0,
    limit: int = 20,
    league: Optional[str] = None,
    country: Optional[str] = None,
    min_budget: Optional[float] = None,
    max_budget: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """Get all teams with optional filters"""
    teams = team_service.get_teams(
        db,
        skip=skip,
        limit=limit,
        league=league,
        country=country,
        min_budget=min_budget,
        max_budget=max_budget,
    )
    return teams


@router.get("/{team_id}", response_model=team_schemas.TeamDetail)
def get_team(team_id: int, db: Session = Depends(get_db)):
    """Get detailed team information"""
    team = team_service.get_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.get("/{team_id}/requirements", response_model=team_schemas.TeamRequirements)
def get_team_requirements(team_id: int, db: Session = Depends(get_db)):
    """Get team requirements and needs"""
    requirements = team_service.get_team_requirements(db, team_id)
    if not requirements:
        raise HTTPException(status_code=404, detail="Team not found")
    return requirements


@router.post("/", response_model=team_schemas.Team)
def create_team(team: team_schemas.TeamCreate, db: Session = Depends(get_db)):
    """Create a new team"""
    return team_service.create_team(db, team)


@router.put("/{team_id}", response_model=team_schemas.Team)
def update_team(team_id: int, team_update: team_schemas.TeamUpdate, db: Session = Depends(get_db)):
    """Update team information"""
    team = team_service.update_team(db, team_id, team_update)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.delete("/{team_id}")
def delete_team(team_id: int, db: Session = Depends(get_db)):
    """Delete a team"""
    success = team_service.delete_team(db, team_id)
    if not success:
        raise HTTPException(status_code=404, detail="Team not found")
    return {"message": "Team deleted successfully"}


# --- Team Requirements Management ---


@router.post("/{team_id}/requirements", response_model=team_schemas.Team)
def set_team_requirements(
    team_id: int, requirements: team_schemas.TeamRequirements, db: Session = Depends(get_db)
):
    """Set or update team requirements for player matching"""
    team = team_service.set_team_requirements(db, team_id, requirements)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


# --- Player Matching & Discovery ---


@router.get("/{team_id}/matching-players")
def find_matching_players(
    team_id: int,
    min_match_score: float = Query(70.0, ge=0, le=100, description="Minimum match score (0-100)"),
    position: Optional[str] = Query(None, description="Filter by specific position"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    db: Session = Depends(get_db),
):
    """Find players that match team requirements"""
    matches = team_service.find_matching_players(db, team_id, min_match_score, position, limit)
    if not matches:
        return {"message": "No matching players found", "matches": []}
    return {"team_id": team_id, "matches": matches}


@router.get("/needing-position/{position}")
def get_teams_needing_position(
    position: str,
    min_budget: Optional[float] = Query(None, description="Minimum budget requirement"),
    db: Session = Depends(get_db),
):
    """Find all teams that need a specific position"""
    teams = team_service.get_teams_needing_position(db, position, min_budget)
    return {"position": position, "teams_count": len(teams), "teams": teams}


# --- Analytics & Statistics ---


@router.get("/{team_id}/analytics")
def get_team_analytics(
    team_id: int,
    analysis_type: str = Query("squad_analysis", description="Type of analysis to perform"),
    db: Session = Depends(get_db),
):
    """Get analytics for team's current squad"""
    analytics = team_service.get_team_analytics(db, team_id, analysis_type)
    if not analytics:
        raise HTTPException(status_code=404, detail="Team not found")
    return analytics


@router.get("/{team_id}/statistics")
def get_team_statistics(team_id: int, db: Session = Depends(get_db)):
    """Get comprehensive team statistics including squad composition"""
    stats = team_service.get_team_statistics(db, team_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Team not found")
    return stats


# --- Matches & Reports ---


@router.get("/{team_id}/matches")
def get_team_matches(
    team_id: int,
    min_score: Optional[float] = Query(
        None, ge=0, le=100, description="Minimum match score filter"
    ),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
    db: Session = Depends(get_db),
):
    """Get all player-team match records for a specific team"""
    matches = team_service.get_team_matches(db, team_id, min_score, limit)
    return {"team_id": team_id, "total_matches": len(matches), "matches": matches}


@router.get("/{team_id}/scouting-reports")
def get_team_scouting_reports(
    team_id: int,
    player_id: Optional[int] = Query(None, description="Filter by specific player"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of reports"),
    db: Session = Depends(get_db),
):
    """Get scouting reports for a team"""
    reports = team_service.get_team_scouting_reports(db, team_id, player_id, limit)
    return {"team_id": team_id, "total_reports": len(reports), "reports": reports}


# --- Comparison & League Operations ---


@router.post("/compare")
def compare_teams(
    team_ids: List[int],
    metrics: Optional[List[str]] = Query(
        None,
        description="Metrics to compare (budget, formation, league, country, playing_style, requirements)",
    ),
    db: Session = Depends(get_db),
):
    """Compare multiple teams across various metrics"""
    if len(team_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 team IDs required for comparison")
    if len(team_ids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 teams can be compared at once")

    comparison = team_service.compare_teams(db, team_ids, metrics)
    return comparison


@router.get("/league/{league}")
def get_teams_by_league(league: str, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    """Get all teams in a specific league"""
    teams = team_service.get_teams_by_league(db, league, skip, limit)
    return {"league": league, "teams_count": len(teams), "teams": teams}


# --- Budget Management ---


@router.patch("/{team_id}/budget")
def update_team_budget(
    team_id: int,
    new_budget: float = Query(..., ge=0, description="New budget amount"),
    db: Session = Depends(get_db),
):
    """Update a team's transfer budget"""
    team = team_service.update_team_budget(db, team_id, new_budget)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return {
        "team_id": team_id,
        "team_name": team.name,
        "old_budget": team.budget,
        "new_budget": new_budget,
        "message": "Budget updated successfully",
    }


# --- Search & Discovery ---


@router.get("/search/by-external-id/{external_id}", response_model=team_schemas.Team)
def get_team_by_external_id(external_id: str, db: Session = Depends(get_db)):
    """Get a team by its external ID"""
    team = team_service.get_team_by_external_id(db, external_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


# --- Bulk Operations ---


@router.get("/stats/summary")
def get_all_teams_summary(
    league: Optional[str] = None, country: Optional[str] = None, db: Session = Depends(get_db)
):
    """Get summary statistics for all teams or filtered subset"""
    teams = team_service.get_teams(db, limit=1000, league=league, country=country)

    if not teams:
        return {"message": "No teams found", "summary": {}}

    total_budget = sum(team.budget for team in teams)
    avg_budget = total_budget / len(teams) if teams else 0

    leagues = {}
    countries = {}
    formations = {}

    for team in teams:
        leagues[team.league] = leagues.get(team.league, 0) + 1
        countries[team.country] = countries.get(team.country, 0) + 1
        formations[team.formation] = formations.get(team.formation, 0) + 1

    return {
        "total_teams": len(teams),
        "total_budget": total_budget,
        "average_budget": avg_budget,
        "leagues_distribution": leagues,
        "countries_distribution": countries,
        "formations_distribution": formations,
    }
