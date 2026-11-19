"""
Kumü — a figure nobody measured gets no verdict
================================================

    python3 tests/test_unmeasured.py

Two ways a strength arrived on the page without anybody having observed
anything, both found in the same afternoon, both reported as measurement.

**The stand-in.** `merge_metrics` fills a metric key the source did not
carry with a constant, so the maths downstream has something to divide.
Nothing downstream could tell the constant from a measurement afterwards:
it was ranked against the positional benchmark like any other figure, and
anything at or above the 75th percentile was published under "Statistical
Strengths". A pass difficulty score of 0.6 — Kumü's constant, carried by
no source in the database — sits above the 90th for every position, so
every player Kumü holds was published as elite at it. 1.5 interceptions
is elite for a striker, good for a centre-back, average for a winger: one
constant, three verdicts, none of them about a footballer.

**The tie.** `calculate_percentile` scanned the thresholds from the top
and returned the first the value cleared. That is right while the
thresholds are distinct, and flattery the moment they tie — and they tie
at zero, for every metric most players in a position never record. A
centre-back with no assists cleared a 90th-percentile threshold of 0.0
and was reported "Assists Per 90: Elite (90th percentile)". That figure
was measured correctly. The rank was an artefact of the ties under it.

The second one is the reason the first one is not the whole fix: it
promotes real zeroes, so no amount of care about stand-ins touches it.
"""

import itertools
import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.services.scouting_report_generator import (  # noqa: E402
    ScoutingReportGenerator,
)

LIGA = "A-League Men"

# Distinct thresholds: an ordinary, informative benchmark.
CLAROS = {10: 0.1, 25: 0.3, 50: 0.6, 75: 1.0, 90: 1.8}
# Every threshold at zero: what a benchmark looks like for a metric most
# of the position never records. This is the real shape, not a contrivance.
TODOS_CERO = {10: 0.0, 25: 0.0, 50: 0.0, 75: 0.0, 90: 0.0}
# Tied in the middle, distinct at the bottom.
EMPATE_MEDIO = {10: 0.1, 25: 0.3, 50: 0.3, 75: 1.0, 90: 1.8}


def generador(tabla):
    g = ScoutingReportGenerator()
    g.benchmarks = {"ST": {LIGA: tabla}}
    return g


class ATieIsNotARank(unittest.TestCase):

    def test_a_zero_against_an_all_zero_table_has_no_rank(self):
        g = generador({"assists_per_90": dict(TODOS_CERO)})
        self.assertIsNone(
            g.calculate_percentile(0.0, "assists_per_90", "ST", LIGA))

    def test_the_old_reading_called_that_zero_elite(self):
        """A check that cannot fail is not a check: this reproduces the
        comparison as it stood and shows it reached the 90th."""
        tabla = dict(TODOS_CERO)
        viejo = next(p for p in sorted(tabla, reverse=True) if 0.0 >= tabla[p])
        self.assertEqual(viejo, 90)
        self.assertEqual(
            ScoutingReportGenerator().categorize_performance(viejo).value,
            "Elite")

    def test_a_distinct_table_is_unchanged(self):
        g = generador({"goals_per_90": dict(CLAROS)})
        for valor, esperado in ((2.0, 90), (1.0, 75), (0.6, 50),
                                (0.3, 25), (0.1, 10)):
            self.assertEqual(
                g.calculate_percentile(valor, "goals_per_90", "ST", LIGA),
                esperado, valor)

    def test_below_every_threshold_is_still_the_bottom(self):
        g = generador({"goals_per_90": dict(CLAROS)})
        self.assertEqual(
            g.calculate_percentile(0.0, "goals_per_90", "ST", LIGA), 10)

    def test_a_tie_that_does_not_reach_the_bottom_reads_at_its_floor(self):
        """0.3 clears the 25th and the 50th, which are the same number. It
        is somewhere in that band and nothing says where, so it is read at
        the bottom of it rather than the top."""
        g = generador({"key_passes_per_90": dict(EMPATE_MEDIO)})
        self.assertEqual(
            g.calculate_percentile(0.3, "key_passes_per_90", "ST", LIGA), 25)

    def test_a_value_above_the_tie_is_unaffected(self):
        g = generador({"key_passes_per_90": dict(EMPATE_MEDIO)})
        self.assertEqual(
            g.calculate_percentile(1.0, "key_passes_per_90", "ST", LIGA), 75)

    def test_no_table_still_means_no_rank(self):
        g = generador({})
        self.assertIsNone(
            g.calculate_percentile(1.0, "goals_per_90", "ST", LIGA))

    def test_nothing_a_tie_produces_is_ever_above_its_own_band(self):
        """The property, over every table a benchmark can take: the rank
        returned is never higher than the lowest percentile sharing the
        threshold that was met."""
        for a, b, c in itertools.product((0.0, 0.3), (0.0, 0.3, 1.0),
                                         (0.0, 1.0, 2.0)):
            tabla = {10: 0.0, 25: a, 50: b, 75: c, 90: max(c, 2.0)}
            if sorted(tabla.values()) != list(tabla.values()):
                continue  # not a valid, rising benchmark
            g = generador({"m": tabla})
            for valor in (0.0, 0.3, 1.0, 2.0, 5.0):
                got = g.calculate_percentile(valor, "m", "ST", LIGA)
                if got is None:
                    continue
                alcanzados = [p for p in tabla if valor >= tabla[p]]
                if not alcanzados:
                    continue
                umbral = tabla[max(alcanzados)]
                piso = min(p for p in alcanzados if tabla[p] == umbral)
                self.assertLessEqual(got, piso if piso else got,
                                     (tabla, valor, got))


