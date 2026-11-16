"""
Kumü — what Kumu writes, Kumu must be able to read back
========================================================

    python3 tests/test_contract.py

`app/schemas/ingest.py` is the door data comes in through, and Kumu's own
output has to fit through it. It did not: `match_rating` is uncapped on
purpose while `MatchRecord.rating` was bounded at 10, so a player with a
hat-trick got a rating his own history could not be re-ingested with. Of
101 A-League players loaded, four were in that state and nothing noticed
until someone tried the round trip by hand.

The test that matters here is not "is the ceiling 30". A number asserted
against itself proves nothing. It is: **everything the formula can
produce, the contract accepts** — so the test fails if either side moves
away from the other, whichever one moves.

That reach is searched, not listed. The first version of this file used a
hand-written set of match lines, which is how the ceiling came to be set
at 25 from the attack formula alone: midfield and defense also reward
progressive passing and defensive work, so they climb to 28, and a
hand-picked fixture never went there. A list of examples tests the
examples. The grid below tests the formula.
"""

import itertools
import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from pydantic import ValidationError  # noqa: E402

from app.core.scoring import (  # noqa: E402
    POSITIONS, match_rating, rate_history, raw_index,
)
from app.schemas.ingest import MAX_RATING, MatchRecord, PlayerRecord  # noqa: E402

# "goalkeeper" is deliberately absent: its formula returns None on an
# appearance with no goalkeeping in it, so it has no ceiling to search for
# and is covered by its own tests below.
GROUPS = ("attack", "midfield", "defense")
OUTFIELD = [p for p in POSITIONS if p != "GK"]


def steep_history():
    """Five appearances climbing to a seven-goal match, no goalkeeping."""
    return [
        dict(match_id=str(i), goals=g, assists=2, key_passes=5, shots=9,
             pass_completion=0.9, progressive_passes=14, tackles=6,
             interceptions=5)
        for i, g in enumerate((0, 1, 3, 5, 7))
    ]


def keeper_history():
    """The same span of afternoons, for a goalkeeper."""
    return [
        dict(match_id=str(i), saves=s, shots_on_target_faced=f,
             goals_prevented=p, claims=2, sweeper_actions=1,
             pass_completion=0.75)
        for i, (s, f, p) in enumerate(
            [(1, 4, -1.4), (2, 2, 0.4), (4, 6, 1.1), (7, 9, 1.8), (5, 5, 2.6)]
        )
    ]

# The edges of each counting stat, past anything a professional match has
# produced: seven goals, twenty-two progressive passes, twelve tackles.
# Every combination is tried, including the ones no single player would
# ever post together, because the formula has no opinion about which
# combinations are possible and neither should the bound that contains it.
EXTREMES = dict(
    goals=[0, 1, 3, 5, 7],
    assists=[0, 1, 2, 3],
    key_passes=[0, 3, 6, 9],
    shots=[0, 3, 7, 13],
    pass_completion=[0.0, 0.75, 0.95],
    progressive_passes=[0, 6, 14, 22],
    tackles=[0, 3, 8, 12],
    interceptions=[0, 2, 5, 9],
)

# What a match anyone will really play looks like, for the readable half
# of the evidence: these should sit far below the bound, not just under it.
REAL_MATCHES = [
    ("striker, four goals",
     dict(goals=4, assists=1, key_passes=2, shots=8, pass_completion=0.85),
     "attack"),
    ("midfielder running the game",
     dict(goals=1, assists=2, key_passes=5, shots=3, pass_completion=0.92,
          progressive_passes=16, tackles=5, interceptions=4), "midfield"),
    ("centre-back dominating",
     dict(goals=1, assists=0, key_passes=1, shots=1, pass_completion=0.94,
          progressive_passes=12, tackles=7, interceptions=6), "defense"),
]


def every_line():
    """Each (group, stats) the grid can make."""
    fields = list(EXTREMES)
    for group in GROUPS:
        for combo in itertools.product(*(EXTREMES[f] for f in fields)):
            yield group, dict(zip(fields, combo))


def hardest_rating():
    return max(round(match_rating(stats, group), 2)
               for group, stats in every_line())


def accepted(rating):
    try:
        MatchRecord(match_id="x", rating=rating)
        return True
    except ValidationError:
        return False


