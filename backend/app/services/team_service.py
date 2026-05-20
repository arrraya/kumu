"""
Team service module for managing team operations.

This module provides functions for team CRUD operations, team requirements management,
and integration with player matching and analytics services.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime

from app.db import models
from app.schemas import team as team_schemas
from app.services.player_team_matcher import PlayerTeamMatcher

# Moved import inside function to avoid circular import


def get_teams(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    league: Optional[str] = None,
    country: Optional[str] = None,
    min_budget: Optional[float] = None,
    max_budget: Optional[float] = None,
    formation: Optional[str] = None,
) -> List[models.Team]:
    """
    Get teams with optional filtering.

    Args:
        db: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        league: Filter by league name
        country: Filter by country
        min_budget: Minimum budget filter
        max_budget: Maximum budget filter
        formation: Filter by formation

    Returns:
        List of teams matching the criteria
    """
    query = db.query(models.Team)

    if league:
        query = query.filter(models.Team.league == league)
    if country:
        query = query.filter(models.Team.country == country)
    if min_budget is not None:
        query = query.filter(models.Team.budget >= min_budget)
    if max_budget is not None:
        query = query.filter(models.Team.budget <= max_budget)
    if formation:
        query = query.filter(models.Team.formation == formation)

    return query.offset(skip).limit(limit).all()


def get_team(db: Session, team_id: int) -> Optional[models.Team]:
    """
    Get a single team by ID.

    Args:
        db: Database session
        team_id: Team ID

    Returns:
        Team object or None if not found
    """
    return db.query(models.Team).filter(models.Team.id == team_id).first()


def get_team_by_external_id(db: Session, external_id: str) -> Optional[models.Team]:
    """
    Get a team by external ID.

    Args:
        db: Database session
        external_id: External team ID

    Returns:
        Team object or None if not found
    """
    return db.query(models.Team).filter(models.Team.external_id == external_id).first()


def create_team(db: Session, team: team_schemas.TeamCreate) -> models.Team:
    """
    Create a new team.

    Args:
        db: Database session
        team: Team creation data

    Returns:
        Created team object
    """
    db_team = models.Team(
        external_id=team.external_id,
        name=team.name,
        league=team.league,
        country=team.country,
        budget=team.budget,
        formation=team.formation,
        playing_style=team.playing_style.dict() if team.playing_style else {},
        created_at=datetime.utcnow(),
    )

    db.add(db_team)
    db.commit()
    db.refresh(db_team)

    return db_team


def update_team(
    db: Session, team_id: int, team_update: team_schemas.TeamUpdate
) -> Optional[models.Team]:
    """
    Update an existing team.

    Args:
        db: Database session
        team_id: Team ID to update
        team_update: Update data

    Returns:
        Updated team object or None if not found
    """
    db_team = get_team(db, team_id)
    if not db_team:
        return None

    update_data = team_update.dict(exclude_unset=True)

    # Handle nested playing_style object
    if "playing_style" in update_data and update_data["playing_style"]:
        update_data["playing_style"] = update_data["playing_style"].dict()

    for field, value in update_data.items():
        setattr(db_team, field, value)

    db.commit()
    db.refresh(db_team)

    return db_team


def delete_team(db: Session, team_id: int) -> bool:
    """
    Delete a team.

    Args:
        db: Database session
        team_id: Team ID to delete

    Returns:
        True if deleted, False if not found
    """
    db_team = get_team(db, team_id)
    if not db_team:
        return False

    db.delete(db_team)
    db.commit()

    return True


def set_team_requirements(
    db: Session, team_id: int, requirements: team_schemas.TeamRequirements
) -> Optional[models.Team]:
    """
    Set or update team requirements for player matching.

    Args:
        db: Database session
        team_id: Team ID
        requirements: Team requirements data

    Returns:
        Updated team object or None if not found
    """
    db_team = get_team(db, team_id)
    if not db_team:
        return None

    db_team.requirements = requirements.dict()

    db.commit()
    db.refresh(db_team)

    return db_team


def get_team_requirements(db: Session, team_id: int) -> Optional[Dict[str, Any]]:
    """
    Get team requirements for player matching.

    Args:
        db: Database session
        team_id: Team ID

    Returns:
        Team requirements dictionary or None
    """
    db_team = get_team(db, team_id)
    if not db_team or not db_team.requirements:
        return None

    # Return the requirements dict which should match TeamRequirements schema
    return db_team.requirements


def find_matching_players(
    db: Session,
    team_id: int,
    min_match_score: float = 70.0,
    position_filter: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Find players that match team requirements.

    Args:
        db: Database session
        team_id: Team ID
        min_match_score: Minimum match score threshold
        position_filter: Optional position filter
        limit: Maximum number of results

    Returns:
        List of matching players with scores
    """
    db_team = get_team(db, team_id)
    if not db_team:
        return []

    # Get all potential players
    query = db.query(models.Player)

    # Apply position filter if specified
    if position_filter:
        query = query.filter(models.Player.position == position_filter)
    elif db_team.requirements:
        # Filter by required positions if available
        positions_needed = db_team.requirements.get("positions_needed", [])
        if positions_needed:
            query = query.filter(models.Player.position.in_(positions_needed))

    # Apply budget constraints
    if db_team.budget:
        query = query.filter(models.Player.market_value <= db_team.budget * 0.5)

    players = query.all()

    # Initialize matcher
    matcher = PlayerTeamMatcher()
    matches = []

    for player in players:
        # Calculate match score
        try:
            match_result = matcher.calculate_fit_score(db, player.id, team_id)

            if match_result.get("overall_score", 0) >= min_match_score:
                matches.append(
                    {
                        "player_id": player.id,
                        "player_name": player.name,
                        "position": player.position,
                        "age": player.age,
                        "market_value": player.market_value,
                        "match_score": match_result.get("overall_score", 0),
                        "score_breakdown": match_result.get("breakdown", {}),
                    }
                )
        except Exception as e:
            # Skip players that cause errors in matching
            continue

    # Sort by match score and limit results
    matches.sort(key=lambda x: x["match_score"], reverse=True)

    return matches[:limit]


