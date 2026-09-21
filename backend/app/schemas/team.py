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
    """Shape shared by every team response.

    Lenient on purpose. This model also serialises teams a client created
    through ingest, where league, country and budget are optional, and a
    response schema that rejects data already stored does not protect anything —
    it just makes the owner's own listing return 500. That is what happened:
    two imported clubs had no country and broke /teams for their organisation.
    Validation belongs on the way in, below, not on the way out.
    """

    name: str
    league: Optional[str] = None
    country: Optional[str] = None
    budget: Optional[float] = Field(None, ge=0)
    # No pattern here: the old one allowed five formations, so a club storing
    # 4-1-4-1 or 3-4-3 — both common — would have broken its own listing too.
    formation: Optional[str] = None


FORMATION_PATTERN = r"^\d(-\d){2,4}$"


class TeamCreate(TeamBase):
    """Input validation lives here, where rejecting bad data is useful."""

    external_id: str
    playing_style: PlayingStyle
    league: str
    country: str
    budget: float = Field(..., ge=0)
    formation: str = Field("4-3-3", pattern=FORMATION_PATTERN)


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
    playing_style: Optional[PlayingStyle] = None
    logo: Optional[str] = None
    # "club" or "national" — the UI needs this to keep national sides out of
    # the transfer market while still showing their real squads.
    team_type: Optional[str] = "club"
    created_at: Optional[datetime] = None

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
