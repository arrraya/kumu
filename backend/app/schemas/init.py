# Import all schemas for easy access
from .player import (
    Player,
    PlayerCreate,
    PlayerUpdate,
    PlayerDetail,
    PlayerInDB,
    PerformanceIndex,
    PlayerMetrics,
    RecentForm,
    InjuryHistory,
)
from .team import Team, TeamCreate, TeamUpdate, TeamDetail, TeamInDB, PlayingStyle, TeamRequirements
from .match import (
    Match,
    MatchScore,
    MatchOffer,
    MatchCalculationRequest,
    MatchCalculationResponse,
    MatchDetail,
    MatchInDB,
)
from .report import (
    ScoutingReport,
    GenerateReportRequest,
    ReportInDB,
    ExecutiveSummary,
    NegotiationStrategy,
)
from .analytics import (
    AdvancedAnalyticsRequest,
    AnalyticsResult,
    PredictionRequest,
    PredictionResult,
)

__all__ = [
    # Player schemas
    "Player",
    "PlayerCreate",
    "PlayerUpdate",
    "PlayerDetail",
    "PlayerInDB",
    "PerformanceIndex",
    "PlayerMetrics",
    "RecentForm",
    "InjuryHistory",
    # Team schemas
    "Team",
    "TeamCreate",
    "TeamUpdate",
    "TeamDetail",
    "TeamInDB",
    "PlayingStyle",
    "TeamRequirements",
    # Match schemas
    "Match",
    "MatchScore",
    "MatchOffer",
    "MatchCalculationRequest",
    "MatchCalculationResponse",
    "MatchDetail",
    "MatchInDB",
    # Report schemas
    "ScoutingReport",
    "GenerateReportRequest",
    "ReportInDB",
    "ExecutiveSummary",
    "NegotiationStrategy",
    # Analytics schemas
    "AdvancedAnalyticsRequest",
    "AnalyticsResult",
    "PredictionRequest",
    "PredictionResult",
]
