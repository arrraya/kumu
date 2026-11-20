"""
Kumü — cheap and worth buying are different claims
===================================================

    python3 tests/test_value.py

Z. Clough, an A-League winger priced at €822K, came out of the market
section with **Undervalued**, **Excellent value opportunity** and
**-95.4% vs valued peers**, printed beside a projected ROI of **-41.2%**,
a risk-adjusted ROI of **-30.3%**, **No breakeven**, and a projection
chart falling every year for five years. One panel, two answers.

Two independent faults produced it, and each one is enough on its own.

**The peers were priced in another currency.** `_find_comparable_transfers`
took the three nearest players by index and ignored where they play. A
player's estimated value is his index multiplied by his market's anchor -
€2.5M per index 100 in the A-League, €30M for international - so an
A-League winger compared against World Cup wingers of almost the same
index is 90-something per cent "below his peers" before anyone has looked
at a footballer. Nearly the whole discount was the ratio between two
anchors. It was a currency conversion presented as a bargain, and it is
the same error as pricing A-League players on the World Cup scale,
pointed the other way round.

**The verdict never saw the return.** `_assess_value` was handed the price
ratio and nothing else, and said "Excellent value opportunity" from that
alone. `_calculate_roi_potential` computed the return and never saw the
price comparison. Nothing in the code connected them, so the panel could
recommend a signing while displaying the evidence against it.
"""

import itertools
import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.services.scouting_report_generator import (  # noqa: E402
    ScoutingReportGenerator,
)

ANCLA_A_LEAGUE = {"value": 2_500_000, "source": "curated", "samples": 0,
                  "market": "a_league"}


def clough(ancla=ANCLA_A_LEAGUE):
    return {
        "id": 9, "name": "Z. Clough", "position": "RW", "age": 30,
        "market_value": None, "market_anchor": ancla,
        "performance_index": {"value": 65.8, "raw_value": 65.8},
        "metrics": {}, "performance_history": [{"rating": 7.0}] * 3,
    }


CLIENTE = {"market_value_source": "client"}


def par(nombre, valor, indice, liga):
    """A row as `_query_db` returns it: name, club, value, index, league."""
    return (nombre, "un club", valor, {"value": indice}, liga)


class PeersArePricedOnTheSameScale(unittest.TestCase):

    def generador(self, filas):
        g = ScoutingReportGenerator()
        g._query_db = lambda sql, params, org_ids=None: filas
        return g

    # Index distances taken from the shape production actually had: the
    # nearest same-position players were the World Cup ones, which is why
    # they were the three the panel compared against.
    MEZCLA = [
        par("Ousmane Dembélé", 60_000_000.0, 65.9, None),       # selección
        par("Ferrán Torres", 55_000_000.0, 66.0, "La Liga"),
        par("Hakim Ziyech", 40_000_000.0, 65.7, None),
        par("A. Nisbet", 900_000.0, 63.0, "A-League Men"),
        par("T. Juric", 780_000.0, 68.4, "A-League Men"),
        par("M. Leckie", 1_100_000.0, 69.1, "A-League Men"),
    ]

    def test_only_peers_from_the_same_market_are_kept(self):
        pares = self.generador(self.MEZCLA)._find_comparable_transfers(clough())
        self.assertEqual([p["player"] for p in pares],
                         ["A. Nisbet", "T. Juric", "M. Leckie"])

    def test_each_peer_carries_the_market_it_was_priced_in(self):
        pares = self.generador(self.MEZCLA)._find_comparable_transfers(clough())
        self.assertEqual({p["market"] for p in pares}, {"a_league"})

    def test_the_nearest_by_index_no_longer_decides_alone(self):
        """The three nearest are all from another market, which is the
        shape that produced the screenshot."""
        tres = sorted(self.MEZCLA, key=lambda f: abs(f[3]["value"] - 65.8))[:3]
        self.assertEqual({f[4] for f in tres} & {"A-League Men"}, set())
        elegidos = [p["player"] for p in
                    self.generador(self.MEZCLA)._find_comparable_transfers(
                        clough())]
        for nombre, _, _, _, liga in tres:
            self.assertNotIn(nombre, elegidos)

    def test_no_peer_in_the_market_is_said_rather_than_substituted(self):
        solo_extranjeros = [f for f in self.MEZCLA if f[4] != "A-League Men"]
        g = self.generador(solo_extranjeros)
        pares = g._find_comparable_transfers(clough())
        self.assertEqual(pares, [])
        valoracion = g._assess_value(822_000.0, pares, dict(CLIENTE))
        self.assertEqual(valoracion["assessment"], "Not assessed")
        self.assertIn("another anchor", valoracion["basis"])
        self.assertIsNone(valoracion["value_ratio"])

    def test_a_player_with_no_market_is_not_filtered_into_nothing(self):
        """Without a market of his own there is nothing to match against,
        so the nearest peers stand - the behaviour before this change."""
        g = self.generador(self.MEZCLA)
        pares = g._find_comparable_transfers(clough(ancla=None))
        self.assertEqual(len(pares), 3)

    def test_the_old_comparison_produced_the_discount_in_the_screenshot(self):
        """A check that cannot fail is not a check: this is the ratio as it
        stood, against the three nearest by index regardless of market."""
        import numpy as np
        tres = sorted(self.MEZCLA, key=lambda f: abs(f[3]["value"] - 65.8))[:3]
        viejo = 822_000.0 / float(np.mean([f[2] for f in tres]))
        self.assertLess(viejo, 0.85, "it would not have read as a discount")
        self.assertLess((viejo - 1) * 100, -90.0)


