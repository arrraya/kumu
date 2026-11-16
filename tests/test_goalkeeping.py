"""
Tests for the goalkeeping derivation.

Both faults this file is written against were mine, and both produced
numbers that looked entirely reasonable.

The first read only `Shot Saved` and `Shot Faced`, not knowing that a
goal is its own event type. Nobody conceded anything, so every keeper in
the World Cup had a 100% save rate and `goals_prevented` measured only
how often he was shot at. It ranked the Golden Glove 25th of 28.

The second took pre-shot expected goals at face value. Conditioned on a
shot being on target it understates by nearly half, so all 28 keepers
came out negative by 0.61 goals a match - a property of the data, the
same for everyone, dressed as a judgement on each of them.

Neither was found by reading the code. The first was found by a save
percentage that could not be true, the second by a sign that could not
be true. So these tests check the shape of the result as well as its
parts: a save rate below 100, an expectation the population fixes, a
distribution that sums to nothing.
"""

import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pipeline"))

import goalkeeping  # noqa: E402


def events(rows):
    """A minimal event frame: only the columns the derivation reads."""
    blank = {
        "id": None, "type": None, "player": None, "team": None,
        "position": None, "period": 1, "minute": 0,
        "goalkeeper_type": None, "related_events": None,
        "shot_outcome": None, "shot_statsbomb_xg": None,
        "pass_outcome": None,
    }
    return pd.DataFrame([{**blank, **row} for row in rows])


def shot(event_id, outcome, xg):
    return {"id": event_id, "type": "Shot", "shot_outcome": outcome,
            "shot_statsbomb_xg": xg, "player": "Delantero", "minute": 10}


def keeper_event(kind, shot_id=None, keeper="Arquero", period=1, minute=10):
    return {"id": f"gk-{kind}-{shot_id}-{minute}", "type": "Goal Keeper",
            "player": keeper, "team": "Equipo", "position": "Goalkeeper",
            "goalkeeper_type": kind, "period": period, "minute": minute,
            "related_events": [shot_id] if shot_id else None}


class AGoalIsCounted(unittest.TestCase):
    """The fault that gave everyone a 100% save rate."""

    def test_goal_conceded_is_a_goal(self):
        frame = events([shot("s1", "Goal", 0.3),
                        keeper_event("Goal Conceded", "s1")])
        record = goalkeeping.derive_match(frame)["keepers"]["Arquero"]
        self.assertEqual(record["goals_conceded"], 1.0)
        self.assertEqual(record["shots_on_target_faced"], 1.0,
                         "a goal is a shot he had to deal with")
        self.assertEqual(record["saves"], 0.0)

    def test_a_penalty_conceded_is_a_goal(self):
        frame = events([shot("s1", "Goal", 0.78),
                        keeper_event("Penalty Conceded", "s1")])
        record = goalkeeping.derive_match(frame)["keepers"]["Arquero"]
        self.assertEqual(record["goals_conceded"], 1.0)

    def test_a_save_rate_of_one_hundred_percent_needs_no_goals(self):
        frame = events([
            shot("s1", "Saved", 0.1), keeper_event("Shot Saved", "s1"),
            shot("s2", "Goal", 0.4), keeper_event("Goal Conceded", "s2",
                                                  minute=20),
        ])
        record = goalkeeping.derive_match(frame)["keepers"]["Arquero"]
        self.assertEqual(record["saves"], 1.0)
        self.assertEqual(record["shots_on_target_faced"], 2.0)
        self.assertLess(record["saves"] / record["shots_on_target_faced"], 1.0,
                        "every keeper in the tournament reading 100% is how "
                        "the missing goal event was found")


class EveryWayAShotIsStopped(unittest.TestCase):
    def test_each_save_type_counts(self):
        for kind in ("Shot Saved", "Penalty Saved", "Shot Saved to Post",
                     "Shot Saved Off Target"):
            frame = events([shot("s1", "Saved", 0.2),
                            keeper_event(kind, "s1")])
            record = goalkeeping.derive_match(frame)["keepers"]["Arquero"]
            self.assertEqual(record["saves"], 1.0, f"{kind} is a save")

    def test_a_shot_he_never_had_to_touch_is_not_his(self):
        for outcome in ("Blocked", "Off T", "Wayward", "Post"):
            frame = events([shot("s1", outcome, 0.2),
                            keeper_event("Shot Faced", "s1")])
            record = goalkeeping.derive_match(frame)["keepers"]["Arquero"]
            self.assertEqual(record["shots_on_target_faced"], 0.0,
                             f"{outcome} never reached the keeper")

    def test_claims_and_sweeping_are_kept_apart_from_shot_stopping(self):
        frame = events([keeper_event("Collected"),
                        keeper_event("Punch", minute=20),
                        keeper_event("Smother", minute=30),
                        keeper_event("Keeper Sweeper", minute=40)])
        record = goalkeeping.derive_match(frame)["keepers"]["Arquero"]
        self.assertEqual(record["claims"], 3.0)
        self.assertEqual(record["sweeper_actions"], 1.0)
        self.assertEqual(record["shots_on_target_faced"], 0.0)

    def test_an_unknown_type_is_reported_not_swallowed(self):
        frame = events([keeper_event("Algo Nuevo")])
        result = goalkeeping.derive_match(frame)
        self.assertEqual(result["unknown"], {"Algo Nuevo": 1},
                         "a vocabulary this file has not seen must surface; "
                         "Goal Conceded was missed exactly this way")


