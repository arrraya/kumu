"""
Kumü — streaming reader for SkillCorner Body Pose match files
==============================================================

Adapted from MattLowrieDS/skillcorner_pose_viz (MIT). The byte-offset
index is the part worth keeping: a match file is 3.3 GB, and this lets
a caller jump to frame 50,000 without reading the 49,999 before it.

Three audited defects are fixed here.

  #6  The two extraction modes disagreed about a filtered joint. For a
      single player, a joint whose stated error exceeded the threshold
      became NaN and KEPT ITS KEY. For all players, it was dropped from
      the dict entirely. That inconsistency was not cosmetic: an absent
      key is exactly the condition that broke the original's hip
      fallback (see metrics.py, finding #1), so the all-players path
      produced precisely the input the maths handled worst. Both modes
      now write NaN and keep every key.

  #7  The cached index was trusted whenever its mtime was not older than
      the source's. A 3.3 GB file restored from a backup, copied with
      `cp -p`, or checked out again carries its original timestamp, so a
      stale index would be reused and every seek would land in the
      middle of some other frame - silently, since a byte offset into
      JSON usually still parses as *something*. The cache now records
      the source's size and mtime and verifies both.

  #8  Finding a player used a substring test for '"player_id": 795530',
      which assumes the file puts exactly one space after the colon.
      Against compact JSON every line fails the test and the function
      raises "no pose frames found" - an absence reported as a fact
      about the player rather than about the parser. The prefilter is
      now a regex that tolerates any spacing, and it is only ever an
      optimisation: the authoritative check is the parsed value.

Compressed inputs stream. A .zip or .gz cannot be seeked by byte
offset, so those are read start to finish and `start_frame` is honoured
by skipping; this is stated rather than silently slower.
"""

import gzip
import json
import os
import re
import time
import zipfile
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np

try:
    from .constants import ALL_JOINTS
except ImportError:  # run as a script
    from constants import ALL_JOINTS

CACHE_DIR = ".cache"


# ---------------------------------------------------------------------------
# Reading lines, whatever the container
# ---------------------------------------------------------------------------

def is_seekable(path: str) -> bool:
    """Whether byte-offset seeking is possible for this file."""
    return not (path.endswith(".zip") or path.endswith(".gz"))


def iter_lines(path: str, start_frame: int = 0) -> Iterator[bytes]:
    """Yield lines from frame `start_frame` on.

    Plain .jsonl uses the byte index. Compressed inputs are streamed and
    skipped to, because a zip member has no usable byte offsets.
    """
    if path.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            members = [
                n for n in z.namelist()
                if n.endswith(".jsonl") and not n.startswith("__MACOSX")
            ]
            if not members:
                raise ValueError("No .jsonl member inside %s" % path)
            with z.open(members[0]) as f:
                for i, line in enumerate(f):
                    if i >= start_frame:
                        yield line
    elif path.endswith(".gz"):
        with gzip.open(path, "rb") as f:
            for i, line in enumerate(f):
                if i >= start_frame:
                    yield line
    else:
        offsets = get_line_offsets(path)
        with open(path, "rb") as f:
            if start_frame > 0:
                if start_frame >= len(offsets):
                    return
                f.seek(int(offsets[start_frame]))
            for line in f:
                yield line


# ---------------------------------------------------------------------------
# The byte-offset index
# ---------------------------------------------------------------------------

def build_line_index(path: str, chunk_size: int = 4 * 1024 * 1024) -> np.ndarray:
    """Byte offset of the first character of every line."""
    offsets = [0]
    pos = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            start = 0
            while True:
                idx = chunk.find(b"\n", start)
                if idx == -1:
                    break
                offsets.append(pos + idx + 1)
                start = idx + 1
            pos += len(chunk)

    # A file ending in a newline produces a final offset at EOF, which is
    # not the start of any line. One that does not end in a newline does
    # not, and its last offset is a real line.
    if len(offsets) > 1 and offsets[-1] == pos:
        offsets.pop()

    return np.array(offsets, dtype=np.uint64)


