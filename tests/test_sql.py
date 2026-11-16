"""
Kumü — every query in the codebase has to parse as PostgreSQL
==============================================================

    python3 tests/test_sql.py

A blind search-and-replace across six queries turned
`p.performance_index IS NOT NULL` into
`p.(performance_index->>'value') IS NOT NULL` in three of them: an alias
welded to a parenthesis, which is not SQL. The report endpoint answered
500 to every request, and the browser reported a CORS failure on top,
because a 500 carries no CORS headers.

What let it through was not the replace. It was that the reports were
verified without a database. `_query_db` fails softly when it cannot
reach one, so all 101 reports generated cleanly in a test run and none
of the changed SQL ever executed. The queries were read, and reading is
what missed three of them.

So this parses every SQL string in the backend with libpg_query, the
parser PostgreSQL itself uses. It catches syntax, not meaning: a query
that parses can still ask the wrong question. But it cannot be the
wrong shape.

Needs `pglast`. Without it the tests skip rather than pass, because a
check that silently does nothing is worse than no check.
"""

import os
import re
import sys
import unittest

try:
    import pglast
except ImportError:  # pragma: no cover
    pglast = None

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOTS = [os.path.join(HERE, "backend"), os.path.join(HERE, "pipeline")]
SKIP_DIRS = (".venv", "__pycache__", "site-packages", ".cache", "node_modules")

# A SQL string has shape, not just a first word. Asking only for the verb
# collected every docstring beginning "Create the squad membership
# relation" or "Update a team's transfer budget" - English sentences that
# open on a SQL keyword - and the parser dutifully rejected them, which
# said nothing about the code. The second keyword is what separates a
# query from a sentence.
QUERY = re.compile(
    r"^\s*(?:"
    r"select\b[\s\S]*\bfrom\b"
    r"|insert\s+into\b"
    r"|update\b[\s\S]*\bset\b"
    r"|delete\s+from\b"
    r"|with\b[\s\S]*\bas\s*\("
    r"|create\s+(?:unique\s+)?(?:table|index|view)\b"
    r")", re.I)

# Placeholders Postgres never sees: SQLAlchemy binds them first.
NAMED = re.compile(r"(?<![:\w]):([a-z_][a-z0-9_]*)", re.I)
# `IN :ids` becomes `IN (...)`, which the parser needs as a real list.
IN_PARAM = re.compile(r"\bIN\s+:[a-z_][a-z0-9_]*", re.I)


def sql_strings():
    """Every triple-quoted string in the tree that looks like a query."""
    for root in ROOTS:
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            if any(part in folder for part in SKIP_DIRS):
                continue
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8") as handle:
                    source = handle.read()
                for block in re.findall(r'"""(.*?)"""', source, re.S):
                    text = block.strip()
                    if QUERY.match(text):
                        yield path, text


def literal_and_templated():
    """Split the queries into the ones a parser can read and the rest.

    A query assembled with f-string holes - `{where}`, `ORDER BY {column}
    {direction}` - is not a query until it is built, and no single
    substitution serves a hole that is sometimes a clause and sometimes a
    column. Those are set aside rather than guessed at, and counted, so
    the gap is a number somebody can see instead of silence.
    """
    literal, templated = [], []
    for path, query in sql_strings():
        (templated if "{" in query else literal).append((path, query))
    return literal, templated


def bindable(query):
    """The query with its placeholders replaced by things Postgres reads."""
    query = IN_PARAM.sub("IN (1, 2)", query)
    return NAMED.sub("1", query)


@unittest.skipIf(pglast is None, "pglast not installed")
class EveryQueryParses(unittest.TestCase):
    def test_the_parser_rejects_what_broke_production(self):
        """A check that cannot fail is not a check."""
        with self.assertRaises(Exception):
            pglast.parse_sql(
                "SELECT 1 FROM players p "
                "WHERE p.(performance_index->>'value') IS NOT NULL")

    def test_the_parser_accepts_the_corrected_form(self):
        pglast.parse_sql(
            "SELECT 1 FROM players p "
            "WHERE (p.performance_index->>'value') IS NOT NULL")

    def test_every_query_in_the_backend_is_valid_postgres(self):
        literal, _templated = literal_and_templated()
        found, broken = 0, []
        for path, query in literal:
            found += 1
            try:
                pglast.parse_sql(bindable(query))
            except Exception as error:  # noqa: BLE001
                broken.append(
                    (os.path.relpath(path, HERE), str(error)[:90],
                     " ".join(query.split())[:90]))
        self.assertGreater(found, 5,
                           "no queries found at all; the collector is "
                           "looking in the wrong place and this test is "
                           "passing on nothing")
        self.assertEqual(
            broken, [],
            "\n" + "\n".join(f"  {p}\n    {e}\n    {q}" for p, e, q in broken))

    def test_no_alias_is_welded_to_a_parenthesis(self):
        """The exact shape, named, so a reader knows what to look for."""
        offenders = []
        for path, query in sql_strings():
            if re.search(r"\b[a-z]\.\(", query):
                offenders.append(os.path.relpath(path, HERE))
        self.assertEqual(offenders, [],
                         "`p.(expr)` is not SQL; it is `(p.expr)`")


    def test_the_templates_left_unchecked_are_named(self):
        """The gap, stated. A skipped query should not be a silent one."""
        _literal, templated = literal_and_templated()
        files = sorted({os.path.relpath(p, HERE) for p, _ in templated})
        self.assertLessEqual(
            len(templated), 4,
            "more queries are being assembled from f-strings than this "
            f"check can read: {files}. Each one is unparsed.")


class TheCollectorFindsQueries(unittest.TestCase):
    """If this file stops finding the SQL, it stops testing anything."""

    def test_it_finds_the_queries_this_session_changed(self):
        paths = {os.path.basename(p) for p, _ in sql_strings()}
        for expected in ("scouting_report_generator.py", "ingest_service.py"):
            self.assertIn(expected, paths,
                          f"{expected} holds SQL and was not collected")

    def test_it_does_not_collect_docstrings(self):
        for path, query in sql_strings():
            self.assertTrue(
                QUERY.match(query),
                f"{path} contributed prose, which a parser will reject for "
                f"reasons that say nothing about the code")

    def test_placeholders_become_something_postgres_reads(self):
        self.assertEqual(bindable("SELECT :a"), "SELECT 1")
        self.assertEqual(bindable("WHERE id IN :ids"), "WHERE id IN (1, 2)")
        self.assertEqual(bindable("WHERE a->>'b' = 'c'"),
                         "WHERE a->>'b' = 'c'",
                         "the ->> operator must survive placeholder "
                         "substitution, since it is what these queries are "
                         "built on")


if __name__ == "__main__":
    unittest.main(verbosity=2)
