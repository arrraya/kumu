"""
Kumü — what the generator writes, the response model must declare
==================================================================

    python3 tests/test_response.py

A FastAPI `response_model` is a filter, not a check. Pydantic keeps the
fields the model declares and drops the rest in silence: no error, no log,
no failing test. The generator computes a field, the endpoint returns it,
and the browser never sees it.

This has now happened seven times. The seventh was found while fixing the
sixth: `ScoutingReport` had just been given `basis` and `source_notes`,
and one class below it `StatisticalOverview` was still dropping
`percentile_basis` — the sentence naming the population every percentile
in that section is measured against. A sweep found ten such fields across
five sections, and four of the ten were that section's own provenance
line. The one thing this product exists to say was the thing most often
deleted on the way out.

The fix is not a longer schema. It is this file: the generator's own
output decides what must be declared, so the two cannot drift apart
without something going red. A key added to a section tomorrow fails here
tomorrow, not in a screenshot three weeks later.

The grid matters. Several of the ten appear only for a particular shape of
player — `athletic_scores_basis` only where the source carries no tracking
data, `peer_group` only where a style comparison was attempted. A single
fixture tests a single shape, which is how ten fields stayed invisible
through five rounds of review.
"""

import itertools
import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.schemas import report as schemas  # noqa: E402
from app.services.scouting_report_generator import (  # noqa: E402
    ScoutingReportGenerator,
)

# Each section of the report and the model that has to let it through.
MODELOS = {
    "report_metadata": schemas.ReportMetadata,
    "executive_summary": schemas.ExecutiveSummary,
    "statistical_overview": schemas.StatisticalOverview,
    "tactical_analysis": schemas.TacticalAnalysis,
    "physical_profile": schemas.PhysicalProfile,
    "market_analysis": schemas.MarketAnalysis,
    "comparison_analysis": schemas.ComparisonAnalysis,
    "risk_assessment": schemas.RiskAssessment,
    "negotiation_strategy": schemas.NegotiationStrategy,
}

CLUB_RICO = {
    "id": 7, "name": "Borussia Dortmund", "league": "Bundesliga",
    "country": "Germany", "budget": 350_000_000.0,
    "playing_style": {"possession": 0.58, "pressing_intensity": 0.72},
    "expected_index": 78.0,
}
CLUB_DESNUDO = {
    "id": 188, "name": "Brisbane Roar FC", "league": "A-League Men",
    "country": "Australia", "budget": None, "playing_style": None,
    "expected_index": None,
}

METRICAS_RICAS = {
    "passing": {"completion_rate": 0.78, "progressive_passes_per_90": 6.2,
                "key_passes_per_90": 1.4, "pass_difficulty_score": 0.71},
    "shooting": {"goals_per_90": 0.96, "assists_per_90": 0.31,
                 "shots_per_90": 3.1, "xG_per_shot": 0.14},
    "defensive": {"tackles_per_90": 0.96, "interceptions_per_90": 0.6,
                  "aerial_duels_won_per_90": 2.2, "blocks_per_90": 0.4},
}
METRICAS_POBRES = {"passing": {"completion_rate": 0.78}}

ANCLA = {"value": 2_500_000, "source": "curated", "samples": 0,
         "market": "a_league"}


def jugador(posicion="ST", edad=22, metricas=None, historial=3, ancla=ANCLA,
            liga="A-League Men"):
    return {
        "id": 2533, "name": "K. Jelacic", "position": posicion, "age": edad,
        "nationality": "Australia", "current_team": "Brisbane Roar FC",
        "current_league": liga,
        "market_value": None,
        "market_anchor": ancla,
        "performance_index": {"value": 71.0, "raw_value": 71.0,
                              "scaled": True},
        "metrics": METRICAS_RICAS if metricas is None else metricas,
        "performance_history": [{"rating": 7.0 + i * 0.1}
                                for i in range(historial)],
    }


def rejilla():
    """Every shape that changes which keys a section produces."""
    for posicion, edad, metricas, historial, ancla, club in itertools.product(
            ("ST", "CB", "GK"),
            (22, None),
            (None, METRICAS_POBRES, {}),
            (0, 3, 6),
            (ANCLA, None),
            (CLUB_RICO, CLUB_DESNUDO)):
        yield (jugador(posicion=posicion, edad=edad, metricas=metricas,
                       historial=historial, ancla=ancla),
               dict(club))


