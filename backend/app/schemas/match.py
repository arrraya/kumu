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


# ---------------------------------------------------------------------------
# Club-first search.
#
# Every other entry point in Kumu starts from a named player and asks whether
# he suits a club. A scout does not work that way: the brief comes from the
# club, and the players are what has to be found. These schemas describe that
# question - and, as importantly, describe what the answer could not assess.


class SearchCriterion(BaseModel):
    """One thing the brief asked for, and whether it could be judged.

    A ranked list has to say this out loud. Assessing one player, "not
    assessed" is a panel the reader sees; ranking thousands, an unassessable
    criterion has only two silent outcomes, and both are wrong: drop the
    player, and the missing data erases a person rather than a claim; or fill
    the gap, which is the defect this codebase has spent its life removing.
    So every result carries its own coverage and the scout decides.
    """
    name: str
    assessed: bool
    detail: Optional[str] = None


class SearchResultPlayer(BaseModel):
    id: str
    name: str
    position: Optional[str] = None
    nationality: Optional[str] = None
    current_team: Optional[str] = None
    age: Optional[int] = None
    market_value: Optional[float] = None
    performance_index: Optional[float] = None


class SearchResult(BaseModel):
    rank: int
    player: SearchResultPlayer
    score: MatchScore
    # How much of the brief this score actually speaks to.
    criteria: List[SearchCriterion]
    coverage: float = Field(..., ge=0, le=1)
    # A near miss fails exactly one stated filter. A scout wants the player
    # they were not looking for, and a filter that hides them silently is the
    # opposite of a search.
    near_miss: bool = False
    missed: Optional[str] = None


class TeamSearchRequest(BaseModel):
    team_id: str
    # Omitted: the club's own declared positional needs are used.
    positions: Optional[List[str]] = None
    max_market_value: Optional[float] = None
    min_performance_index: Optional[float] = None
    max_age: Optional[int] = None
    limit: int = Field(default=20, ge=1, le=100)
    include_near_misses: bool = True


class TeamSearchResponse(BaseModel):
    team: MatchTeam
    brief: List[SearchCriterion]
    # Everything the search looked at, before the brief narrowed it.
    population: int
    considered: int
    results: List[SearchResult]
    basis: str
