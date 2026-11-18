"""
Kumü — the queries actually run, against rows of the right shape
=================================================================

    export KUMU_TEST_DATABASE_URL=postgresql://…/kumu_test
    python3 tests/test_queries.py

Every other test file in this directory answers its question without a
database, and that is a virtue right up to the question these ask.
`_query_db` returns [] when it cannot reach one, so a report generated in
a test takes the same path as a report generated against a database that
is down: every percentile declines, every comparison is empty, and
nothing fails. Three queries broken by a search-and-replace passed that
check 101 times and then answered 500 to every request in production.

`test_sql.py` parses the statements, which catches one that is not SQL.
These execute them, which catches one that is valid and wrong — the
wrong column, the wrong join, a scope that leaks another tenant's
players into a percentile.

They skip, loudly, when no test database is configured. See dbfixture.py
for what it refuses to run against.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

import dbfixture  # noqa: E402

try:
    DISPONIBLE = dbfixture.available()
    RAZON = dbfixture.SKIP_REASON
except dbfixture.UnsafeTestDatabase as error:  # pragma: no cover
    # Say which of the two it was. Reporting "not set" to somebody who did
    # set it, to something the fixture refuses to drop tables in, sends
    # them looking for the wrong problem.
    DISPONIBLE = False
    RAZON = "refused: %s" % error


@unittest.skipUnless(DISPONIBLE, RAZON)
class QueriesRunAgainstRealRows(unittest.TestCase):
    """One database for the class: building the schema costs more than
    every test in here put together."""

    @classmethod
    def setUpClass(cls):
        cls._ctx = dbfixture.database()
        cls.db, cls.models = cls._ctx.__enter__()
        from app.services.scouting_report_generator import (
            ScoutingReportGenerator,
        )
        cls.g = ScoutingReportGenerator()
        cls.TENANT = [23, 1]

    @classmethod
    def tearDownClass(cls):
        cls._ctx.__exit__(None, None, None)

    def player(self, pid):
        return self.g.build_player_data(
            self.db.query(self.models.Player).get(pid))

    def club(self, tid):
        t = self.db.query(self.models.Team).get(tid)
        return {
            "id": t.id, "name": t.name, "league": t.league,
            "country": t.country, "budget": t.budget,
            "formation": t.formation,
            "playing_style": t.playing_style or {},
            "requirements": t.requirements or {},
            "spatial_profile": t.spatial_profile or {},
            "expected_index": getattr(t, "expected_index", None),
        }


class ThePeerRankingIsReal(QueriesRunAgainstRealRows):
    """`_positional_percentile` returned None for every test ever written,
    because none of them had a database and it needs five peers."""

    def test_it_returns_a_rank_and_a_count(self):
        got = self.g._positional_percentile(self.player(2533), self.TENANT)
        self.assertIsNotNone(got, "eight strikers are seeded; if this is "
                                  "None the query is not finding them")
        rank, peers = got
        self.assertEqual(peers, 8)
        self.assertGreater(rank, 0)
        self.assertLess(rank, 100)

    def test_the_rank_is_where_the_player_actually_sits(self):
        """71.0 against 58.0, 62.5, 66.0, 69.5, 74.0, 77.5, 81.0 and itself:
        four below out of eight."""
        rank, peers = self.g._positional_percentile(
            self.player(2533), self.TENANT)
        self.assertAlmostEqual(rank, 4 / 8 * 100, places=1)

    def test_a_player_with_no_index_cannot_be_ranked(self):
        self.assertIsNone(
            self.g._positional_percentile(self.player(2602), self.TENANT))

    def test_a_position_with_too_few_peers_declines(self):
        self.assertIsNone(
            self.g._positional_percentile(self.player(2600), self.TENANT),
            "one midfielder is not a population")


class TheScopeHolds(QueriesRunAgainstRealRows):
    """The other tenant's striker sits at 99.0. If he enters this tenant's
    population the percentile moves, and nothing anywhere would say so."""

    def test_another_tenants_player_is_not_a_peer(self):
        _, peers = self.g._positional_percentile(
            self.player(2533), self.TENANT)
        self.assertEqual(peers, 8, "nine means the other tenant leaked in")

    def test_reading_both_tenants_would_have_changed_the_answer(self):
        """A check that cannot fail is not a check."""
        solo = self.g._positional_percentile(self.player(2533), self.TENANT)
        ambos = self.g._positional_percentile(self.player(2533), [23, 1, 99])
        self.assertNotEqual(solo, ambos)

    def test_no_scope_reads_nothing(self):
        self.assertIsNone(self.g._positional_percentile(self.player(2533), []))
        self.assertIsNone(
            self.g._positional_percentile(self.player(2533), None))


class EveryQueryTheReportIssuesExecutes(QueriesRunAgainstRealRows):
    """The whole point. `_query_db` swallows its exceptions and returns [],
    so a broken statement is invisible unless something watches the engine
    while a real report is generated."""

    def consultas_fallidas(self, player_id, team_id):
        """Every statement that raised while this report was generated.

        `handle_error` fires on the engine before the exception travels
        back up, which is the only place to stand: by the time it reaches
        `_query_db` it has been turned into an empty list.
        """
        from sqlalchemy import event

        from app.db.database import engine

        rotas = []

        def fallo(contexto):
            rotas.append((
                " ".join(str(contexto.statement or "").split())[:120],
                str(contexto.original_exception)[:120],
            ))

        event.listen(engine, "handle_error", fallo)
        try:
            self.g.generate_full_report(
                self.player(player_id), self.club(team_id), self.TENANT)
        finally:
            event.remove(engine, "handle_error", fallo)
        return rotas

    def test_the_watcher_sees_a_broken_statement(self):
        """A check that cannot fail is not a check.

        Issues the exact shape that broke production - an alias welded to
        a parenthesis - and confirms the listener catches it.
        """
        from sqlalchemy import event, text

        from app.db.database import engine

        # Named, not a lambda. `event.remove` matches on identity, so
        # registering one callable and removing another leaves the listener
        # attached to a shared engine for the rest of the run.
        rotas = []

        def fallo(contexto):
            rotas.append(str(contexto.original_exception)[:80])

        event.listen(engine, "handle_error", fallo)
        try:
            with engine.connect() as conn:
                try:
                    conn.execute(text(
                        "SELECT 1 FROM players p "
                        "WHERE p.(performance_index->>'value') IS NOT NULL"))
                except Exception:
                    pass
        finally:
            event.remove(engine, "handle_error", fallo)
        self.assertTrue(rotas, "the listener did not fire on invalid SQL, so "
                               "the tests below prove nothing")

    def test_no_statement_raises_for_a_club_with_a_budget(self):
        rotas = self.consultas_fallidas(2533, 7)
        self.assertEqual(rotas, [], "\n".join("%s\n    %s" % r for r in rotas))

    def test_no_statement_raises_for_a_club_without_one(self):
        rotas = self.consultas_fallidas(2533, 188)
        self.assertEqual(rotas, [], "\n".join("%s\n    %s" % r for r in rotas))

    def test_no_statement_raises_for_a_goalkeeper(self):
        rotas = self.consultas_fallidas(2601, 188)
        self.assertEqual(rotas, [], "\n".join("%s\n    %s" % r for r in rotas))

    def test_no_statement_raises_for_a_player_with_nothing(self):
        rotas = self.consultas_fallidas(2602, 188)
        self.assertEqual(rotas, [], "\n".join("%s\n    %s" % r for r in rotas))


class TheReportSaysWhatTheRowsSupport(QueriesRunAgainstRealRows):
    """With a database the headline figures exist, which is the branch
    every offline test leaves untaken."""

    def test_the_sentence_names_the_peer_group_and_its_size(self):
        report = self.g.generate_full_report(
            self.player(2533), self.club(7), self.TENANT)
        said = report["executive_summary"]["executive_statement"]
        self.assertIn("8 same-position players", said)
        self.assertNotIn("Bundesliga", said,
                         "the ranking spans two organisations and no league; "
                         "naming the buyer's competition is the defect this "
                         "whole file exists to keep out")

    def test_the_percentile_is_a_number_now(self):
        report = self.g.generate_full_report(
            self.player(2533), self.club(7), self.TENANT)
        self.assertIsInstance(
            report["executive_summary"]["overall_percentile"], int)

    def test_a_club_with_no_budget_still_declines_to_price_against_it(self):
        report = self.g.generate_full_report(
            self.player(2533), self.club(188), self.TENANT)
        fin = report["risk_assessment"]["risk_factors"]["financial_risk"]
        self.assertIsNone(fin["score"])
        self.assertIn("Brisbane Roar FC", fin["basis"])

    def test_the_goalkeeper_is_still_refused_with_a_database(self):
        report = self.g.generate_full_report(
            self.player(2601), self.club(188), self.TENANT)
        self.assertIsNone(report["executive_summary"]["overall_percentile"])

    def test_every_section_is_present_in_all_four_cases(self):
        from app.services.scouting_report_generator import (
            ScoutingReportGenerator,
        )
        for pid in (2533, 2600, 2601, 2602):
            for tid in (7, 188):
                report = self.g.generate_full_report(
                    self.player(pid), self.club(tid), self.TENANT)
                self.assertEqual(
                    set(ScoutingReportGenerator.SECTIONS) - set(report), set(),
                    "player %d against club %d" % (pid, tid))


class NationalSidesAreNotDestinations(QueriesRunAgainstRealRows):
    def test_the_club_filter_excludes_them(self):
        from app.services import team_service

        clubes = team_service.get_teams(
            self.db, org_ids=[23, 1], limit=100, team_type="club")
        nombres = {t.name for t in clubes}
        self.assertIn("Borussia Dortmund", nombres)
        self.assertNotIn("Belgium", nombres)

    def test_asking_for_them_still_works(self):
        from app.services import team_service

        nacionales = team_service.get_teams(
            self.db, org_ids=[23, 1], limit=100, team_type="national")
        self.assertEqual({t.name for t in nacionales}, {"Belgium"})

    def test_a_null_team_type_counts_as_a_club(self):
        """The column was added after the first rows were written."""
        from app.services import team_service

        self.db.query(self.models.Team).filter_by(id=189).update(
            {"team_type": None})
        self.db.commit()
        nombres = {t.name for t in team_service.get_teams(
            self.db, org_ids=[23, 1], limit=100, team_type="club")}
        self.assertIn("Melbourne Victory FC", nombres)


if __name__ == "__main__":
    unittest.main(verbosity=2)
