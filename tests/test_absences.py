"""
Kumü — what the report does when a number is not there
=======================================================

    python3 tests/test_absences.py

`scoring.raw_index` returns None below three appearances, on purpose:
two matches are no trend, and inventing one is the filled-in number
these reports exist to avoid. The report could not survive its own
decision. Five places subscripted the index directly and took the whole
thing down with a TypeError, and they were found one at a time, each
only after fixing the one before.

Worse than the crash was what did not crash. A player with no index got
a fee derived from a stand-in index of 50, and that fee went on to set
the buyout clause, the wage, the opening offer and a financial risk
reported as 100% of budget — a real calculation on an invented number,
which reads on the page exactly like a measured one.

So these tests ask two things of every section: does it survive an
absent input, and does it leave the absence visible rather than filling
it. A test that only checked for the exception would have passed on the
fabricated fee.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.services.scouting_report_generator import (  # noqa: E402
    ScoutingReportGenerator,
)

CLUB = {
    "id": 500,
    "name": "Club Comprador",
    "league": "A-League Men",
    "country": "Australia",
    "playing_style": {"possession": 0.52, "pressing_intensity": 0.6},
    "expected_index": 70.0,
    "budget": 1_000_000.0,
}

HISTORY = [
    {"match_id": "1", "date": "2025-01-01", "minutes": 90.0, "rating": 7.1,
     "goals": 1, "assists": 0, "key_passes": 2, "shots": 3, "tackles": 2,
     "progressive_passes": 5, "pass_completion": 0.82},
    {"match_id": "2", "date": "2025-01-08", "minutes": 90.0, "rating": 6.8,
     "goals": 0, "assists": 1, "key_passes": 1, "shots": 2, "tackles": 3,
     "progressive_passes": 4, "pass_completion": 0.79},
]


def player(**overrides):
    base = {
        "id": 9001,
        "name": "Jugador de Prueba",
        "position": "CM",
        "age": 25,
        "current_team": "Club Vendedor",
        "market_value": None,
        "performance_index": None,
        "metrics": {
            "passing": {"completion_rate": 0.81, "key_passes_per_90": 1.5},
            "shooting": {"shots_per_90": 2.5, "goals_per_90": 0.5},
            "defensive": {"tackles_per_90": 2.5},
        },
        "performance_history": list(HISTORY),
    }
    base.update(overrides)
    return base


WITH_INDEX = {"value": 72.4, "raw_value": 72.4, "trend": 0.1,
              "volatility": 0.08, "confidence": 0.92, "scaled": True}


class ASectionSurvivesAnAbsentIndex(unittest.TestCase):
    """The crash, in each of the places it lived."""

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_the_whole_report_generates(self):
        report = self.g.generate_full_report(player(), CLUB)
        self.assertEqual(
            set(ScoutingReportGenerator.SECTIONS) - set(report), set(),
            "every section must still be present")

    def test_market_analysis_does_not_subscript_a_missing_index(self):
        self.g.generate_market_analysis(player(), CLUB)

    def test_performance_risk_does_not_subscript_a_missing_index(self):
        self.g._assess_performance_risk(player())

    def test_financial_risk_does_not_price_from_nothing(self):
        self.g._assess_financial_risk(player(), CLUB)

    def test_negotiation_does_not_subscript_a_missing_index(self):
        market = self.g.generate_market_analysis(player(), CLUB)
        self.g.generate_negotiation_strategy(player(), CLUB, market)

    def test_a_player_with_an_index_is_unaffected(self):
        report = self.g.generate_full_report(
            player(performance_index=dict(WITH_INDEX)), CLUB)
        self.assertIsNotNone(
            report["market_analysis"]["current_market_value"],
            "guarding the absent case must not disable the present one")


class TheAbsenceIsLeftVisible(unittest.TestCase):
    """The half a crash would not have caught."""

    def setUp(self):
        self.g = ScoutingReportGenerator()
        self.report = self.g.generate_full_report(player(), CLUB)

    def test_no_fee_is_invented(self):
        self.assertIsNone(
            self.report["market_analysis"]["current_market_value"],
            "a fee derived from a stand-in index of 50 is not a fee")

    def test_the_financial_section_says_why_it_is_empty(self):
        basis = self.report["market_analysis"].get("basis") or ""
        self.assertIn("no market value", basis.lower())
        self.assertTrue(basis.strip().endswith("."),
                        "a basis line is a sentence, not a label")

    def test_no_negotiation_position_is_taken(self):
        strategy = self.report["negotiation_strategy"]
        self.assertIsNone(strategy["negotiation_position"])
        self.assertTrue(strategy.get("basis"))

    def test_performance_risk_reports_absence_not_calm(self):
        risk = self.report["risk_assessment"]["risk_factors"]["performance_risk"]
        self.assertIsNone(risk["score"],
                          "no volatility is not zero volatility, which would "
                          "make an unknown player look like a steady one")
        self.assertTrue(risk.get("basis"))

    def test_financial_risk_reports_absence_not_danger(self):
        risk = self.report["risk_assessment"]["risk_factors"]["financial_risk"]
        self.assertIsNone(risk["score"],
                          "100% of budget was a real sum over an invented fee")
        self.assertTrue(risk.get("basis"))

    def test_the_overall_risk_counts_only_what_was_assessed(self):
        assessment = self.report["risk_assessment"]
        basis = assessment.get("risk_basis") or ""
        self.assertIn("3 of 5", basis,
                      "the reader has to be told how much of the picture "
                      f"the figure covers; got: {basis!r}")
        self.assertIsNotNone(assessment["risk_score"],
                             "three known risks still average to something")

    def test_no_section_reports_the_stand_in_index_as_a_figure(self):
        stand_in = ScoutingReportGenerator.ASSUMED_INDEX
        market = self.report["market_analysis"]
        for key, value in market.items():
            self.assertNotEqual(
                value, stand_in,
                f"market_analysis.{key} is the stand-in index on the page")


class ASuppliedFeeIsEnoughOnItsOwn(unittest.TestCase):
    """An index is one way to reach a fee, not the only one."""

    def setUp(self):
        self.g = ScoutingReportGenerator()
        self.report = self.g.generate_full_report(
            player(market_value=2_500_000.0), CLUB)

    def test_the_client_price_is_used(self):
        self.assertEqual(
            self.report["market_analysis"]["current_market_value"], 2_500_000.0)

    def test_the_financial_sections_come_back(self):
        self.assertIsNotNone(self.report["market_analysis"]["value_projections"])
        self.assertIsNotNone(
            self.report["negotiation_strategy"]["negotiation_position"])

    def test_financial_risk_is_assessed_again(self):
        risk = self.report["risk_assessment"]["risk_factors"]["financial_risk"]
        self.assertIsInstance(risk["score"], (int, float))

    def test_performance_risk_stays_absent(self):
        """The fee came from the client; the volatility still has no source."""
        risk = self.report["risk_assessment"]["risk_factors"]["performance_risk"]
        self.assertIsNone(risk["score"])


GOALKEEPING = {
    "saves_per_90": 3.1,
    "save_percentage": 0.74,
    "goals_prevented_per_90": 0.35,
    "claims_per_90": 2.0,
    "sweeper_actions_per_90": 1.4,
}


def keeper(**overrides):
    """A goalkeeper from a source with no goalkeeping in it."""
    base = player(position="GK", performance_index=None)
    base["performance_history"] = [
        {"match_id": str(i), "date": f"2025-01-0{i+1}", "minutes": 90.0,
         "pass_completion": 0.86, "progressive_passes": 3,
         "goals": 0, "assists": 0, "key_passes": 0, "shots": 0, "tackles": 0}
        for i in range(5)
    ]
    base.update(overrides)
    return base


class AGoalkeeperIsNotRecommended(unittest.TestCase):
    """The verdict that was being issued over a pass-completion score."""

    def setUp(self):
        self.g = ScoutingReportGenerator()
        self.report = self.g.generate_full_report(keeper(), CLUB)

    def test_no_recommendation_is_issued(self):
        summary = self.report["executive_summary"]
        self.assertIsNone(summary["recommendation"],
                          "RECOMMENDED came from a placeholder match score of "
                          "75 on a player nobody could rate")
        self.assertIsNone(summary["action"])

    def test_the_placeholder_match_score_does_not_reach_the_page(self):
        self.assertIsNone(self.report["executive_summary"]["match_score"])

    def test_no_percentile_is_reported(self):
        summary = self.report["executive_summary"]
        self.assertIsNone(summary["overall_percentile"],
                          "a percentile of 50 means 'no idea', printed as a "
                          "number")
        self.assertIsNone(summary["metric_percentile_average"])

    def test_the_reason_names_what_is_missing(self):
        basis = self.report["executive_summary"]["percentile_basis"] or ""
        for field in ("saves", "save percentage", "goals prevented"):
            self.assertIn(field, basis.lower(),
                          "the reader has to be told which fields unlock this")

    def test_the_statement_does_not_recommend(self):
        statement = self.report["executive_summary"]["executive_statement"]
        self.assertNotIn("recommended", statement.lower())

    def test_nothing_downstream_prices_him(self):
        self.assertIsNone(self.report["market_analysis"]["current_market_value"])
        self.assertIsNone(
            self.report["negotiation_strategy"]["negotiation_position"])


class AGoalkeeperWithGoalkeepingIsAssessed(unittest.TestCase):
    """The absence is in the data, not in the position."""

    def setUp(self):
        self.g = ScoutingReportGenerator()
        rated = keeper(performance_index=dict(WITH_INDEX))
        rated["metrics"] = dict(rated["metrics"], goalkeeping=dict(GOALKEEPING))
        self.report = self.g.generate_full_report(rated, CLUB)

    def test_a_recommendation_is_issued_again(self):
        self.assertIsNotNone(self.report["executive_summary"]["recommendation"])

    def test_the_financial_sections_work(self):
        self.assertIsNotNone(
            self.report["market_analysis"]["current_market_value"])


class TheGoalkeepingBasis(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_an_outfield_player_gets_no_goalkeeping_note(self):
        self.assertIsNone(self.g.goalkeeping_basis(player()),
                          "there is nothing to explain about a midfielder")

    def test_a_keeper_without_the_fields_gets_one(self):
        self.assertIsNotNone(self.g.goalkeeping_basis(keeper()))

    def test_a_keeper_with_the_fields_does_not(self):
        k = keeper()
        k["metrics"] = dict(k["metrics"], goalkeeping=dict(GOALKEEPING))
        self.assertIsNone(self.g.goalkeeping_basis(k))

    def test_a_partial_set_is_not_enough(self):
        for missing in ("saves_per_90", "save_percentage",
                        "goals_prevented_per_90"):
            partial = {k: v for k, v in GOALKEEPING.items() if k != missing}
            k = keeper()
            k["metrics"] = dict(k["metrics"], goalkeeping=partial)
            self.assertIsNotNone(self.g.goalkeeping_basis(k),
                                 f"{missing} is missing, so he is not rateable")

    def test_a_keeper_who_faced_nothing_still_counts_as_rateable(self):
        """A genuine zero is a figure; the test is presence, not size."""
        k = keeper()
        k["metrics"] = dict(k["metrics"], goalkeeping={
            "saves_per_90": 0.0, "save_percentage": 0.0,
            "goals_prevented_per_90": 0.0})
        self.assertIsNone(self.g.goalkeeping_basis(k))


class TheAccessor(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_a_missing_index_yields_none_for_every_field(self):
        for key in ("value", "trend", "volatility", "confidence"):
            self.assertIsNone(self.g._index_value(player(), key))

    def test_a_present_index_yields_its_fields(self):
        p = player(performance_index=dict(WITH_INDEX))
        self.assertEqual(self.g._index_value(p, "value"), 72.4)
        self.assertEqual(self.g._index_value(p, "volatility"), 0.08)

    def test_a_non_numeric_field_is_treated_as_absent(self):
        p = player(performance_index={"value": "muy bueno"})
        self.assertIsNone(self.g._index_value(p, "value"))

    def test_a_field_the_index_does_not_carry_is_absent(self):
        p = player(performance_index=dict(WITH_INDEX))
        self.assertIsNone(self.g._index_value(p, "inventado"))

    def test_can_price_needs_one_of_the_two(self):
        self.assertFalse(self.g._can_price(player()))
        self.assertTrue(self.g._can_price(player(market_value=1.0)))
        self.assertTrue(self.g._can_price(
            player(performance_index=dict(WITH_INDEX))))

    def test_a_zero_price_is_not_a_price(self):
        self.assertFalse(self.g._can_price(player(market_value=0)),
                         "zero is what an empty column holds, not a fee")


if __name__ == "__main__":
    unittest.main(verbosity=2)
