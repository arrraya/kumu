"""
Kumü — record who produced each row's data
===========================================

    source ~/.kumu_env
    python3 pipeline/migrate_source.py            # muestra qué haría
    python3 pipeline/migrate_source.py --i-mean-it

Adds `players.source` and `teams.source`, and fills what can be read
honestly from the identifiers already in the table.

WHY
---
Kumü's whole claim is that every figure declares where it comes from. It
declares what KIND a number is — measured, estimated, decided — and until
now it could not say WHO measured it. A sporting director reading "12.2
km per 90, measured" had no way to tell SkillCorner from StatsBomb from a
spreadsheet their own analyst uploaded, and all three live in the same
table. The word "SkillCorner" appears in exactly one place in the whole
interface: the body-pose panel, for seven players out of a hundred and
one.

WHAT CAN BE DERIVED, AND WHAT CANNOT
------------------------------------
The provider was never recorded as a fact. It was hinted at in the
identifier, by four conventions minted in four different places:

    wc2022_     pipeline/load.py          a tournament, not a provider
    sbgk_       pipeline/goalkeeping.py   the goalkeeping pass over the same
    sc_         pipeline/events/adapter.py
    <source>_   ingest_service, where the prefix is the declared source
                truncated to twelve characters

Each prefix is minted in exactly one place in this repository, so reading
one back is reading, not guessing. That is why this backfills where
migrate_basis.py deliberately did not: there, the information had been
destroyed; here it was only abbreviated.

A prefix this does not recognise is left NULL. Writing a plausible
provider onto a row whose origin is unknown would be the opposite of the
point.
"""

import argparse
import os
import sys
from collections import Counter

from sqlalchemy import create_engine, text

# Prefix -> who actually produced the data. Longest first, so `sc_club_`
# is matched before `sc_`.
PROVEEDORES = [
    ("wc2022_", "statsbomb_wc2022"),
    ("sbgk_", "statsbomb_wc2022"),
    ("sc_club_", "skillcorner"),
    ("sc_", "skillcorner"),
    ("skillcorner", "skillcorner"),
]


def proveedor(external_id):
    """The provider behind an identifier, or None if the prefix is unknown."""
    if not external_id:
        return None
    for prefijo, nombre in PROVEEDORES:
        if external_id.startswith(prefijo):
            return nombre
    return None


# Written out per table rather than interpolated. `tests/test_sql.py` parses
# every query in the tree with libpg_query, and "UPDATE %s SET …" is not
# SQL until Python has formatted it - so a template hides itself from the
# one check that would catch a real mistake in it.
SQL = {
    "players": {
        "ids": "SELECT external_id FROM players",
        "add": "ALTER TABLE players ADD COLUMN IF NOT EXISTS source VARCHAR",
        "index": "CREATE INDEX IF NOT EXISTS players_source_idx "
                 "ON players (source)",
        "fill": """
            UPDATE players SET source = :nombre
            WHERE source IS NULL AND external_id LIKE :patron
        """,
        "missing": "SELECT count(*) FROM players WHERE source IS NULL",
    },
    "teams": {
        "ids": "SELECT external_id FROM teams",
        "add": "ALTER TABLE teams ADD COLUMN IF NOT EXISTS source VARCHAR",
        "index": "CREATE INDEX IF NOT EXISTS teams_source_idx "
                 "ON teams (source)",
        "fill": """
            UPDATE teams SET source = :nombre
            WHERE source IS NULL AND external_id LIKE :patron
        """,
        "missing": "SELECT count(*) FROM teams WHERE source IS NULL",
    },
}


def columnas(conn):
    filas = conn.execute(text("""
        SELECT table_name FROM information_schema.columns
        WHERE table_name IN ('players', 'teams') AND column_name = 'source'
    """)).fetchall()
    return {r[0] for r in filas}


def inventario(conn, tabla):
    filas = conn.execute(text(SQL[tabla]["ids"])).fetchall()
    cuenta = Counter()
    for (eid,) in filas:
        nombre = proveedor(eid)
        if nombre:
            cuenta[nombre] += 1
        else:
            # The prefix up to the first underscore, so an unknown one can be
            # named rather than merely counted.
            cuenta["(sin reconocer: %s)"
                   % ((eid or "").split("_")[0][:14] or "vacío")] += 1
    return cuenta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--i-mean-it", action="store_true")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Falta DATABASE_URL. Corre `source ~/.kumu_env` primero.",
              file=sys.stderr)
        return 2

    engine = create_engine(url)
    with engine.connect() as conn:
        tiene = columnas(conn)
        for tabla in ("players", "teams"):
            print("%s.source: %s"
                  % (tabla, "ya existe" if tabla in tiene else "no existe"))
        print()
        for tabla in ("players", "teams"):
            print("  %s, por proveedor derivado del identificador:" % tabla)
            for nombre, n in sorted(inventario(conn, tabla).items(),
                                    key=lambda kv: -kv[1]):
                print("    %-34s %d" % (nombre, n))
            print()

    if not args.i_mean_it:
        print("Lo que haría:")
        print("  ALTER TABLE players ADD COLUMN source VARCHAR")
        print("  ALTER TABLE teams   ADD COLUMN source VARCHAR")
        print("  UPDATE ... SET source = <el proveedor de arriba>, por prefijo")
        print()
        print("Las filas cuyo prefijo no se reconoce quedan en NULL: escribir")
        print("un proveedor plausible sobre una fila de origen desconocido es")
        print("exactamente lo contrario de lo que esta columna existe para hacer.")
        print()
        print("Para aplicarlo:  python3 pipeline/migrate_source.py --i-mean-it")
        return 0

    with engine.begin() as conn:
        for tabla in ("players", "teams"):
            conn.execute(text(SQL[tabla]["add"]))
            conn.execute(text(SQL[tabla]["index"]))

        escritos = {}
        for tabla in ("players", "teams"):
            total = 0
            for prefijo, nombre in PROVEEDORES:
                res = conn.execute(text(SQL[tabla]["fill"]),
                                   {"nombre": nombre, "patron": prefijo + "%"})
                total += res.rowcount or 0
            escritos[tabla] = total

    with engine.connect() as conn:
        print()
        for tabla in ("players", "teams"):
            sin = conn.execute(text(SQL[tabla]["missing"])).scalar()
            print("  %-8s %d filas con proveedor, %d en NULL"
                  % (tabla, escritos[tabla], sin))
        print()
        print("Las de NULL no tienen prefijo reconocible. Desde ahora la "
              "ingesta escribe\nel `source` declarado, así que sólo lo ya "
              "cargado puede quedar sin él.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
