from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union
from datetime import datetime


class ReportMetadata(BaseModel):
    generated_date: str
    player_name: str
    player_id: Union[str, int]
    team_name: str
    team_id: Union[str, int]
    report_id: Optional[int] = None
    data_coverage: Optional[Dict[str, Any]] = None


class ExecutiveSummary(BaseModel):
    # A goalkeeper whose source carries no goalkeeping is not rated, and the
    # generator returns None for all three rather than recommending him on
    # outfield metrics that say nothing about keeping. Required, they turned
    # that refusal into a ResponseValidationError: no report at all, for the
    # one player the report was right to be careful about.
    recommendation: Optional[str] = None
    action: Optional[str] = None
    match_score: Optional[float] = None
    # Optional because the generator can decline to rank: a goalkeeper whose
    # source carries no goalkeeping gets None, and `int` turned that into a
    # ResponseValidationError — the whole report failing rather than the one
    # figure being absent. The schema has to allow what the generator is
    # right to produce.
    overall_percentile: Optional[int] = None
    # Findings carry their provenance now ({text, origin}); reports
    # stored before that are plain strings and must still deserialise.
    key_findings: List[Any]
    executive_statement: str
    # Reported alongside the ranked percentile so the two are not confused
    metric_percentile_average: Optional[int] = None
    percentile_basis: Optional[str] = None
    # Why there is no rating at all, where there is none: a goalkeeper whose
    # source carries no goalkeeping, for instance.
    basis: Optional[str] = None


class StatisticalOverview(BaseModel):
    position_specific_analysis: Dict[str, Dict[str, Dict]]
    statistical_strengths: List[str]
    statistical_weaknesses: List[str]
    consistency_rating: Dict[str, Any]
    form_trajectory: Dict[str, Any]
    # Which population the percentiles above were measured against, and the
    # sentence that says so when there is none. Undeclared, both were dropped,
    # so every percentile on the page was read against whichever population
    # the reader assumed.
    percentile_population: Optional[str] = None
    percentile_basis: Optional[str] = None
    # Which metrics were left out of the ranking because the source does not
    # carry them. Without it they read as metrics Kumü chose not to show.
    metrics_basis: Optional[str] = None


class TacticalAnalysis(BaseModel):
    formation_compatibility: Dict[str, Any]
    style_compatibility: Dict[str, Any]
    role_suitability: Dict[str, Any]
    tactical_flexibility: Dict[str, Any]
    # Whether the style fit came from measured territory or from the club's
    # declared profile, and how many peers the comparison had.
    peer_group: Optional[Dict[str, Any]] = None
    style_basis: Optional[Dict[str, Any]] = None


class PhysicalProfile(BaseModel):
    athletic_scores: Dict[str, Dict[str, Any]]
    physical_age_analysis: Dict[str, Any]
    injury_risk_factors: Dict[str, Any]
    physical_comparison: Optional[str] = None
    # Says the source carries no tracking data, where it carries none.
    athletic_scores_basis: Optional[str] = None


class MarketAnalysis(BaseModel):
    # Every field here is optional for one reason: a player with no supplied
    # value and too short a log to derive one has no market analysis, and the
    # generator says so in `basis` rather than inventing a figure. Declaring
    # them required made that honest answer fail validation, so the endpoint
    # returned no report at all instead of a report with one section absent.
    current_market_value: Optional[float] = None
    value_assessment: Optional[Dict[str, Any]] = None
    value_projections: Optional[Dict[str, Dict[str, Any]]] = None
    roi_analysis: Optional[Dict[str, Any]] = None
    comparable_transfers: Optional[List[Dict[str, Any]]] = None
    contract_recommendations: Optional[Dict[str, Any]] = None
    financial_risk_assessment: Optional[Dict[str, Any]] = None
    # Says there is no financial analysis, and what would produce one.
    basis: Optional[str] = None


class ComparisonAnalysis(BaseModel):
    squad_comparison: Dict[str, Any]
    league_comparison: Dict[str, Any]
    upgrade_assessment: str
    historical_comparison: Optional[Dict[str, Any]] = None


class RiskAssessment(BaseModel):
    overall_risk_level: str
    risk_score: float
    risk_factors: Dict[str, Dict[str, Any]]
    mitigation_plan: List[str]
    # How many of the five risks the score actually averaged, named one by
    # one. A score over four of five and a score over five read identically
    # without it.
    risk_basis: Optional[str] = None
    decision_impact: Optional[str] = None


class NegotiationStrategy(BaseModel):
    # Optional for the same reason as MarketAnalysis: no fee, no strategy.
    negotiation_position: Optional[Dict[str, Any]] = None
    offer_strategy: Optional[Dict[str, Any]] = None
    timeline: Optional[Dict[str, str]] = None
    tactics: Optional[List[str]] = None
    leverage_factors: Optional[Union[Dict[str, Any], List[Any]]] = None
    key_negotiation_points: Optional[List[Dict[str, Any]]] = None
    contingency_plans: Optional[List[Dict[str, Any]]] = None
    # Says there is no strategy, because there is no fee to build one on.
    basis: Optional[str] = None


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
    # Declared here or dropped on the way out. Pydantic keeps only what the
    # response model lists, so a field added to the generator and not to this
    # class never reaches the interface and nothing fails - the sixth time
    # this has happened in Kumü, and the first where the dropped field was
    # the one that says what the figures were measured against. A report
    # generated today announced that it predated its own basis.
    #
    # Declaring the sixth did not stop the seventh. `StatisticalOverview` was
    # dropping `percentile_basis` while this comment was being written, and a
    # sweep found ten undeclared fields across five sections, four of them
    # the provenance line for their own section. Counting occurrences is not
    # a fix: tests/test_response.py now fails if the generator produces a key
    # this file does not declare, which is the only version of this that
    # cannot reach the eighth.
    source_notes: Optional[List[str]] = None
    basis: Optional[Dict[str, Any]] = None


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