class AStandInIsNotAMeasurement(unittest.TestCase):

    CLUB = {"id": 188, "name": "Brisbane Roar FC", "league": LIGA,
            "country": "Australia", "budget": None, "playing_style": None,
            "expected_index": None}

    # Only pass completion is real. Everything else in the merged structure
    # is Kumü's constant, which is the ordinary case for this source.
    CRUDAS = {"passing": {"completion_rate": 0.9}}

    def setUp(self):
        self.g = ScoutingReportGenerator()
        self.g.benchmarks = {"ST": {LIGA: {
            # 0.6 is the stand-in for pass_difficulty_score, and it clears
            # the 90th here exactly as it does in production.
            "pass_difficulty_score": {10: 0.1, 25: 0.2, 50: 0.3,
                                      75: 0.4, 90: 0.5},
            "interceptions_per_90": {10: 0.1, 25: 0.3, 50: 0.6,
                                     75: 1.0, 90: 1.4},
            "completion_rate": {10: 0.6, 25: 0.7, 50: 0.75,
                                75: 0.82, 90: 0.88},
        }}}
        self.jugador = {
            "id": 1, "name": "K. Jelacic", "position": "ST", "age": 22,
            "market_value": None, "market_anchor": None,
            "performance_index": {"value": 71.0, "raw_value": 71.0},
            "metrics": ScoutingReportGenerator.merge_metrics(self.CRUDAS),
            "metrics_filled": ScoutingReportGenerator.filled_metrics(
                self.CRUDAS),
            "performance_history": [{"rating": 7.0}] * 3,
        }

    def resumen(self):
        return self.g.generate_statistical_overview(
            dict(self.jugador), dict(self.CLUB))

    def test_the_record_names_exactly_what_the_merge_supplied(self):
        """Derived from the same input by the same rules, so they cannot
        drift apart. Checked over every shape a source can arrive in."""
        formas = (
            None, {}, "no es un dict", {"passing": None},
            {"passing": {"completion_rate": 0.9}},
            {"passing": {"completion_rate": None}},
            {"defensive": {"tackles_per_90": 1.0, "interceptions_per_90": None}},
            {"shooting": {"goals_per_90": 0.3}, "passing": {}},
        )
        for crudas in formas:
            fusionadas = ScoutingReportGenerator.merge_metrics(crudas)
            nombradas = ScoutingReportGenerator.filled_metrics(crudas)
            esperado = {
                cat: sorted(k for k in claves
                            if not isinstance(crudas, dict)
                            or not isinstance((crudas or {}).get(cat), dict)
                            or (crudas[cat]).get(k) is None)
                for cat, claves in fusionadas.items()
            }
            esperado = {c: v for c, v in esperado.items() if v}
            self.assertEqual(nombradas, esperado, crudas)

    def test_a_stand_in_is_not_ranked_at_all(self):
        analisis = self.resumen()["position_specific_analysis"]
        self.assertNotIn("pass_difficulty_score", analisis.get("passing", {}))
        self.assertNotIn("interceptions_per_90", analisis.get("defensive", {}))

    def test_a_measurement_is_still_ranked(self):
        analisis = self.resumen()["position_specific_analysis"]
        self.assertIn("completion_rate", analisis["passing"])
        self.assertEqual(analisis["passing"]["completion_rate"]["percentile"],
                         90)

    def test_no_stand_in_reaches_the_strengths(self):
        fortalezas = " ".join(self.resumen()["statistical_strengths"]).lower()
        self.assertNotIn("pass difficulty", fortalezas)
        self.assertNotIn("interceptions", fortalezas)

    def test_no_stand_in_reaches_the_weaknesses_either(self):
        """Not scored means not scored. A constant below the benchmark is
        no more a weakness than one above it is a strength."""
        debilidades = " ".join(self.resumen()["statistical_weaknesses"]).lower()
        self.assertNotIn("pass difficulty", debilidades)
        self.assertNotIn("interceptions", debilidades)

    def test_the_old_reading_published_it_as_elite(self):
        """The stand-in, scored the way it used to be."""
        self.assertEqual(
            self.g.calculate_percentile(0.6, "pass_difficulty_score",
                                        "ST", LIGA), 90)

    def test_what_was_left_out_is_named(self):
        basis = self.resumen()["metrics_basis"]
        self.assertIsNotNone(basis)
        self.assertIn("pass difficulty score", basis)
        self.assertIn("interceptions per 90", basis)

    def test_a_fully_measured_player_is_told_nothing(self):
        completas = {
            "passing": {"completion_rate": 0.9, "pass_difficulty_score": 0.7,
                        "progressive_passes_per_90": 4.0,
                        "key_passes_per_90": 1.1},
            "shooting": {"shots_per_90": 2.0, "xG_per_shot": 0.1,
                         "conversion_rate": 0.1, "goals_per_90": 0.4,
                         "assists_per_90": 0.2},
            "defensive": {"tackles_per_90": 1.0, "interceptions_per_90": 0.8,
                          "aerial_duels_won": 1.2},
        }
        jugador = dict(self.jugador)
        jugador["metrics"] = ScoutingReportGenerator.merge_metrics(completas)
        jugador["metrics_filled"] = ScoutingReportGenerator.filled_metrics(
            completas)
        self.assertIsNone(
            self.g.generate_statistical_overview(
                jugador, dict(self.CLUB))["metrics_basis"])

    def test_every_section_still_generates(self):
        reporte = self.g.generate_full_report(dict(self.jugador),
                                              dict(self.CLUB))
        self.assertEqual(
            set(ScoutingReportGenerator.SECTIONS) - set(reporte), set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
