import numpy as np
from typing import Dict, List


class Player:
    """Represents a football player with performance metrics"""

    def __init__(self, player_id: str, name: str, age: int, position: str):
        self.id = player_id
        self.name = name
        self.age = age
        self.position = position
        self.metrics = {}
        self.performance_history = []
        self.market_value = 0
        self.performance_index = None
        self.playing_style_vector = None

    def add_performance_data(self, match_data: Dict):
        """Add match performance data"""
        self.performance_history.append(match_data)
        self._update_metrics()

    def _update_metrics(self):
        """Calculate aggregated metrics from performance history"""
        if not self.performance_history:
            return

        recent_games = self.performance_history[-10:]  # Last 10 games

        self.metrics = {
            "passing": {
                "completion_rate": np.mean([g.get("pass_completion", 0) for g in recent_games]),
                "progressive_passes_per_90": np.mean(
                    [g.get("progressive_passes", 0) for g in recent_games]
                ),
                "key_passes_per_90": np.mean([g.get("key_passes", 0) for g in recent_games]),
                "pass_difficulty_score": np.mean(
                    [g.get("pass_difficulty", 0.5) for g in recent_games]
                ),
            },
            "shooting": {
                "shots_per_90": np.mean([g.get("shots", 0) for g in recent_games]),
                "xG_per_shot": (
                    lambda xgs: np.mean(xgs) if xgs else 0.0
                )([g.get("xG", 0) for g in recent_games if g.get("shots", 0) > 0]),
                "conversion_rate": sum([g.get("goals", 0) for g in recent_games])
                / max(sum([g.get("shots", 0) for g in recent_games]), 1),
            },
            "movement": {
                "distance_covered_per_90": np.mean([g.get("distance_km", 0) for g in recent_games]),
                "high_intensity_runs": np.mean([g.get("sprints", 0) for g in recent_games]),
                "average_speed": np.mean([g.get("avg_speed", 0) for g in recent_games]),
            },
            "defensive": {
                "tackles_per_90": np.mean([g.get("tackles", 0) for g in recent_games]),
                "interceptions_per_90": np.mean([g.get("interceptions", 0) for g in recent_games]),
                "aerial_duels_won": np.mean([g.get("aerial_won_pct", 0) for g in recent_games]),
            },
        }

    def calculate_performance_index(self) -> Dict:
        """Calculate stock-like performance index"""
        if len(self.performance_history) < 5:
            return {"value": 50, "trend": 0, "volatility": 0}

        # Calculate performance scores for each game
        scores = []
        for game in self.performance_history[-20:]:
            score = (
                game.get("rating", 5) * 10
                + game.get("goals", 0) * 20
                + game.get("assists", 0) * 15
                + game.get("key_passes", 0) * 5
                + game.get("pass_completion", 0.7) * 20
            )
            scores.append(score)

        # Calculate trend (simple linear regression slope)
        x = np.arange(len(scores))
        trend = np.polyfit(x, scores, 1)[0]

        # Calculate volatility
        volatility = np.std(scores) / np.mean(scores) if np.mean(scores) > 0 else 0

        # Current value (weighted average of recent performances)
        weights = np.exp(np.linspace(-1, 0, min(5, len(scores))))
        weights /= weights.sum()
        current_value = np.average(scores[-5:], weights=weights) if len(scores) >= 5 else scores[-1]

        return {
            "value": current_value,
            "trend": trend,
            "volatility": volatility,
            "confidence": max(0.0, min(1.0, 1 - volatility)),
        }


class Team:
    """Represents a football team with requirements and constraints"""

    def __init__(self, team_id: str, name: str, league: str, budget: float):
        self.id = team_id
        self.name = name
        self.league = league
        self.budget = budget
        self.formation = "4-3-3"
        self.playing_style = {}
        self.position_needs = {}
        self.performance_requirements = {}
        self.expected_index = None

    def set_requirements(self, requirements: Dict):
        """Set team requirements for player matching"""
        self.position_needs = requirements.get("positions", {})
        self.performance_requirements = requirements.get("performance", {})
        self.playing_style = requirements.get("style", {})


