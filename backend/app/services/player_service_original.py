from sqlalchemy.orm import Session
from app.db import models
from app.core.ml_models import PlayerAnalyzer
from typing import Optional, List

player_analyzer = PlayerAnalyzer()


def get_players(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    position: Optional[str] = None,
    min_age: Optional[int] = None,
    max_age: Optional[int] = None,
) -> List[models.Player]:
    query = db.query(models.Player)

    if position:
        query = query.filter(models.Player.position == position)
    if min_age:
        query = query.filter(models.Player.age >= min_age)
    if max_age:
        query = query.filter(models.Player.age <= max_age)

    return query.offset(skip).limit(limit).all()


def get_player(db: Session, player_id: int) -> Optional[models.Player]:
    return db.query(models.Player).filter(models.Player.id == player_id).first()


def get_player_analytics(db: Session, player_id: int, period: str):
    player = get_player(db, player_id)
    if not player:
        return None

    # Use the ML model to analyze player performance
    analytics = player_analyzer.analyze_player(player, period)
    return analytics
