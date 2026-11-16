"""
Kumü — cut each player's best run out of a match and render it
===============================================================

    python3 pipeline/pose/clips.py --file data/pose/1925299.jsonl.zip
    python3 pipeline/pose/clips.py --file ... --player 795530
    python3 pipeline/pose/clips.py --file ... --out frontend/public/clips

A skeleton running is a nice picture. A skeleton running beside the
figures the report already states about that player is the product:
"covers 12.2 km per 90 at 8.1 km/h average" is a claim, and this is the
same player, in the same match, making it.

WHY THE CLIPS ARE MADE HERE AND NOT ON DEMAND
---------------------------------------------
One match of body pose is 609 MB zipped and 3.3 GB open. That cannot
live on the application server, so nothing can render a clip when
somebody opens a report. The clips are cut here, written as GIFs into
the frontend's static folder, and listed in a manifest beside them. The
page asks the manifest who has one; a player with none simply has no
panel, which is the same absence the rest of the report already knows
how to state.

That ties a clip to a frontend deployment rather than to the player's
row, which is wrong for a tenant whose data should travel with it.
It is right for today, when the clips are a demonstration and belong to
nobody. When they belong to a client they move into the database or an
object store, and the manifest is what gets replaced.

TWO PASSES, ON PURPOSE
----------------------
Finding the best run needs every frame's hip; rendering needs all 29
joints, but only for the frames chosen. Holding 29 joints for every
player across a match is gigabytes, so the first pass keeps hips alone
and decides the windows, and the second keeps only what those windows
ask for.
"""

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "backend"))

from aggregate import speed_series  # noqa: E402
from ingest import HIP, open_lines, read_hips  # noqa: E402
import render as renderer  # noqa: E402

# A clip wants to be long enough to read and short enough to watch.
CLIP_SECONDS = 4.0
# Run a little before the peak so the viewer sees him build into it,
# rather than opening at full speed with no idea where it came from.
LEAD_IN = 0.35

MANIFEST = "manifest.json"

# mp4 by default: the same clip is 1.8 MB as a GIF and a fraction of that
# as video, and seven of them ship to every browser that opens a report.
DEFAULT_SUFFIX = ".mp4"


def kumu_id(player_id, source, org_id):
    """The external_id this player carries inside Kumu.

    The manifest has to be joinable from the page, and the page gets
    `external_id` from the API - not the provider's own id, which the
    loader hashes away. Computed with the loader's own function rather
    than a copy of its rule, so the two cannot drift apart.
    """
    if org_id is None:
        return None
    from app.services.ingest_service import stable_external_id

    return stable_external_id(source, org_id, "sc_%d" % player_id)


def read_names(sheet_path):
    """player id -> short name, from a SkillCorner match sheet.

    The renderer has no way to know a name, so the headline read
    "Player 560986" - a database id above prose the rest of the report
    words carefully.
    """
    if not sheet_path or not os.path.exists(sheet_path):
        return {}
    with open(sheet_path, encoding="utf-8") as handle:
        sheet = json.load(handle)
    names = {}
    for entry in sheet.get("players") or []:
        pid = entry.get("id")
        if pid is None:
            continue
        names[int(pid)] = (
            entry.get("short_name")
            or " ".join(p for p in (entry.get("first_name"),
                                    entry.get("last_name")) if p)
            or None
        )
    return {k: v for k, v in names.items() if v}


def best_window(hip, fps, seconds=CLIP_SECONDS, lead_in=LEAD_IN):
    """The fastest sustained stretch of observed frames, as (start, end).

    Picks on the mean speed of the window rather than its peak: one
    frame of noise can beat a real sprint on a peak, and smoothing has
    already removed what it can. Returns None when no window of this
    length is observed throughout - a player seen in scattered frames
    has no run to show, and stitching one together from fragments would
    be a picture of something that did not happen.
    """
    width = int(round(seconds * fps))
    if width < 2 or len(hip) < width:
        return None

    speed = speed_series({HIP: hip}, fps=fps)["speed_kmh"]
    observed = ~np.isnan(hip[:, 0])

    # A window counts only if every frame in it was seen.
    whole = np.convolve(observed.astype(np.float64),
                        np.ones(width), mode="valid") == width
    if not whole.any():
        return None

    filled = np.where(np.isnan(speed), 0.0, speed)
    means = np.convolve(filled, np.ones(width) / width, mode="valid")
    means = np.where(whole, means, -np.inf)

    start = int(np.argmax(means))
    if not np.isfinite(means[start]):
        return None

    lead = int(round(lead_in * fps))
    start = max(0, start - lead)
    end = min(len(hip), start + width + lead)
    return start, end, float(np.nanmax(speed[start:end]))


