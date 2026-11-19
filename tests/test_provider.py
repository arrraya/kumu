"""
Kumü — reading a provider back out of an identifier
====================================================

    python3 tests/test_provider.py

The provider was never recorded as a fact. It was abbreviated into the
identifier, by conventions minted in several different places, and the
first attempt at a mapping was written from reading the loaders rather
than from reading the table. It covered 408 of 441 players and 8 of 63
clubs. The prefixes below are the ones production actually holds.

One of them is not a provider at all. `pipeline/seed_teams.py` invents
twenty clubs: the names are real — Manchester City among them — and the
budget, formation, possession, pressing, declared needs and expected
level are all Kumü's own curation. Calling that statsbomb would be the
precise error this column exists to prevent, so it reads kumu_curated.

And the rows that came through the API need no table entry at all. Their
identifier is `<source truncated to twelve>_<sixteen hex>`, so the prefix
IS the source the client declared: reading it back is reading, not
inferring.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pipeline"))

from migrate_source import DEL_API, PROVEEDORES, proveedor  # noqa: E402


class TheRealPrefixesResolve(unittest.TestCase):
    """Every shape counted in production, with a real identifier each."""

    CASOS = [
        ("skillcorner__0442b67b69af4095", "skillcorner", 101),
        ("statsbomb_wc_002f8cd1eb6e9741", "statsbomb_wc2022", 28),
        ("wc2022_c25c44c630f0803a", "statsbomb_wc2022", 307),
        ("nat_France", "statsbomb_wc2022", 32),
        ("nat_South Korea", "statsbomb_wc2022", 32),
        ("club_020", "kumu_curated", 20),
        ("scouting-pro_0fd2b64c434d6619", "scouting-pro", 2),
        ("mi-proveedor_1f4653de69f6a0dd", "mi-proveedor", 1),
        ("demo_6ecebc0734309681", "demo", 2),
    ]

    def test_each_one(self):
        for eid, esperado, _ in self.CASOS:
            self.assertEqual(proveedor(eid), esperado, eid)

    def test_a_space_in_the_name_does_not_break_it(self):
        """`nat_South Korea` and `nat_Saudi Arabia` are real rows."""
        self.assertEqual(proveedor("nat_Saudi Arabia"), "statsbomb_wc2022")

    def test_nothing_unreadable_is_given_a_provider(self):
        for eid in ("", None, "raro", "sin-guion-bajo", "club", "x_notahex"):
            self.assertIsNone(proveedor(eid), repr(eid))


class CurationIsNotAProvider(unittest.TestCase):
    def test_the_seeded_clubs_are_kumus_own(self):
        """Real names, invented everything else. Manchester City at €900M,
        4-3-3, possession 0.68 is a decision."""
        self.assertEqual(proveedor("club_001"), "kumu_curated")
        self.assertEqual(proveedor("club_020"), "kumu_curated")

    def test_it_is_not_confused_with_a_measured_source(self):
        self.assertNotEqual(proveedor("club_007"), "statsbomb_wc2022")
        self.assertNotEqual(proveedor("club_007"), "skillcorner")


class ApiRowsCarryTheirOwnSource(unittest.TestCase):
    """No table entry each: the prefix is what the client declared."""

    def test_the_shape_is_source_then_sixteen_hex(self):
        self.assertIsNotNone(DEL_API.match("cualquiera_0123456789abcdef"))
        self.assertEqual(
            DEL_API.match("cualquiera_0123456789abcdef").group(1),
            "cualquiera")

    def test_fifteen_hex_is_not_the_shape(self):
        self.assertIsNone(DEL_API.match("x_0123456789abcde"))

    def test_a_provider_nobody_listed_still_resolves(self):
        self.assertEqual(proveedor("opta_aaaaaaaaaaaaaaaa"), "opta")

    def test_a_listed_prefix_wins_over_the_shape(self):
        """`wc2022_<16 hex>` fits both; the explicit answer is the right
        one, since the prefix names a tournament and not a provider."""
        self.assertEqual(proveedor("wc2022_0123456789abcdef"),
                         "statsbomb_wc2022")


class TheTableIsOrderedSafely(unittest.TestCase):
    def test_longer_prefixes_come_before_the_ones_inside_them(self):
        """`sc_club_` before `sc_`, or every club reads as a player's
        source; `statsbomb_wc` before nothing that contains it."""
        orden = [p for p, _ in PROVEEDORES]
        for largo in orden:
            for corto in orden:
                if largo != corto and largo.startswith(corto):
                    self.assertLess(
                        orden.index(largo), orden.index(corto),
                        "%r is matched by %r first" % (largo, corto))

    def test_sc_club_resolves_to_skillcorner_not_to_curation(self):
        """`sc_club_brisbane` begins with neither `club_` nor `sc_club_`
        by accident — the order is what keeps it right."""
        self.assertEqual(proveedor("sc_club_brisbane"), "skillcorner")


if __name__ == "__main__":
    unittest.main(verbosity=2)
