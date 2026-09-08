from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db import models
from app.core.ml_models import PlayerAnalyzer
from app.db.tenancy import get_scoped, scope
from typing import Optional, List

player_analyzer = PlayerAnalyzer()

def get_players(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    position: Optional[str] = None,
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
    search: Optional[str] = None,
    org_ids: Optional[List[int]] = None,
) -> List[models.Player]:
    # Only query database - don't call external APIs for now
    query = scope(db.query(models.Player), models.Player, org_ids)
    
    if search:
        # Case-insensitive search on multiple fields
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                models.Player.name.ilike(search_pattern),
                models.Player.nationality.ilike(search_pattern),
                models.Player.current_team.ilike(search_pattern)
            )
        )
    if position:
        query = query.filter(models.Player.position == position)
    if min_age:
        query = query.filter(models.Player.age >= min_age)
    if max_age:
        query = query.filter(models.Player.age <= max_age)
    
    return query.offset(skip).limit(limit).all()

def get_player(db: Session, player_id: int, org_ids=None) -> Optional[models.Player]:
    return get_scoped(db, models.Player, player_id, org_ids)

def get_player_analytics(db: Session, player_id: int, period: str, org_ids=None):
    player = get_player(db, player_id, org_ids)
    if not player:
        return None
    analytics = player_analyzer.analyze_player(player, period)
    return analytics
