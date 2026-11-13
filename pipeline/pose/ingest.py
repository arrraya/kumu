"""
Kumü — read a SkillCorner Body Pose match and derive per-90 movement
=====================================================================

Reads a match file (.jsonl, .jsonl.gz or .jsonl.zip, streamed, never
extracted), pulls each player's hip trajectory, and turns it into the
three figures `players.metrics["movement"]` holds.

    python3 ingest.py --file data/pose/1925299.jsonl.zip
    python3 ingest.py --file ... --player 11897
    python3 ingest.py --file ... --write --org 7     # needs DATABASE_URL

It does NOT write by default. `--write` is opt-in, requires an explicit
`--org`, and refuses the public organisation unless `--i-mean-it` is
passed as well: the public reference population is what every client's
percentiles are computed against, so a figure landing there by accident
moves numbers for people who never asked for it.

WHAT THIS CANNOT DO
-------------------
SkillCorner's open pose covers two A-League matches. Kumü's reference
population is World Cup 2022. They are different people, so this script
cannot fill in the athletic profile of a player already in Kumü - there
is no overlap to join on. What it can do is measure the players it
actually observed, which is why `--write` takes a tenant: those players
belong in one of their own, not in the public set.
"""

import argparse
import gzip
import json
import os
import sys
import time
import zipfile
from typing import Dict, Iterator, Optional

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aggregate import summarise_movement  # noqa: E402

HIP = "midHip"
# Generous: the two published matches are 153k and 144k frames.
MAX_FRAMES_GUESS = 200_000


def open_lines(path: str) -> Iterator[bytes]:
    """Yield one line at a time from .jsonl, .jsonl.gz or .jsonl.zip.

    The zip is read through, not unpacked. A full match is 3.3 GB
    uncompressed and there is no reason to put that on anyone's disk.
    """
    if path.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            members = [
                n for n in z.namelist()
                if n.endswith(".jsonl") and not n.startswith("__MACOSX")
            ]
            if not members:
                raise SystemExit("No .jsonl member inside %s" % path)
            with z.open(members[0]) as f:
                for line in f:
                    yield line
    elif path.endswith(".gz"):
        with gzip.open(path, "rb") as f:
            for line in f:
                yield line
    else:
        with open(path, "rb") as f:
            for line in f:
                yield line