class PlayerTeamMatcher:
    """Main matching engine"""

    def __init__(self):
        # Financial fit is now an affordability gate: it reads 1.0 for most
        # realistic moves, so it carries little information and gets less
        # weight. Growth depends only on the player, so it never separates one
        # club from another either. Tactical and performance are what actually
        # discriminate between destinations, so they carry the score.
        self.weights = {
            "tactical_fit": 0.35,
            "performance_match": 0.40,
            "financial_fit": 0.10,
            "potential_growth": 0.15,
        }

    # Positions a player can credibly cover beyond their primary one
    ADJACENT_POSITIONS = {
        "ST": ["CAM", "RW", "LW"], "CAM": ["CM", "ST", "RW", "LW"],
        "RW": ["LW", "ST", "CAM", "RM"], "LW": ["RW", "ST", "CAM", "LM"],
        "CM": ["CAM", "CDM", "RM", "LM"], "CDM": ["CM", "CB"],
        "CB": ["CDM", "RB", "LB"], "RB": ["LB", "CB", "RM"], "LB": ["RB", "CB", "LM"],
    }

    def calculate_tactical_fit(self, player: Player, team: Team) -> float:
        """How well the player suits the team's needs and playing style.

        Replaces the previous hardcoded style placeholder: the style component
        now compares the player's actual metrics against the club's declared
        possession / pressing profile.
        """
        needs = team.position_needs or []
        if player.position in needs:
            position_match = 1.0
        elif any(p in needs for p in self.ADJACENT_POSITIONS.get(player.position, [])):
            position_match = 0.75          # can adapt to an adjacent role
        else:
            position_match = 0.4

        style_score = self._calculate_style_score(player, team)
        return position_match * 0.6 + style_score * 0.4

    # What "good" looks like per role, so style fit stops using one yardstick.
    STYLE_REFERENCE = {
        "attack":   {"completion": 0.80, "progressive": 4.0, "actions": 1.5},
        "midfield": {"completion": 0.87, "progressive": 6.0, "actions": 4.0},
        "defense":  {"completion": 0.90, "progressive": 5.0, "actions": 5.0},
    }

    def _calculate_style_score(self, player: Player, team: Team) -> float:
        """Match player output against the club's tactical identity.

        References are per position group: judging a striker's pressing by the
        same tackle count as a midfielder repeated the defensive bias we had
        already removed from performance fit.
        """
        style = team.playing_style or {}
        metrics = player.metrics or {}
        if not style or not metrics:
            return 0.6

        group = self.POSITION_GROUP.get(player.position, "midfield")
        ref = self.STYLE_REFERENCE[group]

        passing = metrics.get("passing", {})
        defensive = metrics.get("defensive", {})
        components = []

        possession = style.get("possession")
        if possession is not None:
            completion = passing.get("completion_rate") or 0
            progressive = passing.get("progressive_passes_per_90") or 0
            passing_quality = (
                min(completion / ref["completion"], 1.0) * 0.6
                + min(progressive / ref["progressive"], 1.0) * 0.4
            )
            components.append(passing_quality * possession + (1 - possession) * 0.6)

        pressing = style.get("pressing_intensity")
        if pressing is not None:
            actions = (defensive.get("tackles_per_90") or 0) + (defensive.get("interceptions_per_90") or 0)
            work_rate = min(actions / ref["actions"], 1.0)
            components.append(work_rate * pressing + (1 - pressing) * 0.6)

        return float(np.mean(components)) if components else 0.6

    # Position-aware reference values (per 90) used to normalize performance.
    # Declared curation: elite-ish targets per role, not scraped data.
    POSITION_METRICS = {
        "attack": [
            ("shooting", "goals_per_90", 0.5),
            ("shooting", "assists_per_90", 0.3),
            ("shooting", "shots_per_90", 3.0),
            ("shooting", "xG_per_shot", 0.15),
            ("passing", "key_passes_per_90", 2.0),
        ],
        "midfield": [
            ("passing", "completion_rate", 0.85),
            ("passing", "progressive_passes_per_90", 6.0),
            ("passing", "key_passes_per_90", 1.8),
            ("defensive", "tackles_per_90", 2.5),
            ("defensive", "interceptions_per_90", 2.5),
        ],
        "defense": [
            ("defensive", "tackles_per_90", 3.0),
            ("defensive", "interceptions_per_90", 3.0),
            ("passing", "completion_rate", 0.85),
            ("passing", "progressive_passes_per_90", 4.0),
        ],
    }

    POSITION_GROUP = {
        "ST": "attack", "RW": "attack", "LW": "attack", "CAM": "attack",
        "CM": "midfield", "CDM": "midfield", "RM": "midfield", "LM": "midfield",
        "CB": "defense", "RB": "defense", "LB": "defense", "GK": "defense",
    }

    def calculate_performance_fit(self, player: Player, team: Team) -> float:
        """Score the player's output against role-appropriate expectations.

        Previously this only checked pass completion and defensive actions,
        which structurally penalised attackers (a striker doesn't tackle).
        Now each position group is judged on the metrics that matter for it.
        """
        if not player.metrics:
            return 0.5

        group = self.POSITION_GROUP.get(player.position, "midfield")
        scores = []
        for category, metric, reference in self.POSITION_METRICS[group]:
            value = player.metrics.get(category, {}).get(metric)
            if value is None or reference <= 0:
                continue
            scores.append(min(float(value) / reference, 1.0))

        # Respect explicit team requirements when provided
        reqs = team.performance_requirements or {}
        if "min_pass_completion" in reqs and reqs["min_pass_completion"]:
            cr = player.metrics.get("passing", {}).get("completion_rate")
            if cr is not None:
                scores.append(min(float(cr) / reqs["min_pass_completion"], 1.0))
        if "min_defensive_actions" in reqs and reqs["min_defensive_actions"]:
            d = player.metrics.get("defensive", {})
            actions = (d.get("tackles_per_90") or 0) + (d.get("interceptions_per_90") or 0)
            scores.append(min(actions / reqs["min_defensive_actions"], 1.0))

        role_score = float(np.mean(scores)) if scores else 0.6
        level_score = self._calculate_level_fit(player, team)
        return role_score * 0.6 + level_score * 0.4

    def calculate_financial_fit(self, player: Player, team: Team) -> float:
        """Affordability, not cheapness.

        The old formula rewarded low value: the cheaper a player was relative
        to the budget, the closer to 1.0 the score — so a modest player scored
        better financially at a rich club than a star did. Affordability is
        really a gate: everything comfortably affordable scores the same, and
        the score only drops as the fee starts to strain the budget.
        """
        if player.market_value <= 0 or team.budget <= 0:
            return 0.7  # unknown value or budget: neutral, never a bonus

        share = player.market_value / team.budget
        if share <= 0.25:
            return 1.0
        if share <= 0.60:
            return 1.0 - (share - 0.25) * (0.4 / 0.35)
        if share <= 1.0:
            return 0.6 - (share - 0.60) * (0.35 / 0.40)
        return max(0.1, 0.25 - (share - 1.0) * 0.15)

    def _calculate_level_fit(self, player: Player, team: Team) -> float:
        """Is the player at the level this club operates at?

        Without this the matcher had no notion of standing: every club was
        judged against the same fixed reference values, so a modest player
        scored much the same at an elite club as anywhere else.
        """
        expected = getattr(team, "expected_index", None)
        index_data = getattr(player, "performance_index", None) or {}
        index = index_data.get("value") if isinstance(index_data, dict) else None

        if not expected or not isinstance(index, (int, float)) or index <= 0:
            return 0.7

        ratio = float(index) / float(expected)
        if ratio < 1.0:
            return max(0.0, 1.0 - (1.0 - ratio) * 4.0)
        if ratio <= 1.25:
            return 1.0
        return max(0.5, 1.0 - (ratio - 1.25) * 0.8)

    def calculate_growth_potential(self, player: Player) -> float:
        """Calculate player's growth potential"""
        # Age factor
        age_score = max(0, 1 - (player.age - 23) / 15) if player.age < 30 else 0.2

        # Performance trend
        perf_index = player.calculate_performance_index()
        trend_score = min(1.0, 0.5 + perf_index["trend"] / 10)

        return age_score * 0.6 + trend_score * 0.4

    def calculate_match_score(self, player: Player, team: Team) -> Dict:
        """Calculate overall match score between player and team"""
        tactical = self.calculate_tactical_fit(player, team)
        performance = self.calculate_performance_fit(player, team)
        financial = self.calculate_financial_fit(player, team)
        growth = self.calculate_growth_potential(player)

        overall = (
            tactical * self.weights["tactical_fit"]
            + performance * self.weights["performance_match"]
            + financial * self.weights["financial_fit"]
            + growth * self.weights["potential_growth"]
        ) * 100

        return {
            "overall_score": round(overall, 1),
            "breakdown": {
                "tactical_fit": round(tactical * 100, 1),
                "performance_match": round(performance * 100, 1),
                "financial_fit": round(financial * 100, 1),
                "growth_potential": round(growth * 100, 1),
            },
        }

    def calculate_fit_score(self, db, player_id, team_id) -> Dict:
        """Score a player against a team by id, loading both from the database.

        Three call sites (team_service, analytics_service x2) have always called
        this method, but it did not exist — every call raised AttributeError.
        team_service swallowed it in a try/except and returned nothing;
        analytics_service surfaced it as a 500.
        """
        from app.db import models  # local import avoids a circular dependency

        db_player = db.query(models.Player).filter(models.Player.id == int(player_id)).first()
        db_team = db.query(models.Team).filter(models.Team.id == int(team_id)).first()
        if not db_player or not db_team:
            return {
                "overall_score": 0.0,
                "breakdown": {},
                "error": "player or team not found",
            }

        player = Player(
            player_id=str(db_player.id),
            name=db_player.name or "",
            age=db_player.age or 26,
            position=db_player.position or "",
        )
        player.market_value = float(db_player.market_value or 0)
        # Metrics may carry None for values the pipeline could not compute;
        # the scoring maths needs numbers.
        player.metrics = {
            category: {k: (0.0 if v is None else v) for k, v in values.items()}
            for category, values in (db_player.metrics or {}).items()
            if isinstance(values, dict)
        }
        player.performance_history = db_player.performance_history or []
        player.performance_index = db_player.performance_index or None

        team = Team(
            team_id=str(db_team.id),
            name=db_team.name or "",
            league=db_team.league or "",
            budget=float(db_team.budget or 0),
        )
        team.formation = db_team.formation or "4-3-3"
        team.playing_style = db_team.playing_style or {}
        requirements = db_team.requirements or {}
        team.position_needs = requirements.get("positions", [])
        team.performance_requirements = requirements.get("performance", {})
        team.expected_index = requirements.get("expected_index")

        return self.calculate_match_score(player, team)

    def find_matches(
        self, player: Player, teams: List[Team], min_score: float = 70.0
    ) -> List[Dict]:
        """Find all compatible teams for a player"""
        matches = []

        for team in teams:
            score = self.calculate_match_score(player, team)
            if score["overall_score"] >= min_score:
                matches.append(
                    {
                        "team": team,
                        "score": score,
                        "recommendation": self.generate_recommendation(player, team, score),
                    }
                )

        return sorted(matches, key=lambda x: x["score"]["overall_score"], reverse=True)

    def generate_recommendation(self, player: Player, team: Team, score: Dict) -> str:
        """Generate a recommendation summary"""
        if score["overall_score"] >= 85:
            strength = "Excellent"
        elif score["overall_score"] >= 75:
            strength = "Strong"
        else:
            strength = "Good"

        return f"{strength} match - {player.name} shows high compatibility with {team.name}'s requirements"