def extract(path, windows, progress_every=20000):
    """Second pass: the full joints for the frames the windows ask for.

    `windows` is {player_id: (start, end)}. Returns {player_id: [frame]}
    in the shape `render.read_clip` reads, so the renderer needs no
    knowledge of where its frames came from.
    """
    wanted = {pid: (int(a), int(b)) for pid, (a, b) in windows.items()}
    frames = {pid: [] for pid in wanted}
    # Past the last frame anybody asked for there is nothing left to
    # collect, and the rest of a 3.3 GB file is read for no reason.
    last = max(b for _a, b in wanted.values())
    index = 0

    for raw in open_lines(path):
        # Parsed before counting, exactly as `read_hips` counts in the
        # first pass. Advancing the index on a line that failed to parse
        # would shift every frame number between the two passes and point
        # the windows at the wrong moment of the match.
        try:
            frame = json.loads(raw)
        except ValueError:
            continue
        i = index
        index += 1
        if i >= last:
            break
        due = [pid for pid, (a, b) in wanted.items() if a <= i < b]
        if due:
            for player in frame.get("player_data", []):
                pid = player.get("player_id")
                if pid in due and player.get("joints"):
                    frames[pid].append({"player_data": [player]})
        if progress_every and index % progress_every == 0:
            print("    %7d / %d frames" % (index, last), file=sys.stderr)
    return frames


