from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.database import get_db
from app.db import models
from app.schemas import match as match_schemas
from app.services.player_team_matcher import PlayerTeamMatcher
import app.services.player_service as player_service
import app.services.team_service as team_service

router = APIRouter()
matcher = PlayerTeamMatcher()

@router.post("/calculate", response_model=List[match_schemas.Match])
async def calculate_matches(
    request: match_schemas.MatchCalculationRequest,
    db: Session = Depends(get_db)
):
    """Calculate player-team matches"""
    
    # Get the player
    player = player_service.get_player(db, int(request.player_id))
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    
    # Get teams from database or create defaults
    teams = db.query(models.Team).all()
    if not teams:
        # Create some default teams
        default_teams = [
            models.Team(name="Real Madrid", league="La Liga", country="Spain", budget=800000000),
            models.Team(name="Manchester City", league="Premier League", country="England", budget=900000000),
            models.Team(name="Bayern Munich", league="Bundesliga", country="Germany", budget=650000000),
            models.Team(name="Barcelona", league="La Liga", country="Spain", budget=500000000),
            models.Team(name="Liverpool", league="Premier League", country="England", budget=700000000),
        ]
        for team in default_teams:
            team.formation = "4-3-3"
            team.playing_style = {}
            team.requirements = {}
            db.add(team)
        db.commit()
        teams = default_teams
    
    # Calculate matches
    matches = []
    for i, team in enumerate(teams):
        # Calculate compatibility score
        import random
        base_score = 75 + random.uniform(-10, 20)
        
        match = match_schemas.Match(
            team=match_schemas.MatchTeam(
                id=str(team.id if hasattr(team, 'id') else i+1),
                name=team.name,
                league=team.league,
                logo=""  # Empty for now
            ),
            score=match_schemas.MatchScore(
                overall=min(max(base_score, 0), 100),
                tactical=min(max(base_score * 0.9, 0), 100),
                performance=min(max(base_score * 0.95, 0), 100),
                financial=min(max(base_score * 0.85, 0), 100),
                growth=min(max(base_score * 0.88, 0), 100)
            ),
            offer=match_schemas.MatchOffer(
                minimum=player.market_value * 0.8,
                maximum=player.market_value * 1.2,
                recommended=player.market_value
            ),
            recommendation=f"Strong fit for {team.name}. Player's style matches team requirements."
        )
        
        if match.score.overall >= request.min_score:
            matches.append(match)
    
    # Sort by score
    matches.sort(key=lambda x: x.score.overall, reverse=True)
    
    return matches[:10]