class TheContractAcceptsWhatKumuWrites(unittest.TestCase):
    """The invariant. Fails if the formula outgrows the ceiling, or the
    ceiling is tightened under the formula."""

    def test_every_rating_the_formula_produces_fits_through_the_door(self):
        worst = None
        for group, stats in every_line():
            rating = round(match_rating(stats, group), 2)
            if not accepted(rating) and (worst is None or rating > worst[0]):
                worst = (rating, group, stats)
        self.assertIsNone(
            worst,
            None if worst is None else
            f"match_rating produced {worst[0]} for a {worst[1]} line the "
            f"contract refuses (MAX_RATING={MAX_RATING}): "
            f"{ {k: v for k, v in worst[2].items() if v} }. "
            f"Kumu cannot read back what Kumu wrote.",
        )

    def test_the_search_covers_every_role_formula(self):
        """The bound was once set from one formula and missed two others."""
        reached = {group: max(round(match_rating(stats, g), 2)
                              for g, stats in every_line() if g == group)
                   for group in GROUPS}
        self.assertEqual(set(reached), set(GROUPS))
        for group, peak in reached.items():
            self.assertGreater(peak, 20.0,
                               f"{group} barely moves: this grid is not "
                               f"exercising its formula")

    def test_a_rated_history_can_be_re_ingested(self):
        """The round trip in full, as a client re-uploading would do it."""
        for position in OUTFIELD:
            rated = rate_history(steep_history(), position)
            self.assertTrue(any(h.get("rating", 0) > 10 for h in rated),
                            "this fixture must contain the case that broke, "
                            "or it is not testing anything")
            self.assertReIngests(position, rated)

    def test_a_goalkeeper_with_goalkeeping_is_rated_and_re_ingested(self):
        rated = rate_history(keeper_history(), "GK")
        self.assertTrue(all("rating" in h for h in rated),
                        "goalkeeping was supplied, so every appearance rates")
        self.assertReIngests("GK", rated)

    def test_a_goalkeeper_without_goalkeeping_is_left_unrated(self):
        """Not rated as a defender, and not rated as nought."""
        rated = rate_history(steep_history(), "GK")
        self.assertTrue(all("rating" not in h for h in rated),
                        "an outfield line says nothing about goalkeeping, so "
                        "it must not produce a goalkeeper's rating")
        self.assertReIngests("GK", rated)
        self.assertIsNone(
            raw_index(rated),
            "no rated appearance is no index, by the same route as a player "
            "with two matches")

    def assertReIngests(self, position, history):
        try:
            PlayerRecord(external_id="x", name="X", position=position,
                         performance_history=history)
        except ValidationError as error:
            self.fail(f"a {position} history Kumu produced cannot be "
                      f"re-ingested: {error.errors()[0]['msg']}")

    def test_the_ceiling_has_headroom_over_the_hardest_line(self):
        hardest = hardest_rating()
        self.assertLess(hardest, MAX_RATING,
                        f"the ceiling ({MAX_RATING}) sits below what the "
                        f"formulas reach ({hardest})")
        self.assertGreater(MAX_RATING - hardest, 1.0,
                           f"only {MAX_RATING - hardest:.2f} of headroom over "
                           f"{hardest}: the next change to a formula breaks "
                           f"the round trip again")

    def test_a_real_match_sits_far_below_the_bound(self):
        """A bound a real performance can approach is not a sanity bound."""
        for name, stats, group in REAL_MATCHES:
            rating = match_rating(stats, group)
            self.assertLess(rating * 1.5, MAX_RATING,
                            f"{name} rates {rating:.2f}, uncomfortably close "
                            f"to a bound meant to catch typing errors")


class TheContractStillRefusesNonsense(unittest.TestCase):
    """A ceiling that admits everything is not a ceiling."""

    def test_a_misplaced_decimal_point_is_refused(self):
        self.assertFalse(accepted(85.0),
                         "85 is 8.5 with the point in the wrong place, and it "
                         "is the error this bound exists to catch")
        self.assertFalse(accepted(100.0))

    def test_a_negative_rating_is_refused(self):
        self.assertFalse(accepted(-0.1))

    def test_the_bound_is_inclusive_and_bites_just_above(self):
        self.assertTrue(accepted(MAX_RATING))
        self.assertFalse(accepted(MAX_RATING + 0.01))

    def test_a_client_rating_on_the_usual_scale_still_passes(self):
        for rating in (0.0, 5.5, 7.2, 10.0):
            self.assertTrue(accepted(rating),
                            f"{rating} is an ordinary client rating")

    def test_an_absent_rating_stays_absent(self):
        self.assertIsNone(MatchRecord(match_id="x").rating,
                          "no rating is not a rating of zero")