def to_clip(player_id, frames):
    """The structure `render.render` wants, built in memory.

    `read_clip` reads the same thing off disk; this avoids writing a
    temporary .jsonl per player only to read it straight back.
    """
    from constants import ALL_JOINTS

    n = len(frames)
    traj = {joint: np.full((n, 3), np.nan) for joint in ALL_JOINTS}
    for i, frame in enumerate(frames):
        joints = frame["player_data"][0].get("joints") or {}
        for joint, value in joints.items():
            if joint in traj and value and value.get("xyz"):
                traj[joint][i] = value["xyz"]
    return {"traj": traj, "n": n, "player_id": player_id}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", default=None, help="Pose match file")
    parser.add_argument("--player", type=int, action="append", default=None,
                        help="Only these players; default is all observed")
    parser.add_argument("--out", default="frontend/public/clips")
    parser.add_argument("--sheet", default=None,
                        help="SkillCorner match .json, for the players' names")
    parser.add_argument("--suffix", default=DEFAULT_SUFFIX,
                        choices=[".mp4", ".gif"])
    parser.add_argument("--org", type=int, default=None,
                        help="Tenant these players were loaded into; without "
                             "it the manifest cannot be joined from the page")
    parser.add_argument("--source", default="skillcorner_open",
                        help="The source name used when they were loaded")
    parser.add_argument("--only", type=int, action="append", default=None,
                        metavar="ID",
                        help="Keep only these players in the manifest and "
                             "delete the rest; the match has 32 and Kumu "
                             "may hold a handful")
    parser.add_argument("--from-cuts", default=None, metavar="DIR",
                        help="Re-render from saved cuts instead of reading "
                             "the match again")
    parser.add_argument("--keep-frames", default=None, metavar="DIR",
                        help="Also write each cut as .jsonl, to re-render "
                             "without reading the match again")
    parser.add_argument("--fps", type=float, default=25.0)
    parser.add_argument("--seconds", type=float, default=CLIP_SECONDS)
    parser.add_argument("--dpi", type=int, default=110)
    args = parser.parse_args()

    names = read_names(args.sheet)
    if args.sheet and not names:
        print("[!] %s no dio ningun nombre" % args.sheet, file=sys.stderr)

    keep = set(args.only) if args.only else None

    if args.from_cuts:
        # Everything the two passes would have produced is already on
        # disk. Reading it back is how a margin gets adjusted, or a
        # manifest rebuilt, without touching the 3.3 GB again.
        frames, peaks = {}, {}
        for name in sorted(os.listdir(args.from_cuts)):
            if not name.endswith(".jsonl"):
                continue
            pid = int(name[:-len(".jsonl")])
            if keep is not None and pid not in keep:
                continue
            if args.player and pid not in set(args.player):
                continue
            with open(os.path.join(args.from_cuts, name), encoding="utf-8") as f:
                frames[pid] = [json.loads(line) for line in f if line.strip()]
            peaks[pid] = 0.0
        print("[*] %d recortes leidos de %s" % (len(frames), args.from_cuts),
              file=sys.stderr)
        windows = {pid: (0, len(f)) for pid, f in frames.items()}
    else:
        if not args.file:
            raise SystemExit("--file o --from-cuts: uno de los dos.")
        print("[*] primera pasada: caderas", file=sys.stderr)
        hips, n_frames, _detected, _periods = read_hips(args.file)
        if args.player:
            hips = {pid: h for pid, h in hips.items() if pid in set(args.player)}
        if keep is not None:
            hips = {pid: h for pid, h in hips.items() if pid in keep}
        print("[*] %d frames, %d jugadores" % (n_frames, len(hips)),
              file=sys.stderr)

        windows, peaks = {}, {}
        for pid, hip in hips.items():
            found = best_window(hip, args.fps, seconds=args.seconds)
            if found:
                start, end, peak = found
                windows[pid] = (start, end)
                peaks[pid] = peak
        print("[*] %d con una ventana completa de %.1fs"
              % (len(windows), args.seconds), file=sys.stderr)
        if not windows:
            print("Ningun jugador tiene una ventana observada de punta a punta.")
            return 0

        print("[*] segunda pasada: articulaciones", file=sys.stderr)
        frames = extract(args.file, windows)

    os.makedirs(args.out, exist_ok=True)
    manifest_path = os.path.join(args.out, MANIFEST)
    manifest = {}
    if os.path.exists(manifest_path) and keep is None:
        with open(manifest_path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    previous = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as handle:
            previous = json.load(handle)

    print()
    for pid in sorted(windows, key=lambda p: -peaks[p]):
        if not frames[pid]:
            continue
        if args.keep_frames:
            # The cut frames, in the shape `render.read_clip` reads. Two
            # passes over 3.3 GB to adjust a margin is not iteration, and
            # this turns the next attempt into a second's work.
            cut = os.path.join(args.keep_frames, "%d.jsonl" % pid)
            os.makedirs(args.keep_frames, exist_ok=True)
            with open(cut, "w", encoding="utf-8") as handle:
                for frame in frames[pid]:
                    handle.write(json.dumps(frame) + "\n")

        clip = to_clip(pid, frames[pid])
        filename = "%d%s" % (pid, args.suffix)
        out_path = os.path.join(args.out, filename)
        renderer.render(clip, out_path, fps=args.fps, dpi=args.dpi,
                        name=names.get(pid))
        size = os.path.getsize(out_path)
        was = previous.get(str(pid)) or {}
        manifest[str(pid)] = {
            "file": filename,
            "name": names.get(pid) or was.get("name"),
            # What the page joins on. The API hands it `external_id`, not
            # the provider's id, so without this the manifest and the
            # player list have no key in common.
            "external_id": kumu_id(pid, args.source, args.org),
            "frames": clip["n"],
            "seconds": round(clip["n"] / args.fps, 1),
            "peak_kmh": round(peaks[pid] or was.get("peak_kmh") or 0.0, 1),
        }
        print("  %7d  %-22s %5.1f km/h  %4d frames  %6.0f KB"
              % (pid, (names.get(pid) or "-")[:22], peaks[pid],
                 clip["n"], size / 1024))

    if keep is not None:
        # The match holds 32 players and Kumu may hold a handful. Clips
        # nobody can open are repository weight for ever.
        removed = 0
        for name in os.listdir(args.out):
            if name == MANIFEST:
                continue
            pid = name.rsplit(".", 1)[0]
            if pid not in manifest:
                os.unlink(os.path.join(args.out, name))
                removed += 1
        if removed:
            print("\n  %d clips sin jugador en Kumu, borrados" % removed)

    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=1, sort_keys=True)
    print("\n%d clips -> %s" % (len(manifest), args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
