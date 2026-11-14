"""
Kumü — check what the SkillCorner load actually put in the database
====================================================================

    python3 pipeline/events/verify.py --org 23

Read-only. Every statement is a SELECT, and every one is scoped to an
organisation id except the two that exist to prove the load did NOT
reach anywhere else.

Checks, in order:

  1. the tenant holds what the loader said it wrote
  2. no row landed outside it
  3. every player got an index, and on which scale
  4. why the goalkeepers came back unscaled
  5. the per-90 figures are inside real football ranges
  6. movement is absent, and says so rather than reading zero
  7. one record in full, to look at
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "backend"))

# Real-football bounds, declared here rather than inferred from the rows
# being judged: a range read off the data it is checking will always pass.
RANGES = {
    "completion_rate": (0.55, 0.95),
    "progressive_passes_per_90": (0.0, 18.0),
    "key_passes_per_90": (0.0, 5.0),
    "shots_per_90": (0.0, 6.0),
    "goals_per_90": (0.0, 1.5),
    "assists_per_90": (0.0, 1.5),
    "tackles_per_90": (0.0, 6.0),
}
GROUP_OF = {
    "completion_rate": "passing",
    "progressive_passes_per_90": "passing",
    "key_passes_per_90": "passing",
    "shots_per_90": "shooting",
    "goals_per_90": "shooting",
    "assists_per_90": "shooting",
    "tackles_per_90": "defensive",
}


def main() -> int:
    from sqlalchemy import create_engine, text

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--org", type=int, required=True)
    args = parser.parse_args()
    org = args.org

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL first (source ~/.kumu_env).")
    engine = create_engine(url)

    with engine.connect() as conn:
        def q(sql, **params):
            return conn.execute(text(sql), params).fetchall()

        name = q("SELECT name, slug, kind, allows_aggregate "
                 "FROM organizations WHERE id = :o", o=org)
        if not name:
            raise SystemExit("No organisation with id %d." % org)
        print("1. EL TENANT")
        print(f"   id {org}: {name[0][0]}")
        print(f"   slug={name[0][1]}  kind={name[0][2]}  "
              f"allows_aggregate={name[0][3]}")

        counts = q("""
            SELECT (SELECT count(*) FROM players WHERE organization_id = :o),
                   (SELECT count(*) FROM teams   WHERE organization_id = :o),
                   (SELECT count(*) FROM squad_memberships
                      WHERE team_id IN (SELECT id FROM teams
                                        WHERE organization_id = :o))
        """, o=org)[0]
        print(f"   jugadores={counts[0]}  clubes={counts[1]}  "
              f"vinculos de plantel={counts[2]}")

        print("\n2. NADA SE ESCAPO DEL TENANT")
        strays = q("""
            SELECT organization_id, count(*) FROM players
            WHERE external_id LIKE 'skillcorne%' AND organization_id <> :o
            GROUP BY organization_id
        """, o=org)
        print(f"   filas con external_id de esta fuente fuera del org {org}: "
              f"{strays or 'ninguna'}")
        public = q("SELECT id, (SELECT count(*) FROM players p "
                   "WHERE p.organization_id = o.id) FROM organizations o "
                   "WHERE slug = 'public'")
        if public:
            print(f"   el org publico ({public[0][0]}) sigue con "
                  f"{public[0][1]} jugadores")

        print("\n3. INDICE")
        rows = q("""
            SELECT position,
                   count(*),
                   count(performance_index) ,
                   count(*) FILTER (WHERE performance_index->>'scaled' = 'true'),
                   round(min((performance_index->>'value')::numeric), 1),
                   round(max((performance_index->>'value')::numeric), 1)
            FROM players WHERE organization_id = :o
            GROUP BY position ORDER BY position
        """, o=org)
        print(f"   {'pos':5s} {'n':>3s} {'con idx':>8s} {'escalado':>9s} "
              f"{'min':>6s} {'max':>6s}")
        for pos, n, idx, scaled, lo, hi in rows:
            flag = "" if scaled == n else "   <- SIN ESCALA"
            print(f"   {str(pos):5s} {n:3d} {idx:8d} {scaled:9d} "
                  f"{lo:6} {hi:6}{flag}")
        missing = q("SELECT count(*) FROM players WHERE organization_id = :o "
                    "AND performance_index IS NULL", o=org)[0][0]
        print(f"   sin indice: {missing}")

        print("\n4. POR QUE LOS ARQUEROS QUEDARON SIN ESCALA")
        print("   MIN_PEERS_FOR_SCALE = 5: una posicion necesita 5 pares con")
        print("   indice en la poblacion de referencia para tener escala.")
        ref = q("""
            SELECT position, count(*) FROM players
            WHERE organization_id IN (SELECT id FROM organizations
                                      WHERE slug = 'public')
              AND performance_index IS NOT NULL
            GROUP BY position ORDER BY count(*)
        """)
        print(f"   {'pos':5s} {'pares en la poblacion publica':>30s}")
        for pos, n in ref:
            flag = "   <- bajo el umbral" if n < 5 else ""
            print(f"   {str(pos):5s} {n:30d}{flag}")
        gk_total = q("""
            SELECT count(*), count(performance_index) FROM players
            WHERE organization_id IN (SELECT id FROM organizations
                                      WHERE slug = 'public')
              AND position = 'GK'
        """)[0]
        print(f"   arqueros en la poblacion publica: {gk_total[0]}, "
              f"de ellos con indice: {gk_total[1]}")

        print("\n5. RANGOS POR 90")
        metrics = q("SELECT name, position, metrics FROM players "
                    "WHERE organization_id = :o", o=org)
        print(f"   {'campo':28s} {'n':>3s} {'min':>7s} {'mediana':>8s} "
              f"{'max':>7s}  {'esperado':>12s}")
        for field, (lo, hi) in RANGES.items():
            group = GROUP_OF[field]
            vals = []
            for _n, _p, m in metrics:
                m = m if isinstance(m, dict) else json.loads(m or "{}")
                v = (m.get(group) or {}).get(field)
                if isinstance(v, (int, float)):
                    vals.append(float(v))
            if not vals:
                print(f"   {field:28s} ausente")
                continue
            vals.sort()
            out = [v for v in vals if v < lo or v > hi]
            flag = f"   <- {len(out)} FUERA" if out else ""
            print(f"   {field:28s} {len(vals):3d} {vals[0]:7.2f} "
                  f"{vals[len(vals)//2]:8.2f} {vals[-1]:7.2f}  "
                  f"{lo:5.2f}-{hi:5.2f}{flag}")

        print("\n6. MOVIMIENTO")
        with_mov = 0
        zeroed = []
        for n, _p, m in metrics:
            m = m if isinstance(m, dict) else json.loads(m or "{}")
            mov = m.get("movement")
            if mov:
                with_mov += 1
                if all((v or 0) == 0 for v in mov.values()):
                    zeroed.append(n)
        print(f"   con movimiento: {with_mov} de {len(metrics)}")
        print(f"   con movimiento en cero (seria 'no se' disfrazado de 0): "
              f"{zeroed or 'ninguno'}")
        print("   los demas no traen la clave: el reporte dira que esta fuente")
        print("   no carga tracking, en vez de puntuar un cero.")

        print("\n7. UNA FICHA COMPLETA")
        one = q("""
            SELECT name, position, age, current_team, performance_index,
                   metrics, performance_history
            FROM players WHERE organization_id = :o
            ORDER BY (performance_index->>'value')::numeric DESC NULLS LAST
            LIMIT 1
        """, o=org)[0]
        print(f"   {one[0]} — {one[1]}, {one[2]} años, {one[3]}")
        for label, value in (("indice", one[4]), ("metrics", one[5])):
            data = value if isinstance(value, dict) else json.loads(value or "{}")
            print(f"   {label}: {json.dumps(data, ensure_ascii=False)}")
        hist = one[6] if isinstance(one[6], list) else json.loads(one[6] or "[]")
        print(f"   historial: {len(hist)} partidos")
        for h in hist:
            print(f"     {h.get('date')}  {h.get('minutes'):5}min  "
                  f"rating={h.get('rating')}  g={h.get('goals'):.0f} "
                  f"a={h.get('assists'):.0f} pc={h.get('key_passes'):.0f} "
                  f"rem={h.get('shots'):.0f} ent={h.get('tackles'):.0f} "
                  f"pp={h.get('progressive_passes'):.0f} "
                  f"comp={h.get('pass_completion')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