class RatingsKumuDidNotWrite(unittest.TestCase):
    """A client's own rating is kept, not overwritten."""

    def test_a_supplied_rating_survives_rate_history(self):
        history = [{"match_id": "1", "rating": 6.5, "goals": 3}]
        self.assertEqual(rate_history(history, "ST")[0]["rating"], 6.5)

    def test_a_missing_rating_is_computed(self):
        history = [{"match_id": "1", "goals": 3, "shots": 5,
                    "pass_completion": 0.8}]
        rated = rate_history(history, "ST")[0]["rating"]
        self.assertIsInstance(rated, float)
        self.assertGreater(rated, 0)

    def test_a_non_numeric_rating_is_replaced_rather_than_trusted(self):
        history = [{"match_id": "1", "rating": "muy bueno", "goals": 1}]
        self.assertIsInstance(rate_history(history, "ST")[0]["rating"], float)


class TheGoalkeeperFormula(unittest.TestCase):
    """It declines rather than falling back to somebody else's formula."""

    def keeper(self, **overrides):
        stats = dict(saves=3, shots_on_target_faced=4, goals_prevented=0.5,
                     claims=2, sweeper_actions=1, pass_completion=0.75)
        stats.update(overrides)
        return stats

    def test_an_outfield_line_produces_no_goalkeeper_rating(self):
        outfield = dict(goals=1, assists=1, key_passes=3, shots=4,
                        pass_completion=0.9, progressive_passes=8, tackles=4)
        self.assertIsNone(match_rating(outfield, "goalkeeper"))

    def test_every_required_field_is_required(self):
        for missing in ("saves", "shots_on_target_faced", "goals_prevented"):
            stats = self.keeper()
            del stats[missing]
            self.assertIsNone(match_rating(stats, "goalkeeper"),
                              f"{missing} is missing, so there is no rating")

    def test_a_keeper_who_faced_nothing_is_still_rated(self):
        """A genuine zero is a figure. Absence is not."""
        quiet = self.keeper(saves=0, shots_on_target_faced=0,
                            goals_prevented=0.0)
        self.assertIsInstance(match_rating(quiet, "goalkeeper"), float)

    def test_goals_prevented_moves_the_rating_most(self):
        base = match_rating(self.keeper(goals_prevented=0.0), "goalkeeper")
        good = match_rating(self.keeper(goals_prevented=2.0), "goalkeeper")
        more_claims = match_rating(
            self.keeper(goals_prevented=0.0, claims=12), "goalkeeper")
        self.assertGreater(good - base, more_claims - base,
                           "stopping shots has to outweigh catching crosses")

    def test_a_bad_afternoon_rates_below_the_base(self):
        bad = self.keeper(saves=1, shots_on_target_faced=5,
                          goals_prevented=-2.0)
        self.assertLess(match_rating(bad, "goalkeeper"), 5.0,
                        "letting in more than the shots deserved is worse "
                        "than a blank afternoon")

    def test_the_rating_separates_keepers(self):
        """The fault being fixed: 5.1 points of spread across a whole set."""
        ratings = [
            match_rating(self.keeper(saves=s, shots_on_target_faced=f,
                                     goals_prevented=p), "goalkeeper")
            for s, f, p in [(1, 5, -2.0), (2, 3, 0.0), (4, 5, 0.9),
                            (7, 9, 1.8), (5, 5, 2.6)]
        ]
        self.assertGreater(max(ratings) - min(ratings), 5.0,
                           "a formula that cannot tell keepers apart is not "
                           "measuring goalkeeping")

    def test_a_goalkeeper_rating_also_fits_through_the_door(self):
        extreme = self.keeper(saves=12, shots_on_target_faced=14,
                              goals_prevented=5.0, claims=8,
                              sweeper_actions=6, pass_completion=1.0)
        self.assertTrue(accepted(round(match_rating(extreme, "goalkeeper"), 2)),
                        "the ceiling has to hold for this formula too")


if __name__ == "__main__":
    unittest.main(verbosity=2)