def read_hips(path: str, player_id: Optional[int] = None, progress_every: int = 20000):
    """One pass over the match, keeping each player's hip trajectory.

    Only midHip is kept. Holding all 29 joints for 22 players across a
    full match would be several gigabytes; the hip is what the movement
    figures are derived from, and it is 48 MB for the lot.
    """
    hips: Dict[int, np.ndarray] = {}
    detected: Dict[int, int] = {}
    n_frames = 0
    periods = set()
    t0 = time.time()

    for raw in open_lines(path):
        try:
            frame = json.loads(raw)
        except ValueError:
            continue
        i = n_frames
        n_frames += 1
        if frame.get("period") is not None:
            periods.add(frame["period"])

        for p in frame.get("player_data", []):
            pid = p.get("player_id")
            if pid is None or (player_id is not None and pid != player_id):
                continue
            if p.get("is_detected"):
                detected[pid] = detected.get(pid, 0) + 1
            joints = p.get("joints")
            if not joints or HIP not in joints:
                continue
            if pid not in hips:
                hips[pid] = np.full((MAX_FRAMES_GUESS, 3), np.nan, dtype=np.float32)
            if i < MAX_FRAMES_GUESS:
                hips[pid][i] = joints[HIP]["xyz"]

        if progress_every and n_frames % progress_every == 0:
            rate = n_frames / max(time.time() - t0, 1e-9)
            print("    %7d frames  (%.0f/s)" % (n_frames, rate), file=sys.stderr)

    for pid in hips:
        hips[pid] = hips[pid][:n_frames].astype(np.float64)

    return hips, n_frames, detected, sorted(periods)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", required=True, help="Match file (.jsonl/.gz/.zip)")
    ap.add_argument("--player", type=int, default=None, help="Only this player id")
    ap.add_argument("--fps", type=float, default=25.0)
    ap.add_argument("--top", type=int, default=12, help="How many players to print")
    ap.add_argument("--write", action="store_true", help="Write to the database")
    ap.add_argument("--org", type=int, default=None, help="Tenant to write into")
    ap.add_argument("--i-mean-it", action="store_true",
                    help="Required to write into the public organisation")
    args = ap.parse_args()

    if args.write and args.org is None:
        raise SystemExit("--write needs --org: this script will not guess a tenant.")

    print("[*] Reading %s" % args.file, file=sys.stderr)
    hips, n_frames, detected, periods = read_hips(args.file, args.player)
    print("[*] %d frames, periods %s, %d players with a hip"
          % (n_frames, periods, len(hips)), file=sys.stderr)

    rows = []
    for pid, hip in hips.items():
        result = summarise_movement(
            {HIP: hip}, fps=args.fps, total_match_frames=n_frames
        )
        rows.append((pid, result))

    rows.sort(key=lambda r: r[1]["coverage"]["observed_seconds"], reverse=True)

    print()
    print("  player    observed   match     speed   dist/90   HSR/90")
    print("                 min       %      km/h        km    count")
    print("  " + "-" * 60)
    for pid, r in rows[: args.top]:
        cov = r["coverage"]
        m = r["movement"]
        if m is None:
            print("  %7d   %7.1f  %5.1f%%        not assessed"
                  % (pid, cov["observed_seconds"] / 60.0,
                     100.0 * (cov["match_coverage"] or 0)))
        else:
            print("  %7d   %7.1f  %5.1f%%   %7.2f  %8.2f  %7d"
                  % (pid, cov["observed_seconds"] / 60.0,
                     100.0 * (cov["match_coverage"] or 0),
                     m["average_speed"], m["distance_covered_per_90"],
                     m["high_intensity_runs"]))

    assessed = [r for _, r in rows if r["movement"] is not None]
    print()
    print("  %d of %d players produced a figure; the rest were observed too"
          % (len(assessed), len(rows)))
    print("  briefly for a per-90 number to mean anything.")
    if assessed:
        print()
        print("  " + assessed[0]["basis"].replace("\n", " "))

    if not args.write:
        print()
        print("  Nothing was written. Pass --write --org N to store these.")
        return 0

    return write_rows(rows, args)


def write_rows(rows, args) -> int:
    """Store the figures, scoped to one tenant."""
    from sqlalchemy import create_engine, text

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("Set DATABASE_URL first.")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        public = conn.execute(
            text("SELECT id FROM organizations WHERE slug = 'public'")
        ).fetchone()
        if public and int(public[0]) == args.org and not args.i_mean_it:
            raise SystemExit(
                "Refusing to write into the public organisation (%d). Every "
                "client's percentiles are computed against it. Pass "
                "--i-mean-it if that is really what you want." % args.org
            )

        written = 0
        for pid, r in rows:
            if r["movement"] is None:
                continue
            row = conn.execute(
                text("SELECT id, metrics FROM players "
                     "WHERE external_id = :eid AND organization_id = :oid"),
                {"eid": "skillcorner_%d" % pid, "oid": args.org},
            ).fetchone()
            if not row:
                continue
            metrics = dict(row[1] or {})
            metrics["movement"] = dict(
                r["movement"],
                basis=r["basis"],
                coverage=r["coverage"],
                source="skillcorner-bodypose",
            )
            conn.execute(
                text("UPDATE players SET metrics = CAST(:m AS JSON) "
                     "WHERE id = :id AND organization_id = :oid"),
                {"m": json.dumps(metrics), "id": row[0], "oid": args.org},
            )
            written += 1

    print("  updated %d players in organisation %d" % (written, args.org))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
