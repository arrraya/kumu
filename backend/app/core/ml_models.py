"""Per-player performance summaries over a chosen window.

This used to instantiate an untrained XGBClassifier and GaussianMixture at
import time and never use them, which pulled sklearn and xgboost into the API
process for nothing. The real modelling lives in `pipeline/`, which trains a
pass-difficulty model on actual event data; this module only summarises the
match history the pipeline produces.
"""
from typing import Any, Dict, List

import numpy as np


class PlayerAnalyzer:
    """Summarise a player's recent form from their match history."""

    WINDOWS = {"last_5": 5, "last_10": 10}

    def analyze_player(self, player: Any, period: str) -> Dict[str, Any]:
        history = getattr(player, "performance_history", None) or []
        window = self.WINDOWS.get(period)
        if window:
            history = history[-window:]

        ratings = [
            float(entry["rating"])
            for entry in history
            if isinstance(entry, dict) and isinstance(entry.get("rating"), (int, float))
        ]

        if not ratings:
            return {
                "matches_analysed": 0,
                "average_rating": None,
                "trend": None,
                "consistency": None,
                "peak_performance": None,
                "note": "no match ratings available for this period",
            }

        mean = float(np.mean(ratings))
        # Report consistency the way it reads: higher means steadier. Raw
        # standard deviation was labelled "consistency" but means the opposite.
        variation = float(np.std(ratings)) / mean if mean else 0.0

        return {
            "matches_analysed": len(ratings),
            "average_rating": round(mean, 2),
            "trend": round(self._calculate_trend(ratings), 3),
            "consistency": round(max(0.0, min(1.0, 1 - variation)) * 100, 1),
            "rating_std": round(float(np.std(ratings)), 3),
            "peak_performance": round(max(ratings), 2),
        }

    def _calculate_trend(self, ratings: List[float]) -> float:
        """Slope of a linear fit across the window."""
        if len(ratings) < 2:
            return 0.0
        return float(np.polyfit(np.arange(len(ratings)), ratings, 1)[0])
