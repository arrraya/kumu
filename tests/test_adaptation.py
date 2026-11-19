"""
Kumü — a player does not move leagues to join the club he plays for
====================================================================

    python3 tests/test_adaptation.py

`_assess_adaptation_risk` opened with:

    if player_data.get("current_league") != team_data["league"]:
        risk_score += 25
        factors.append("Moving to new league")

`players` has no league column. It never has. So the left side was None
for every player in the database and the right side never is, and every
report ever generated scored twenty-five points of adaptation risk and
listed "Moving to new league" — including K. Jelacic assessed for
Brisbane Roar, which is where he plays. He came out at 60% adaptation
risk for staying put.

A term with the same value for everyone carries no information, which
the handbook already says about the financial component. This one was
worse: it was also false.

The league is recoverable. `player_market` has always read the club of a
player's open squad spell to decide which market prices him, and the same
read gives the league. Where there is no spell, the factor is not scored
and the report says why.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.services.scouting_report_generator import (  # noqa: E402
    ScoutingReportGenerator,
)

BRISBANE = {"id": 188, "name": "Brisbane Roar FC", "league": "A-League Men",
            "country": "Australia", "budget": None, "playing_style": None,
            "expected_index": None}

DORTMUND = {"id": 7, "name": "Borussia Dortmund", "league": "Bundesliga",
            "country": "Germany", "budget": 350_000_000.0,
            "playing_style": {"possession": 0.58, "pressing_intensity": 0.72},
            "expected_index": 78.0}


def player(**overrides):
    base = {
        "id": 2533, "name": "K. Jelacic", "position": "ST", "age": 22,
        "nationality": "Australia", "current_team": "Brisbane Roar FC",
        "current_league": "A-League Men",
        "market_value": None,
        "market_anchor": {"value": 2_500_000, "source": "curated",
                          "samples": 0, "market": "a_league"},
        "performance_index": {"value": 71.0, "raw_value": 71.0,
                              "scaled": True},
        "metrics": {"passing": {"completion_rate": 0.78},
                    "defensive": {"tackles_per_90": 0.96},
                    "shooting": {"goals_per_90": 0.96}},
        "performance_history": [],
    }
    base.update(overrides)
    return base


class StayingPutIsNotAMove(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_his_own_club_scores_no_league_change(self):
        got = self.g._assess_adaptation_risk(player(), dict(BRISBANE))
        self.assertNotIn("Moving to new league", got["factors"])

    def test_his_own_country_scores_no_international_transfer(self):
        got = self.g._assess_adaptation_risk(player(), dict(BRISBANE))
        self.assertNotIn("International transfer", got["factors"])

    def test_a_real_move_still_scores_both(self):
        """Guarding the false case must not disable the true one."""
        got = self.g._assess_adaptation_risk(player(), dict(DORTMUND))
        self.assertIn("Moving to new league", got["factors"])
        self.assertIn("International transfer", got["factors"])

    def test_the_real_move_is_the_riskier_of_the_two(self):
        quedarse = self.g._assess_adaptation_risk(player(), dict(BRISBANE))
        irse = self.g._assess_adaptation_risk(player(), dict(DORTMUND))
        self.assertGreater(irse["score"], quedarse["score"])

    def test_the_old_reading_would_have_charged_him_anyway(self):
        """A check that cannot fail is not a check.

        Reproduces the comparison as it stood: a player with no recorded
        league against a club that has one.
        """
        sin_liga = player(current_league=None)
        self.assertNotEqual(sin_liga.get("current_league"),
                            BRISBANE["league"],
                            "if these matched there was nothing to fix")


class AnUnrecordedLeagueIsNotAMove(unittest.TestCase):
    """Every player in the database was in this state until the endpoint
    began supplying the league."""

    def setUp(self):
        self.g = ScoutingReportGenerator()
        self.sin = player(current_league=None)

    def test_it_is_not_scored(self):
        got = self.g._assess_adaptation_risk(self.sin, dict(DORTMUND))
        self.assertNotIn("Moving to new league", got["factors"])

    def test_it_says_why(self):
        got = self.g._assess_adaptation_risk(self.sin, dict(DORTMUND))
        self.assertIn("league he plays in now is not recorded", got["basis"])

    def test_an_unknown_nationality_is_also_declared(self):
        got = self.g._assess_adaptation_risk(
            player(nationality=None), dict(DORTMUND))
        self.assertNotIn("International transfer", got["factors"])
        self.assertIn("nationality is not recorded", got["basis"])

    def test_both_unknown_are_named_together(self):
        got = self.g._assess_adaptation_risk(
            player(current_league=None, nationality=None), dict(DORTMUND))
        self.assertIn("league", got["basis"])
        self.assertIn("nationality", got["basis"])

    def test_a_fully_known_player_gets_no_caveat(self):
        got = self.g._assess_adaptation_risk(player(), dict(DORTMUND))
        self.assertIsNone(got["basis"])

    def test_it_still_scores_what_it_can(self):
        """Style difference is measured from the metrics and does not
        depend on either missing field."""
        got = self.g._assess_adaptation_risk(
            player(current_league=None, nationality=None), dict(DORTMUND))
        self.assertGreater(got["score"], 0)


class TheOriginIsReadFromTheSquadSpell(unittest.TestCase):
    """`players` has no league column; the club's does, and the open spell
    is what connects them."""

    def test_the_accessor_exists_and_reports_the_three_fields(self):
        import inspect

        from app.core import markets

        fuente = inspect.getsource(markets.player_origin)
        for campo in ("league", "country", "team_type"):
            self.assertIn(campo, fuente)

    def test_player_market_still_goes_through_it(self):
        import inspect

        from app.core import markets

        self.assertIn("player_origin",
                      inspect.getsource(markets.player_market),
                      "two reads of the same spell would be two chances to "
                      "disagree about where a player plays")

    def test_the_endpoint_supplies_it(self):
        """Read as a file rather than imported: the endpoint module pulls in
        the JWT library, which a test run has no reason to need."""
        ruta = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "backend", "app", "api", "v1", "endpoints", "reports.py")
        with open(ruta, encoding="utf-8") as handle:
            fuente = handle.read()
        self.assertIn('player_data["current_league"]', fuente,
                      "the generator reads this key; something has to set it")
        self.assertIn("player_origin", fuente)


class TheWholeReportStillGenerates(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_for_every_combination_of_what_is_known(self):
        for liga in ("A-League Men", None):
            for nacion in ("Australia", None):
                for club in (BRISBANE, DORTMUND):
                    report = self.g.generate_full_report(
                        player(current_league=liga, nationality=nacion),
                        dict(club))
                    self.assertEqual(
                        set(ScoutingReportGenerator.SECTIONS) - set(report),
                        set(), "league=%r nationality=%r club=%s"
                               % (liga, nacion, club["name"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
