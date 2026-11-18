"""
Kumü — a percentile belongs to the population that produced it
===============================================================

    python3 tests/test_populations.py

K. Jelacic plays in the A-League. Assessed for Borussia Dortmund, his
report opened with "Statistical analysis places the player in the 70th
percentile for their position in Bundesliga." The 70 was sound. The
Bundesliga was not: `_positional_percentile` ranks against every
same-position player Kumü holds, with no league filter anywhere in the
query. The sentence named the club in the dropdown and a reader who went
to check the claim against the Bundesliga would have found nothing to
check it against.

Two more defaults of the same family sat underneath it. A missing
benchmark returned 50, which is not a neutral value but the assertion
that a player is exactly average, and it reached the page as "50th
percentile · Average performance" for metrics Kumü held no reference
for. And when the club's own league had no benchmark, the code fell back
to `list(populations)[0]` — whichever key happened to come back first —
and printed the result under the club's league name regardless.

These tests need no database. Every question here is about which
population a figure is attributed to, and that is decided before any row
is read.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.services.scouting_report_generator import (  # noqa: E402
    ScoutingReportGenerator,
)

# A club in one competition, a player who has never played in it. The whole
# defect lived in the gap between those two facts.
GERMAN_CLUB = {
    "id": 7,
    "name": "Borussia Dortmund",
    "league": "Bundesliga",
    "country": "Germany",
    "budget": 350_000_000.0,
    "formation": "4-2-3-1",
    "playing_style": {"possession": 0.58, "pressing_intensity": 0.72},
    "expected_index": 78.0,
}

AUSTRALIAN_CLUB = dict(GERMAN_CLUB, id=188, name="Brisbane Roar FC",
                       league="A-League Men", country="Australia",
                       budget=None, playing_style=None, expected_index=None)


def player(**overrides):
    base = {
        "id": 2533,
        "name": "K. Jelacic",
        "position": "ST",
        "age": 22,
        "current_team": "Brisbane Roar FC",
        "current_league": "A-League Men",
        "market_value": None,
        "match_score": 77.9,
        "performance_index": {"value": 71.0, "raw_value": 71.0, "trend": 0.1,
                              "volatility": 0.12, "confidence": 0.88,
                              "scaled": True},
        "metrics": {
            "passing": {"completion_rate": 0.78, "key_passes_per_90": 1.2},
            "shooting": {"shots_per_90": 3.1, "goals_per_90": 0.96},
            "defensive": {"tackles_per_90": 0.96},
        },
        "performance_history": [
            {"match_id": str(i), "rating": 7.0 + i * 0.3, "minutes": 90.0}
            for i in range(4)
        ],
    }
    base.update(overrides)
    return base


class TheHeadlineSentenceNamesItsPopulation(unittest.TestCase):
    """The sentence a reader reads first, and the one that was wrong."""

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def statement(self, p, t):
        return self.g.generate_executive_summary(p, t)["executive_statement"]

    def test_it_does_not_name_the_assessing_clubs_league(self):
        said = self.statement(player(), dict(GERMAN_CLUB))
        self.assertNotIn(
            "Bundesliga", said,
            "the ranking has no league filter, so no league may be named as "
            "the population it came from")

    def test_it_does_not_name_the_players_league_either(self):
        """Tempting, and still false.

        The obvious repair was to swap the club's league for the player's.
        It would have read correctly for Jelacic and been just as invented:
        the query selects every same-position player in the readable
        organisations, which is not the A-League and not any league.
        """
        said = self.statement(player(), dict(AUSTRALIAN_CLUB))
        self.assertNotIn("A-League", said)

    def test_it_names_the_club_being_assessed_for(self):
        """The club still belongs in the sentence — as the buyer, not as
        the population."""
        self.assertIn("Borussia Dortmund",
                      self.statement(player(), dict(GERMAN_CLUB)))

    def test_with_no_ranking_and_no_benchmark_it_states_no_percentile(self):
        """Offline there is no peer query and no ST benchmark, which is
        exactly the case that used to print 50."""
        said = self.statement(player(), dict(GERMAN_CLUB))
        self.assertIn("No percentile is stated", said)

    def test_a_metric_average_is_never_called_a_rank(self):
        """CAM has a benchmark, so the fallback branch is reachable."""
        said = self.statement(player(position="CAM"), dict(GERMAN_CLUB))
        self.assertIn("not a rank among other players", said)
        self.assertIn("Premier League", said,
                      "the substituted population has to be named, or the "
                      "reader assumes the club's own league")


class TheSummaryReportsWhatItHas(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_an_unrankable_player_has_no_percentile_at_all(self):
        summary = self.g.generate_executive_summary(player(), dict(GERMAN_CLUB))
        self.assertIsNone(summary["overall_percentile"])
        self.assertIsNone(summary["metric_percentile_average"])

    def test_the_basis_says_which_of_the_three_cases_it_is(self):
        summary = self.g.generate_executive_summary(player(), dict(GERMAN_CLUB))
        self.assertIn("not established", summary["percentile_basis"])

    def test_findings_do_not_contrast_two_absences(self):
        """"Rates higher overall than the individual metrics suggest" was
        drawn between two numbers that were both the same default."""
        summary = self.g.generate_executive_summary(player(), dict(GERMAN_CLUB))
        texts = " ".join(f.get("text", "") for f in summary["key_findings"])
        self.assertNotIn("individual metrics", texts.lower())


class AMissingBenchmarkIsNotAnAveragePlayer(unittest.TestCase):
    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_it_returns_none_rather_than_fifty(self):
        self.assertIsNone(
            self.g.calculate_percentile(0.78, "pass_completion", "ST",
                                        "Bundesliga"),
            "50 is a claim about the player, not the absence of one")

    def test_a_metric_with_no_benchmark_gets_no_verdict(self):
        stats = self.g.generate_statistical_overview(player(),
                                                     dict(GERMAN_CLUB))
        for category in stats["position_specific_analysis"].values():
            for metric, analysis in category.items():
                if analysis["percentile"] is None:
                    self.assertIsNone(
                        analysis["performance"],
                        f"{metric} kept its verdict after losing the "
                        f"percentile that justified it")

    def test_the_value_itself_survives(self):
        """Losing the comparison must not lose the measurement."""
        stats = self.g.generate_statistical_overview(player(),
                                                     dict(GERMAN_CLUB))
        shooting = stats["position_specific_analysis"]["shooting"]
        self.assertEqual(shooting["goals_per_90"]["value"], 0.96)

    def test_an_unbenchmarked_metric_is_neither_strength_nor_weakness(self):
        stats = self.g.generate_statistical_overview(player(),
                                                     dict(GERMAN_CLUB))
        self.assertEqual(stats["statistical_strengths"], [])
        self.assertEqual(stats["statistical_weaknesses"], [])

    def test_the_section_names_its_population_once(self):
        stats = self.g.generate_statistical_overview(player(position="CAM"),
                                                     dict(GERMAN_CLUB))
        self.assertEqual(stats["percentile_population"], "Premier League")
        self.assertIn("Premier League", stats["percentile_basis"])


class TheSubstitutedPopulationIsStable(unittest.TestCase):
    """`list(populations)[0]` followed insertion order, which came from the
    order the benchmark rows were read in. The same player could be ranked
    against a different population on two consecutive loads."""

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_it_is_chosen_deterministically(self):
        self.g.benchmarks["XX"] = {"Zeta": {}, "Alpha": {}, "Mu": {}}
        first = self.g.percentile_population("XX", "Bundesliga")
        self.g.benchmarks["XX"] = {"Mu": {}, "Alpha": {}, "Zeta": {}}
        self.assertEqual(first, self.g.percentile_population("XX", "Bundesliga"))

    def test_the_clubs_own_league_wins_when_it_exists(self):
        self.assertEqual(
            self.g.percentile_population("CAM", "Premier League"),
            "Premier League")

    def test_no_population_at_all_is_none(self):
        self.assertIsNone(self.g.percentile_population("ST", "Bundesliga"))


class AnUnknownBudgetIsNotLowRisk(unittest.TestCase):
    """The safest-looking card on the page, produced by knowing nothing."""

    def setUp(self):
        self.g = ScoutingReportGenerator()
        self.p = player()

    def test_it_is_not_assessed(self):
        risk = self.g._assess_financial_risk(self.p, dict(AUSTRALIAN_CLUB))
        self.assertIsNone(risk["score"])
        self.assertIsNone(risk["level"])

    def test_it_says_which_club_and_why(self):
        risk = self.g._assess_financial_risk(self.p, dict(AUSTRALIAN_CLUB))
        self.assertIn("Brisbane Roar FC", risk["basis"])
        self.assertIn("matches, not finances", risk["basis"])

    def test_a_known_budget_still_scores(self):
        risk = self.g._assess_financial_risk(self.p, dict(GERMAN_CLUB))
        self.assertIsInstance(risk["score"], (int, float))
        self.assertIn("declared budget", risk["basis"])

    def test_it_is_excluded_from_the_overall_figure(self):
        assessment = self.g.generate_risk_assessment(self.p,
                                                     dict(AUSTRALIAN_CLUB))
        self.assertNotIn("financial", assessment["risk_basis"],
                         "a risk that was not assessed must not be listed "
                         "among the ones that were")

    def test_knowing_less_does_not_make_the_signing_look_safer(self):
        """The property the whole pass is about.

        With `else 0` an unknown budget scored zero and dragged the mean
        down, so the less Kumü knew about a club the safer the signing
        looked.

        The first version of this test compared Brisbane Roar against
        Borussia Dortmund and failed: 15.25 against 16.28, with the unknown
        club still lower. It was measuring the wrong thing. The two clubs
        differ in league, country and declared style, so adaptation risk
        alone moved more than the budget did. Holding the club fixed and
        removing only the budget asks the question the defect was about.
        """
        rich = dict(GERMAN_CLUB)
        same_club_no_budget = dict(GERMAN_CLUB, budget=None)

        known = self.g.generate_risk_assessment(self.p, rich)
        unknown = self.g.generate_risk_assessment(self.p, same_club_no_budget)

        self.assertIsNotNone(known["risk_score"])
        self.assertIsNotNone(unknown["risk_score"])
        self.assertGreaterEqual(
            unknown["risk_score"], known["risk_score"],
            "removing the budget lowered the overall risk, which is the "
            "absence paying a dividend")

    def test_the_overall_figure_says_how_many_it_averaged(self):
        assessment = self.g.generate_risk_assessment(
            self.p, dict(GERMAN_CLUB, budget=None))
        self.assertIn("4 of 5", assessment["risk_basis"])


class TheCaveatsDescribeThisReport(unittest.TestCase):
    """Four sentences of fixed prose, printed whatever the page contained.
    One of them said age was not carried, directly above "Age 22"."""

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def notes(self, p, t):
        return " ".join(self.g._source_notes(p, t))

    def test_no_age_caveat_when_the_age_is_known(self):
        said = self.notes(player(age=22), dict(GERMAN_CLUB))
        self.assertNotIn("Age is not carried", said)

    def test_an_age_caveat_when_it_is_not(self):
        said = self.notes(player(age=None), dict(GERMAN_CLUB))
        self.assertIn("Age is not carried", said)

    def test_the_assumed_age_counts_as_absent(self):
        """26 is what the pipeline filled in, not what a source recorded."""
        said = self.notes(player(age=self.g.ASSUMED_AGE), dict(GERMAN_CLUB))
        self.assertIn("Age is not carried", said)

    def test_a_budget_caveat_only_for_the_club_that_lacks_one(self):
        self.assertIn("carries no budget",
                      self.notes(player(), dict(AUSTRALIAN_CLUB)))
        self.assertNotIn("carries no budget",
                         self.notes(player(), dict(GERMAN_CLUB)))

    def test_no_style_caveat_for_a_club_that_declares_none(self):
        self.assertNotIn("declared judgements",
                         self.notes(player(), dict(AUSTRALIAN_CLUB)))

    def test_the_report_carries_them(self):
        report = self.g.generate_full_report(player(), dict(AUSTRALIAN_CLUB))
        self.assertIn("source_notes", report)
        self.assertIsInstance(report["source_notes"], list)

    def test_the_page_never_contradicts_itself_about_age(self):
        """The defect as a reader met it: two sentences, one page."""
        report = self.g.generate_full_report(player(age=22),
                                             dict(GERMAN_CLUB))
        findings = " ".join(
            f.get("text", "")
            for f in report["executive_summary"]["key_findings"])
        notes = " ".join(report["source_notes"])
        if "Age 22" in findings:
            self.assertNotIn("Age is not carried", notes)


class EverySectionStillGenerates(unittest.TestCase):
    """None travels further than a number did. Each of these used to be a
    place where 50 or 0 stood in for an answer."""

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_for_a_club_with_a_budget(self):
        report = self.g.generate_full_report(player(), dict(GERMAN_CLUB))
        self.assertEqual(
            set(ScoutingReportGenerator.SECTIONS) - set(report), set())

    def test_for_a_club_without_one(self):
        report = self.g.generate_full_report(player(), dict(AUSTRALIAN_CLUB))
        self.assertEqual(
            set(ScoutingReportGenerator.SECTIONS) - set(report), set())

    def test_for_a_position_with_a_benchmark(self):
        report = self.g.generate_full_report(player(position="CAM"),
                                             dict(GERMAN_CLUB))
        self.assertEqual(
            set(ScoutingReportGenerator.SECTIONS) - set(report), set())

    def test_for_a_player_with_no_index_and_no_price(self):
        report = self.g.generate_full_report(
            player(performance_index=None, market_value=None),
            dict(AUSTRALIAN_CLUB))
        self.assertEqual(
            set(ScoutingReportGenerator.SECTIONS) - set(report), set())


class TheVerifierObjectsToClaimsNotWords(unittest.TestCase):
    """The checker that watches the reports needs watching too.

    Its first run objected 24 times — three goalkeepers against eight
    clubs — to reports that were right. Kumü declines to rate a keeper
    the source carries no goalkeeping for, and the refusal ends "supply
    those three and the rating, the percentile and the recommendation all
    start working". The checker searched for the word and found it. What
    makes a percentile a claim is a figure in front of it.
    """

    def setUp(self):
        sys.path.insert(0, os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "pipeline"))
        import verify_reports
        self.claim = verify_reports.PERCENTILE_CLAIM

    def test_a_refusal_that_mentions_percentiles_is_not_a_claim(self):
        self.assertIsNone(self.claim.search(
            "Kumü does not rate this goalkeeper: the source carries no "
            "goalkeeping. Supply those three and the rating, the percentile "
            "and the recommendation all start working."))

    def test_a_stated_figure_is(self):
        self.assertIsNotNone(self.claim.search(
            "places the player in the 70th percentile among the 53 "
            "same-position players Kumü holds"))

    def test_the_sentence_that_states_nothing_is_not(self):
        self.assertIsNone(self.claim.search(
            "No percentile is stated: Kumü holds neither a peer group for "
            "this position nor a reference population."))

    def test_the_old_bundesliga_sentence_would_still_be_caught(self):
        """Check 1 is about the league; this one is about the figure. The
        sentence that started all of this trips both."""
        said = ("Statistical analysis places the player in the 70th "
                "percentile for their position in Bundesliga.")
        self.assertIsNotNone(self.claim.search(said))
        self.assertIn("Bundesliga", said)


if __name__ == "__main__":
    unittest.main(verbosity=2)
