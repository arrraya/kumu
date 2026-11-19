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

What the comment did not say is that nothing downstream could tell the
stand-in apart from a measurement afterwards. The merged structure was
scored against the benchmark key by key, and anything at or above the 75th
percentile was published under "Statistical Strengths". 0.6 is above the
90th for every position, so every player in the database was elite at pass
difficulty; 1.5 interceptions is elite for a striker and average for a
winger. The generator now leaves stand-ins out of the ranking and names
them in `metrics_basis`, and this script is how that is checked: a line
marked RELLENO should no longer carry a verdict anybody acts on.

    --benchmarks

scans the reference tables instead, for the second way an invented strength
reached the page. `calculate_percentile` reads a value against rising
thresholds; where several thresholds hold the same number — which is what a
benchmark looks like for a metric most of a position never records — a
player sitting on that number used to clear all of them and be reported at
the top of the band. A centre-back with no assists came out "Elite (90th
percentile)". This lists the tables where that can happen.

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


def umbrales(gen) -> int:
    """Where the thresholds tie low enough that a value on them has no rank."""
    afectados = []
    for posicion, poblaciones in (gen.benchmarks or {}).items():
        for poblacion, metricas in (poblaciones or {}).items():
            for metrica, tabla in (metricas or {}).items():
                if not tabla:
                    continue
                piso = min(tabla)
                empatados = sorted(p for p in tabla
                                   if tabla[p] == tabla[piso])
                if len(empatados) > 1:
                    afectados.append((posicion, poblacion, metrica,
                                      tabla[piso], empatados))
    if not afectados:
        print("Ningún umbral empatado en el piso. Nada que corregir acá.")
        return 0
    print("%-5s %-18s %-26s %-8s %s"
          % ("POS", "POBLACIÓN", "MÉTRICA", "UMBRAL", "PERCENTILES EMPATADOS"))
    for posicion, poblacion, metrica, valor, empatados in sorted(afectados):
        print("%-5s %-18s %-26s %-8s %s"
              % (posicion, poblacion[:18], metrica, valor,
                 ", ".join(str(p) for p in empatados)))
    print()
    print("%d tablas donde un jugador situado en el umbral del piso no tiene "
          "rango que reportar." % len(afectados))
    print("Antes se le reportaba el percentil más alto de la banda. Un "
          "central sin asistencias salía Elite.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", action="append", default=[],
                        help="nombre exacto; repetible")
    parser.add_argument("--all", action="store_true",
                        help="recorre la tabla en vez de la muestra")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--benchmarks", action="store_true",
                        help="revisa los umbrales empatados en vez de los jugadores")
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

    if args.benchmarks:
        return umbrales(gen)

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
                         "   <-- puntuaría como fortaleza" if premiado else ""))
        print()

    print("%d valores rellenos en total; %d de ellos puntuarían en el percentil "
          "75 o más." % (total_rellenos, total_rellenos_premiados))
    if total_rellenos_premiados:
        print("Ninguno llega ya al reporte: el generador deja los rellenos "
              "fuera del ranking y los nombra en `metrics_basis`. Esta línea "
              "mide lo que se evitó, no lo que se publica.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