class NegotiationReportGenerator:
    """Generates detailed negotiation reports"""

    def __init__(self):
        self.market_multiplier = 1000000  # Convert to millions

    def generate_report(self, player: Player, team: Team, match_score: Dict) -> Dict:
        """Generate comprehensive negotiation report"""
        # Unit: euros (absolute). Fallback default is 10M euros, not 10.
        player_value = player.market_value if player.market_value > 0 else 10_000_000

        # Calculate offer range based on match score and budget
        base_offer = min(player_value * 0.8, team.budget * 0.3)
        max_offer = min(player_value * 1.2, team.budget * 0.5)

        strengths = []
        concerns = []

        # Analyze strengths and concerns
        if match_score["breakdown"]["tactical_fit"] > 80:
            strengths.append("Excellent tactical fit with team's playing style")
        if match_score["breakdown"]["performance_match"] > 75:
            strengths.append("Performance metrics exceed team requirements")
        if match_score["breakdown"]["growth_potential"] > 70:
            strengths.append("High growth potential based on age and trend")

        if match_score["breakdown"]["financial_fit"] < 60:
            concerns.append("Player value may strain budget constraints")
        if player.age > 28:
            concerns.append("Limited resale value due to age")

        return {
            "executive_summary": {
                "player_name": player.name,
                "team_name": team.name,
                "match_score": match_score["overall_score"],
                "recommendation": (
                    "Proceed with negotiation"
                    if match_score["overall_score"] > 75
                    else "Consider alternatives"
                ),
            },
            "financial_analysis": {
                "current_market_value": f"€{player_value/1_000_000:.1f}M",
                "recommended_offer_range": {
                    "minimum": f"€{base_offer/1_000_000:.1f}M",
                    "maximum": f"€{max_offer/1_000_000:.1f}M",
                },
                "budget_impact": f"{(base_offer/team.budget)*100:.1f}% of available budget",
            },
            "key_points": {"strengths": strengths, "concerns": concerns},
            "negotiation_strategy": {
                "opening_offer": f"€{base_offer/1_000_000:.1f}M",
                "contract_length": "3-4 years" if player.age < 28 else "2-3 years",
                "performance_bonuses": "Recommended to align interests",
                "key_talking_points": [
                    f"Player fits {team.formation} formation perfectly",
                    "Recent performance trend shows consistent improvement",
                    "Style of play complements existing squad",
                ],
            },
        }


