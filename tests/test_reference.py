"""
Kumü — an index carries the population it was measured against
===============================================================

    python3 tests/test_reference.py

70 is not a mark out of a hundred. It is where the typical player of that
position sits, and ten points is roughly a deviation — so the figure only
means something alongside the population that produced it.

That population moves. The public organisation went from 307 players to
335 the day twenty-eight goalkeepers were loaded, and every index written
before it kept its digits and lost its meaning. With one client nobody
notices. With two it stops being subtle: one scaled against 335 and
another against 835 are not on the same scale, and a scout comparing two
reports would be comparing two yardsticks without being told.

So each scaled index carries a stamp, and the report declares it.

The part that needed care is the stamp's identity. `renormalise` decides
whether a row changed by comparing what it would write against what is
already there, so a stamp holding "now" would mark every player as
reindexed on every load, every day, forever — and `test_reproducible`'s
idempotence would have been the first casualty. The identity is a
property of the population: same rows, same fingerprint.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.services.ingest_service import Reference, _apply_scale  # noqa: E402
from app.services.scouting_report_generator import (  # noqa: E402
    ScoutingReportGenerator,
)

STAMP = {"peers": 28, "population": 335, "as_of": "2026-11-18",
         "fingerprint": "a3f19c2b"}


def reference(scales=None, peers=None, population=335, as_of="2026-11-18",
              fingerprint="a3f19c2b"):
    return Reference(
        scales=scales if scales is not None else {"ST": (70.0, 8.0)},
        peers=peers if peers is not None else {"ST": 28},
        population=population, as_of=as_of, fingerprint=fingerprint)


class TheStampTravelsWithTheFigure(unittest.TestCase):
    def test_a_scaled_index_carries_it(self):
        got = _apply_scale(78.0, (70.0, 8.0), STAMP)
        self.assertEqual(got["reference"], STAMP)
        self.assertTrue(got["scaled"])

    def test_an_unscaled_index_carries_none(self):
        """Too few peers to rank against is not a population to name."""
        got = _apply_scale(78.0, None, STAMP)
        self.assertNotIn("reference", got)
        self.assertFalse(got["scaled"])

    def test_omitting_it_changes_nothing_else(self):
        """Callers with no population to name are not made to invent one."""
        con = _apply_scale(78.0, (70.0, 8.0), STAMP)
        sin = _apply_scale(78.0, (70.0, 8.0))
        self.assertEqual(sin, {k: v for k, v in con.items()
                               if k != "reference"})

    def test_the_figure_itself_is_unaffected(self):
        self.assertEqual(_apply_scale(78.0, (70.0, 8.0), STAMP)["value"],
                         _apply_scale(78.0, (70.0, 8.0))["value"])


class TheStampIsAPropertyOfThePopulation(unittest.TestCase):
    """Not of the clock. See the module docstring for what that would cost."""

    def test_a_position_with_no_scale_has_no_stamp(self):
        self.assertIsNone(reference().stamp("CB"))
        self.assertIsNone(reference().stamp(None))

    def test_it_names_the_peers_for_that_position(self):
        ref = reference(scales={"ST": (70.0, 8.0), "CB": (68.0, 7.0)},
                        peers={"ST": 28, "CB": 41})
        self.assertEqual(ref.stamp("ST")["peers"], 28)
        self.assertEqual(ref.stamp("CB")["peers"], 41)

    def test_both_positions_report_the_same_population(self):
        ref = reference(scales={"ST": (70.0, 8.0), "CB": (68.0, 7.0)},
                        peers={"ST": 28, "CB": 41})
        self.assertEqual(ref.stamp("ST")["population"],
                         ref.stamp("CB")["population"])

    def test_the_same_population_gives_the_same_stamp(self):
        self.assertEqual(reference().stamp("ST"), reference().stamp("ST"))

    def test_a_different_population_gives_a_different_one(self):
        self.assertNotEqual(reference().stamp("ST"),
                            reference(fingerprint="ffffffff").stamp("ST"))


class RenormalisingStaysIdempotent(unittest.TestCase):
    """The property the stamp could most easily have broken."""

    def test_writing_the_same_stamp_twice_is_no_change(self):
        ref = reference()
        once = _apply_scale(78.0, ref.scales["ST"], ref.stamp("ST"))
        twice = _apply_scale(once["raw_value"], ref.scales["ST"],
                             ref.stamp("ST"))
        self.assertEqual(once, twice)

    def test_renormalise_would_see_no_difference(self):
        """Its actual test: `all(index.get(k) == v for k, v in fresh)`."""
        ref = reference()
        stored = _apply_scale(78.0, ref.scales["ST"], ref.stamp("ST"))
        fresh = _apply_scale(float(stored["raw_value"]), ref.scales["ST"],
                             ref.stamp("ST"))
        self.assertTrue(all(stored.get(k) == v for k, v in fresh.items()))

    def test_a_moved_population_does_show_as_a_difference(self):
        """A check that cannot fail is not a check."""
        viejo = reference()
        nuevo = reference(scales={"ST": (71.5, 8.2)}, peers={"ST": 35},
                          population=342, fingerprint="b7c0d1e2")
        stored = _apply_scale(78.0, viejo.scales["ST"], viejo.stamp("ST"))
        fresh = _apply_scale(float(stored["raw_value"]), nuevo.scales["ST"],
                             nuevo.stamp("ST"))
        self.assertFalse(all(stored.get(k) == v for k, v in fresh.items()))


class TheReportDeclaresIt(unittest.TestCase):
    CLUB = {"id": 188, "name": "Brisbane Roar FC", "league": "A-League Men",
            "country": "Australia", "budget": None, "playing_style": None,
            "expected_index": None}

    def player(self, index=None, anchor="default"):
        return {
            "id": 2533, "name": "K. Jelacic", "position": "ST", "age": 22,
            "market_value": None,
            "market_anchor": ({"value": 2_500_000, "source": "curated",
                               "samples": 0, "market": "a_league"}
                              if anchor == "default" else anchor),
            "performance_index": index if index is not None else {
                "value": 71.0, "raw_value": 71.0, "scaled": True,
                "reference": dict(STAMP)},
            "metrics": {"shooting": {"goals_per_90": 0.96}},
            "performance_history": [],
        }

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_the_report_carries_a_basis(self):
        report = self.g.generate_full_report(self.player(), dict(self.CLUB))
        self.assertIn("basis", report)

    def test_it_repeats_the_population_the_index_names(self):
        basis = self.g.generate_full_report(
            self.player(), dict(self.CLUB))["basis"]
        self.assertEqual(basis["index_reference"], STAMP)
        self.assertTrue(basis["index_scaled"])

    def test_it_names_the_market_the_fee_is_in(self):
        basis = self.g.generate_full_report(
            self.player(), dict(self.CLUB))["basis"]
        self.assertEqual(basis["fee_anchor"]["market"], "a_league")
        self.assertEqual(basis["fee_anchor"]["value"], 2_500_000)
        self.assertEqual(basis["fee_anchor"]["source"], "curated")

    def test_an_index_with_no_stamp_says_so_rather_than_guessing(self):
        """Every index written before the stamp existed is in this state."""
        basis = self.g.generate_full_report(
            self.player(index={"value": 71.0, "raw_value": 71.0,
                               "scaled": True}),
            dict(self.CLUB))["basis"]
        self.assertIsNone(basis["index_reference"])
        self.assertTrue(basis["index_scaled"],
                        "it was scaled; what is missing is the record of "
                        "against what")

    def test_no_market_means_no_fee_anchor(self):
        basis = self.g.generate_full_report(
            self.player(anchor=None), dict(self.CLUB))["basis"]
        self.assertIsNone(basis["fee_anchor"])

    def test_an_unscaled_index_is_reported_as_unscaled(self):
        basis = self.g.generate_full_report(
            self.player(index={"value": 71.0, "raw_value": 71.0,
                               "scaled": False}),
            dict(self.CLUB))["basis"]
        self.assertFalse(basis["index_scaled"])
        self.assertIsNone(basis["index_reference"])

    def test_every_section_still_generates(self):
        for index in (None, {"value": 71.0, "raw_value": 71.0, "scaled": True},
                      {"value": 71.0, "raw_value": 71.0, "scaled": False}):
            report = self.g.generate_full_report(
                self.player(index=index), dict(self.CLUB))
            self.assertEqual(
                set(ScoutingReportGenerator.SECTIONS) - set(report), set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
