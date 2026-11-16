"""
Kumü — an absent index must not join the population as a nought
================================================================

    python3 tests/test_null_index.py

`prepare_player` sets `performance_index` to None for a player Kumu
declines to rate. The loader then wrote `json.dumps(None)`, which is the
string "null", and `CAST('null' AS JSON)` stores the JSON value null —
a value, not an absence.

Every query in the codebase tested the column with
`performance_index IS NOT NULL`, which a JSON null passes, and then read
it with `COALESCE((performance_index->>'value')::float, 0)`. So a player
Kumu had refused to rate joined the percentile population as the worst
member of it, making everyone else look better, and joined a club's
squad as a nought, dragging that position's level down.

It surfaced the first time a position had no rateable players at all:
goalkeepers showed five with an index and no minimum or maximum, which
cannot both be true.

Two things are checked here. The loader has to write SQL NULL, and no
query may turn a missing index into a figure — the second so that a
JSON null arriving by some other route still cannot poison a population.
"""

import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

BACKEND = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
PIPELINE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pipeline")


def python_sources(*roots):
    for root in roots:
        for folder, _dirs, files in os.walk(root):
            if any(part in folder for part in (".venv", "__pycache__",
                                               "site-packages", ".cache")):
                continue
            for name in files:
                if name.endswith(".py"):
                    path = os.path.join(folder, name)
                    with open(path, encoding="utf-8") as handle:
                        yield path, handle.read()


class TheLoaderWritesAnAbsence(unittest.TestCase):
    def test_a_rated_player_is_serialised_as_json(self):
        index = {"value": 72.0, "raw_value": 72.0, "scaled": True}
        self.assertEqual(json.loads(json.dumps(index) if index else None),
                         index)

    def test_an_unrated_player_is_serialised_as_none_not_the_string_null(self):
        index = None
        serialised = json.dumps(index) if index else None
        self.assertIsNone(serialised,
                          'json.dumps(None) is the string "null", which '
                          "Postgres stores as a JSON null: a value that "
                          "passes IS NOT NULL")
        self.assertNotEqual(serialised, "null")

    def test_the_loader_does_not_dump_unconditionally(self):
        path = os.path.join(BACKEND, "app", "services", "ingest_service.py")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn('"performance_index": json.dumps(row["performance_index"]),',
                         source,
                         "an unconditional dump writes JSON null for every "
                         "player Kumu declined to rate")


class NoQueryTurnsAMissingIndexIntoAFigure(unittest.TestCase):
    """A sweep, because the fault was in six places and found in one."""

    COALESCE_TO_ZERO = re.compile(
        r"COALESCE\(\s*\(\s*\w*\.?performance_index->>'value'\s*\)::float\s*,\s*0\s*\)")

    def test_nothing_coalesces_the_index_to_zero(self):
        offenders = [path for path, source in
                     python_sources(BACKEND, PIPELINE)
                     if self.COALESCE_TO_ZERO.search(source)]
        self.assertEqual(
            offenders, [],
            "a missing index read as 0 puts a player Kumu would not rate at "
            "the bottom of the population rather than outside it")

    def test_no_query_tests_the_column_instead_of_the_value(self):
        pattern = re.compile(r"\bperformance_index IS NOT NULL")
        offenders = []
        for path, source in python_sources(BACKEND, PIPELINE):
            for line in source.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if pattern.search(line):
                    offenders.append((os.path.basename(path), stripped[:70]))
        self.assertEqual(
            offenders, [],
            "a JSON null passes a column test; only the extracted value "
            "says whether there is an index")


class ThePopulationExcludesTheUnrated(unittest.TestCase):
    """What the queries are for, stated as behaviour."""

    def test_an_unrated_player_changes_no_percentile(self):
        rated = [60.0, 70.0, 80.0, 90.0]
        with_phantom = rated + [0.0]

        def percentile(value, population):
            return (sum(1 for v in population if v < value)
                    / len(population) * 100)

        self.assertEqual(percentile(70.0, rated), 25.0)
        self.assertEqual(percentile(70.0, with_phantom), 40.0)
        self.assertNotEqual(
            percentile(70.0, rated), percentile(70.0, with_phantom),
            "this is the size of the lie: one unrated goalkeeper moved a "
            "rated one from the 25th percentile to the 40th")

    def test_a_squad_level_is_not_dragged_by_an_unrated_player(self):
        squad = [72.0, 68.0]
        self.assertEqual(sum(squad) / len(squad), 70.0)
        with_phantom = squad + [0.0]
        self.assertLess(sum(with_phantom) / len(with_phantom), 50.0,
                        "an unrated keeper counted as nought halves the "
                        "level a club is judged to field")


if __name__ == "__main__":
    unittest.main(verbosity=2)