class TheVerdictCannotContradictTheReturn(unittest.TestCase):

    ETIQUETAS = ("Priced below peers", "In line with peers",
                 "Priced above peers")

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def recomendacion(self, etiqueta, retorno):
        return self.g._value_recommendation(
            {"assessment": etiqueta},
            None if retorno is None else {"roi_percentage": retorno})

    def test_a_negative_return_is_never_dressed_as_an_opportunity(self):
        for etiqueta, retorno in itertools.product(
                self.ETIQUETAS, (-95.0, -41.2, -0.1, 0.0)):
            dicho = self.recomendacion(etiqueta, retorno)
            self.assertIn("negative", dicho, (etiqueta, retorno))
            for palabra in ("opportunity", "excellent", "bargain"):
                self.assertNotIn(palabra, dicho.lower(), (etiqueta, retorno))

    def test_a_positive_return_says_so(self):
        for etiqueta, retorno in itertools.product(
                self.ETIQUETAS, (0.1, 27.0, 358.0)):
            dicho = self.recomendacion(etiqueta, retorno)
            self.assertIn("positive", dicho, (etiqueta, retorno))

    def test_cheap_and_worth_buying_are_separated_in_so_many_words(self):
        dicho = self.recomendacion("Priced below peers", -41.2)
        self.assertIn("Cheap and worth buying are different claims", dicho)

    def test_every_label_has_a_verdict_on_both_sides(self):
        """A label with no entry would fall through to None and print an
        empty recommendation."""
        for etiqueta in self.ETIQUETAS:
            for retorno in (10.0, -10.0):
                self.assertIsNotNone(self.recomendacion(etiqueta, retorno))

    def test_an_unassessed_price_recommends_nothing(self):
        self.assertIsNone(self.recomendacion("Not assessed", 27.0))
        self.assertIsNone(self.recomendacion(None, 27.0))

    def test_without_a_return_it_says_it_is_only_a_price(self):
        dicho = self.recomendacion("Priced below peers", None)
        self.assertIn("price comparison only", dicho)


class TheLabelDescribesTheComparison(unittest.TestCase):
    """"Undervalued" is a claim about what a player is worth. This ratio
    knows what Kumü estimated for three other players."""

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def pares(self, *valores):
        return [{"transfer_fee": v, "market": "a_league"} for v in valores]

    def valorar(self, valor, *pares):
        """With a price the client put on the player, so the comparison is
        not refused as circular before the label is reached."""
        return self.g._assess_value(valor, self.pares(*pares), dict(CLIENTE))

    def test_the_three_bands(self):
        for valor, esperado in ((500_000.0, "Priced below peers"),
                                (1_000_000.0, "In line with peers"),
                                (2_000_000.0, "Priced above peers")):
            self.assertEqual(
                self.valorar(valor, 1_000_000.0)["assessment"], esperado, valor)

    def test_no_label_claims_to_know_what_the_player_is_worth(self):
        for valor in (100_000.0, 1_000_000.0, 9_000_000.0):
            etiqueta = self.valorar(valor, 1_000_000.0)["assessment"]
            for palabra in ("undervalued", "overvalued", "fair value"):
                self.assertNotIn(palabra, etiqueta.lower(), valor)

    def test_the_basis_says_the_peers_share_the_market(self):
        got = self.valorar(500_000.0, 1_000_000.0)
        self.assertIn("same market", got["basis"])
        self.assertIn("not observed transfer fees", got["basis"])

    def test_the_ratio_itself_is_unchanged(self):
        got = self.valorar(500_000.0, 1_000_000.0)
        self.assertAlmostEqual(got["value_ratio"], 0.5)
        self.assertEqual(got["vs_comparables"], "-50.0% (1 peers)")


