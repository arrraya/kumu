import numpy as np
from sklearn.mixture import GaussianMixture
import xgboost as xgb
from typing import Dict, List


class PlayerAnalyzer:
    def __init__(self):
        self.pass_difficulty_model = self._load_pass_difficulty_model()
        self.style_clustering_model = self._load_style_clustering_model()

    def _load_pass_difficulty_model(self):
        # In production, load from saved model
        # For now, create a simple model
        return xgb.XGBClassifier(random_state=0)

    def _load_style_clustering_model(self):
        # In production, load from saved model
        return GaussianMixture(n_components=40)

    def analyze_player(self, player, period: str) -> Dict:
        # Analyze player performance
        performance_data = player.performance_history

        if period == "last_5":
            performance_data = performance_data[-5:]
        elif period == "last_10":
            performance_data = performance_data[-10:]

        # Calculate statistics
        ratings = [p.get("rating", 0) for p in performance_data]

        return {
            "average_rating": np.mean(ratings),
            "trend": self._calculate_trend(ratings),
            "consistency": np.std(ratings),
            "peak_performance": max(ratings) if ratings else 0,
        }

    def _calculate_trend(self, ratings: List[float]) -> float:
        if len(ratings) < 2:
            return 0
        x = np.arange(len(ratings))
        return np.polyfit(x, ratings, 1)[0]
