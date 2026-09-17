"""Derive each side's playing style from its squad's actual pass flows."""
import json
import os
import sys

from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.dirname(__file__))
import spatial  # noqa: E402


def main():
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        equipos = conn.execute(text("""
            SELECT t.id, t.name, count(m.id) AS n
            FROM teams t
            JOIN squad_memberships m ON m.team_id = t.id AND m.left_at IS NULL
            GROUP BY t.id, t.name HAVING count(m.id) > 0 ORDER BY t.name
        """)).fetchall()

        resultados = []
        for team_id, name, n in equipos:
            perfiles = conn.execute(text("""
                SELECT p.spatial_profile FROM squad_memberships m
                JOIN players p ON p.id = m.player_id
                WHERE m.team_id = :t AND m.left_at IS NULL
                  AND p.spatial_profile IS NOT NULL
            """), {"t": team_id}).fetchall()

            perfiles = [r[0] for r in perfiles if r[0]]
            if not perfiles:
                continue

            # A style read off three or four players is the style of those
            # players, not the side. Partial squads get the profile but it is
            # flagged, the same way a thin match log suppresses an index.
            if len(perfiles) < 6:
                continue

            perfil = spatial.team_profile(perfiles)
            estilo = spatial.style_from_flows(perfil["pass_flows"])

            conn.execute(text(
                "UPDATE teams SET spatial_profile = CAST(:p AS JSON) WHERE id = :id"
            ), {"p": json.dumps({**perfil, "style": estilo}), "id": team_id})
            resultados.append((name, n, estilo))

        print(f"{len(resultados)} equipos con estilo derivado\n")
        for name, n, e in sorted(resultados, key=lambda r: -(r[2]["territory"] or 0))[:8]:
            print(f"  {name[:22]:22s} {n:2d} jug  territorio {e['territory']:.2f}  "
                  f"progresion {e['progression']:+.3f}  ({e['passes_counted']} pases)")
        print("  ...")
        for name, n, e in sorted(resultados, key=lambda r: (r[2]["territory"] or 0))[:4]:
            print(f"  {name[:22]:22s} {n:2d} jug  territorio {e['territory']:.2f}  "
                  f"progresion {e['progression']:+.3f}  ({e['passes_counted']} pases)")


if __name__ == "__main__":
    main()
