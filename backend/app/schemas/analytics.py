from pydantic import BaseModel, Field
from typing import Dict, List, Any
from datetime import datetime


class AdvancedAnalyticsRequest(BaseModel):
    type: str = Field(
        ..., pattern=r"^(playing_style_clustering|performance_prediction|tactical_analysis)$"
    )
    player_ids: List[str]
    parameters: Dict[str, Any] = Field(default={})


class AnalyticsResult(BaseModel):
    analysis_id: str
    type: str
    results: Dict[str, Any]
    generated_at: datetime


class PredictionRequest(BaseModel):
    player_id: str
    team_id: str
    horizon: str = Field(..., pattern=r"^(next_match|next_5|next_season)$")
    factors: List[str] = Field(default=["age", "form", "team_fit"])


class PredictionResult(BaseModel):
    player_id: str
    team_id: str
    predictions: Dict[str, float]
    confidence_intervals: Dict[str, tuple]
    factors_impact: Dict[str, float]