# Example usage and demonstration
def create_sample_data():
    """Create sample players and teams for demonstration"""
    # Create sample players
    players = []

    # Player 1: Young attacking midfielder
    p1 = Player("P001", "Lucas Silva", 23, "CAM")
    p1.market_value = 25  # €25M
    # Add sample performance data
    for i in range(10):
        p1.add_performance_data(
            {
                "rating": 7.5 + np.random.normal(0, 0.5),
                "goals": np.random.poisson(0.3),
                "assists": np.random.poisson(0.4),
                "key_passes": np.random.poisson(2),
                "pass_completion": 0.82 + np.random.normal(0, 0.05),
                "distance_km": 10.5 + np.random.normal(0, 1),
                "tackles": np.random.poisson(1.5),
                "interceptions": np.random.poisson(2),
            }
        )
    players.append(p1)

    # Player 2: Experienced defender
    p2 = Player("P002", "Marco Rossi", 29, "CB")
    p2.market_value = 15  # €15M
    for i in range(10):
        p2.add_performance_data(
            {
                "rating": 7.2 + np.random.normal(0, 0.3),
                "goals": np.random.poisson(0.05),
                "assists": np.random.poisson(0.1),
                "key_passes": np.random.poisson(0.5),
                "pass_completion": 0.88 + np.random.normal(0, 0.03),
                "distance_km": 9.5 + np.random.normal(0, 0.8),
                "tackles": np.random.poisson(3),
                "interceptions": np.random.poisson(4),
                "aerial_won_pct": 0.65 + np.random.normal(0, 0.1),
            }
        )
    players.append(p2)

    # Create sample teams
    teams = []

    # Team 1: Wealthy club needing attacking midfielder
    t1 = Team("T001", "FC Metropolitan", "Premier League", 100)  # €100M budget
    t1.set_requirements(
        {
            "positions": ["CAM", "CM", "RW"],
            "performance": {"min_pass_completion": 0.80, "min_defensive_actions": 3.0},
            "style": {"attacking": True, "high_press": True},
        }
    )
    teams.append(t1)

    # Team 2: Mid-tier club needing defender
    t2 = Team("T002", "Athletic United", "Serie A", 40)  # €40M budget
    t2.set_requirements(
        {
            "positions": ["CB", "LB", "CDM"],
            "performance": {"min_pass_completion": 0.85, "min_defensive_actions": 6.0},
            "style": {"defensive": True, "possession": True},
        }
    )
    teams.append(t2)

    return players, teams


