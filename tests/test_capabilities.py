"""
Kumü — what a client is told about their own file
==================================================

    python3 tests/test_capabilities.py

`/ingest/validate` is deliberately open: judging a file should not
require an account. So it is the first thing a prospective client sees
about their own data, and for a long time it told most of them their
data was broken.

`describe_capabilities` tested `position in POSITIONS`, which holds
Kumu's own ten codes, while `prepare_player` puts the provider's name
through `normalize_position` first. Two readings of one field. Anybody
who speaks a provider's vocabulary — StatsBomb, SkillCorner, anyone
exporting from a real tool rather than typing Kumu's codes by hand — was
told "positions not recognised and ignored" and had `comparison`, the
headline capability, reported as unavailable. Then the same file loaded
without trouble.

These tests hold the two readings together: whatever the validator says
about a position, the loader has to agree.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.core.scoring import (  # noqa: E402
    PROVIDER_POSITION_MAP, normalize_position,
)
from app.schemas.ingest import (  # noqa: E402
    POSITIONS, IngestPayload, describe_capabilities,
)


def player(position, **overrides):
    record = {
        "external_id": "x",
        "name": "Jugador",
        "position": position,
        "metrics": {"passing": {"completion_rate": 0.81}},
        "performance_history": [
            {"match_id": str(i), "goals": 1, "pass_completion": 0.8}
            for i in range(4)
        ],
    }
    record.update(overrides)
    return record


def describe(*players):
    return describe_capabilities(
        IngestPayload(source="prueba", players=list(players)))


def unknown_warnings(result):
    return [w for w in result["warnings"] if "not recognised" in w]


class TheValidatorAgreesWithTheLoader(unittest.TestCase):
    """One field, one reading."""

    def test_every_name_the_loader_accepts_the_validator_accepts(self):
        for name in sorted(PROVIDER_POSITION_MAP):
            result = describe(player(name))
            self.assertTrue(
                result["capabilities"]["comparison"]["enabled"],
                f"{name!r} loads as {normalize_position(name)} but the "
                f"validator reports comparison as unavailable")
            self.assertEqual(
                unknown_warnings(result), [],
                f"{name!r} loads fine, so nothing should say it was ignored")

    def test_kumus_own_codes_still_pass(self):
        for code in sorted(POSITIONS):
            result = describe(player(code))
            self.assertTrue(result["capabilities"]["comparison"]["enabled"])
            self.assertEqual(unknown_warnings(result), [])

    def test_a_name_nobody_maps_is_still_reported(self):
        """Fixing the false alarm must not silence the true one."""
        result = describe(player("Portero de Barrio"))
        self.assertFalse(result["capabilities"]["comparison"]["enabled"])
        self.assertEqual(len(unknown_warnings(result)), 1)
        self.assertIn("Portero de Barrio", unknown_warnings(result)[0])

    def test_the_warning_no_longer_claims_only_codes_are_read(self):
        warning = unknown_warnings(describe(player("Inventado")))[0]
        self.assertIn("StatsBomb", warning,
                      "the old wording listed Kumu's ten codes as if they "
                      "were the whole vocabulary, which is why a provider "
                      "name looked like an error")

    def test_a_mixed_file_counts_only_the_ones_that_fail(self):
        result = describe(player("Center Midfield"), player("GK"),
                          player("Qué Sé Yo"))
        self.assertEqual(result["capabilities"]["comparison"]["covers"], 3)
        self.assertEqual(len(unknown_warnings(result)), 1)
        self.assertIn("Qué Sé Yo", unknown_warnings(result)[0])


class GoalkeepersAreCountedByWhatTheyLoadAs(unittest.TestCase):
    GOALKEEPING = {"saves_per_90": 3.0, "save_percentage": 0.72,
                   "goals_prevented_per_90": 0.2}

    def test_a_keeper_under_either_spelling_is_found(self):
        for name in ("GK", "Goalkeeper"):
            result = describe(player(name))
            self.assertEqual(
                result["capabilities"]["goalkeeper_rating"]
                ["goalkeepers_in_file"], 1,
                f"{name!r} is a goalkeeper however it is spelled")

    def test_a_file_without_goalkeeping_says_so(self):
        capability = describe(player("Goalkeeper"))["capabilities"]
        self.assertFalse(capability["goalkeeper_rating"]["enabled"])
        self.assertEqual(capability["goalkeeper_rating"]["covers"], 0)

    def test_a_file_with_goalkeeping_enables_it(self):
        keeper = player("Goalkeeper")
        keeper["metrics"] = dict(keeper["metrics"],
                                 goalkeeping=dict(self.GOALKEEPING))
        capability = describe(keeper)["capabilities"]
        self.assertTrue(capability["goalkeeper_rating"]["enabled"])
        self.assertEqual(capability["goalkeeper_rating"]["covers"], 1)

    def test_one_keeper_short_leaves_it_disabled(self):
        rated = player("Goalkeeper")
        rated["metrics"] = dict(rated["metrics"],
                                goalkeeping=dict(self.GOALKEEPING))
        capability = describe(rated, player("GK"))["capabilities"]
        self.assertFalse(capability["goalkeeper_rating"]["enabled"],
                         "half the keepers rateable is not the capability")
        self.assertEqual(capability["goalkeeper_rating"]["covers"], 1)
        self.assertEqual(
            capability["goalkeeper_rating"]["goalkeepers_in_file"], 2)

    def test_an_outfield_file_does_not_claim_goalkeeper_rating(self):
        capability = describe(player("CM"))["capabilities"]
        self.assertFalse(capability["goalkeeper_rating"]["enabled"])
        self.assertEqual(
            capability["goalkeeper_rating"]["goalkeepers_in_file"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
