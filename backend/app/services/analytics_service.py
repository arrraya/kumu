"""
Analytics service module for advanced analytics and performance predictions.

This module orchestrates analytics operations by utilizing existing services
like player_service, player_team_matcher, and scouting_report_generator.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

# Import your existing services - FIXED to avoid circular import
import app.services.player_service as player_service
from app.services.player_team_matcher import PlayerTeamMatcher
from app.services.scouting_report_generator import ScoutingReportGenerator


def run_analysis(
    db: Session,
    analysis_type: str,
    player_ids: List[int],
    parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run advanced analytics based on the specified type.

    Args:
        db: Database session
        analysis_type: Type of analysis to perform
        player_ids: List of player IDs to analyze
        parameters: Additional parameters for the analysis

    Returns:
        Dictionary containing analysis results

    Raises:
        ValueError: If analysis_type is not supported
    """
    if parameters is None:
        parameters = {}

    # Get player data using existing player service
    players = []
    for player_id in player_ids:
        player = player_service.get_player(db, player_id)
        if player:
            players.append(player)

    if not players:
        raise ValueError("No valid players found for analysis")

    # Route to different analysis types
    if analysis_type == "performance_comparison":
        return _performance_comparison_analysis(players, parameters)
    elif analysis_type == "team_fit_analysis":
        return _team_fit_analysis(db, players, parameters)
    elif analysis_type == "scouting_analysis":
        return _scouting_analysis(db, players, parameters)
    elif analysis_type == "statistical_summary":
        return _statistical_summary_analysis(players, parameters)
    else:
        raise ValueError(f"Unsupported analysis type: {analysis_type}")


