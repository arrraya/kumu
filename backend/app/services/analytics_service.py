"""Analytics service.

Rewritten against the data contract the pipeline actually writes. The previous
version was built for a per-match statistics table with a `performance_score`
column that never existed: it called `player_service.get_player_stats` and
`get_recent_player_stats` (neither of which exist) and
`ScoutingReportGenerator.generate_report` (wrong name and signature), and read
metrics as ORM attributes when they live inside the `metrics` JSON column.
Everything here now reads `metrics` and `performance_history`.
"""
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

import app.services.player_service as player_service
from app.services.player_team_matcher import PlayerTeamMatcher
from app.services.scouting_report_generator import ScoutingReportGenerator

DEFAULT_METRICS = ["goals_per_90", "assists_per_90", "key_passes_per_90", "completion_rate"]


def _metric_value(player: Any, metric: str) -> Optional[float]:
    """Read a metric from the player's `metrics` JSON, whatever category holds it."""
    metrics = getattr(player, "metrics", None) or {}
    for values in metrics.values():
        if isinstance(values, dict) and metric in values:
            value = values[metric]
            if isinstance(value, (int, float)):
                return float(value)
    return None


def _ratings(player: Any) -> List[float]:
    """Per-match ratings from performance_history (the real series)."""
    history = getattr(player, "performance_history", None) or []
    return [
        float(h["rating"])
        for h in history
        if isinstance(h, dict) and isinstance(h.get("rating"), (int, float))
    ]


