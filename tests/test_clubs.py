"""
Kumü — a club Kumü knows nothing about the finances of
=======================================================

    python3 tests/test_clubs.py

A club loaded from a match feed has no budget. The feed records what
happened on the pitch, not what the club can pay. Eight A-League clubs
arrived that way, and every report generated against one of them
returned 500: `_calculate_base_wage` divided None by two hundred
million.

It was broken from the day those clubs were loaded, and the check that
should have caught it generated all 101 reports against a club invented
for the test, with a budget of one million. The endpoint's own clubs
were never used. The same lesson as a previous session, learned again:
exercise the path the endpoint takes, not one built to be convenient.

So the fixture here is a club with the fields a match feed actually
leaves empty, and the test that matters walks every section.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.services.scouting_report_generator import (  # noqa: E402
    ScoutingReportGenerator,
)

# What `_ingest_club` writes when a payload carries no finances: a name,
# a league, a country, and nothing else. Exactly the eight A-League rows.
FROM_A_MATCH_FEED = {
    "id": 188,
    "name": "Brisbane Roar FC",
    "league": "A-League Men",
    "country": "Australia",
    "budget": None,
    "formation": None,
    "playing_style": None,
    "expected_index": None,
}

FULLY_DESCRIBED = dict(FROM_A_MATCH_FEED,
                       id=7, name="Club Con Plata", budget=50_000_000.0,
                       playing_style={"possession": 0.55,
                                      "pressing_intensity": 0.6},
                       expected_index=72.0)


def player(**overrides):
    base = {
        "id": 2533,
        "name": "K. Jelacic",
        "position": "ST",
        "age": 23,
        "current_team": "Brisbane Roar FC",
        "market_value": None,
        "performance_index": {"value": 71.0, "raw_value": 71.0, "trend": 0.1,
                              "volatility": 0.12, "confidence": 0.88,
                              "scaled": True},
        "metrics": {
            "passing": {"completion_rate": 0.78},
            "shooting": {"shots_per_90": 3.1, "goals_per_90": 0.96},
            "defensive": {"tackles_per_90": 0.96},
        },
        "performance_history": [
            {"match_id": str(i), "rating": 7.0 + i * 0.3, "minutes": 90.0,
             "goals": 1, "pass_completion": 0.8}
            for i in range(4)
        ],
    }
    base.update(overrides)
    return base


class EverySectionSurvivesAClubWithNoBudget(unittest.TestCase):
    """Walked one by one, because the whole report answered 500 and the
    browser called it a CORS failure, which named nothing."""

    def setUp(self):
        self.g = ScoutingReportGenerator()
        self.p = player()
        self.t = dict(FROM_A_MATCH_FEED)

    def test_the_whole_report_generates(self):
        report = self.g.generate_full_report(self.p, self.t)
        self.assertEqual(len(report), 9)

    def test_market_analysis(self):
        self.g.generate_market_analysis(self.p, self.t)

    def test_the_wage_is_a_number(self):
        wage = self.g._calculate_base_wage(self.p, self.t)
        self.assertIsInstance(wage, float)
        self.assertGreater(wage, 0)

    def test_the_contract_section_says_the_wage_is_unadjusted(self):
        contract = self.g._recommend_contract_structure(self.p, self.t)
        basis = contract.get("basis") or ""
        self.assertIn("not adjusted", basis.lower(),
                      "a wage that was never scaled to the club looks like "
                      "every other figure unless it says so")
        self.assertIn("Brisbane Roar FC", basis)

    def test_the_payment_structure_does_not_assume_cash(self):
        structure = self.g._recommend_payment_structure(5_000_000.0, self.t)
        self.assertNotEqual(structure.get("structure"), "Front-loaded",
                            "front-loading is advice about cash, and there "
                            "is no reason to think this club has any")

    def test_financial_risk_reports_no_budget_impact(self):
        risk = self.g._assess_financial_risk(self.p, self.t)
        self.assertIn("score", risk)

    def test_negotiation(self):
        market = self.g.generate_market_analysis(self.p, self.t)
        self.g.generate_negotiation_strategy(self.p, self.t, market)


class AClubWithABudgetIsUnaffected(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()
        self.p = player()

    def test_the_wage_is_scaled_to_the_club(self):
        rich = self.g._calculate_base_wage(self.p, dict(FULLY_DESCRIBED))
        unknown = self.g._calculate_base_wage(self.p, dict(FROM_A_MATCH_FEED))
        self.assertNotEqual(rich, unknown,
                            "a known budget has to change the figure, or the "
                            "scaling does nothing for anybody")

    def test_the_contract_section_adds_no_caveat(self):
        contract = self.g._recommend_contract_structure(
            self.p, dict(FULLY_DESCRIBED))
        self.assertIsNone(contract.get("basis"),
                          "there is nothing to explain about a club whose "
                          "means are known")

    def test_the_whole_report_still_generates(self):
        report = self.g.generate_full_report(self.p, dict(FULLY_DESCRIBED))
        self.assertEqual(len(report), 9)


class TheBudgetAccessor(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_absent_is_not_known(self):
        self.assertFalse(self.g._has_budget({}))
        self.assertFalse(self.g._has_budget({"budget": None}))

    def test_zero_is_not_a_budget(self):
        self.assertFalse(self.g._has_budget({"budget": 0}),
                         "zero is what an empty column holds, not a club "
                         "that cannot spend")

    def test_a_figure_is_known(self):
        self.assertTrue(self.g._has_budget({"budget": 1.0}))
        self.assertTrue(self.g._has_budget({"budget": 50_000_000.0}))


class NothingElseDividesByAMissingField(unittest.TestCase):
    """A sweep, because this one was found by walking into it."""

    def test_no_unguarded_budget_arithmetic(self):
        import re

        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "backend", "app", "services", "scouting_report_generator.py")
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()

        offenders = []
        for number, line in enumerate(lines, 1):
            if 'team_data["budget"]' not in line or line.strip().startswith("#"):
                continue
            # Guarded either on the same line or by the one before it.
            window = " ".join(lines[max(0, number - 3):number])
            if "_has_budget" in window or 'team_data.get("budget")' in window:
                continue
            offenders.append((number, line.strip()[:70]))

        self.assertEqual(
            offenders, [],
            "every arithmetic on a budget needs to know there is one")


if __name__ == "__main__":
    unittest.main(verbosity=2)
