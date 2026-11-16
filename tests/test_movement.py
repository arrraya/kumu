"""
Kumü — a source may carry some of the athletic figures and not others
======================================================================

    python3 tests/test_movement.py

`_movement` was all or nothing, and that was right while a source either
had tracking or did not. Pose is neither: it measures average speed and
distance over the time a player was actually seen, and those come out
independent of how much of the match that was. The run count does not.
It is a tally of threshold crossings in the frames nearest the ball,
scaled up by one over the coverage, so a window already weighted toward
the moments a player is sprinting gets multiplied.

Measured across the 32 players of the published match: runs per 90
correlate with coverage at r = -0.35 where speed and distance sit at
+0.09. The three best observed produced a median of 50 runs against 83
for the other 29, and the midfield reference is 35.

Demanding all three threw away two sound figures to avoid one unsound
one. So the aggregator declines the run count below the coverage that
can carry it, and the report scores whatever it was given and names what
it was not.
"""

import os
import sys
import unittest

import numpy as np

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "backend"))
sys.path.insert(0, os.path.join(HERE, "pipeline", "pose"))

import aggregate  # noqa: E402

from app.services.scouting_report_generator import (  # noqa: E402
    ScoutingReportGenerator,
)

FULL = {"average_speed": 8.1, "distance_covered_per_90": 12.2,
        "high_intensity_runs": 34}
RATES_ONLY = {"average_speed": 8.1, "distance_covered_per_90": 12.2,
              "high_intensity_runs": None}


def player(movement=None, position="CM"):
    metrics = {"passing": {"completion_rate": 0.81}}
    if movement is not None:
        metrics["movement"] = dict(movement)
    return {
        "id": 1, "name": "Jugador", "position": position, "age": 25,
        "performance_index": {"value": 70.0, "trend": 0.0,
                              "volatility": 0.1, "confidence": 0.9},
        "metrics": metrics,
        "performance_history": [
            {"match_id": str(i), "rating": 7.0, "minutes": 90.0}
            for i in range(4)
        ],
    }


def running_at(kmh, coverage, total_frames=150_000, fps=25.0):
    """A player moving at a constant speed for `coverage` of the match."""
    observed = int(total_frames * coverage)
    hip = np.full((total_frames, 3), np.nan)
    seconds = np.arange(observed) / fps
    hip[:observed, 0] = (kmh / 3.6) * seconds
    hip[:observed, 1] = 0.0
    hip[:observed, 2] = 0.0
    return aggregate.summarise_movement(
        {"midHip": hip}, fps=fps, total_match_frames=total_frames)


class TheAggregatorDeclinesTheRunCount(unittest.TestCase):
    def test_a_partial_window_yields_no_run_count(self):
        result = running_at(22.0, coverage=0.40)
        self.assertIsNone(result["movement"]["high_intensity_runs"],
                          "scaling a tally of bursts up from 40% of a match "
                          "multiplies a window already weighted to the ball")

    def test_the_rates_survive_a_partial_window(self):
        movement = running_at(22.0, coverage=0.40)["movement"]
        self.assertIsInstance(movement["average_speed"], float)
        self.assertIsInstance(movement["distance_covered_per_90"], float)

    def test_a_nearly_complete_window_yields_one(self):
        result = running_at(22.0, coverage=0.90)
        self.assertIsNotNone(result["movement"]["high_intensity_runs"])

    def test_the_rates_do_not_move_with_coverage(self):
        """What makes them safe to extrapolate and the count not."""
        low = running_at(22.0, coverage=0.40)["movement"]
        high = running_at(22.0, coverage=0.90)["movement"]
        self.assertAlmostEqual(low["average_speed"], high["average_speed"],
                               places=1)
        self.assertAlmostEqual(low["distance_covered_per_90"],
                               high["distance_covered_per_90"], delta=0.5)

    def test_the_basis_says_what_became_of_the_count(self):
        basis = running_at(22.0, coverage=0.40)["basis"]
        self.assertIn("No high-intensity run count", basis)
        self.assertIn("r = -0.35", basis,
                      "the bias was measured, so the figure that justifies "
                      "the refusal belongs in the line that reports it")

    def test_the_old_claim_that_nothing_could_be_quantified_is_gone(self):
        basis = running_at(22.0, coverage=0.40)["basis"]
        self.assertNotIn("cannot quantify", basis)
        self.assertNotIn("every figure here", basis)

    def test_the_movement_dict_carries_only_the_contract_fields(self):
        """It is written into players.metrics by raw SQL, unvalidated."""
        movement = running_at(22.0, coverage=0.90)["movement"]
        self.assertEqual(
            set(movement),
            {"average_speed", "distance_covered_per_90",
             "high_intensity_runs"},
            "an extra key here lands in the database unchecked")

    def test_the_observed_count_is_kept_where_it_cannot_leak(self):
        result = running_at(22.0, coverage=0.40)
        self.assertIn("high_intensity_runs_observed", result["coverage"])


class TheReportScoresWhatItWasGiven(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()

    def scores(self, movement):
        return self.g.generate_physical_profile(
            player(movement))["athletic_scores"]

    def test_all_three_when_all_three_are_there(self):
        self.assertEqual(set(self.scores(FULL)),
                         {"speed", "endurance", "intensity"})

    def test_two_when_the_run_count_is_absent(self):
        scored = self.scores(RATES_ONLY)
        self.assertEqual(set(scored), {"speed", "endurance"},
                         "refusing the lot to avoid one unsound figure threw "
                         "away two sound ones")

    def test_none_when_the_source_has_no_tracking(self):
        self.assertEqual(self.scores(None), {})

    def test_the_mean_counts_only_what_was_scored(self):
        basis = self.g.generate_physical_profile(
            player(RATES_ONLY))["athletic_scores_basis"]
        self.assertIn("over 2 of 3", basis)

    def test_the_basis_names_the_missing_figure(self):
        basis = self.g.generate_physical_profile(
            player(RATES_ONLY))["athletic_scores_basis"]
        self.assertIn("intensity", basis)
        self.assertIn("high_intensity_runs", basis)

    def test_a_complete_source_says_so(self):
        basis = self.g.generate_physical_profile(
            player(FULL))["athletic_scores_basis"]
        self.assertIn("over 3 of 3", basis)
        self.assertNotIn("does not carry", basis)

    def test_an_absent_figure_is_not_scored_as_nought(self):
        for label, score in self.scores(RATES_ONLY).items():
            self.assertGreater(score["score"], 0,
                               f"{label} would be the old .get(key, 0) fault "
                               f"coming back one level down")

    def test_a_genuine_zero_is_still_scored(self):
        """Presence is the test, not size."""
        still_counts = dict(FULL, high_intensity_runs=0)
        scored = self.scores(still_counts)
        self.assertIn("intensity", scored)
        self.assertEqual(scored["intensity"]["score"], 0.0)

    def test_the_whole_report_survives_a_partial_profile(self):
        club = {"id": 5, "name": "Club", "league": "Liga",
                "country": "Pais", "budget": 1_000_000.0,
                "playing_style": {"possession": 0.5,
                                  "pressing_intensity": 0.5}}
        report = self.g.generate_full_report(player(RATES_ONLY), club)
        self.assertEqual(len(report), 9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