def etiqueta(p, c):
    return ("position=%s age=%s metrics=%s history=%d anchor=%s club=%s"
            % (p["position"], p["age"],
               "rich" if p["metrics"] is METRICAS_RICAS
               else ("sparse" if p["metrics"] else "none"),
               len(p["performance_history"]),
               "yes" if p["market_anchor"] else "no", c["name"]))


class NothingTheGeneratorWritesIsDropped(unittest.TestCase):
    """The set difference is the test. Listing the fields by hand is how
    ten of them stayed hidden."""

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def test_every_section_key_is_declared(self):
        huerfanas = {}
        for jugador_data, club in rejilla():
            reporte = self.g.generate_full_report(jugador_data, club)
            for seccion, modelo in MODELOS.items():
                producidas = set(reporte.get(seccion) or {})
                sobrantes = producidas - set(modelo.model_fields)
                for clave in sobrantes:
                    huerfanas.setdefault("%s.%s" % (seccion, clave),
                                         etiqueta(jugador_data, club))
        self.assertEqual(
            huerfanas, {},
            "the generator produces these and the response model drops them "
            "in silence; declare each one in app/schemas/report.py: %s"
            % huerfanas)

    def test_every_envelope_key_is_declared(self):
        declaradas = set(schemas.ScoutingReport.model_fields)
        for jugador_data, club in rejilla():
            reporte = self.g.generate_full_report(jugador_data, club)
            self.assertEqual(
                set(reporte) - declaradas, set(), etiqueta(jugador_data, club))

    def test_every_declared_section_is_produced(self):
        """The other direction: a section the model requires and the
        generator stopped writing would fail at the endpoint, not here."""
        for jugador_data, club in rejilla():
            reporte = self.g.generate_full_report(jugador_data, club)
            for seccion in MODELOS:
                self.assertIn(seccion, reporte, etiqueta(jugador_data, club))


class TheRoundTripKeepsTheProvenance(unittest.TestCase):
    """Set arithmetic proves the fields are declared. This proves they
    survive the trip the endpoint actually makes."""

    PROVENIENCIA = (
        ("statistical_overview", "percentile_basis"),
        ("tactical_analysis", "style_basis"),
        ("physical_profile", "athletic_scores_basis"),
        ("risk_assessment", "risk_basis"),
    )

    def setUp(self):
        self.g = ScoutingReportGenerator()

    def _validado(self, jugador_data, club):
        reporte = self.g.generate_full_report(jugador_data, club)
        return reporte, schemas.ScoutingReport(**reporte).model_dump()

    def test_a_basis_the_generator_wrote_arrives_at_the_other_end(self):
        for jugador_data, club in rejilla():
            crudo, validado = self._validado(jugador_data, club)
            for seccion, clave in self.PROVENIENCIA:
                if (crudo.get(seccion) or {}).get(clave) is None:
                    continue
                self.assertEqual(
                    validado[seccion][clave], crudo[seccion][clave],
                    "%s.%s was computed and lost in validation (%s)"
                    % (seccion, clave, etiqueta(jugador_data, club)))

    def test_the_envelope_basis_survives(self):
        """The sixth occurrence, kept as a test so it cannot be the eighth."""
        for jugador_data, club in rejilla():
            crudo, validado = self._validado(jugador_data, club)
            self.assertEqual(validado.get("basis"), crudo.get("basis"))
            self.assertEqual(validado.get("source_notes"),
                             crudo.get("source_notes"))

    def test_at_least_one_shape_in_the_grid_carries_each_basis(self):
        """A guard on the guard: if every fixture happened to omit a basis,
        the loop above would pass by never looking at anything."""
        vistos = set()
        for jugador_data, club in rejilla():
            reporte = self.g.generate_full_report(jugador_data, club)
            for seccion, clave in self.PROVENIENCIA:
                if (reporte.get(seccion) or {}).get(clave) is not None:
                    vistos.add((seccion, clave))
        self.assertEqual(set(self.PROVENIENCIA) - vistos, set(),
                         "no fixture in the grid exercises these")


if __name__ == "__main__":
    unittest.main(verbosity=2)
