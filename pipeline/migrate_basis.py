"""
Kumü — record what a report was computed against
=================================================

    source ~/.kumu_env
    python3 pipeline/migrate_basis.py            # muestra qué haría
    python3 pipeline/migrate_basis.py --i-mean-it

Adds `scouting_reports.basis` and leaves every existing row NULL.

WHY NULL AND NOT A GUESS
------------------------
A report's figures rest on two things it never wrote down: the reference
population that scaled the index, and the market anchor that turned that
index into money. Both moved. The public organisation went from 307 to
335 players the day twenty-eight goalkeepers were loaded, and every index
issued before it kept its digits and lost its meaning. The A-League had
no anchor of its own until the 18th, so its players were priced on the
World Cup scale — K. Jelacic at €11.2M in a league whose record transfers
are around €3M.

The reports written before those changes cannot have their basis
reconstructed. The population that scaled them is gone, and the anchor
they used is not recorded anywhere. Filling the column with today's
values would be worse than leaving it empty: it would state, in Kumü's
own voice, that an old figure was computed against a yardstick it never
saw.

So the column goes in empty, and a report with no basis says so. That is
the same answer this codebase gives everywhere else: an absence is
declared, not filled.
"""

import argparse
import os
import sys

from sqlalchemy import create_engine, text

PREGUNTAS = [
    ("reportes en total", "SELECT count(*) FROM scouting_reports"),
    ("con basis ya escrita",
     "SELECT count(*) FROM scouting_reports WHERE basis IS NOT NULL"),
    ("sobre jugadores de un cliente",
     """SELECT count(*) FROM scouting_reports r
        JOIN players p ON p.id = r.player_id
        JOIN organizations o ON o.id = p.organization_id
        WHERE o.kind = 'client'"""),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--i-mean-it", action="store_true",
                        help="Aplica el ALTER TABLE; sin esto sólo informa")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Falta DATABASE_URL. Corre `source ~/.kumu_env` primero.",
              file=sys.stderr)
        return 2

    engine = create_engine(url)
    with engine.connect() as conn:
        existe = conn.execute(text("""
            SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'scouting_reports' AND column_name = 'basis'
        """)).scalar()
        print("columna basis: %s" % ("ya existe" if existe else "no existe"))

        for etiqueta, sql in PREGUNTAS:
            if "basis" in sql and not existe:
                continue
            try:
                print("  %-32s %s" % (etiqueta, conn.execute(text(sql)).scalar()))
            except Exception as error:  # noqa: BLE001
                print("  %-32s (no se pudo: %s)" % (etiqueta, str(error)[:60]))

        por_fecha = conn.execute(text("""
            SELECT generated_at::date AS dia, count(*)
            FROM scouting_reports GROUP BY 1 ORDER BY 1 DESC LIMIT 10
        """)).fetchall()
        if por_fecha:
            print("\n  por día (últimos 10):")
            for dia, n in por_fecha:
                print("    %s  %d" % (dia, n))

    if existe:
        print("\nNada que hacer.")
        return 0

    if not args.i_mean_it:
        print("\nLo que haría:")
        print("  ALTER TABLE scouting_reports ADD COLUMN basis JSON")
        print("\nLas filas existentes quedan en NULL a propósito: su base no "
              "es reconstruible,\ny escribir la de hoy afirmaría que una cifra "
              "vieja se calculó contra una vara\nque nunca vio.")
        print("\nPara aplicarlo:  python3 pipeline/migrate_basis.py --i-mean-it")
        return 0

    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE scouting_reports ADD COLUMN IF NOT EXISTS basis JSON"))
    print("\nColumna agregada. Las filas anteriores quedaron en NULL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