class KumuDoesNotCompareItselfToItself(unittest.TestCase):
    """The ratio is f(index) over f(the three nearest indices), by one
    formula, against peers chosen on that same index. `derive_anchor`
    already refuses the public population's values for calibrating anchors
    for this reason; the same objection applies here."""

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def pares(self, *valores, **extra):
        return [dict({"transfer_fee": v, "market": "a_league"}, **extra)
                for v in valores]

    def test_estimates_on_both_sides_are_refused(self):
        got = self.g._assess_value(822_000.0, self.pares(900_000.0), clough())
        self.assertEqual(got["assessment"], "Not assessed")
        self.assertIsNone(got["value_ratio"])
        self.assertIn("measures the formula, not the player", got["basis"])

    def test_no_row_in_the_database_carries_a_declared_price_today(self):
        """`players.market_value_source` does not exist, so this is False
        for everything. When the column arrives, this test is where the
        change announces itself."""
        for fila in (None, {}, {"market_value": 822_000.0},
                     {"market_value_source": None}):
            self.assertFalse(ScoutingReportGenerator._declared_price(fila), fila)

    def test_a_price_on_the_player_turns_it_on(self):
        got = self.g._assess_value(500_000.0, self.pares(1_000_000.0),
                                   dict(CLIENTE))
        self.assertEqual(got["assessment"], "Priced below peers")

    def test_a_price_on_a_single_peer_turns_it_on(self):
        got = self.g._assess_value(
            500_000.0, self.pares(1_000_000.0, market_value_source="client"),
            clough())
        self.assertEqual(got["assessment"], "Priced below peers")

    def test_the_whole_section_still_generates_when_it_is_refused(self):
        club = {"id": 1, "name": "Fiorentina", "league": "Serie A",
                "country": "Italy", "budget": 110_000_000.0,
                "playing_style": None, "expected_index": None}
        self.g._query_db = lambda sql, params, org_ids=None: []
        seccion = self.g.generate_market_analysis(clough(), club)
        self.assertEqual(seccion["value_assessment"]["assessment"],
                         "Not assessed")
        self.assertIsNone(seccion["value_assessment"]["recommendation"])
        self.assertIsNotNone(seccion["roi_analysis"])


class AFeeIsNeverRoundedToNothing(unittest.TestCase):
    """`int(share * 100)` truncated, in both directions."""

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_a_real_fee_against_a_large_budget_is_not_zero(self):
        """€822K against €110M: 0.75%, printed "0% of €110.0M"."""
        self.assertEqual(self.g._fmt_share(822_000 / 110_000_000), "under 1%")

    def test_the_three_fees_from_the_reports_reviewed(self):
        for fee, presupuesto in ((936_000, 900_000_000),
                                 (946_000, 400_000_000),
                                 (822_000, 110_000_000)):
            self.assertEqual(self.g._fmt_share(fee / presupuesto), "under 1%")

    def test_it_rounds_rather_than_truncating(self):
        self.assertEqual(self.g._fmt_share(0.996), "100%")
        self.assertEqual(self.g._fmt_share(0.014), "1%")
        self.assertEqual(self.g._fmt_share(0.4), "40%")

    def test_a_share_of_nothing_is_zero(self):
        self.assertEqual(self.g._fmt_share(0), "0%")
        self.assertEqual(self.g._fmt_share(None), "0%")

    def test_nothing_between_nought_and_one_per_cent_prints_as_a_digit(self):
        for pct in (0.0001, 0.001, 0.005, 0.0099):
            self.assertEqual(self.g._fmt_share(pct), "under 1%", pct)


if __name__ == "__main__":
    unittest.main(verbosity=2)