def get_team_analytics(
    db: Session, team_id: int, analysis_type: str = "squad_analysis"
) -> Optional[Dict[str, Any]]:
    """
    Get analytics for a team's current squad.

    Args:
        db: Database session
        team_id: Team ID
        analysis_type: Type of analysis to perform

    Returns:
        Analytics results or None if team not found
    """

    # Import move inside the function to avoid circular import
    from app.services.analytics_service import run_analysis

    db_team = get_team(db, team_id)
    if not db_team:
        return None

    # Get all players currently in the team
    # This assumes you have a way to track current squad
    # You might need a separate table for this
    squad_players = db.query(models.Player).filter(models.Player.current_team == db_team.name).all()

    if not squad_players:
        return {
            "team_id": team_id,
            "team_name": db_team.name,
            "analysis_type": analysis_type,
            "message": "No players found in current squad",
        }

    player_ids = [player.id for player in squad_players]

    # Run analysis on the squad
    analytics = run_analysis(
        db,
        analysis_type="statistical_summary",
        player_ids=player_ids,
        parameters={"metrics": ["goals", "assists", "minutes_played", "pass_completion"]},
    )

    # Add team-specific context
    analytics["team_context"] = {
        "team_id": team_id,
        "team_name": db_team.name,
        "formation": db_team.formation,
        "budget": db_team.budget,
        "squad_size": len(squad_players),
    }

    return analytics


def get_team_matches(
    db: Session, team_id: int, min_score: Optional[float] = None, limit: int = 50
) -> List[models.PlayerTeamMatch]:
    """
    Get all player-team matches for a specific team.

    Args:
        db: Database session
        team_id: Team ID
        min_score: Minimum match score filter
        limit: Maximum number of results

    Returns:
        List of player-team match records
    """
    query = db.query(models.PlayerTeamMatch).filter(models.PlayerTeamMatch.team_id == team_id)

    if min_score is not None:
        query = query.filter(models.PlayerTeamMatch.match_score >= min_score)

    return query.order_by(models.PlayerTeamMatch.match_score.desc()).limit(limit).all()


def get_team_scouting_reports(
    db: Session, team_id: int, player_id: Optional[int] = None, limit: int = 20
) -> List[models.ScoutingReport]:
    """
    Get scouting reports for a team.

    Args:
        db: Database session
        team_id: Team ID
        player_id: Optional filter by specific player
        limit: Maximum number of results

    Returns:
        List of scouting reports
    """
    query = db.query(models.ScoutingReport).filter(models.ScoutingReport.team_id == team_id)

    if player_id:
        query = query.filter(models.ScoutingReport.player_id == player_id)

    return query.order_by(models.ScoutingReport.generated_at.desc()).limit(limit).all()


