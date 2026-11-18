"""
Kumü — a fee is denominated in a market, or it is not a fee
============================================================

    python3 tests/test_markets.py

`market_of` turned a league it did not recognise into `international`:
€30M per index 100, the World Cup scale, and the third highest anchor of
fifteen. So the value standing for "Kumü does not know this market" was
nearly the most expensive one on the list.

The A-League was not in the table. All 101 players Kumü holds from a
client source were priced on that fallback, and K. Jelacic came out at
€11.2M in a league whose record transfers are around €3M — off by an
order of magnitude, and with him the ROI, the opening offer, the ceiling
and the wage. Nothing failed. The figures looked like figures.

The decision taken was that nobody guesses: a client declares the market
of their clubs at load, Kumü reads it from the league name when it can,
and when neither works the report carries no money rather than money in
an invented currency.

Two things this file watches, then. That an unknown market produces no
price anywhere — and that a known one still does, because a guard that
disables the working case is not a fix.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.core import markets  # noqa: E402
from app.schemas.ingest import (  # noqa: E402
    IngestPayload,
    describe_capabilities,
)
from app.services.scouting_report_generator import (  # noqa: E402
    ScoutingReportGenerator,
)

A_LEAGUE_ANCHOR = {"value": 2_500_000, "source": "curated", "samples": 0,
                   "market": "a_league"}

CLUB = {
    "id": 188, "name": "Brisbane Roar FC", "league": "A-League Men",
    "country": "Australia", "budget": None, "formation": "4-3-3",
    "playing_style": None, "expected_index": None,
}


def player(**overrides):
    base = {
        "id": 2533, "name": "K. Jelacic", "position": "ST", "age": 22,
        "current_team": "Brisbane Roar FC", "market_value": None,
        "market_anchor": dict(A_LEAGUE_ANCHOR),
        "performance_index": {"value": 71.0, "raw_value": 71.0,
                              "scaled": True},
        "metrics": {"shooting": {"shots_per_90": 3.1, "goals_per_90": 0.96},
                    "passing": {"completion_rate": 0.78}},
        "performance_history": [
            {"match_id": str(i), "rating": 7.0 + i * 0.2, "minutes": 90.0}
            for i in range(5)
        ],
    }
    base.update(overrides)
    return base


class AnUnrecognisedLeagueIsNotAMarket(unittest.TestCase):
    def test_it_resolves_to_nothing(self):
        self.assertIsNone(markets.market_of("League", None))
        self.assertIsNone(markets.market_of("Liga Que No Existe", "Narnia"))

    def test_it_used_to_resolve_to_the_world_cup_scale(self):
        """A check that cannot fail is not a check.

        The anchor that was being substituted is still in the table, and
        still the third highest, which is the whole reason this matters.
        """
        self.assertEqual(markets.CURATED_ANCHORS["international"], 30_000_000)
        self.assertGreater(
            markets.CURATED_ANCHORS["international"],
            markets.CURATED_ANCHORS["a_league"] * 10,
            "if these were close the substitution would have been harmless")

    def test_no_anchor_comes_from_no_market(self):
        self.assertIsNone(markets.anchor_for(None))
        self.assertIsNone(markets.anchor_for("narnia_premier"))

    def test_a_recognised_league_still_resolves(self):
        self.assertEqual(markets.market_of("Bundesliga", "Germany"),
                         "bundesliga")
        self.assertEqual(markets.market_of("Primera Division de Chile",
                                           "Chile"), "chile_primera")


class TheALeagueIsItsOwnMarket(unittest.TestCase):
    """It was the one market Kumü actually held client data from, and the
    only one missing from the table."""

    def test_it_resolves(self):
        self.assertEqual(markets.market_of("A-League Men", "Australia"),
                         "a_league")

    def test_its_anchor_is_near_chile_and_nowhere_near_the_world_cup(self):
        anchor = markets.anchor_for("a_league")["value"]
        self.assertEqual(anchor, 2_500_000)
        self.assertLess(anchor, markets.CURATED_ANCHORS["mls"])
        self.assertGreater(anchor, markets.CURATED_ANCHORS["chile_primera"])

    def test_a_player_is_priced_in_millions_not_tens_of_millions(self):
        """The figure that started this: €11.2M for a 22-year-old in a
        league whose record fees are around €3M."""
        value = ScoutingReportGenerator()._market_value(player())
        self.assertLess(value, 3_000_000,
                        "still priced on somebody else's market")
        self.assertGreater(value, 100_000)

    def test_the_old_anchor_would_have_produced_the_old_figure(self):
        """Confirms the diagnosis rather than assuming it."""
        g = ScoutingReportGenerator()
        como_antes = g._market_value(player(
            market_anchor={"value": 30_000_000, "source": "curated",
                           "samples": 0, "market": "international"}))
        self.assertAlmostEqual(como_antes, 10_650_000, delta=600_000)


class WithoutAMarketThereIsNoPrice(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()
        self.sin = player(market_anchor=None)

    def test_an_index_alone_cannot_be_priced(self):
        self.assertFalse(self.g._can_price(self.sin))
        self.assertIsNone(self.g._market_value(self.sin))

    def test_a_supplied_price_needs_no_market(self):
        """It is already in euros."""
        self.assertTrue(self.g._can_price(
            player(market_anchor=None, market_value=800_000.0)))

    def test_the_market_section_declines(self):
        section = self.g.generate_market_analysis(self.sin, dict(CLUB))
        self.assertIsNotNone(section.get("basis") or section.get("note"),
                             "declining has to say why")

    def test_the_whole_report_still_generates(self):
        report = self.g.generate_full_report(self.sin, dict(CLUB))
        self.assertEqual(
            set(ScoutingReportGenerator.SECTIONS) - set(report), set())

    def test_no_finding_quotes_a_fee(self):
        """`_key_findings` reads the fee itself, outside the guard that
        covers the market section."""
        report = self.g.generate_full_report(
            self.sin, dict(CLUB, budget=50_000_000.0))
        texts = " ".join(f.get("text", "")
                         for f in report["executive_summary"]["key_findings"])
        self.assertNotIn("€", texts)

    def test_a_player_with_a_market_is_unaffected(self):
        """Guarding the absent case must not disable the present one."""
        section = self.g.generate_market_analysis(player(), dict(CLUB))
        self.assertTrue(self.g._can_price(player()))
        self.assertIsNotNone(section.get("current_value")
                             or section.get("value_assessment"))


class ProjectionNeedsBothMarkets(unittest.TestCase):
    def test_an_unknown_side_is_not_projected(self):
        got = markets.project_index(71.0, None, "bundesliga")
        self.assertIsNone(got["value"])
        self.assertIn("not known", got["basis"])

    def test_both_known_still_projects(self):
        got = markets.project_index(71.0, "a_league", "bundesliga")
        self.assertIsNotNone(got["value"])
        self.assertLess(got["value"], 71.0,
                        "moving up a level should cost him something")


class TheLoadSaysWhetherMoneyWillWork(unittest.TestCase):
    """The decision taken: nobody guesses, the client declares."""

    def capabilities(self, **club_overrides):
        club = {"external_id": "c1", "name": "Brisbane Roar FC",
                "league": "A-League Men", "country": "Australia",
                "squad": []}
        club.update(club_overrides)
        return describe_capabilities(
            IngestPayload(source="prueba", players=[], club=club))

    def test_a_readable_league_switches_money_on(self):
        cap = self.capabilities()["capabilities"]["monetary_figures"]
        self.assertTrue(cap["enabled"])
        self.assertEqual(cap["market"], "a_league")
        self.assertIn("league name", cap["market_source"])

    def test_a_declared_market_beats_an_unreadable_league(self):
        cap = self.capabilities(league="League", country=None,
                                market="a_league")["capabilities"]
        self.assertTrue(cap["monetary_figures"]["enabled"])
        self.assertEqual(cap["monetary_figures"]["market_source"], "declared")

    def test_an_unreadable_league_switches_money_off(self):
        cap = self.capabilities(league="League", country=None)
        self.assertFalse(cap["capabilities"]["monetary_figures"]["enabled"])
        self.assertTrue(any("does not recognise" in w
                            for w in cap["warnings"]))

    def test_an_invented_market_is_refused_rather_than_accepted(self):
        cap = self.capabilities(league="League", country=None, market="narnia")
        self.assertFalse(cap["capabilities"]["monetary_figures"]["enabled"])
        self.assertTrue(any("not one Kumü knows" in w
                            for w in cap["warnings"]))

    def test_the_warning_lists_what_it_would_accept(self):
        aviso = next(w for w in self.capabilities(
            league="League", country=None)["warnings"]
            if "does not recognise" in w)
        self.assertIn("a_league", aviso)
        self.assertIn("chile_primera", aviso)

    def test_an_empty_file_does_not_report_money_as_working(self):
        """`with_value == total` is vacuously true at zero, so a payload
        with no players claimed every player carried a price."""
        cap = self.capabilities(league="League", country=None)
        self.assertFalse(cap["capabilities"]["monetary_figures"]["enabled"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
