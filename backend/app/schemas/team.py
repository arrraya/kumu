from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime


class PlayingStyle(BaseModel):
    # Support both old and new data formats
    style: Optional[str] = None
    tempo: Optional[str] = None
    possession: Optional[float] = Field(default=0.5, ge=0, le=1)
    pressing_intensity: Optional[float] = Field(default=0.5, ge=0, le=1)
    defensive_line: Optional[str] = Field(default="medium", pattern=r"^(high|medium|low)$")
    attacking: Optional[bool] = False
    high_press: Optional[bool] = False
    build_up: Optional[str] = Field(None, pattern=r"^(short|long|mixed)$")
    chance_creation: Optional[str] = Field(None, pattern=r"^(through_middle|wings|mixed)$")


class TeamRequirements(BaseModel):
    positions_needed: List[str]
    priority_positions: List[str]
    performance_thresholds: Dict[str, float]
    tactical_preferences: Dict[str, Any]
    financial_constraints: Dict[str, float]


class TeamBase(BaseModel):
    name: str
    league: str
    country: str
    budget: float = Field(..., ge=0)
    formation: str = Field(..., pattern=r"^(4-3-3|4-4-2|4-2-3-1|3-5-2|5-3-2)$")


class TeamCreate(TeamBase):
    external_id: str
    playing_style: PlayingStyle


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    league: Optional[str] = None
    country: Optional[str] = None
    budget: Optional[float] = None
    formation: Optional[str] = None
    playing_style: Optional[PlayingStyle] = None


class Team(TeamBase):
    id: int
    external_id: Optional[str] = None  # Make optional since some teams don't have external IDs
    playing_style: PlayingStyle
    logo: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class TeamDetail(Team):
    stadium: Optional[str] = None
    capacity: Optional[int] = None
    manager: Optional[str] = None
    wage_budget: Optional[float] = None
    current_squad_size: Optional[int] = None
    average_age: Optional[float] = None
    requirements: Optional[TeamRequirements] = None

    class Config:
        from_attributes = True


class TeamInDB(Team):
    pass