def run_analysis(
    db: Session,
    analysis_type: str,
    player_ids: List[int],
    parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run advanced analytics of the requested type over the given players."""
    if parameters is None:
        parameters = {}

    players = [p for p in (player_service.get_player(db, pid) for pid in player_ids) if p]
    if not players:
        raise ValueError("No valid players found for analysis")

    if analysis_type == "performance_comparison":
        return _performance_comparison_analysis(players, parameters)
    if analysis_type == "team_fit_analysis":
        return _team_fit_analysis(db, players, parameters)
    if analysis_type == "scouting_analysis":
        return _scouting_analysis(db, players, parameters)
    if analysis_type == "statistical_summary":
        return _statistical_summary_analysis(players, parameters)
    raise ValueError(f"Unsupported analysis type: {analysis_type}")


def predict_performance(
    db: Session,
    player_id: int,
    team_id: Optional[int] = None,
    horizon: str = "next_5",
    factors: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Project a player's outlook from their own match history and club fit."""
    if factors is None:
        factors = ["historical_performance", "team_fit", "recent_form"]

    player = player_service.get_player(db, int(player_id))
    if not player:
        raise ValueError("Player not found")

    ratings = _ratings(player)
    predictions: Dict[str, Any] = {
        "player_id": player_id,
        "team_id": team_id,
        "horizon": horizon,
        "factors_considered": factors,
        "matches_available": len(ratings),
        "predictions": {},
    }

    if "historical_performance" in factors:
        predictions["predictions"]["historical_trend"] = _analyze_historical_trend(ratings)

    if "team_fit" in factors and team_id:
        matcher = PlayerTeamMatcher()
        predictions["predictions"]["team_fit_score"] = matcher.calculate_fit_score(
            db, player_id, team_id
        )

    if "recent_form" in factors:
        predictions["predictions"]["recent_form"] = _analyze_recent_form(ratings[-5:])

    predictions["predictions"]["overall_score"] = _calculate_overall_prediction(
        predictions["predictions"]
    )
    return predictions


def _performance_comparison_analysis(
    players: List[Any], parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Compare metrics across players, marking what is genuinely unavailable."""
    metrics = parameters.get("metrics") or DEFAULT_METRICS

    return {
        "analysis_type": "performance_comparison",
        "players_count": len(players),
        "metrics": metrics,
        "comparison_data": [
            {
                "player_id": p.id,
                "player_name": getattr(p, "name", "Unknown"),
                "position": getattr(p, "position", None),
                "metrics": {m: _metric_value(p, m) for m in metrics},
            }
            for p in players
        ],
    }


def _team_fit_analysis(
    db: Session, players: List[Any], parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Score how well each player fits a target club."""
    target_team_id = parameters.get("target_team_id")
    if not target_team_id:
        raise ValueError("target_team_id required for team fit analysis")

    matcher = PlayerTeamMatcher()
    fit_scores = []
    for player in players:
        result = matcher.calculate_fit_score(db, player.id, target_team_id)
        fit_scores.append(
            {
                "player_id": player.id,
                "player_name": getattr(player, "name", "Unknown"),
                "overall_score": result.get("overall_score", 0),
                "breakdown": result.get("breakdown", {}),
            }
        )

    fit_scores.sort(key=lambda x: x["overall_score"], reverse=True)
    return {
        "analysis_type": "team_fit_analysis",
        "target_team_id": target_team_id,
        "fit_scores": fit_scores,
    }


def _scouting_analysis(db: Session, players: List[Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
    """Generate full scouting reports against a target club."""
    from app.db import models  # local import keeps this module import-safe

    target_team_id = parameters.get("target_team_id")
    if not target_team_id:
        raise ValueError("target_team_id required for scouting analysis")

    team = db.query(models.Team).filter(models.Team.id == int(target_team_id)).first()
    if not team:
        raise ValueError("Target team not found")

    generator = ScoutingReportGenerator()
    team_data = {
        "id": team.id,
        "name": team.name,
        "league": team.league,
        "country": team.country,
        "budget": float(team.budget or 0),
        "formation": team.formation,
        "playing_style": team.playing_style or {},
    }

    reports = []
    for player in players:
        player_data = {
            "id": player.id,
            "name": player.name,
            "age": player.age or 26,
            "position": player.position,
            "nationality": player.nationality,
            "current_team": player.current_team,
            "market_value": float(player.market_value or 0),
            "performance_index": player.performance_index or {},
            "metrics": player.metrics or {},
            "performance_history": player.performance_history or [],
        }
        reports.append(
            {
                "player_id": player.id,
                "player_name": player.name,
                "scouting_report": generator.generate_full_report(player_data, team_data),
            }
        )

    return {"analysis_type": "scouting_analysis", "target_team_id": target_team_id, "reports": reports}


def _statistical_summary_analysis(
    players: List[Any], parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Summary statistics per metric, ignoring players who lack the metric."""
    metrics = parameters.get("metrics") or DEFAULT_METRICS
    statistics: Dict[str, Any] = {}

    for metric in metrics:
        values = [v for v in (_metric_value(p, metric) for p in players) if v is not None]
        if not values:
            statistics[metric] = {"available": 0, "note": "metric not available for these players"}
            continue
        statistics[metric] = {
            "available": len(values),
            "min": round(min(values), 3),
            "max": round(max(values), 3),
            "average": round(float(np.mean(values)), 3),
            "median": round(float(np.median(values)), 3),
        }

    return {
        "analysis_type": "statistical_summary",
        "summary": {
            "total_players": len(players),
            "metrics_analyzed": metrics,
            "statistics": statistics,
        },
    }


def _analyze_historical_trend(ratings: List[float]) -> Dict[str, Any]:
    """Trend across the whole history, using non-overlapping halves.

    The old version compared stats[-5:] against stats[:5]; with fewer than ten
    matches those windows overlap, and with exactly five they are the same
    slice, so the trend was always "stable".
    """
    if len(ratings) < 4:
        return {"trend": "insufficient_data", "confidence": 0, "matches": len(ratings)}

    half = len(ratings) // 2
    earlier = ratings[:half]
    recent = ratings[half:]
    earlier_avg = float(np.mean(earlier))
    recent_avg = float(np.mean(recent))
    change = ((recent_avg - earlier_avg) / earlier_avg * 100) if earlier_avg else 0.0

    if change > 5:
        trend = "improving"
    elif change < -5:
        trend = "declining"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "change_pct": round(change, 1),
        "recent_avg": round(recent_avg, 2),
        "historical_avg": round(earlier_avg, 2),
        "confidence": round(min(len(ratings) / 10, 1.0), 2),
        "matches": len(ratings),
    }


def _analyze_recent_form(ratings: List[float]) -> Dict[str, Any]:
    """Form over the most recent matches, on the 0-10 rating scale."""
    if not ratings:
        return {"form": "unknown", "games_analyzed": 0}

    avg = float(np.mean(ratings))
    if avg >= 8.0:
        form = "excellent"
    elif avg >= 7.0:
        form = "good"
    elif avg >= 6.0:
        form = "average"
    else:
        form = "poor"

    return {
        "form": form,
        "average_score": round(avg, 2),
        "games_analyzed": len(ratings),
        "consistency": _calculate_consistency(ratings),
    }


def _calculate_consistency(ratings: List[float]) -> float:
    """Consistency from the coefficient of variation.

    The old formula was `100 - variance`, which on a 0-100 scale drove the
    result to zero for anything but near-identical values.
    """
    if len(ratings) < 2:
        return 0.0
    mean = float(np.mean(ratings))
    if mean <= 0:
        return 0.0
    cv = float(np.std(ratings)) / mean
    return round(max(0.0, min(100.0, (1 - cv) * 100)), 1)


def _calculate_overall_prediction(predictions: Dict[str, Any]) -> Dict[str, Any]:
    """Blend the available factors onto a common 0-100 scale."""
    weights = {"historical_trend": 0.4, "team_fit_score": 0.3, "recent_form": 0.3}
    weighted_score = 0.0
    total_weight = 0.0

    for factor, weight in weights.items():
        data = predictions.get(factor)
        if not isinstance(data, dict):
            continue

        if factor == "historical_trend":
            value = data.get("recent_avg")
            score = float(value) * 10 if isinstance(value, (int, float)) else None
        elif factor == "team_fit_score":
            value = data.get("overall_score")
            score = float(value) if isinstance(value, (int, float)) else None
        else:
            value = data.get("average_score")
            score = float(value) * 10 if isinstance(value, (int, float)) else None

        if score is None:
            continue
        weighted_score += score * weight
        total_weight += weight

    return {
        "score": round(weighted_score / total_weight, 1) if total_weight else 0,
        # Share of the prediction weights actually available, not a confidence level
        "factor_coverage": round(total_weight, 2),
        "factors_used": [k for k in weights if isinstance(predictions.get(k), dict)],
    }