def compare_teams(
    db: Session, team_ids: List[int], metrics: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Compare multiple teams across various metrics.

    Args:
        db: Database session
        team_ids: List of team IDs to compare
        metrics: Optional list of metrics to compare

    Returns:
        Comparison results
    """
    if not metrics:
        metrics = ["budget", "formation", "league", "country"]

    teams_data = []

    for team_id in team_ids:
        team = get_team(db, team_id)
        if team:
            team_data = {"id": team.id, "name": team.name, "metrics": {}}

            for metric in metrics:
                team_data["metrics"][metric] = getattr(team, metric, None)

            # Add playing style if requested
            if "playing_style" in metrics and team.playing_style:
                team_data["metrics"]["playing_style"] = team.playing_style

            # Add requirements if requested
            if "requirements" in metrics and team.requirements:
                team_data["metrics"]["requirements"] = team.requirements

            teams_data.append(team_data)

    return {
        "comparison_type": "team_comparison",
        "teams_count": len(teams_data),
        "metrics_compared": metrics,
        "teams": teams_data,
    }


def get_teams_by_league(
    db: Session, league: str, skip: int = 0, limit: int = 50
) -> List[models.Team]:
    """
    Get all teams in a specific league.

    Args:
        db: Database session
        league: League name
        skip: Number of records to skip
        limit: Maximum number of records

    Returns:
        List of teams in the league
    """
    return (
        db.query(models.Team).filter(models.Team.league == league).offset(skip).limit(limit).all()
    )


def get_teams_needing_position(
    db: Session, position: str, min_budget: Optional[float] = None
) -> List[models.Team]:
    """
    Find teams that need a specific position.

    Args:
        db: Database session
        position: Position needed
        min_budget: Minimum budget requirement

    Returns:
        List of teams needing the position
    """
    teams = db.query(models.Team).all()

    matching_teams = []
    for team in teams:
        if team.requirements:
            positions_needed = team.requirements.get("positions_needed", [])
            priority_positions = team.requirements.get("priority_positions", [])

            if position in positions_needed or position in priority_positions:
                if min_budget is None or team.budget >= min_budget:
                    matching_teams.append(team)

    return matching_teams


def update_team_budget(db: Session, team_id: int, new_budget: float) -> Optional[models.Team]:
    """
    Update a team's transfer budget.

    Args:
        db: Database session
        team_id: Team ID
        new_budget: New budget amount

    Returns:
        Updated team object or None
    """
    db_team = get_team(db, team_id)
    if not db_team:
        return None

    db_team.budget = new_budget

    db.commit()
    db.refresh(db_team)

    return db_team


def get_team_statistics(db: Session, team_id: int) -> Dict[str, Any]:
    """
    Get comprehensive statistics for a team.

    Args:
        db: Database session
        team_id: Team ID

    Returns:
        Team statistics dictionary
    """
    db_team = get_team(db, team_id)
    if not db_team:
        return {}

    # Get squad statistics
    squad = db.query(models.Player).filter(models.Player.current_team == db_team.name).all()

    # Calculate various statistics
    stats = {
        "team_id": team_id,
        "team_name": db_team.name,
        "squad_size": len(squad),
        "total_market_value": sum(p.market_value for p in squad) if squad else 0,
        "average_age": sum(p.age for p in squad) / len(squad) if squad else 0,
        "budget_remaining": db_team.budget,
        "formation": db_team.formation,
        "league": db_team.league,
        "country": db_team.country,
    }

    # Position distribution
    position_count = {}
    for player in squad:
        position_count[player.position] = position_count.get(player.position, 0) + 1
    stats["position_distribution"] = position_count

    # Age distribution
    age_groups = {
        "under_23": len([p for p in squad if p.age < 23]),
        "23_to_27": len([p for p in squad if 23 <= p.age <= 27]),
        "28_to_32": len([p for p in squad if 28 <= p.age <= 32]),
        "over_32": len([p for p in squad if p.age > 32]),
    }
    stats["age_distribution"] = age_groups

    # Nationality distribution
    nationality_count = {}
    for player in squad:
        nationality_count[player.nationality] = nationality_count.get(player.nationality, 0) + 1
    stats["nationality_distribution"] = nationality_count

    return stats
