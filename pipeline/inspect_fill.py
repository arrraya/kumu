"""
Kumü — which figures in a report were measured, and which were filled
=====================================================================

    source ~/.kumu_env
    python3 pipeline/inspect_fill.py                 # dos jugadores de muestra
    python3 pipeline/inspect_fill.py --name "K. Jelacic"
    python3 pipeline/inspect_fill.py --all --limit 50

`build_player_data` runs every player through `merge_metrics`, which fills
any metric key the source did not carry with a neutral stand-in — 1.5
interceptions per 90, 1.5 tackles, 0.2 goals. The comment above
NEUTRAL_METRICS explains why they exist: the maths downstream could not
handle a missing key.

What the comment does not say is that nothing downstream can tell the
stand-in apart from a measurement afterwards. `generate_statistical_overview`
iterates the merged structure, scores every value against the benchmark, and
`_identify_statistical_strengths` promotes anything at or above the 75th
percentile. A constant that happens to sit above the positional median
therefore arrives on the page as a strength — K. Jelacic, a striker, listed
"Interceptions Per 90: Elite (90th percentile)" on that path.

This script prints, per metric, whether the value came from the source or
from the fill, and what percentile it scored. It answers the question the
report itself cannot: how much of this verdict is measurement.

Read-only. It opens one connection and runs one SELECT.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from sqlalchemy import create_engine, text  # noqa: E402

from app.services.scouting_report_generator import (  # noqa: E402
    ScoutingReportGenerator,
)

MUESTRA = ("K. Jelacic", "P. Kikianis")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", action="append", default=[],
                        help="nombre exacto; repetible")
    parser.add_argument("--all", action="store_true",
                        help="recorre la tabla en vez de la muestra")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--league", default=None,
                        help="liga contra la que se calcula el percentil")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Falta DATABASE_URL. Corre `source ~/.kumu_env` primero.",
              file=sys.stderr)
        return 2

    gen = ScoutingReportGenerator()
    engine = create_engine(url)

    if args.all:
        sql = "SELECT id, name, position, metrics FROM players ORDER BY id LIMIT :n"
        params = {"n": args.limit}
    else:
        nombres = args.name or list(MUESTRA)
        sql = ("SELECT id, name, position, metrics FROM players "
               "WHERE name = ANY(:nombres) ORDER BY name")
        params = {"nombres": nombres}

    with engine.connect() as conn:
        filas = conn.execute(text(sql), params).fetchall()

    if not filas:
        print("Ningún jugador con ese nombre.")
        return 1

    total_rellenos = 0
    total_rellenos_premiados = 0

    for pid, nombre, posicion, crudo in filas:
        crudo = crudo or {}
        fusionado = ScoutingReportGenerator.merge_metrics(crudo)
        poblacion = gen.percentile_population(posicion, args.league)
        print("=== %s · %s · id %s ===" % (nombre, posicion or "sin posición", pid))
        print("    población de referencia: %s" % (poblacion or "ninguna"))
        for categoria in sorted(fusionado):
            for metrica in sorted(fusionado[categoria]):
                valor = fusionado[categoria][metrica]
                real = (crudo.get(categoria) or {}).get(metrica)
                medido = real is not None
                pct = gen.calculate_percentile(valor, metrica, posicion, args.league)
                veredicto = (gen.categorize_performance(pct).value
                             if pct is not None else "sin referencia")
                marca = "medido" if medido else "RELLENO"
                premiado = (not medido) and pct is not None and pct >= 75
                if not medido:
                    total_rellenos += 1
                if premiado:
                    total_rellenos_premiados += 1
                print("    %-8s %-12s %-26s %-8s  p%-5s %s%s"
                      % (marca, categoria, metrica, valor,
                         pct if pct is not None else "—", veredicto,
                         "   <-- se publica como fortaleza" if premiado else ""))
        print()

    print("%d valores rellenos en total; %d de ellos puntúan en el percentil 75 "
          "o más y entran a 'Statistical Strengths'."
          % (total_rellenos, total_rellenos_premiados))
    if total_rellenos_premiados:
        print("Cada uno de esos es una fortaleza que nadie midió, pesando sobre "
              "una recomendación de fichaje.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