def predict_performance(
    db: Session,
    player_id: int,
    team_id: Optional[int] = None,
    horizon: str = "season",
    factors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Predict player performance based on various factors.

    Args:
        db: Database session
        player_id: ID of the player to predict performance for
        team_id: Optional team ID for team-specific predictions
        horizon: Prediction horizon ("game", "month", "season")
        factors: List of factors to consider in prediction

    Returns:
        Dictionary containing prediction results
    """
    if factors is None:
        factors = ["historical_performance", "team_fit", "recent_form"]

    # Get player data
    player = player_service.get_player(db, player_id)
    if not player:
        raise ValueError(f"Player with ID {player_id} not found")

    predictions = {
        "player_id": player_id,
        "team_id": team_id,
        "horizon": horizon,
        "factors_considered": factors,
        "predictions": {},
    }

    # Historical performance analysis
    if "historical_performance" in factors:
        historical_stats = player_service.get_player_stats(db, player_id)
        predictions["predictions"]["historical_trend"] = _analyze_historical_trend(historical_stats)

    # Team fit analysis
    if "team_fit" in factors and team_id:
        matcher = PlayerTeamMatcher()
        fit_score = matcher.calculate_fit_score(db, player_id, team_id)
        predictions["predictions"]["team_fit_score"] = fit_score

    # Recent form analysis
    if "recent_form" in factors:
        recent_stats = player_service.get_recent_player_stats(db, player_id, limit=10)
        predictions["predictions"]["recent_form"] = _analyze_recent_form(recent_stats)

    # Generate overall prediction score
    predictions["predictions"]["overall_score"] = _calculate_overall_prediction(
        predictions["predictions"]
    )

    return predictions


def _performance_comparison_analysis(
    players: List[Any], parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Compare performance metrics across multiple players."""
    comparison_metrics = parameters.get("metrics", ["goals", "assists", "minutes_played"])

    results = {
        "analysis_type": "performance_comparison",
        "players_count": len(players),
        "metrics": comparison_metrics,
        "comparison_data": [],
    }

    for player in players:
        player_data = {
            "player_id": player.id,
            "player_name": getattr(player, "name", "Unknown"),
            "metrics": {},
        }

        # Extract metrics for each player
        for metric in comparison_metrics:
            player_data["metrics"][metric] = getattr(player, metric, 0)

        results["comparison_data"].append(player_data)

    return results


def _team_fit_analysis(
    db: Session, players: List[Any], parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Analyze how well players fit with potential teams."""
    target_team_id = parameters.get("target_team_id")

    if not target_team_id:
        raise ValueError("target_team_id required for team fit analysis")

    matcher = PlayerTeamMatcher()
    results = {
        "analysis_type": "team_fit_analysis",
        "target_team_id": target_team_id,
        "fit_scores": [],
    }

    for player in players:
        fit_score = matcher.calculate_fit_score(db, player.id, target_team_id)
        results["fit_scores"].append(
            {
                "player_id": player.id,
                "player_name": getattr(player, "name", "Unknown"),
                "fit_score": fit_score,
            }
        )

    return results


def _scouting_analysis(
    db: Session, players: List[Any], parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate scouting analysis for players."""
    report_generator = ScoutingReportGenerator()
    results = {"analysis_type": "scouting_analysis", "reports": []}

    for player in players:
        report = report_generator.generate_report(db, player.id)
        results["reports"].append(
            {
                "player_id": player.id,
                "player_name": getattr(player, "name", "Unknown"),
                "scouting_report": report,
            }
        )

    return results


def _statistical_summary_analysis(players: List[Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Generate statistical summary for players."""
    metrics = parameters.get("metrics", ["goals", "assists", "minutes_played"])

    results = {
        "analysis_type": "statistical_summary",
        "summary": {"total_players": len(players), "metrics_analyzed": metrics, "statistics": {}},
    }

    # Calculate summary statistics for each metric
    for metric in metrics:
        values = [getattr(player, metric, 0) for player in players]
        if values:
            results["summary"]["statistics"][metric] = {
                "min": min(values),
                "max": max(values),
                "average": sum(values) / len(values),
                "total": sum(values),
            }

    return results


def _analyze_historical_trend(historical_stats: List[Any]) -> Dict[str, Any]:
    """Analyze historical performance trend."""
    if not historical_stats:
        return {"trend": "insufficient_data", "confidence": 0}

    # Simple trend analysis (you can enhance this with more sophisticated algorithms)
    recent_performance = sum(
        getattr(stat, "performance_score", 0) for stat in historical_stats[-5:]
    )
    earlier_performance = sum(
        getattr(stat, "performance_score", 0) for stat in historical_stats[:5]
    )

    if recent_performance > earlier_performance:
        trend = "improving"
    elif recent_performance < earlier_performance:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "confidence": min(len(historical_stats) / 20, 1.0),  # Higher confidence with more data
        "recent_avg": recent_performance / min(5, len(historical_stats)),
        "historical_avg": earlier_performance / min(5, len(historical_stats)),
    }


def _analyze_recent_form(recent_stats: List[Any]) -> Dict[str, Any]:
    """Analyze recent form based on latest statistics."""
    if not recent_stats:
        return {"form": "unknown", "games_analyzed": 0}

    # Calculate recent form score
    total_performance = sum(getattr(stat, "performance_score", 0) for stat in recent_stats)
    avg_performance = total_performance / len(recent_stats)

    if avg_performance >= 80:
        form = "excellent"
    elif avg_performance >= 60:
        form = "good"
    elif avg_performance >= 40:
        form = "average"
    else:
        form = "poor"

    return {
        "form": form,
        "average_score": avg_performance,
        "games_analyzed": len(recent_stats),
        "consistency": _calculate_consistency(recent_stats),
    }


def _calculate_consistency(stats: List[Any]) -> float:
    """Calculate consistency score based on performance variance."""
    if len(stats) < 2:
        return 0.0

    scores = [getattr(stat, "performance_score", 0) for stat in stats]
    avg_score = sum(scores) / len(scores)

    # Calculate variance
    variance = sum((score - avg_score) ** 2 for score in scores) / len(scores)

    # Convert to consistency score (lower variance = higher consistency)
    consistency = max(0, 100 - variance)
    return min(consistency, 100)


def _calculate_overall_prediction(predictions: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate overall prediction score from individual factors."""
    scores = []
    weights = {"historical_trend": 0.4, "team_fit_score": 0.3, "recent_form": 0.3}

    total_weight = 0
    weighted_score = 0

    for factor, weight in weights.items():
        if factor in predictions:
            if factor == "historical_trend":
                score = predictions[factor].get("recent_avg", 0)
            elif factor == "team_fit_score":
                score = (
                    predictions[factor].get("overall_score", 0)
                    if isinstance(predictions[factor], dict)
                    else predictions[factor]
                )
            elif factor == "recent_form":
                score = predictions[factor].get("average_score", 0)
            else:
                continue

            weighted_score += score * weight
            total_weight += weight

    overall_score = weighted_score / total_weight if total_weight > 0 else 0

    return {
        "score": overall_score,
        "confidence": total_weight,  # Confidence based on available data
        "factors_used": list(predictions.keys()),
    }
