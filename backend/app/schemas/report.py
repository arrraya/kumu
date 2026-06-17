from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime


class ReportMetadata(BaseModel):
    generated_date: str
    player_name: str
    player_id: Union[str, int]
    team_name: str
    team_id: Union[str, int]


class ExecutiveSummary(BaseModel):
    recommendation: str
    action: str
    match_score: float
    overall_percentile: int
    key_findings: List[str]
    executive_statement: str


class StatisticalOverview(BaseModel):
    position_specific_analysis: Dict[str, Dict[str, Dict]]
    statistical_strengths: List[str]
    statistical_weaknesses: List[str]
    consistency_rating: Dict[str, Any]
    form_trajectory: Dict[str, Any]


class TacticalAnalysis(BaseModel):
    formation_compatibility: Dict[str, Any]
    style_compatibility: Dict[str, Any]
    role_suitability: Dict[str, Any]
    tactical_flexibility: Dict[str, Any]


class PhysicalProfile(BaseModel):
    athletic_scores: Dict[str, Dict[str, Any]]
    physical_age_analysis: Dict[str, Any]
    injury_risk_factors: Dict[str, Any]


class MarketAnalysis(BaseModel):
    current_market_value: float
    value_assessment: Dict[str, Any]
    value_projections: Dict[str, Dict[str, Any]]
    roi_analysis: Dict[str, Any]


class ComparisonAnalysis(BaseModel):
    squad_comparison: Dict[str, Any]
    league_comparison: Dict[str, Any]
    upgrade_assessment: str


class RiskAssessment(BaseModel):
    overall_risk_level: str
    risk_score: float
    risk_factors: Dict[str, Dict[str, Any]]
    mitigation_plan: List[str]


class NegotiationStrategy(BaseModel):
    negotiation_position: Dict[str, Any]
    offer_strategy: Dict[str, Any]
    timeline: Dict[str, str]
    tactics: List[str]


class ScoutingReport(BaseModel):
    report_metadata: ReportMetadata
    executive_summary: ExecutiveSummary
    statistical_overview: StatisticalOverview
    tactical_analysis: TacticalAnalysis
    physical_profile: PhysicalProfile
    market_analysis: MarketAnalysis
    comparison_analysis: ComparisonAnalysis
    risk_assessment: RiskAssessment
    negotiation_strategy: NegotiationStrategy


class GenerateReportRequest(BaseModel):
    player_id: str
    team_id: str
    match_id: Optional[int] = None
    sections: List[str] = Field(default=["all"])
    format: str = Field(default="json", pattern=r"^(json|pdf)$")


class ReportInDB(BaseModel):
    id: int
    player_id: int
    team_id: int
    match_id: Optional[int]
    report_data: Dict
    generated_at: datetime

    class Config:
        from_attributes = True
