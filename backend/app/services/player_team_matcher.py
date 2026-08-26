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

    # A squad this thin at a position is a gap whoever is already there.
    HEALTHY_DEPTH = 3

    def _positional_need(self, player: Player, team: Team) -> tuple:
        """How badly this club needs this position, read from its actual squad.

        Position needs used to come only from a hand-written list of four
        priorities per club. With twenty clubs that is eighty slots for nine
        positions, so whether a player "fits a need" was decided by how the
        list happened to be written — a right winger matched four clubs and
        missed sixteen. Squad membership now answers the question directly:
        a club needs a position when it has few players there, or when the ones
        it has fall short of the level the club operates at. The curated list
        stays as a fallback for clubs with no squad on file.

        Returns (score, basis) so the report can say which one was used.
        """
        team_id = getattr(team, "team_id", None)
        squad = []
        if team_id:
            try:
                rows = self._query_squad(int(team_id), player.position)
                squad = [float(r[0]) for r in rows if r[0] is not None]
            except Exception:  # noqa: BLE001 - fall back to the curated list
                squad = []

        # An empty result means one of two very different things, and treating
        # them alike wasted the strongest signal available: a club with a squad
        # on file and nobody in this position has a hole, which is maximum
        # need — not missing data.
        if not squad and self._squad_size(team_id):
            return 1.0, f"no {player.position} in the squad at all"

        if not squad:
            needs = team.position_needs or []
            if player.position in needs:
                return 1.0, "listed as a club priority"
            if any(p in needs for p in self.ADJACENT_POSITIONS.get(player.position, [])):
                return 0.75, "adjacent to a club priority"
            return 0.55, "not among the club's listed priorities"

        # Depth: fewer bodies at the position means more need
        depth_need = max(0.0, min(1.0, (self.HEALTHY_DEPTH - len(squad)) / self.HEALTHY_DEPTH))

        # Quality: how the incumbents compare to the club's expected level
        expected = getattr(team, "expected_index", None) or 70.0
        best_incumbent = max(squad)
        quality_need = max(0.0, min(1.0, (float(expected) - best_incumbent) / 20.0))

        need = 0.45 + (depth_need * 0.30) + (quality_need * 0.25)
        basis = (
            f"{len(squad)} {player.position}(s) in the squad, "
            f"best index {best_incumbent:.1f} vs club level {float(expected):.0f}"
        )
        return round(min(1.0, need), 3), basis

    def _squad_size(self, team_id) -> int:
        """How many players the club has on file, regardless of position."""
        if not team_id:
            return 0
        from sqlalchemy import text

        from app.db.database import SessionLocal

        session = SessionLocal()
        try:
            row = session.execute(
                text("SELECT count(*) FROM squad_memberships WHERE team_id = :t"),
                {"t": int(team_id)},
            ).fetchone()
            return int(row[0]) if row else 0
        except Exception:  # noqa: BLE001
            return 0
        finally:
            session.close()

    def _query_squad(self, team_id: int, position: str) -> list:
        """Indices of the club's current players in a position."""
        from sqlalchemy import text

        from app.db.database import SessionLocal

        session = SessionLocal()
        try:
            return session.execute(text("""
                SELECT COALESCE((p.performance_index->>'value')::float, 0)
                FROM squad_memberships m
                JOIN players p ON p.id = m.player_id
                WHERE m.team_id = :team_id AND p.position = :position
            """), {"team_id": team_id, "position": position}).fetchall()
        finally:
            session.close()

    def calculate_tactical_fit(self, player: Player, team: Team) -> float:
        """How well the player suits the team's needs and playing style.

        Replaces the previous hardcoded style placeholder: the style component
        now compares the player's actual metrics against the club's declared
        possession / pressing profile.
        """
        position_match, self._last_need_basis = self._positional_need(player, team)

        # Evened out from 60/40: the position side leans on curation (or on a
        # squad that may be small), while the style side is measured from match
        # events, so neither should dominate the other.
        style_score = self._calculate_style_score(player, team)
        return position_match * 0.5 + style_score * 0.5

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

        # Affordability is still a gate — cheapness is never rewarded — but a
        # flat 1.0 for everything comfortably affordable made this component
        # constant across most moves, so it carried no information. Grading the
        # easy range by how much of the budget the fee consumes distinguishes
        # "the club barely notices" from "this is their signing of the year",
        # which is a real difference to a sporting director.
        if share <= 0.05:
            return 1.0                                      # pocket change
        if share <= 0.25:
            return 1.0 - (share - 0.05) * (0.15 / 0.20)     # 1.00 -> 0.85
        if share <= 0.60:
            return 0.85 - (share - 0.25) * (0.25 / 0.35)    # 0.85 -> 0.60
        if share <= 1.0:
            return 0.6 - (share - 0.60) * (0.35 / 0.40)     # 0.60 -> 0.25
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

    # Age the pipeline assigns when no birth date is available in the source
    ASSUMED_AGE = 26

    def calculate_growth_potential(self, player: Player, team: Team = None) -> float:
        """How much this player stands to develop AT THIS CLUB.

        This used to take only the player, so the same number repeated across
        every destination and the component never helped choose between clubs.
        Development is a two-sided thing: the player brings age and trajectory,
        the club brings a level to grow into. A rising player has room at a club
        that operates above him and little at one he already outgrows.
        """
        index_data = getattr(player, "performance_index", None) or {}
        index = index_data.get("value") if isinstance(index_data, dict) else None
        if not isinstance(index, (int, float)):
            index = player.calculate_performance_index().get("value", 70)

        # Trajectory: is he trending up?
        trend = player.calculate_performance_index().get("trend", 0)
        trend_score = max(0.0, min(1.0, 0.5 + float(trend) / 10))

        # Age is uniform in this dataset (no birth dates available), so it is
        # held neutral rather than pretending to discriminate. Real ages make
        # this branch meaningful without further changes.
        age = getattr(player, "age", None)
        age_score = 0.5 if not age or age == self.ASSUMED_AGE else (
            max(0.0, 1 - (age - 23) / 15) if age < 30 else 0.2
        )

        if team is None:
            return age_score * 0.4 + trend_score * 0.6

        # Headroom: how far the club's level sits above the player's.
        expected = getattr(team, "expected_index", None)
        if not expected:
            headroom_score = 0.5
        else:
            gap = (float(expected) - float(index)) / 20.0
            if gap >= 0:
                # Room to grow, best when the club is a clear step up
                headroom_score = min(1.0, 0.55 + gap * 0.9)
            else:
                # Already at or above the club's level: there is no upside left
                # to measure, so this reads NEUTRAL rather than poor. Being
                # overqualified is already penalised inside performance fit via
                # level fit; scoring it low here too punished the same fact
                # twice and cost the strongest players several points for
                # having nothing left to learn.
                headroom_score = max(0.45, 0.55 + gap * 0.15)

        return age_score * 0.25 + trend_score * 0.35 + headroom_score * 0.40

    def calculate_match_score(self, player: Player, team: Team) -> Dict:
        """Calculate overall match score between player and team"""
        tactical = self.calculate_tactical_fit(player, team)
        performance = self.calculate_performance_fit(player, team)
        financial = self.calculate_financial_fit(player, team)
        growth = self.calculate_growth_potential(player, team)

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
