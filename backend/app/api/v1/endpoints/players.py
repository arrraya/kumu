from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.database import get_db
from app.schemas import player as player_schemas
import app.services.player_service as player_service

router = APIRouter()


@router.get("/", response_model=List[player_schemas.Player])
def get_players(
    skip: int = 0,
    limit: int = 20,
    position: Optional[str] = None,
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get all players with optional filters"""
    players = player_service.get_players(
        db, skip=skip, limit=limit, position=position, min_age=min_age, max_age=max_age
, search=search
    )
    return players


@router.get("/{player_id}", response_model=player_schemas.PlayerDetail)
def get_player(player_id: int, db: Session = Depends(get_db)):
    """Get detailed player information"""
    player = player_service.get_player(db, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


@router.get("/{player_id}/analytics")
def get_player_analytics(
    player_id: int,
    period: str = Query("last_10", enum=["last_5", "last_10", "season", "all"]),
    db: Session = Depends(get_db),
):
    """Get player analytics data"""
    analytics = player_service.get_player_analytics(db, player_id, period)
    return analytics