class AShootoutIsNotTheMatch(unittest.TestCase):
    def test_period_five_is_excluded(self):
        frame = events([
            shot("s1", "Goal", 0.78),
            keeper_event("Penalty Conceded", "s1", period=5, minute=121),
            shot("s2", "Saved", 0.78),
            keeper_event("Penalty Saved", "s2", period=5, minute=122),
        ])
        record = goalkeeping.derive_match(frame)["keepers"]["Arquero"]
        self.assertEqual(record["goals_conceded"], 0.0)
        self.assertEqual(record["saves"], 0.0)

    def test_extra_time_is_still_the_match(self):
        frame = events([shot("s1", "Saved", 0.3),
                        keeper_event("Shot Saved", "s1", period=4,
                                     minute=105)])
        record = goalkeeping.derive_match(frame)["keepers"]["Arquero"]
        self.assertEqual(record["saves"], 1.0,
                         "a save in extra time is a save")


class TheExpectationIsFixedByThePopulation(unittest.TestCase):
    """The fault that made all 28 keepers negative."""

    def population(self, shots_each, goals_each, xg_each, keepers=40):
        return {
            f"k{i}": {"history": [{
                "goals_conceded": float(goals_each),
                "shots_on_target_faced": float(shots_each),
                "expected_on_target_faced": float(xg_each),
            }]} for i in range(keepers)
        }

    def test_the_scale_corrects_the_understatement(self):
        # 100 keepers, 5 on-target each, 2 conceded, pre-shot xG of 1.0.
        scale = goalkeeping.conversion_scale(
            self.population(shots_each=5, goals_each=2, xg_each=1.0))
        self.assertAlmostEqual(
            scale, 2.0, places=6,
            msg="twice as many goals as the pre-shot figure expected means "
                "the expectation doubles")

    def test_a_corrected_population_sums_to_nothing(self):
        keepers = self.population(shots_each=5, goals_each=2, xg_each=1.0)
        scale = goalkeeping.conversion_scale(keepers)
        total = sum(record["expected_on_target_faced"] * scale
                    - record["goals_conceded"]
                    for entry in keepers.values()
                    for record in entry["history"])
        self.assertAlmostEqual(
            total, 0.0, places=6,
            msg="every keeper coming out negative is how the raw pre-shot "
                "figure was found")

    def test_a_sample_too_small_leaves_the_figure_uncorrected(self):
        scale = goalkeeping.conversion_scale(
            self.population(shots_each=1, goals_each=1, xg_each=0.2,
                            keepers=3))
        self.assertEqual(scale, 1.0,
                         "a factor fitted to three keepers is a fudge factor")

    def test_the_scale_is_not_written_down_anywhere(self):
        """It came out near 1.9 here; it must not be stored as 1.9."""
        with open(goalkeeping.__file__, encoding="utf-8") as handle:
            source = handle.read()
        body = source.split('"""', 2)[-1]
        self.assertNotIn("1.905", body)
        self.assertNotIn("= 1.9", body)


class PerNinety(unittest.TestCase):
    def test_the_save_rate_is_over_the_sample_not_the_mean_of_matches(self):
        history = [
            {"minutes": 90.0, "saves": 9.0, "shots_on_target_faced": 10.0,
             "goals_prevented": 1.0, "claims": 0.0, "sweeper_actions": 0.0},
            {"minutes": 90.0, "saves": 0.0, "shots_on_target_faced": 1.0,
             "goals_prevented": -0.5, "claims": 0.0, "sweeper_actions": 0.0},
        ]
        metrics = goalkeeping.per_90(history)
        self.assertAlmostEqual(metrics["save_percentage"], 9 / 11, places=3)  # noqa
        self.assertNotAlmostEqual(
            metrics["save_percentage"], 0.45, places=2,
            msg="averaging the two rates lets a one-shot match weigh as much "
                "as a ten-shot one")

    def test_a_keeper_who_faced_nothing_has_no_save_rate(self):
        history = [{"minutes": 90.0, "saves": 0.0,
                    "shots_on_target_faced": 0.0, "goals_prevented": 0.0,
                    "claims": 1.0, "sweeper_actions": 2.0}]
        self.assertIsNone(goalkeeping.per_90(history)["save_percentage"],
                          "nought from nought is not nought per cent")

    def test_no_minutes_yields_nothing_rather_than_dividing_by_zero(self):
        self.assertEqual(goalkeeping.per_90([{"minutes": 0.0}]), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
