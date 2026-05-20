from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class MatchScore(BaseModel):
    overall: float = Field(..., ge=0, le=100)
    tactical: float = Field(..., ge=0, le=100)
    performance: float = Field(..., ge=0, le=100)
    financial: float = Field(..., ge=0, le=100)
    growth: float = Field(..., ge=0, le=100)


class MatchOffer(BaseModel):
    minimum: float
    maximum: float
    recommended: float


class MatchTeam(BaseModel):
    id: str
    name: str
    league: str
    logo: str


class Match(BaseModel):
    team: MatchTeam
    score: MatchScore
    offer: MatchOffer
    recommendation: str


class MatchCalculationRequest(BaseModel):
    player_id: str
    team_ids: List[str]
    min_score: float = Field(default=70.0, ge=0, le=100)
    include_report: bool = False


class MatchCalculationResponse(BaseModel):
    player_id: str
    matches: List[Match]
    calculation_time: Optional[float] = None


class MatchDetail(BaseModel):
    id: int
    player_id: int
    team_id: int
    match_score: float
    score_breakdown: MatchScore
    calculated_at: datetime
    recommendation: Optional[str] = None

    class Config:
        from_attributes = True


class MatchInDB(MatchDetail):
    pass
