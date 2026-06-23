import numpy as np
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass
from enum import Enum


class PerformanceCategory(Enum):
    ELITE = "Elite"
    EXCELLENT = "Excellent"
    GOOD = "Good"
    AVERAGE = "Average"
    BELOW_AVERAGE = "Below Average"


@dataclass
class StatisticalBenchmark:
    """Benchmarks for different positions and leagues"""

    position: str
    league: str
    percentiles: Dict[str, Dict[int, float]]  # metric -> percentile -> value


class ScoutingReportGenerator:
    """Generates comprehensive scouting reports with statistical analysis"""

    def __init__(self):
        self.benchmarks = self._load_benchmarks()
        self.report_sections = [
            "executive_summary",
            "statistical_overview",
            "strengths_weaknesses",
            "tactical_analysis",
            "physical_profile",
            "mental_attributes",
            "injury_history",
            "market_analysis",
            "comparison_analysis",
            "risk_assessment",
            "negotiation_strategy",
        ]

    def _load_benchmarks(self) -> Dict:
        """Load statistical benchmarks for different positions"""
        # Sample benchmarks (in production, load from database)
        return {
            "CAM": {
                "Premier League": {
                    "pass_completion": {10: 0.72, 25: 0.78, 50: 0.82, 75: 0.86, 90: 0.89},
                    "key_passes_per_90": {10: 0.8, 25: 1.2, 50: 1.8, 75: 2.5, 90: 3.2},
                    "progressive_passes_per_90": {10: 2.0, 25: 3.0, 50: 4.2, 75: 5.5, 90: 7.0},
                    "shots_per_90": {10: 0.8, 25: 1.3, 50: 2.0, 75: 2.8, 90: 3.5},
                    "goals_per_90": {10: 0.05, 25: 0.10, 50: 0.18, 75: 0.28, 90: 0.40},
                    "assists_per_90": {10: 0.05, 25: 0.12, 50: 0.20, 75: 0.32, 90: 0.45},
                }
            },
            "CB": {
                "Premier League": {
                    "pass_completion": {10: 0.78, 25: 0.82, 50: 0.86, 75: 0.89, 90: 0.92},
                    "tackles_per_90": {10: 1.0, 25: 1.8, 50: 2.5, 75: 3.2, 90: 4.0},
                    "interceptions_per_90": {10: 1.5, 25: 2.5, 50: 3.5, 75: 4.5, 90: 5.5},
                    "aerial_duels_won": {10: 0.45, 25: 0.55, 50: 0.65, 75: 0.72, 90: 0.80},
                    "clearances_per_90": {10: 2.0, 25: 3.0, 50: 4.0, 75: 5.0, 90: 6.5},
                    "blocks_per_90": {10: 0.3, 25: 0.6, 50: 0.9, 75: 1.3, 90: 1.8},
                }
            },
        }

    def calculate_percentile(self, value: float, metric: str, position: str, league: str) -> int:
        """Calculate percentile rank for a given metric"""
        if position not in self.benchmarks or league not in self.benchmarks[position]:
            return 50  # Default to average if no benchmark

        benchmarks = self.benchmarks[position][league].get(metric, {})
        if not benchmarks:
            return 50

        for percentile in sorted(benchmarks.keys(), reverse=True):
            if value >= benchmarks[percentile]:
                return percentile

        return 10  # Below 10th percentile

    def categorize_performance(self, percentile: int) -> PerformanceCategory:
        """Categorize performance based on percentile"""
        if percentile >= 90:
            return PerformanceCategory.ELITE
        elif percentile >= 75:
            return PerformanceCategory.EXCELLENT
        elif percentile >= 50:
            return PerformanceCategory.GOOD
        elif percentile >= 25:
            return PerformanceCategory.AVERAGE
        else:
            return PerformanceCategory.BELOW_AVERAGE

    def generate_executive_summary(self, player_data: Dict, team_data: Dict) -> Dict:
        """Generate executive summary with key findings"""
        match_score = player_data.get("match_score", 0)

        # Determine recommendation strength
        if match_score >= 85:
            recommendation = "STRONGLY RECOMMENDED"
            action = "Proceed immediately with negotiations"
        elif match_score >= 75:
            recommendation = "RECOMMENDED"
            action = "Proceed with negotiations"
        elif match_score >= 65:
            recommendation = "CONDITIONALLY RECOMMENDED"
            action = "Proceed with caution, address concerns"
        else:
            recommendation = "NOT RECOMMENDED"
            action = "Consider alternative targets"

        # Calculate key metrics
        percentile_values = [
            self.calculate_percentile(
                player_data["metrics"].get(cat, {}).get(metric, 0),
                metric,
                player_data["position"],
                team_data["league"],
            )
            for cat in player_data["metrics"]
            for metric in player_data["metrics"][cat]
        ]
        performance_percentile = np.mean(percentile_values) if percentile_values else 50.0

        return {
            "recommendation": recommendation,
            "action": action,
            "match_score": match_score,
            "overall_percentile": int(performance_percentile),
            "key_findings": [
                f"Player ranks in the {int(performance_percentile)}th percentile overall",
                f"Match compatibility score: {match_score}%",
                f"Age profile: {player_data['age']} years - {'Optimal' if 23 <= player_data['age'] <= 28 else 'Consider age factor'}",
                f"Financial fit: {'Within budget' if player_data['market_value'] <= team_data['budget'] * 0.4 else 'Stretches budget'}",
            ],
            "executive_statement": f"{player_data['name']} represents a {recommendation.lower()} acquisition for {team_data['name']}. Statistical analysis places the player in the {int(performance_percentile)}th percentile for their position in {team_data['league']}.",
        }

    def generate_statistical_overview(self, player_data: Dict, team_data: Dict) -> Dict:
        """Generate detailed statistical analysis"""
        position = player_data["position"]
        league = team_data["league"]
        metrics_analysis = {}

        for category, metrics in player_data["metrics"].items():
            category_analysis = {}
            for metric, value in metrics.items():
                percentile = self.calculate_percentile(value, metric, position, league)
                performance = self.categorize_performance(percentile)

                category_analysis[metric] = {
                    "value": value,
                    "percentile": percentile,
                    "performance": performance.value,
                    "vs_league_average": self._compare_to_average(value, metric, position, league),
                }
            metrics_analysis[category] = category_analysis

        return {
            "position_specific_analysis": metrics_analysis,
            "statistical_strengths": self._identify_statistical_strengths(metrics_analysis),
            "statistical_weaknesses": self._identify_statistical_weaknesses(metrics_analysis),
            "consistency_rating": self._calculate_consistency(
                player_data.get("performance_history", [])
            ),
            "form_trajectory": self._analyze_form_trajectory(
                player_data.get("performance_history", [])
            ),
        }

    def _compare_to_average(self, value: float, metric: str, position: str, league: str) -> str:
        """Compare value to league average (50th percentile)"""
        if position not in self.benchmarks or league not in self.benchmarks[position]:
            return "No benchmark available"

        avg_value = self.benchmarks[position][league].get(metric, {}).get(50, 0)
        if avg_value == 0:
            return "No benchmark available"

        percentage_diff = ((value - avg_value) / avg_value) * 100

        if percentage_diff > 20:
            return f"+{percentage_diff:.1f}% well above average"
        elif percentage_diff > 0:
            return f"+{percentage_diff:.1f}% above average"
        elif percentage_diff > -20:
            return f"{percentage_diff:.1f}% below average"
        else:
            return f"{percentage_diff:.1f}% well below average"

    def _identify_statistical_strengths(self, metrics_analysis: Dict) -> List[str]:
        """Identify player's statistical strengths"""
        strengths = []
        for category, metrics in metrics_analysis.items():
            for metric, analysis in metrics.items():
                if analysis["percentile"] >= 75:
                    strengths.append(
                        f"{metric.replace('_', ' ').title()}: {analysis['performance']} ({analysis['percentile']}th percentile)"
                    )
        return strengths[:5]  # Top 5 strengths

    def _identify_statistical_weaknesses(self, metrics_analysis: Dict) -> List[str]:
        """Identify player's statistical weaknesses"""
        weaknesses = []
        for category, metrics in metrics_analysis.items():
            for metric, analysis in metrics.items():
                if analysis["percentile"] < 40:
                    weaknesses.append(
                        f"{metric.replace('_', ' ').title()}: {analysis['performance']} ({analysis['percentile']}th percentile)"
                    )
        return weaknesses[:3]  # Top 3 weaknesses

    def _calculate_consistency(self, performance_history: List[Dict]) -> Dict:
        """Calculate performance consistency"""
        if len(performance_history) < 5:
            return {"rating": "Insufficient data", "score": 0}

        ratings = [p.get("rating", 0) for p in performance_history[-10:]]
        std_dev = np.std(ratings)

        if std_dev < 0.3:
            return {"rating": "Very Consistent", "score": 90}
        elif std_dev < 0.5:
            return {"rating": "Consistent", "score": 75}
        elif std_dev < 0.8:
            return {"rating": "Moderately Consistent", "score": 60}
        else:
            return {"rating": "Inconsistent", "score": 40}

    def _analyze_form_trajectory(self, performance_history: List[Dict]) -> Dict:
        """Analyze recent form trajectory"""
        if len(performance_history) < 3:
            return {"trend": "Insufficient data", "direction": "neutral"}

        recent_ratings = [p.get("rating", 0) for p in performance_history[-5:]]

        # Simple linear regression for trend
        x = np.arange(len(recent_ratings))
        slope = np.polyfit(x, recent_ratings, 1)[0]

        if slope > 0.1:
            return {"trend": "Improving", "direction": "positive", "slope": slope}
        elif slope < -0.1:
            return {"trend": "Declining", "direction": "negative", "slope": slope}
        else:
            return {"trend": "Stable", "direction": "neutral", "slope": slope}

    def generate_tactical_analysis(self, player_data: Dict, team_data: Dict) -> Dict:
        """Generate tactical fit analysis"""
        position = player_data["position"]

        # Position-specific tactical analysis
        tactical_fit = {
            "formation_compatibility": self._assess_formation_fit(
                position, team_data.get("formation", "4-3-3")
            ),
            "style_compatibility": self._assess_style_fit(player_data, team_data),
            "role_suitability": self._assess_role_suitability(player_data, team_data),
            "tactical_flexibility": self._assess_flexibility(player_data),
        }

        return tactical_fit

    def _assess_formation_fit(self, position: str, formation: str) -> Dict:
        """Assess how well player fits team formation"""
        formation_positions = {
            "4-3-3": ["GK", "RB", "CB", "CB", "LB", "CDM", "CM", "CM", "RW", "ST", "LW"],
            "4-2-3-1": ["GK", "RB", "CB", "CB", "LB", "CDM", "CDM", "RM", "CAM", "LM", "ST"],
            "3-5-2": ["GK", "CB", "CB", "CB", "RM", "CM", "CDM", "CM", "LM", "ST", "ST"],
        }

        if formation in formation_positions:
            if position in formation_positions[formation]:
                return {"fit": "Perfect", "score": 100, "note": f"Natural position in {formation}"}
            elif position == "CAM" and "CM" in formation_positions[formation]:
                return {"fit": "Good", "score": 80, "note": "Can adapt to central midfield role"}
            else:
                return {
                    "fit": "Requires adaptation",
                    "score": 60,
                    "note": "May need positional adjustment",
                }

        return {"fit": "Unknown", "score": 50, "note": "Formation compatibility unclear"}

    def _assess_style_fit(self, player_data: Dict, team_data: Dict) -> Dict:
        """Assess playing style compatibility"""
        player_style = self._determine_player_style(player_data)
        team_style = team_data.get("playing_style", {})

        compatibility_score = 0
        notes = []

        metrics = player_data.get("metrics", {})

        # Check passing style fit
        if team_style.get("possession", 0.5) > 0.6:
            completion_rate = metrics.get("passing", {}).get("completion_rate", 0)
            if completion_rate > 0.82:
                compatibility_score += 25
                notes.append("Excellent fit for possession-based system")
            else:
                compatibility_score += 10
                notes.append("May need to improve passing accuracy for possession style")

        # Check pressing fit
        if team_style.get("pressing_intensity", 0.5) > 0.7:
            distance = metrics.get("movement", {}).get("distance_covered_per_90", 0)
            if distance > 10:
                compatibility_score += 25
                notes.append("High work rate suits pressing system")
            else:
                compatibility_score += 10
                notes.append("May need to increase work rate for pressing system")

        return {
            "compatibility_score": min(compatibility_score * 2, 100),
            "player_style": player_style,
            "team_style": team_style,
            "notes": notes,
        }

    def _determine_player_style(self, player_data: Dict) -> str:
        """Determine player's playing style from stats"""
        metrics = player_data["metrics"]

        if metrics["passing"]["key_passes_per_90"] > 2.5:
            return "Creative Playmaker"
        elif metrics["shooting"]["shots_per_90"] > 3.0:
            return "Goal Threat"
        elif metrics["defensive"]["tackles_per_90"] > 3.0:
            return "Defensive Anchor"
        elif metrics["movement"]["distance_covered_per_90"] > 11:
            return "Box-to-Box"
        else:
            return "Balanced"

    def _assess_role_suitability(self, player_data: Dict, team_data: Dict) -> Dict:
        """Assess suitability for specific tactical roles"""
        position = player_data["position"]

        role_scores = {}

        if position == "CAM":
            # Assess different CAM roles
            role_scores["Playmaker"] = self._score_playmaker_attributes(player_data)
            role_scores["Shadow Striker"] = self._score_shadow_striker_attributes(player_data)
            role_scores["Wide Playmaker"] = self._score_wide_playmaker_attributes(player_data)
        elif position == "CB":
            # Assess different CB roles
            role_scores["Ball Playing Defender"] = self._score_ball_playing_defender(player_data)
            role_scores["Stopper"] = self._score_stopper_attributes(player_data)
            role_scores["Sweeper"] = self._score_sweeper_attributes(player_data)

        best_role = (
            max(role_scores.items(), key=lambda x: x[1]["score"])
            if role_scores
            else ("Unknown", {"score": 0})
        )

        return {
            "best_role": best_role[0],
            "role_scores": role_scores,
            "recommendation": f"Best suited as {best_role[0]} with {best_role[1]['score']}% compatibility",
        }

    def _score_playmaker_attributes(self, player_data: Dict) -> Dict:
        """Score playmaker attributes"""
        metrics = player_data["metrics"]
        score = 0
        factors = []

        # Key passes
        if metrics["passing"]["key_passes_per_90"] > 2.5:
            score += 30
            factors.append("Excellent chance creation")
        elif metrics["passing"]["key_passes_per_90"] > 1.8:
            score += 20
            factors.append("Good chance creation")

        # Pass completion
        if metrics["passing"]["completion_rate"] > 0.85:
            score += 25
            factors.append("High passing accuracy")

        # Progressive passes
        if metrics["passing"]["progressive_passes_per_90"] > 5:
            score += 25
            factors.append("Strong progressive passing")

        return {"score": score, "factors": factors}

    def _score_shadow_striker_attributes(self, player_data: Dict) -> Dict:
        """Score shadow striker attributes"""
        metrics = player_data["metrics"]
        score = 0
        factors = []

        # Goal threat
        if metrics["shooting"]["shots_per_90"] > 2.5:
            score += 35
            factors.append("High goal threat")

        # Movement
        if metrics["movement"]["high_intensity_runs"] > 25:
            score += 30
            factors.append("Excellent attacking runs")

        # Conversion
        if metrics["shooting"]["conversion_rate"] > 0.15:
            score += 35
            factors.append("Clinical finishing")

        return {"score": score, "factors": factors}

    def _score_wide_playmaker_attributes(self, player_data: Dict) -> Dict:
        """Score wide playmaker attributes"""
        # Similar implementation
        return {"score": 70, "factors": ["Good dribbling", "Creates width"]}

    def _score_ball_playing_defender(self, player_data: Dict) -> Dict:
        """Score ball playing defender attributes"""
        metrics = player_data["metrics"]
        score = 0
        factors = []

        # Passing ability
        if metrics["passing"]["completion_rate"] > 0.88:
            score += 40
            factors.append("Excellent distribution")

        # Progressive passes
        if metrics["passing"]["progressive_passes_per_90"] > 3:
            score += 30
            factors.append("Breaks lines with passing")

        # Defensive solidity
        if metrics["defensive"]["tackles_per_90"] > 2.5:
            score += 30
            factors.append("Solid defensive base")

        return {"score": score, "factors": factors}

    def _score_stopper_attributes(self, player_data: Dict) -> Dict:
        """Score stopper attributes"""
        metrics = player_data["metrics"]
        score = 0
        factors = []

        # Aerial dominance
        if metrics["defensive"]["aerial_duels_won"] > 0.7:
            score += 35
            factors.append("Dominant in the air")

        # Defensive actions
        if metrics["defensive"]["tackles_per_90"] > 3:
            score += 35
            factors.append("High tackle volume")

        # Blocks
        if metrics["defensive"].get("blocks_per_90", 0) > 1:
            score += 30
            factors.append("Excellent shot blocking")

        return {"score": score, "factors": factors}

    def _score_sweeper_attributes(self, player_data: Dict) -> Dict:
        """Score sweeper attributes"""
        # Similar implementation
        return {"score": 75, "factors": ["Good positioning", "Reads game well"]}

    def _assess_flexibility(self, player_data: Dict) -> Dict:
        """Assess player's tactical flexibility"""
        position = player_data["position"]

        # Define position versatility
        versatility_map = {
            "CAM": ["CM", "RW", "LW", "CF"],
            "CB": ["RB", "LB", "CDM"],
            "CM": ["CAM", "CDM", "RM", "LM"],
            "ST": ["RW", "LW", "CAM"],
            "RW": ["RWB", "RM", "ST"],
            "LW": ["LWB", "LM", "ST"],
        }

        alternative_positions = versatility_map.get(position, [])

        # Assess metrics for alternative positions
        versatility_score = len(alternative_positions) * 20

        return {
            "primary_position": position,
            "alternative_positions": alternative_positions,
            "versatility_score": min(versatility_score, 100),
            "tactical_flexibility": (
                "High"
                if versatility_score > 60
                else "Moderate" if versatility_score > 30 else "Low"
            ),
        }

    def generate_physical_profile(self, player_data: Dict) -> Dict:
        """Generate physical and athletic profile"""
        metrics = player_data["metrics"]["movement"]

        # Calculate physical scores
        speed_score = min((metrics["average_speed"] / 8.5) * 100, 100)
        endurance_score = min((metrics["distance_covered_per_90"] / 12) * 100, 100)
        intensity_score = min((metrics["high_intensity_runs"] / 35) * 100, 100)

        physical_age = player_data["age"]
        if physical_age < 24:
            development_stage = "Still developing physically"
            peak_years_remaining = 5 + (28 - physical_age)
        elif physical_age <= 28:
            development_stage = "Physical prime"
            peak_years_remaining = 28 - physical_age
        elif physical_age <= 32:
            development_stage = "Experienced, slight physical decline possible"
            peak_years_remaining = max(0, 32 - physical_age)
        else:
            development_stage = "Veteran, manage physical load"
            peak_years_remaining = 0

        return {
            "athletic_scores": {
                "speed": {
                    "score": speed_score,
                    "rating": self._rate_physical_attribute(speed_score),
                },
                "endurance": {
                    "score": endurance_score,
                    "rating": self._rate_physical_attribute(endurance_score),
                },
                "intensity": {
                    "score": intensity_score,
                    "rating": self._rate_physical_attribute(intensity_score),
                },
            },
            "physical_age_analysis": {
                "current_age": physical_age,
                "development_stage": development_stage,
                "peak_years_remaining": peak_years_remaining,
            },
            "injury_risk_factors": self._assess_injury_risk(player_data),
            "physical_comparison": f"Ranks {int((speed_score + endurance_score + intensity_score) / 3)}th percentile athletically for position",
        }

    def _rate_physical_attribute(self, score: float) -> str:
        """Rate physical attribute based on score"""
        if score >= 90:
            return "Elite"
        elif score >= 75:
            return "Excellent"
        elif score >= 60:
            return "Good"
        elif score >= 40:
            return "Average"
        else:
            return "Below Average"

    def _assess_injury_risk(self, player_data: Dict) -> Dict:
        """Assess injury risk factors"""
        age = player_data["age"]
        injury_history = player_data.get("injury_history", [])
        workload = player_data["metrics"]["movement"]["distance_covered_per_90"]

        risk_score = 0
        risk_factors = []

        # Age factor
        if age > 30:
            risk_score += 20
            risk_factors.append("Age over 30")
        elif age > 28:
            risk_score += 10

        # Injury history
        recent_injuries = [i for i in injury_history if i.get("days_missed", 0) > 14]
        if len(recent_injuries) > 2:
            risk_score += 30
            risk_factors.append("Multiple recent injuries")
        elif len(recent_injuries) > 0:
            risk_score += 15
            risk_factors.append("Some injury history")

        # Workload
        if workload > 11.5:
            risk_score += 10
            risk_factors.append("Very high workload")

        return {
            "risk_level": "High" if risk_score > 40 else "Moderate" if risk_score > 20 else "Low",
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "mitigation_suggestions": self._suggest_injury_mitigation(risk_factors),
        }

    def _suggest_injury_mitigation(self, risk_factors: List[str]) -> List[str]:
        """Suggest injury risk mitigation strategies"""
        suggestions = []

        if "Age over 30" in risk_factors:
            suggestions.append("Implement rotation policy")
            suggestions.append("Enhanced recovery protocols")

        if "Multiple recent injuries" in risk_factors:
            suggestions.append("Comprehensive medical assessment before signing")
            suggestions.append("Gradual integration into team")

        if "Very high workload" in risk_factors:
            suggestions.append("Monitor training loads carefully")
            suggestions.append("Strategic rest periods")

        return suggestions

    def generate_market_analysis(self, player_data: Dict, team_data: Dict) -> Dict:
        """Generate market value and financial analysis"""
        current_value = player_data["market_value"]
        age = player_data["age"]
        performance_index = player_data["performance_index"]["value"]

        # Calculate value projections
        value_projections = self._project_market_value(current_value, age, performance_index)

        # Compare with similar players
        comparable_players = self._find_comparable_transfers(player_data)

        # Calculate ROI potential
        roi_analysis = self._calculate_roi_potential(player_data, team_data, value_projections)

        return {
            "current_market_value": current_value,
            "value_assessment": self._assess_value(current_value, comparable_players),
            "value_projections": value_projections,
            "comparable_transfers": comparable_players,
            "roi_analysis": roi_analysis,
            "contract_recommendations": self._recommend_contract_structure(player_data, team_data),
            "financial_risk_assessment": self._assess_financial_risk(player_data, team_data),
        }

    def _project_market_value(
        self, current_value: float, age: int, performance_index: float
    ) -> Dict:
        """Project future market value"""
        projections = {}

        for year in range(1, 6):
            age_factor = 1.0
            if age + year < 24:
                age_factor = 1.15  # Young player growth
            elif age + year <= 27:
                age_factor = 1.05  # Prime years
            elif age + year <= 30:
                age_factor = 0.95  # Slight decline
            else:
                age_factor = 0.85  # Significant decline

            performance_factor = 1.0 + (performance_index - 70) / 100

            projected_value = current_value * (age_factor**year) * performance_factor
            projections[f"year_{year}"] = {
                "value": projected_value,
                "age": age + year,
                "change_pct": ((projected_value - current_value) / current_value) * 100,
            }

        return projections

    def _find_comparable_transfers(self, player_data: Dict) -> List[Dict]:
        """Find comparable recent transfers"""
        # In production, query database for similar transfers
        # This is mock data for demonstration
        position = player_data["position"]
        age = player_data["age"]

        comparables = [
            {
                "player": "Player A",
                "age": age - 1,
                "position": position,
                "from_club": "Club X",
                "to_club": "Club Y",
                "transfer_fee": player_data["market_value"] * 0.9,
                "date": "2024-07",
                "performance_index": 75,
            },
            {
                "player": "Player B",
                "age": age + 1,
                "position": position,
                "from_club": "Club M",
                "to_club": "Club N",
                "transfer_fee": player_data["market_value"] * 1.1,
                "date": "2024-08",
                "performance_index": 79,
            },
        ]

        return comparables

    def _assess_value(self, current_value: float, comparable_players: List[Dict]) -> Dict:
        """Assess if player represents good value"""
        avg_comparable_fee = np.mean([p["transfer_fee"] for p in comparable_players])

        value_ratio = current_value / avg_comparable_fee

        if value_ratio < 0.85:
            assessment = "Undervalued"
            recommendation = "Excellent value opportunity"
        elif value_ratio < 1.15:
            assessment = "Fair value"
            recommendation = "Market-appropriate pricing"
        else:
            assessment = "Overvalued"
            recommendation = "Negotiate aggressively or consider alternatives"

        return {
            "assessment": assessment,
            "recommendation": recommendation,
            "value_ratio": value_ratio,
            "vs_comparables": f"{((value_ratio - 1) * 100):+.1f}% vs similar transfers",
        }

    def _calculate_roi_potential(
        self, player_data: Dict, team_data: Dict, projections: Dict
    ) -> Dict:
        """Calculate potential return on investment"""
        initial_investment = player_data["market_value"]

        # Consider multiple ROI factors
        sporting_value = self._estimate_sporting_value(player_data, team_data)
        commercial_value = self._estimate_commercial_value(player_data)
        resale_value = projections.get("year_3", {}).get("value", initial_investment * 0.7)

        total_value = sporting_value + commercial_value + resale_value
        roi = ((total_value - initial_investment) / initial_investment) * 100

        return {
            "roi_percentage": roi,
            "breakeven_period": self._calculate_breakeven(
                initial_investment, sporting_value, commercial_value
            ),
            "value_components": {
                "sporting_value": sporting_value,
                "commercial_value": commercial_value,
                "projected_resale_value": resale_value,
            },
            "risk_adjusted_roi": roi * (1 - self._calculate_risk_factor(player_data) / 100),
        }

    def _estimate_sporting_value(self, player_data: Dict, team_data: Dict) -> float:
        """Estimate sporting value contribution"""
        # Simplified calculation based on performance impact
        performance_index = player_data["performance_index"]["value"]
        position_importance = {"ST": 1.2, "CAM": 1.1, "CM": 1.0, "CB": 0.9, "GK": 0.8}.get(
            player_data["position"], 1.0
        )

        base_sporting_value = (performance_index / 100) * 50000000 * position_importance

        # Adjust for team needs
        if player_data["position"] in team_data.get("priority_positions", []):
            base_sporting_value *= 1.3

        return base_sporting_value

    def _estimate_commercial_value(self, player_data: Dict) -> float:
        """Estimate commercial value (merchandise, sponsorship, etc.)"""
        # Simplified calculation
        age_factor = 1.2 if player_data["age"] < 25 else 1.0 if player_data["age"] < 30 else 0.7
        marketability = player_data.get("marketability_score", 50) / 100

        return 10000000 * marketability * age_factor

    def _calculate_breakeven(
        self, investment: float, sporting_value: float, commercial_value: float
    ) -> str:
        """Calculate breakeven period"""
        annual_value = (sporting_value + commercial_value) / 5  # Assume 5-year impact

        if annual_value <= 0:
            return "No breakeven"

        years = investment / annual_value

        if years < 2:
            return "Less than 2 years"
        elif years < 3:
            return "2-3 years"
        elif years < 5:
            return "3-5 years"
        else:
            return "More than 5 years"

    def _calculate_risk_factor(self, player_data: Dict) -> float:
        """Calculate overall risk factor"""
        risk = 0

        # Age risk
        if player_data["age"] > 28:
            risk += 15
        if player_data["age"] > 30:
            risk += 20

        # Performance volatility
        risk += player_data["performance_index"]["volatility"] * 100

        # Injury history
        injury_count = len(player_data.get("injury_history", []))
        risk += min(injury_count * 10, 30)

        return min(risk, 80)  # Cap at 80% risk

    def _recommend_contract_structure(self, player_data: Dict, team_data: Dict) -> Dict:
        """Recommend optimal contract structure"""
        age = player_data["age"]

        # Base recommendations on age and value
        if age < 24:
            base_length = 5
            option_years = 1
            sell_on_clause = True
            buyout_clause = player_data["market_value"] * 2.5
        elif age < 28:
            base_length = 4
            option_years = 1
            sell_on_clause = False
            buyout_clause = player_data["market_value"] * 2.0
        elif age < 31:
            base_length = 3
            option_years = 0
            sell_on_clause = False
            buyout_clause = player_data["market_value"] * 1.5
        else:
            base_length = 2
            option_years = 0
            sell_on_clause = False
            buyout_clause = None

        # Calculate wage structure
        base_wage = self._calculate_base_wage(player_data, team_data)

        return {
            "contract_length": f"{base_length} years{f' + {option_years} optional' if option_years else ''}",
            "wage_structure": {
                "base_weekly_wage": base_wage,
                "performance_bonus": base_wage * 0.25,
                "goal_bonus": (
                    10000 if player_data["position"] in ["ST", "CAM", "RW", "LW"] else 5000
                ),
                "clean_sheet_bonus": (
                    10000 if player_data["position"] in ["GK", "CB", "RB", "LB"] else 0
                ),
            },
            "clauses": {
                "buyout_clause": buyout_clause,
                "sell_on_percentage": 20 if sell_on_clause else 0,
                "performance_escalators": "Recommended",
                "injury_protection": "Essential" if age > 28 else "Recommended",
            },
            "total_package_value": self._calculate_total_package(
                base_length, base_wage, player_data["market_value"]
            ),
        }

    def _calculate_base_wage(self, player_data: Dict, team_data: Dict) -> float:
        """Calculate recommended base wage"""
        # Base on market value and team wage structure
        value_based_wage = player_data["market_value"] * 0.002  # 0.2% of value per week

        # Adjust for team budget
        budget_factor = min(team_data["budget"] / 200000000, 1.5)  # Normalize to 200M budget

        return value_based_wage * budget_factor

    def _calculate_total_package(
        self, years: int, weekly_wage: float, transfer_fee: float
    ) -> float:
        """Calculate total investment package"""
        annual_wage = weekly_wage * 52
        total_wages = annual_wage * years

        # Add typical bonuses and fees
        signing_bonus = transfer_fee * 0.1
        agent_fees = transfer_fee * 0.05

        return transfer_fee + total_wages + signing_bonus + agent_fees

    def _assess_financial_risk(self, player_data: Dict, team_data: Dict) -> Dict:
        """Assess financial risk of the transfer"""
        total_investment = self._calculate_total_package(
            4,  # Assume 4-year contract
            self._calculate_base_wage(player_data, team_data),
            player_data["market_value"],
        )

        budget_percentage = (total_investment / team_data["budget"]) * 100

        if budget_percentage < 30:
            risk_level = "Low"
            risk_description = "Comfortable within budget parameters"
        elif budget_percentage < 50:
            risk_level = "Moderate"
            risk_description = "Significant but manageable investment"
        elif budget_percentage < 70:
            risk_level = "High"
            risk_description = "Major financial commitment"
        else:
            risk_level = "Very High"
            risk_description = "Risky - dominates transfer budget"

        return {
            "risk_level": risk_level,
            "risk_description": risk_description,
            "budget_impact": f"{budget_percentage:.1f}% of available budget",
            "mitigation_strategies": (
                [
                    "Structure payments over multiple years",
                    "Include performance-based add-ons",
                    "Negotiate sell-on clause for future profit",
                ]
                if risk_level in ["High", "Very High"]
                else []
            ),
        }

    def generate_comparison_analysis(self, player_data: Dict, team_data: Dict) -> Dict:
        """Generate comparison with current squad and league peers"""
        position = player_data["position"]

        # Compare with current squad
        squad_comparison = self._compare_with_squad(player_data, team_data)

        # Compare with league peers
        league_comparison = self._compare_with_league_peers(player_data, team_data)

        # Historical comparison
        historical_comparison = self._historical_performance_comparison(player_data)

        return {
            "squad_comparison": squad_comparison,
            "league_comparison": league_comparison,
            "historical_comparison": historical_comparison,
            "upgrade_assessment": self._assess_upgrade_potential(
                squad_comparison, league_comparison
            ),
        }

    def _compare_with_squad(self, player_data: Dict, team_data: Dict) -> Dict:
        """Compare with current squad players in same position"""
        # Mock comparison - in production, would query actual squad data
        position = player_data["position"]

        current_players = [
            {"name": "Current Player 1", "performance_index": 72, "age": 26},
            {"name": "Current Player 2", "performance_index": 68, "age": 30},
        ]

        avg_current_performance = np.mean([p["performance_index"] for p in current_players])
        improvement = (
            (player_data["performance_index"]["value"] - avg_current_performance)
            / avg_current_performance
        ) * 100

        return {
            "current_options": current_players,
            "performance_improvement": f"{improvement:+.1f}%",
            "immediate_impact": (
                "Likely starter"
                if improvement > 10
                else "Rotation option" if improvement > 0 else "Squad depth"
            ),
            "position_upgrade": improvement > 15,
        }

    def _compare_with_league_peers(self, player_data: Dict, team_data: Dict) -> Dict:
        """Compare with top performers in the league"""
        position = player_data["position"]
        league = team_data["league"]

        # Mock data - in production, would query league statistics
        league_percentile = self.calculate_percentile(
            player_data["performance_index"]["value"], "overall_performance", position, league
        )

        return {
            "league_percentile": league_percentile,
            "vs_top_performers": (
                "Top tier"
                if league_percentile >= 80
                else "Upper mid-tier" if league_percentile >= 60 else "Mid-tier"
            ),
            "statistical_rank": f"Ranks approximately {11 - int(league_percentile/10)}th in position",
            "elite_potential": league_percentile >= 75,
        }

    def _historical_performance_comparison(self, player_data: Dict) -> Dict:
        """Compare current form with historical performance"""
        history = player_data.get("performance_history", [])

        if len(history) < 20:
            return {"analysis": "Insufficient historical data"}

        # Calculate performance trends
        recent_avg = np.mean([h.get("rating", 0) for h in history[-10:]])
        historical_avg = np.mean([h.get("rating", 0) for h in history])
        peak_performance = max([h.get("rating", 0) for h in history])

        if historical_avg == 0 or peak_performance == 0:
            return {"analysis": "Insufficient rating data"}

        return {
            "recent_vs_historical": f"{((recent_avg - historical_avg) / historical_avg * 100):+.1f}%",
            "current_vs_peak": f"{((recent_avg - peak_performance) / peak_performance * 100):.1f}%",
            "form_assessment": (
                "Excellent form"
                if recent_avg > historical_avg * 1.1
                else "Good form" if recent_avg > historical_avg else "Below average form"
            ),
            "consistency_trend": "Improving" if recent_avg > historical_avg else "Declining",
        }

    def _assess_upgrade_potential(self, squad_comparison: Dict, league_comparison: Dict) -> str:
        """Assess overall upgrade potential"""
        if squad_comparison["position_upgrade"] and league_comparison["elite_potential"]:
            return "Significant upgrade - would transform position"
        elif squad_comparison["position_upgrade"]:
            return "Clear upgrade - would improve squad quality"
        elif float(squad_comparison["performance_improvement"].strip("%+")) > 5:
            return "Marginal upgrade - adds depth and competition"
        else:
            return "Lateral move - consider only if replacing departing player"

    def generate_risk_assessment(self, player_data: Dict, team_data: Dict) -> Dict:
        """Generate comprehensive risk assessment"""

        risk_factors = {
            "performance_risk": self._assess_performance_risk(player_data),
            "injury_risk": self._assess_injury_risk(player_data),
            "adaptation_risk": self._assess_adaptation_risk(player_data, team_data),
            "financial_risk": self._assess_financial_risk(player_data, team_data),
            "age_related_risk": self._assess_age_risk(player_data),
        }

        # Normalize each sub-risk to expose uniform "score" and "level" keys.
        # Sub-assessments historically used inconsistent key names
        # (e.g. injury_risk -> risk_score/risk_level, financial_risk -> risk_level only),
        # which broke consumers expecting score/level and excluded them from the average.
        for rf in risk_factors.values():
            if "score" not in rf:
                rf["score"] = rf.get("risk_score", 0)
            if "level" not in rf:
                rf["level"] = rf.get("risk_level", self._categorize_risk(rf["score"]))

        # Calculate overall risk score (now includes all sub-risks)
        total_risk_score = np.mean([rf["score"] for rf in risk_factors.values()])

        return {
            "overall_risk_level": self._categorize_risk(total_risk_score),
            "risk_score": total_risk_score,
            "risk_factors": risk_factors,
            "mitigation_plan": self._create_risk_mitigation_plan(risk_factors),
            "decision_impact": self._assess_decision_impact(total_risk_score),
        }

    def _assess_performance_risk(self, player_data: Dict) -> Dict:
        """Assess performance-related risks"""
        volatility = player_data["performance_index"]["volatility"]
        trend = player_data["performance_index"]["trend"]

        risk_score = volatility * 50  # High volatility increases risk

        if trend < 0:
            risk_score += 20

        return {
            "score": risk_score,
            "level": self._categorize_risk(risk_score),
            "factors": [
                f"Performance volatility: {volatility:.2f}",
                f"Recent trend: {trend:+.1f}%",
            ],
        }

    def _assess_adaptation_risk(self, player_data: Dict, team_data: Dict) -> Dict:
        """Assess adaptation and integration risks"""
        risk_score = 0
        factors = []

        # League change
        if player_data.get("current_league") != team_data["league"]:
            risk_score += 25
            factors.append("Moving to new league")

        # Cultural/language factors
        if player_data.get("nationality") != team_data.get("country"):
            risk_score += 15
            factors.append("International transfer")

        # Playing style change
        style_difference = 20  # Simplified - would calculate based on actual style metrics
        risk_score += style_difference

        return {
            "score": risk_score,
            "level": self._categorize_risk(risk_score),
            "factors": factors,
            "adaptation_period": "3-6 months" if risk_score > 40 else "1-3 months",
        }

    def _assess_age_risk(self, player_data: Dict) -> Dict:
        """Assess age-related risks"""
        age = player_data["age"]

        if age < 23:
            risk_score = 20
            factors = ["Young player - development uncertainty"]
        elif age < 28:
            risk_score = 10
            factors = ["Prime age - minimal age risk"]
        elif age < 31:
            risk_score = 30
            factors = ["Approaching 30 - limited resale value"]
        else:
            risk_score = 50
            factors = ["Over 30 - physical decline risk", "No resale value"]

        return {"score": risk_score, "level": self._categorize_risk(risk_score), "factors": factors}

    def _categorize_risk(self, risk_score: float) -> str:
        """Categorize risk level based on score"""
        if risk_score < 20:
            return "Low"
        elif risk_score < 40:
            return "Moderate"
        elif risk_score < 60:
            return "High"
        else:
            return "Very High"

    def _create_risk_mitigation_plan(self, risk_factors: Dict) -> List[str]:
        """Create risk mitigation strategies"""
        mitigation_strategies = []

        for risk_type, risk_data in risk_factors.items():
            if risk_data.get("level") in ["High", "Very High"]:
                if risk_type == "injury_risk":
                    mitigation_strategies.extend(
                        [
                            "Comprehensive medical examination",
                            "Customized training program",
                            "Load management protocol",
                        ]
                    )
                elif risk_type == "adaptation_risk":
                    mitigation_strategies.extend(
                        [
                            "Assign integration mentor",
                            "Language support if needed",
                            "Gradual tactical integration",
                        ]
                    )
                elif risk_type == "financial_risk":
                    mitigation_strategies.extend(
                        [
                            "Performance-based payment structure",
                            "Sell-on clause negotiation",
                            "Wage structure optimization",
                        ]
                    )

        return list(set(mitigation_strategies))  # Remove duplicates

    def _assess_decision_impact(self, risk_score: float) -> str:
        """Assess how risk should impact decision"""
        if risk_score < 30:
            return "Low risk - proceed with confidence"
        elif risk_score < 50:
            return "Moderate risk - proceed with appropriate safeguards"
        elif risk_score < 70:
            return "High risk - proceed only with significant mitigation measures"
        else:
            return "Very high risk - consider alternative targets"

    def generate_negotiation_strategy(
        self, player_data: Dict, team_data: Dict, market_analysis: Dict
    ) -> Dict:
        """Generate detailed negotiation strategy"""

        # Determine negotiation position strength
        position_strength = self._assess_negotiation_position(player_data, team_data)

        # Set negotiation parameters
        opening_offer = self._calculate_opening_offer(
            player_data, market_analysis, position_strength
        )

        # Identify key negotiation points
        negotiation_points = self._identify_negotiation_points(player_data, team_data)

        # Create negotiation timeline
        timeline = self._create_negotiation_timeline(player_data)

        return {
            "negotiation_position": position_strength,
            "offer_strategy": {
                "opening_offer": opening_offer,
                "maximum_offer": opening_offer * 1.25,
                "walk_away_price": opening_offer * 1.35,
                "payment_structure": self._recommend_payment_structure(opening_offer, team_data),
            },
            "key_negotiation_points": negotiation_points,
            "leverage_factors": self._identify_leverage_factors(player_data, team_data),
            "timeline": timeline,
            "tactics": self._recommend_negotiation_tactics(position_strength),
            "contingency_plans": self._create_contingency_plans(player_data),
        }

    def _assess_negotiation_position(self, player_data: Dict, team_data: Dict) -> Dict:
        """Assess strength of negotiating position"""
        strength_score = 50  # Base score
        factors = []

        # Contract situation
        if player_data.get("contract_expires_months", 24) < 12:
            strength_score += 20
            factors.append("Player in final year of contract")
        elif player_data.get("contract_expires_months", 24) < 24:
            strength_score += 10
            factors.append("Contract expiring soon")

        # Player desire to move
        if player_data.get("wants_move", False):
            strength_score += 15
            factors.append("Player wants transfer")

        # Alternative options
        if len(team_data.get("alternative_targets", [])) > 2:
            strength_score += 10
            factors.append("Multiple alternative targets available")

        # Selling club's financial situation
        if player_data.get("club_needs_sale", False):
            strength_score += 15
            factors.append("Selling club needs funds")

        return {
            "strength": (
                "Strong" if strength_score > 70 else "Moderate" if strength_score > 50 else "Weak"
            ),
            "score": strength_score,
            "factors": factors,
        }

    def _calculate_opening_offer(
        self, player_data: Dict, market_analysis: Dict, position_strength: Dict
    ) -> float:
        """Calculate strategic opening offer"""
        market_value = player_data["market_value"]

        # Base on negotiation strength
        if position_strength["strength"] == "Strong":
            multiplier = 0.75
        elif position_strength["strength"] == "Moderate":
            multiplier = 0.85
        else:
            multiplier = 0.95

        # Adjust for market conditions
        if market_analysis["value_assessment"]["assessment"] == "Overvalued":
            multiplier *= 0.9
        elif market_analysis["value_assessment"]["assessment"] == "Undervalued":
            multiplier *= 1.1

        return market_value * multiplier

    def _identify_negotiation_points(self, player_data: Dict, team_data: Dict) -> List[Dict]:
        """Identify key points for negotiation"""
        points = []

        # Age and contract length
        if player_data["age"] < 25:
            points.append(
                {
                    "topic": "Development potential",
                    "argument": "Significant room for growth and future value",
                    "counter_argument": "Unproven at highest level",
                }
            )

        # Performance trends
        if player_data["performance_index"]["trend"] > 0:
            points.append(
                {
                    "topic": "Form trajectory",
                    "argument": "Improving performance trend suggests higher future value",
                    "counter_argument": "Current form may not be sustainable",
                }
            )

        # Market conditions
        points.append(
            {
                "topic": "Market alternatives",
                "argument": f"{len(team_data.get('alternative_targets', []))} alternative targets identified",
                "counter_argument": "Player offers unique qualities not found in alternatives",
            }
        )

        return points

    def _identify_leverage_factors(self, player_data: Dict, team_data: Dict) -> Dict:
        """Identify factors that provide negotiation leverage"""
        our_leverage = []
        their_leverage = []

        # Our leverage
        if player_data.get("contract_expires_months", 24) < 18:
            our_leverage.append("Short contract remaining")
        if team_data.get("alternative_targets"):
            our_leverage.append("Alternative options available")
        if not player_data.get("other_interested_clubs"):
            our_leverage.append("Limited competition for signature")

        # Their leverage
        if player_data.get("key_player", False):
            their_leverage.append("Key player for selling club")
        if player_data.get("long_contract", False):
            their_leverage.append("Long contract remaining")
        if player_data.get("multiple_suitors", False):
            their_leverage.append("Multiple clubs interested")

        return {
            "our_leverage": our_leverage,
            "their_leverage": their_leverage,
            "balance": (
                "In our favor"
                if len(our_leverage) > len(their_leverage)
                else "Balanced" if len(our_leverage) == len(their_leverage) else "In their favor"
            ),
        }

    def _create_negotiation_timeline(self, player_data: Dict) -> Dict:
        """Create recommended negotiation timeline"""
        urgency = "High" if player_data.get("multiple_suitors", False) else "Medium"

        if urgency == "High":
            timeline = {
                "initial_contact": "Immediately",
                "first_offer": "Within 48 hours",
                "negotiation_window": "1-2 weeks",
                "decision_deadline": "2 weeks",
            }
        else:
            timeline = {
                "initial_contact": "Within 1 week",
                "first_offer": "Within 2 weeks",
                "negotiation_window": "2-4 weeks",
                "decision_deadline": "4-6 weeks",
            }

        return timeline

    def _recommend_payment_structure(self, total_fee: float, team_data: Dict) -> Dict:
        """Recommend payment structure"""
        if team_data["budget"] > total_fee * 2:
            # Cash rich
            return {
                "structure": "Front-loaded",
                "initial_payment": 0.6,
                "installments": 2,
                "add_ons": 0.2,
            }
        else:
            # Budget conscious
            return {
                "structure": "Balanced",
                "initial_payment": 0.3,
                "installments": 4,
                "add_ons": 0.25,
            }

    def _recommend_negotiation_tactics(self, position_strength: Dict) -> List[str]:
        """Recommend specific negotiation tactics"""
        if position_strength["strength"] == "Strong":
            return [
                "Start with aggressive opening offer",
                "Set firm deadlines",
                "Emphasize alternative options",
                "Be prepared to walk away",
            ]
        elif position_strength["strength"] == "Moderate":
            return [
                "Build relationship first",
                "Find win-win scenarios",
                "Be flexible on payment terms",
                "Focus on total package value",
            ]
        else:
            return [
                "Emphasize player's desire to join",
                "Highlight project ambition",
                "Be flexible on all terms",
                "Consider player exchange options",
            ]

    def _create_contingency_plans(self, player_data: Dict) -> List[Dict]:
        """Create contingency plans for negotiation scenarios"""
        return [
            {
                "scenario": "Selling club rejects initial offers",
                "action": "Activate interest in alternative target #1",
                "timeline": "Within 48 hours of rejection",
            },
            {
                "scenario": "Competing bid from rival club",
                "action": "Fast-track negotiations and improve personal terms",
                "timeline": "Immediate response required",
            },
            {
                "scenario": "Player wage demands excessive",
                "action": "Propose performance-based structure with lower base",
                "timeline": "Counter within 24 hours",
            },
        ]

    def generate_full_report(self, player_data: Dict, team_data: Dict) -> Dict:
        """Generate complete scouting report"""

        # Calculate match score if not provided
        if "match_score" not in player_data:
            # Simple match score calculation
            player_data["match_score"] = 75.0  # Placeholder

        # Generate all report sections
        report = {
            "report_metadata": {
                "generated_date": datetime.now().isoformat(),
                "player_name": player_data["name"],
                "player_id": player_data["id"],
                "team_name": team_data["name"],
                "team_id": team_data["id"],
            },
            "executive_summary": self.generate_executive_summary(player_data, team_data),
            "statistical_overview": self.generate_statistical_overview(player_data, team_data),
            "tactical_analysis": self.generate_tactical_analysis(player_data, team_data),
            "physical_profile": self.generate_physical_profile(player_data),
            "market_analysis": self.generate_market_analysis(player_data, team_data),
            "comparison_analysis": self.generate_comparison_analysis(player_data, team_data),
            "risk_assessment": self.generate_risk_assessment(player_data, team_data),
            "negotiation_strategy": self.generate_negotiation_strategy(
                player_data, team_data, self.generate_market_analysis(player_data, team_data)
            ),
        }

        return report


