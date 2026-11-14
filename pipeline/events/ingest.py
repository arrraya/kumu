"""
Kumü — load SkillCorner's open A-League events into a tenant
=============================================================

    python3 pipeline/events/ingest.py --root data/events
    python3 pipeline/events/ingest.py --root data/events --pose data/pose/1925299.jsonl.zip
    python3 pipeline/events/ingest.py --root data/events --write --org 7
    python3 pipeline/events/ingest.py --root data/events --write \
        --org-slug skillcorner_aleague --create-org "A-League Men (SkillCorner open)"

Reads every match under --root, builds one payload per club, and runs it
through `ingest_service.ingest` — the same path a client's own upload
takes. Nothing here computes an index: the service does, because the
index is normalised against the whole population and a pipeline script
has no business deciding where a player sits on it.

It does NOT write by default. `--write` is opt-in, requires an explicit
`--org`, and refuses the public organisation unless `--i-mean-it` is
passed too. These are 101 A-League players and the public reference
population is World Cup 2022; mixing them would shift every client's
percentiles toward a different league without anyone asking.

WITH --pose
-----------
Joins the measured movement from a pose match onto the players it
observed. The open pose release covers one of these twenty matches, so
this fills in a handful of players and leaves the rest declaring
movement unavailable — which is what MovementMetrics is for.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "backend"))

import adapter  # noqa: E402


def load_movement(pose_file: str, fps: float = 25.0):
    """Measured movement per SkillCorner player id, from one pose match.

    Reads the hips once and summarises each player with the same
    aggregator `pipeline/pose/ingest.py` uses, so the figures that land
    here and the figures that script prints are the same figures.
    Players observed too briefly come back as None and are left out
    rather than carried as zeros.
    """
    pose_dir = os.path.join(REPO, "pipeline", "pose")
    sys.path.insert(0, pose_dir)
    from aggregate import summarise_movement  # noqa: E402
    import ingest as pose_ingest  # noqa: E402

    hips, n_frames, _detected, _periods = pose_ingest.read_hips(pose_file)
    movement = {}
    for pid, hip in hips.items():
        result = summarise_movement(
            {pose_ingest.HIP: hip}, fps=fps, total_match_frames=n_frames
        )
        if result.get("movement"):
            movement[int(pid)] = result["movement"]
    return movement


def describe(payloads) -> None:
    from app.schemas.ingest import IngestPayload, describe_capabilities

    total = 0
    for raw in payloads:
        payload = IngestPayload(**raw)
        capability = describe_capabilities(payload)
        squad = len(payload.players)
        total += squad
        with_movement = sum(1 for p in payload.players if p.metrics.movement)
        print(f"  {payload.club.name[:30]:31s} {squad:3d} jugadores"
              f"   movimiento medido: {with_movement}")
        tier = capability.get("tier") or capability.get("level")
        if tier:
            print(f"      nivel que desbloquea: {tier}")
    print(f"\n  total: {total} jugadores en {len(payloads)} clubes")


def resolve_org(db, org_id, slug, create_name, i_mean_it):
    """Find the tenant to write into, or create it.

    Either `--org N` for one that exists, or `--org-slug S --create-org`
    to make one. Refuses the public organisation without `--i-mean-it`:
    these are 101 A-League players and the public set is the reference
    every client's percentiles are computed against.
    """
    from sqlalchemy import text

    public = db.execute(
        text("SELECT id FROM organizations WHERE slug = 'public'")
    ).fetchone()
    public_id = int(public[0]) if public else None

    if slug:
        row = db.execute(
            text("SELECT id, name FROM organizations WHERE slug = :s"), {"s": slug}
        ).fetchone()
        if row is None:
            if not create_name:
                raise SystemExit(
                    "No organisation with slug '%s'. Pass --create-org NAME "
                    "to make one." % slug
                )
            db.execute(text("""
                INSERT INTO organizations (name, slug, kind, allows_aggregate)
                VALUES (:name, :slug, 'client', FALSE)
                ON CONFLICT (slug) DO NOTHING
            """), {"name": create_name, "slug": slug})
            db.commit()
            row = db.execute(
                text("SELECT id, name FROM organizations WHERE slug = :s"),
                {"s": slug},
            ).fetchone()
            print(f"Organizacion creada: {row[1]} (id {row[0]}, slug {slug})")
        org_id = int(row[0])
        name = row[1]
    else:
        if org_id is None:
            raise SystemExit("--write needs --org N or --org-slug S.")
        row = db.execute(
            text("SELECT name FROM organizations WHERE id = :i"), {"i": org_id}
        ).fetchone()
        if not row:
            raise SystemExit("No organisation with id %d." % org_id)
        name = row[0]

    if public_id is not None and org_id == public_id and not i_mean_it:
        raise SystemExit(
            "Organisation %d is the public reference population. Every "
            "client's percentiles are computed against it. Pass --i-mean-it "
            "if that is really what you want." % org_id
        )

    print(f"Escribiendo en la organizacion {org_id}: {name}")
    return org_id, public_id


def write(payloads, org_id, slug, create_name, i_mean_it: bool) -> int:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.schemas.ingest import IngestPayload
    from app.services import ingest_service

    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Set DATABASE_URL first (source ~/.kumu_env).")

    engine = create_engine(url)
    Session = sessionmaker(bind=engine)
    db = Session()

    org_id, public = resolve_org(db, org_id, slug, create_name, i_mean_it)

    # The tenant reads its own rows and the public ones, which is what the
    # API grants a client: percentiles need a reference population.
    org_ids = [org_id]
    if public is not None:
        org_ids.append(public)

    written = 0
    for raw in payloads:
        payload = IngestPayload(**raw)
        result = ingest_service.ingest(db, payload, org_id, org_ids)
        written += int(result.get("players_written") or 0)
        dropped = result.get("players_skipped") or []
        note = f"  descartados: {dropped}" if dropped else ""
        print(f"  {payload.club.name[:30]:31s} "
              f"escritos {result.get('players_written')}{note}")
        if result.get("positions_without_reference"):
            print("      sin poblacion de referencia: "
                  f"{result['positions_without_reference']}")
    db.close()
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True,
                        help="Folder of <id>_match.json / <id>_dynamic_events.csv")
    parser.add_argument("--pose", default=None,
                        help="A pose match file, to join measured movement")
    parser.add_argument("--min-matches", type=int, default=3,
                        help="Appearances needed to load a player (Kumu needs 3)")
    parser.add_argument("--out", default=None, help="Write the payloads to a file")
    parser.add_argument("--write", action="store_true", help="Write to the database")
    parser.add_argument("--org", type=int, default=None, help="Tenant id to write into")
    parser.add_argument("--org-slug", default=None,
                        help="Tenant slug, resolved or created instead of --org")
    parser.add_argument("--create-org", default=None, metavar="NAME",
                        help="Create --org-slug under this name if it is missing")
    parser.add_argument("--i-mean-it", action="store_true",
                        help="Allow writing into the public organisation")
    args = parser.parse_args()

    players = adapter.read_release(args.root)
    print(f"Partidos leidos de {args.root}: "
          f"{len({h['match_id'] for p in players.values() for h in p['history']})}")
    print(f"Jugadores con al menos una aparicion: {len(players)}")

    movement = {}
    if args.pose:
        movement = load_movement(args.pose)
        print(f"Movimiento medido disponible para {len(movement)} jugadores")

    payloads = adapter.build_payloads(
        players, min_matches=args.min_matches, movement_by_id=movement
    )
    print(f"\nCargables (>= {args.min_matches} partidos):")
    describe(payloads)

    print("\nProcedencia de cada campo:")
    for field, origin in adapter.PROVENANCE.items():
        print(f"  {field:20s} {origin}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(payloads, handle, indent=1, ensure_ascii=False)
        print(f"\nPayloads -> {args.out}")

    if not args.write:
        print("\nNada escrito. Pasa --write con --org N o --org-slug S.")
        return 0
    if args.org is None and args.org_slug is None:
        raise SystemExit("--write needs an explicit --org or --org-slug: "
                         "this script will not guess a tenant.")

    written = write(payloads, args.org, args.org_slug,
                    args.create_org, args.i_mean_it)
    print(f"\nEscritos {written} jugadores.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
