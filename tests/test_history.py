"""
Kumü — a gap in the match log is not a bad performance
=======================================================

    python3 tests/test_history.py

Two figures read the same history and both read it wrong in the same
way. `p.get("rating", 0)` turned a match with no rating into a nought,
and a nought is not a missing value — it is the worst rating there is.

In the consistency figure that inflated the spread, so a steady player
with one unrecorded appearance came out Inconsistent. In the trajectory
it dragged the regression down, so the same player came out Declining.
Declining is the worse of the two: nothing about the word suggests a
default, and a club reading it would pass on a player for a hole in the
feed.

Both also answered when they had nothing. Consistency returned
`{"rating": "Insufficient data", "score": 0}`, which the page printed as
"Insufficient data" above "Score: 0/100" — the score of a maximally
erratic footballer, sitting under the words saying there was no score.
Eighty-five of the hundred and one players loaded are below the
five-match gate, so that was the common case, not the edge.

Trajectory returned "Insufficient data" with `direction: "neutral"`,
a verdict printed beside the statement that there was no verdict, and
no slope at all where the interface's type promised a number.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.services.scouting_report_generator import (  # noqa: E402
    ScoutingReportGenerator,
)


def history(*ratings):
    """A log where None means the match is recorded and the rating is not."""
    out = []
    for i, r in enumerate(ratings):
        match = {"match_id": str(i), "minutes": 90.0}
        if r is not None:
            match["rating"] = r
        out.append(match)
    return out


STEADY = (7.2, 7.1, 7.3, 7.2, 7.1, 7.2)


class AMissingRatingIsNotAZero(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_the_extractor_drops_it(self):
        self.assertEqual(
            self.g._ratings(history(7.0, None, 7.4)), [7.0, 7.4])

    def test_it_drops_nothing_that_is_a_rating(self):
        self.assertEqual(self.g._ratings(history(0.0, 7.4)), [0.0, 7.4],
                         "a real nought is a rating; only an absent one is "
                         "not, and the two were indistinguishable before")

    def test_a_steady_player_is_not_made_inconsistent_by_a_gap(self):
        whole = self.g._calculate_consistency(history(*STEADY))
        gapped = self.g._calculate_consistency(
            history(*STEADY[:3], None, *STEADY[3:]))
        self.assertEqual(whole["rating"], gapped["rating"])
        self.assertNotEqual(gapped["rating"], "Inconsistent")

    def test_a_steady_player_is_not_made_to_decline_by_a_gap(self):
        """The one that would have cost somebody a signing."""
        whole = self.g._analyze_form_trajectory(history(*STEADY))
        gapped = self.g._analyze_form_trajectory(
            history(*STEADY[:4], None, STEADY[4]))
        self.assertEqual(whole["trend"], gapped["trend"])
        self.assertNotEqual(gapped["trend"], "Declining")

    def test_the_old_behaviour_really_was_wrong(self):
        """A check that cannot fail is not a check.

        Reads the history the way the code used to, and confirms the gap
        produced the verdict this test exists to prevent.
        """
        import numpy as np

        como_antes = [m.get("rating", 0)
                      for m in history(*STEADY[:4], None, STEADY[4])][-5:]
        pendiente = float(np.polyfit(np.arange(len(como_antes)),
                                     como_antes, 1)[0])
        self.assertLess(pendiente, -0.1,
                        "the old reading has to slope down, or there was "
                        "nothing here to fix")


class ConsistencyDeclinesRatherThanScoreZero(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_too_short_a_log_has_no_score(self):
        got = self.g._calculate_consistency(history(7.0, 7.2, 7.1))
        self.assertIsNone(got["score"])
        self.assertIsNone(got["rating"])

    def test_it_says_how_short(self):
        got = self.g._calculate_consistency(history(7.0, 7.2, 7.1))
        self.assertIn("3 rated appearances", got["basis"])
        self.assertIn("5", got["basis"])

    def test_one_appearance_reads_as_one(self):
        """Plural agreement, because the sentence is read by people."""
        self.assertIn("1 rated appearance,",
                      self.g._calculate_consistency(history(7.0))["basis"])

    def test_a_long_enough_log_still_scores(self):
        got = self.g._calculate_consistency(history(*STEADY))
        self.assertEqual(got["rating"], "Very Consistent")
        self.assertEqual(got["score"], 90)
        self.assertIn("Spread of", got["basis"])

    def test_an_erratic_player_is_still_called_erratic(self):
        got = self.g._calculate_consistency(
            history(4.0, 9.0, 4.5, 8.8, 5.0, 9.2))
        self.assertEqual(got["rating"], "Inconsistent")
        self.assertEqual(got["score"], 40)

    def test_the_gate_counts_ratings_and_not_rows(self):
        """Six appearances, two of them unrated, is four ratings."""
        got = self.g._calculate_consistency(
            history(7.0, None, 7.2, None, 7.1, 7.3))
        self.assertIsNone(got["score"])
        self.assertIn("4 rated appearances", got["basis"])


class TrajectoryDeclinesRatherThanSayNeutral(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_too_short_a_log_has_no_direction(self):
        got = self.g._analyze_form_trajectory(history(7.0, 7.2))
        self.assertIsNone(got["trend"])
        self.assertIsNone(got["direction"],
                          "neutral is a verdict, printed beside the words "
                          "saying there was no verdict")

    def test_the_slope_key_is_always_there(self):
        """It was absent, and the interface typed it as a number."""
        got = self.g._analyze_form_trajectory(history(7.0, 7.2))
        self.assertIn("slope", got)
        self.assertIsNone(got["slope"])

    def test_a_rising_player_still_rises(self):
        got = self.g._analyze_form_trajectory(
            history(6.0, 6.5, 7.0, 7.5, 8.0))
        self.assertEqual(got["trend"], "Improving")
        self.assertGreater(got["slope"], 0.1)

    def test_a_falling_player_still_falls(self):
        got = self.g._analyze_form_trajectory(
            history(8.0, 7.5, 7.0, 6.5, 6.0))
        self.assertEqual(got["trend"], "Declining")

    def test_a_flat_player_is_stable(self):
        got = self.g._analyze_form_trajectory(history(*STEADY))
        self.assertEqual(got["trend"], "Stable")


class TheSectionSurvivesEitherWay(unittest.TestCase):
    """Both figures live in the statistical overview, which the report
    builds for every player whatever his log holds."""

    CLUB = {
        "id": 188, "name": "Brisbane Roar FC", "league": "A-League Men",
        "country": "Australia", "budget": None, "playing_style": None,
        "expected_index": None,
    }

    def player(self, hist):
        return {
            "id": 1, "name": "K. Jelacic", "position": "ST", "age": 22,
            "current_team": "Brisbane Roar FC", "market_value": None,
            "performance_index": {"value": 71.0, "raw_value": 71.0,
                                  "scaled": True},
            "metrics": {"shooting": {"goals_per_90": 0.96}},
            "performance_history": hist,
        }

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_with_a_short_log(self):
        stats = self.g.generate_statistical_overview(
            self.player(history(7.0, 7.2)), dict(self.CLUB))
        self.assertIsNone(stats["consistency_rating"]["score"])
        self.assertIsNone(stats["form_trajectory"]["trend"])

    def test_with_a_full_log(self):
        stats = self.g.generate_statistical_overview(
            self.player(history(*STEADY)), dict(self.CLUB))
        self.assertEqual(stats["consistency_rating"]["score"], 90)
        self.assertEqual(stats["form_trajectory"]["trend"], "Stable")

    def test_with_no_log_at_all(self):
        stats = self.g.generate_statistical_overview(
            self.player([]), dict(self.CLUB))
        self.assertIsNone(stats["consistency_rating"]["score"])
        self.assertIn("0 rated appearances",
                      stats["consistency_rating"]["basis"])

    def test_the_whole_report_generates_either_way(self):
        for hist in ([], history(7.0, 7.2), history(*STEADY)):
            report = self.g.generate_full_report(
                self.player(hist), dict(self.CLUB))
            self.assertEqual(
                set(ScoutingReportGenerator.SECTIONS) - set(report), set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