# Example usage
if __name__ == "__main__":
    # Create sample player data
    player_data = {
        "id": "P001",
        "name": "Lucas Silva",
        "age": 23,
        "position": "CAM",
        "nationality": "Brazil",
        "current_team": "Santos FC",
        "current_league": "Serie A Brazil",
        "market_value": 25000000,
        "contract_expires_months": 18,
        "match_score": 87.5,
        "performance_index": {"value": 78.5, "trend": 2.3, "volatility": 0.15, "confidence": 0.85},
        "metrics": {
            "passing": {
                "completion_rate": 0.82,
                "progressive_passes_per_90": 4.2,
                "key_passes_per_90": 2.8,
                "pass_difficulty_score": 0.72,
            },
            "shooting": {
                "shots_per_90": 2.4,
                "xG_per_shot": 0.18,
                "conversion_rate": 0.15,
                "goals_per_90": 0.25,
                "assists_per_90": 0.35,
            },
            "movement": {
                "distance_covered_per_90": 10.5,
                "high_intensity_runs": 28,
                "average_speed": 7.2,
            },
            "defensive": {
                "tackles_per_90": 1.5,
                "interceptions_per_90": 2.1,
                "aerial_duels_won": 0.45,
            },
        },
        "performance_history": [
            {"rating": 7.2, "goals": 0, "assists": 1},
            {"rating": 7.8, "goals": 1, "assists": 0},
            {"rating": 8.1, "goals": 1, "assists": 1},
            {"rating": 7.5, "goals": 0, "assists": 0},
            {"rating": 8.3, "goals": 2, "assists": 0},
        ]
        * 4,  # Repeat for more history
        "injury_history": [{"date": "2024-03", "injury": "Hamstring strain", "days_missed": 21}],
    }

    # Create sample team data
    team_data = {
        "id": "T001",
        "name": "FC Metropolitan",
        "league": "Premier League",
        "country": "England",
        "budget": 100000000,
        "formation": "4-3-3",
        "playing_style": {
            "possession": 0.65,
            "pressing_intensity": 0.78,
            "defensive_line": "high",
            "attacking": True,
            "high_press": True,
        },
        "priority_positions": ["CAM", "RW"],
        "alternative_targets": ["P002", "P003"],
    }

    # Generate report
    generator = ScoutingReportGenerator()
    report = generator.generate_full_report(player_data, team_data)

    # Print executive summary
    print("SCOUTING REPORT - EXECUTIVE SUMMARY")
    print("=" * 60)
    print(f"Player: {player_data['name']} ({player_data['position']}, {player_data['age']} years)")
    print(f"Target Club: {team_data['name']}")
    print(f"Match Score: {report['executive_summary']['match_score']}%")
    print(f"\nRecommendation: {report['executive_summary']['recommendation']}")
    print(f"Action: {report['executive_summary']['action']}")
    print(f"\nKey Findings:")
    for finding in report["executive_summary"]["key_findings"]:
        print(f"  • {finding}")

    # Print statistical highlights
    print(f"\n\nSTATISTICAL HIGHLIGHTS")
    print("=" * 60)
    stats = report["statistical_overview"]
    print("Strengths:")
    for strength in stats["statistical_strengths"][:3]:
        print(f"  • {strength}")
    print("\nAreas for Development:")
    for weakness in stats["statistical_weaknesses"][:2]:
        print(f"  • {weakness}")
    print(f"\nConsistency: {stats['consistency_rating']['rating']}")
    print(f"Form: {stats['form_trajectory']['trend']}")

    # Print negotiation summary
    print(f"\n\nNEGOTIATION STRATEGY")
    print("=" * 60)
    negotiation = report["negotiation_strategy"]
    print(f"Position Strength: {negotiation['negotiation_position']['strength']}")
    print(f"Opening Offer: €{negotiation['offer_strategy']['opening_offer']/1000000:.1f}M")
    print(f"Maximum Offer: €{negotiation['offer_strategy']['maximum_offer']/1000000:.1f}M")
    print(f"Timeline: {negotiation['timeline']['negotiation_window']}")
    print("\nKey Tactics:")
    for tactic in negotiation["tactics"][:3]:
        print(f"  • {tactic}")