def get_line_offsets(path: str, cache_dir: str = CACHE_DIR,
                     force_rebuild: bool = False) -> np.ndarray:
    """The index, from cache when the cache provably matches the source.

    Finding #7: the stamp records the source's size and mtime, and both
    must match. Size is the cheap half of the check and the half that
    catches a truncated or replaced file whose timestamp happens to look
    right.
    """
    base = os.path.basename(path)
    os.makedirs(cache_dir, exist_ok=True)
    idx_path = os.path.join(cache_dir, "%s.idx.npy" % base)
    stamp_path = os.path.join(cache_dir, "%s.idx.json" % base)

    try:
        st = os.stat(path)
        signature = {"size": st.st_size, "mtime": int(st.st_mtime)}
    except OSError as exc:
        raise ValueError("Cannot stat %s: %s" % (path, exc))

    if not force_rebuild and os.path.exists(idx_path) and os.path.exists(stamp_path):
        try:
            with open(stamp_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if (cached.get("size") == signature["size"]
                    and cached.get("mtime") == signature["mtime"]):
                return np.load(idx_path, mmap_mode="r")
        except (OSError, ValueError):
            pass  # unreadable stamp: rebuild rather than trust it

    t0 = time.time()
    print("[*] Indexing %s ..." % base)
    offsets = build_line_index(path)
    try:
        np.save(idx_path, offsets)
        with open(stamp_path, "w", encoding="utf-8") as f:
            json.dump(signature, f)
        print("[OK] %d frames in %.1fs -> %s" % (len(offsets), time.time() - t0, idx_path))
        return np.load(idx_path, mmap_mode="r")
    except OSError as exc:
        print("[!] Could not cache the index (%s); using it in memory." % exc)
        return offsets


# ---------------------------------------------------------------------------
# Finding things in a match
# ---------------------------------------------------------------------------

def _player_pattern(player_id: int) -> "re.Pattern[bytes]":
    """Finding #8: tolerant of whatever spacing the writer used."""
    return re.compile(rb'"player_id"\s*:\s*%d\b' % player_id)


def find_first_pose_frame(path: str, player_id: Optional[int] = None,
                          max_scan_frames: int = 50000,
                          start_frame: int = 0) -> Tuple[int, Optional[int]]:
    """First frame with a usable pose, and whose it is."""
    pattern = _player_pattern(player_id) if player_id is not None else None

    for i, raw in enumerate(iter_lines(path, start_frame)):
        if i >= max_scan_frames:
            break
        # The prefilter only skips work. Anything it lets through is
        # still checked against the parsed value below.
        if pattern is not None and not pattern.search(raw):
            continue
        try:
            frame = json.loads(raw)
        except ValueError:
            continue
        if frame.get("period") is None:
            continue
        for p in frame.get("player_data", []):
            if not p.get("joints"):
                continue
            pid = p.get("player_id")
            if player_id is None or pid == player_id:
                return start_frame + i, pid

    who = "player %d" % player_id if player_id is not None else "any player"
    raise ValueError(
        "No pose frames for %s in %d frames from %d."
        % (who, max_scan_frames, start_frame)
    )


def scan_players(path: str, start_frame: int = 0,
                 scan_frames: int = 300) -> List[Tuple[int, int]]:
    """(player_id, frames with a pose) over a window, best covered first."""
    counts: Dict[int, int] = {}
    for i, raw in enumerate(iter_lines(path, start_frame)):
        if i >= scan_frames:
            break
        try:
            frame = json.loads(raw)
        except ValueError:
            continue
        for p in frame.get("player_data", []):
            pid = p.get("player_id")
            if pid is None:
                continue
            counts.setdefault(pid, 0)
            if p.get("joints"):
                counts[pid] += 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _joint_xyz(joints: Optional[Dict[str, Any]], name: str,
               max_error_cm: Optional[float]) -> List[float]:
    """One joint's coordinates, or NaN - but always three numbers.

    Finding #6. The all-players path used to omit a filtered joint's key
    altogether while the single-player path wrote NaN and kept it. Both
    mean "no usable value here", and the second says so in a way the
    maths downstream can read; the first produced the absent-key case
    that broke the hip fallback. One behaviour now, and it is this one.
    """
    nan3 = [float("nan")] * 3
    if not joints or name not in joints:
        return nan3
    info = joints[name]
    if max_error_cm is not None and info.get("p90_mae_cm", 0.0) > max_error_cm:
        return nan3
    xyz = info.get("xyz")
    if not xyz or len(xyz) != 3:
        return nan3
    return [float(v) for v in xyz]


def load_pose(path: str, start_frame: Optional[int] = None, num_frames: int = 100,
              player_id: Optional[int] = None, max_error_cm: Optional[float] = None,
              joints: Optional[List[str]] = None) -> Dict[str, Any]:
    """A window of one player's pose, as trajectories the metrics accept.

    Returns frames, timestamps, joint_trajectories (every requested
    joint present, NaN where unknown), player_xy, valid_pose_mask and
    ball_xyz.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    wanted = list(joints) if joints else list(ALL_JOINTS)

    if start_frame is None:
        start_frame, resolved = find_first_pose_frame(path, player_id)
        if player_id is None:
            player_id = resolved
        print("[*] Starting at frame %d for player %s" % (start_frame, player_id))

    if player_id is None:
        found = scan_players(path, start_frame, max(num_frames, 50))
        if not found or found[0][1] == 0:
            raise ValueError("No player has a pose near frame %d." % start_frame)
        player_id = found[0][0]
        print("[*] Chose player %d (%d frames with a pose)" % (player_id, found[0][1]))

    frames: List[int] = []
    timestamps: List[Optional[str]] = []
    ball: List[List[float]] = []
    xy: List[List[float]] = []
    has_pose: List[bool] = []
    traj: Dict[str, List[List[float]]] = {j: [] for j in wanted}

    for i, raw in enumerate(iter_lines(path, start_frame)):
        if i >= num_frames:
            break
        try:
            frame = json.loads(raw)
        except ValueError:
            continue

        frames.append(frame.get("frame", start_frame + i))
        timestamps.append(frame.get("timestamp"))

        bd = frame.get("ball_data") or {}
        if bd.get("x") is not None and bd.get("is_detected"):
            ball.append([bd["x"], bd["y"], bd.get("z") or 0.0])
        else:
            ball.append([float("nan")] * 3)

        target = None
        for p in frame.get("player_data", []):
            if p.get("player_id") == player_id:
                target = p
                break

        if target is None:
            xy.append([float("nan")] * 2)
            player_joints = None
        else:
            xy.append([target.get("x", float("nan")), target.get("y", float("nan"))])
            player_joints = target.get("joints")

        has_pose.append(bool(player_joints))
        for j in wanted:
            traj[j].append(_joint_xyz(player_joints, j, max_error_cm))

    return {
        "player_id": player_id,
        "frames": frames,
        "timestamps": timestamps,
        "joint_trajectories": {k: np.array(v, dtype=np.float64) for k, v in traj.items()},
        "player_xy": np.array(xy, dtype=np.float64),
        "valid_pose_mask": np.array(has_pose, dtype=bool),
        "ball_xyz": np.array(ball, dtype=np.float64),
        "seekable": is_seekable(path),
    }
