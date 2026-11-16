"""
Kumü — the same file loaded twice has to give the same index
=============================================================

    python3 tests/test_reproducible.py

An index has two halves. `raw_value` comes from a player's own match log
and is his alone: load him first or last, it does not move. `value` is
that figure placed against his positional peers, and the peers are
whoever is in the database the moment he is written.

`ingest` runs once per club, and the scales were read afresh each time,
over the tenant's own rows as well as the reference population. So the
first club of a load was measured against an empty tenant and the eighth
against the seven before it. Loading the identical file twice produced
centre-backs spanning 44.2 to 73.4 one day and 45.7 to 75.7 the next.

A player's index is meant to be a property of him and his peers, not of
the order a loader happened to visit the clubs in.

These tests do not need a database. The whole question is whether the
final figure is a function of the final population, and that is decided
by two pure functions — `raw_index`, which must not depend on anything
outside one player, and `_apply_scale`, which must depend only on the
raw population it is handed.
"""

import os
import random
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.core.scoring import raw_index  # noqa: E402
from app.services.ingest_service import _apply_scale  # noqa: E402


def history(ratings):
    return [{"match_id": str(i), "rating": r} for i, r in enumerate(ratings)]


def scale_of(raw_values):
    """What `reference_scales` computes for one position."""
    spread = float(np.std(raw_values))
    return float(np.mean(raw_values)), spread if spread > 0 else 1.0


def population(n=40, seed=7):
    rng = random.Random(seed)
    return [round(rng.uniform(55.0, 95.0), 1) for _ in range(n)]


class TheRawFigureIsThePlayersAlone(unittest.TestCase):
    """The half that must not move, whatever else is in the database."""

    def test_it_depends_on_nothing_but_his_own_matches(self):
        ratings = [7.1, 6.4, 8.2, 7.7]
        self.assertEqual(raw_index(history(ratings)),
                         raw_index(history(ratings)))

    def test_it_is_the_same_whoever_else_was_loaded_first(self):
        """There is no population argument, and there must not be one."""
        import inspect
        parameters = list(inspect.signature(raw_index).parameters)
        self.assertEqual(parameters, ["history"],
                         "a raw index that could see the population would "
                         "move when somebody else was loaded")


class TheScaledFigureFollowsTheFinalPopulation(unittest.TestCase):
    def setUp(self):
        self.raws = population()
        self.mine = self.raws[0]

    def test_the_order_of_the_population_changes_nothing(self):
        forwards = _apply_scale(self.mine, scale_of(self.raws))
        backwards = _apply_scale(self.mine, scale_of(list(reversed(self.raws))))
        shuffled = list(self.raws)
        random.Random(3).shuffle(shuffled)
        self.assertEqual(forwards, backwards)
        self.assertEqual(forwards, _apply_scale(self.mine, scale_of(shuffled)))

    def test_a_partial_population_gives_a_different_answer(self):
        """The fault itself: this is what loading club by club did."""
        early = _apply_scale(self.mine, scale_of(self.raws[:8]))
        final = _apply_scale(self.mine, scale_of(self.raws))
        self.assertNotEqual(
            early["value"], final["value"],
            "if these agreed there would have been nothing to fix, and no "
            "reason to rescale after the rows land")

    def test_rescaling_from_the_raw_figure_is_idempotent(self):
        """Why the pass can run after every payload without compounding.

        `reference_scales` reads `raw_value`, never `value`. Normalising
        an already-normalised number would compress the scale a second
        time, and running the pass eight times in a load would compress
        it eight.
        """
        scale = scale_of(self.raws)
        once = _apply_scale(self.mine, scale)
        twice = _apply_scale(once["raw_value"], scale)
        thrice = _apply_scale(twice["raw_value"], scale)
        self.assertEqual(once, twice)
        self.assertEqual(twice, thrice)

    def test_the_raw_figure_survives_rescaling(self):
        scaled = _apply_scale(self.mine, scale_of(self.raws))
        self.assertEqual(scaled["raw_value"], round(self.mine, 1))

    def test_a_population_with_no_peers_leaves_the_figure_unscaled(self):
        unscaled = _apply_scale(self.mine, None)
        self.assertFalse(unscaled["scaled"])
        self.assertEqual(unscaled["value"], unscaled["raw_value"])


class LoadingClubByClubEndsWhereLoadingAtOnceDoes(unittest.TestCase):
    """The property the rescaling pass exists to restore."""

    def simulate(self, clubs, rescale):
        """Load a tenant club by club and report each player's final value.

        `rescale` says whether the pass runs after each payload. Without
        it, a player keeps whatever scale existed when his club landed.
        """
        loaded, stored = [], {}
        for club in clubs:
            loaded.extend(club)
            scale = scale_of(loaded)
            for raw in club:
                stored[raw] = _apply_scale(raw, scale)["value"]
            if rescale:
                for raw in loaded:
                    stored[raw] = _apply_scale(raw, scale)["value"]
        return stored

    def clubs(self, seed=11):
        raws = population(n=36, seed=seed)
        return [raws[i:i + 6] for i in range(0, 36, 6)]

    def test_without_rescaling_the_order_decides_the_answer(self):
        clubs = self.clubs()
        first = self.simulate(clubs, rescale=False)
        last = self.simulate(list(reversed(clubs)), rescale=False)
        self.assertNotEqual(
            first, last,
            "this is the fault as it stood: the same players, the same "
            "matches, a different index for having been visited later")

    def test_with_rescaling_the_order_stops_mattering(self):
        clubs = self.clubs()
        first = self.simulate(clubs, rescale=True)
        last = self.simulate(list(reversed(clubs)), rescale=True)
        self.assertEqual(first, last)

    def test_with_rescaling_club_by_club_matches_loading_at_once(self):
        clubs = self.clubs()
        in_parts = self.simulate(clubs, rescale=True)
        at_once = self.simulate([[raw for club in clubs for raw in club]],
                                rescale=True)
        self.assertEqual(in_parts, at_once)

    def test_loading_the_same_file_twice_changes_nothing(self):
        clubs = self.clubs()
        once = self.simulate(clubs, rescale=True)
        # A reload sees the tenant's own rows already there, which is what
        # moved centre-backs from 44.2-73.4 to 45.7-75.7 on an identical
        # file. The raw values are the same rows, so the scale is too.
        twice = self.simulate(clubs + clubs, rescale=True)
        self.assertEqual(once, twice)


class TheRescalingPassIsWired(unittest.TestCase):
    def test_ingest_runs_it_before_reporting(self):
        import inspect

        from app.services import ingest_service
        source = inspect.getsource(ingest_service.ingest)
        self.assertIn("renormalise(db, org_id, org_ids)", source,
                      "a pass nothing calls fixes nothing")
        self.assertIn('"rescaled": rescaled', source,
                      "what it moved has to reach the caller, or a load "
                      "quietly reindexes a tenant and says nothing")

    def test_it_reads_the_raw_figure_and_not_the_scaled_one(self):
        import inspect

        from app.services import ingest_service
        source = inspect.getsource(ingest_service.renormalise)
        self.assertIn("raw_value", source)
        self.assertIn("_apply_scale", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
