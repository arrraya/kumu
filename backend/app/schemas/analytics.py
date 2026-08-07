"""Analytics request/response schemas.

Aligned with what analytics_service actually implements. The previous version
allowed only three analysis types, none of which existed in the service, so the
/analytics/advanced endpoint could not be called successfully at all.
"""
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

ANALYSIS_TYPES = r"^(performance_comparison|team_fit_analysis|scouting_analysis|statistical_summary)$"
PREDICTION_FACTORS = ["historical_performance", "team_fit", "recent_form"]


class AdvancedAnalyticsRequest(BaseModel):
    type: str = Field(..., pattern=ANALYSIS_TYPES)
    # IDs arrive as ints or strings depending on the caller; the service casts.
    player_ids: List[Union[int, str]]
    parameters: Dict[str, Any] = Field(default_factory=dict)


class AnalyticsResult(BaseModel):
    analysis_type: str
    results: Dict[str, Any]


class PredictionRequest(BaseModel):
    player_id: Union[int, str]
    team_id: Optional[Union[int, str]] = None
    horizon: str = Field(default="next_5", pattern=r"^(next_match|next_5|next_season)$")
    factors: List[str] = Field(default_factory=lambda: list(PREDICTION_FACTORS))


class PredictionResult(BaseModel):
    player_id: Union[int, str]
    team_id: Optional[Union[int, str]] = None
    horizon: str
    factors_considered: List[str]
    matches_available: int
    # Nested per-factor results, not flat floats.
    predictions: Dict[str, Any]