# Run demonstration
if __name__ == "__main__":
    # Create sample data
    players, teams = create_sample_data()

    # Initialize matcher and report generator
    matcher = PlayerTeamMatcher()
    report_gen = NegotiationReportGenerator()

    print("FOOTBALL PLAYER-TEAM MATCHING SYSTEM")
    print("=" * 50)

    # Find matches for each player
    for player in players:
        print(f"\n--- Analyzing {player.name} ({player.position}, Age: {player.age}) ---")

        # Calculate performance index
        perf_index = player.calculate_performance_index()
        print(f"Performance Index: {perf_index['value']:.1f} (Trend: {perf_index['trend']:+.2f})")

        # Find matches
        matches = matcher.find_matches(player, teams, min_score=50)

        if matches:
            print(f"\nFound {len(matches)} compatible teams:")
            for match in matches:
                team = match["team"]
                score = match["score"]
                print(f"\n{team.name} - Overall Score: {score['overall_score']:.1f}%")
                print(f"  Tactical Fit: {score['breakdown']['tactical_fit']:.1f}%")
                print(f"  Performance Match: {score['breakdown']['performance_match']:.1f}%")
                print(f"  Financial Fit: {score['breakdown']['financial_fit']:.1f}%")
                print(f"  Growth Potential: {score['breakdown']['growth_potential']:.1f}%")

                # Generate negotiation report for top match
                if match == matches[0]:
                    report = report_gen.generate_report(player, team, score)
                    print(f"\n  NEGOTIATION REPORT:")
                    print(f"  Recommended Offer: {report['negotiation_strategy']['opening_offer']}")
                    print(f"  Budget Impact: {report['financial_analysis']['budget_impact']}")
        else:
            print("No compatible teams found")

    print("\n" + "=" * 50)
    print("Analysis Complete")
