"""
Kumü — render a body-pose sequence in the Cancha visual language
==================================================================

The original repository ships an 893-line 3D animator with a dark
theme and bright green pitch lines. Rather than port it and repaint it,
this is a smaller renderer that does only what Kumü needs and speaks
the product's own language from the start: paper ground, ink type,
clay for the left side and slate for the right, and the figures
written the way the report writes them.

It also does the thing the original does not: it puts the MEASUREMENT
beside the movement. A skeleton running is a nice picture; a skeleton
running with its speed, its cadence and its coverage counting up next
to it is the product.

    python3 render.py --file clip.jsonl --player 795530 --out sprint.gif
"""

import argparse
import json
import os
import sys
from typing import Dict, List, Optional

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import animation  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Line3DCollection  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from constants import ALL_JOINTS, CONNECTIONS  # noqa: E402
from palette import (  # noqa: E402
    CLAY, FLAG_MARK, GRASS, GRASS_SHADE, INK, INK_FAINT, INK_SOFT,
    PAPER, RULE_STRONG, SLATE, bone_colour, side_of,
)
from aggregate import speed_series  # noqa: E402
from metrics import compute_num_steps, compute_knee_angles  # noqa: E402

LABEL_KW = dict(family="DejaVu Sans", color=INK_FAINT, fontsize=7.5)


def spaced(text: str) -> str:
    """Cancha's label voice: uppercase and letterspaced.

    Matplotlib text has no letter-spacing property, so the spacing goes
    into the string. Doubling existing spaces keeps word breaks legible
    once every character is held apart.
    """
    return " ".join(text.replace("  ", "   "))


def read_clip(path: str, player_id: Optional[int]) -> Dict[str, object]:
    """One player's joints across a small .jsonl, as (n, 3) arrays."""
    records: List[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except ValueError:
                continue
    if not records:
        raise SystemExit("No frames in %s" % path)

    if player_id is None:
        counts: Dict[int, int] = {}
        for r in records:
            for p in r.get("player_data", []):
                if p.get("joints"):
                    counts[p["player_id"]] = counts.get(p["player_id"], 0) + 1
        if not counts:
            raise SystemExit("No player in %s has a pose." % path)
        player_id = max(counts, key=counts.get)

    n = len(records)
    traj = {j: np.full((n, 3), np.nan) for j in ALL_JOINTS}
    for i, r in enumerate(records):
        for p in r.get("player_data", []):
            if p.get("player_id") != player_id:
                continue
            joints = p.get("joints") or {}
            for j in ALL_JOINTS:
                if j in joints:
                    traj[j][i] = joints[j]["xyz"]
    return {"player_id": player_id, "n": n, "traj": traj,
            "timestamps": [r.get("timestamp") for r in records]}


def draw_pitch(ax, xlim, ylim) -> None:
    """Ground markings at z = 0, in Cancha's quietest tones.

    Only the lines that fall inside the view are drawn. A halfway line
    rendered off-camera is ink spent on nothing.
    """
    def line(xs, ys, colour=GRASS_SHADE, lw=1.0, alpha=0.9):
        ax.plot(xs, ys, [0, 0] if len(xs) == 2 else [0] * len(xs),
                color=colour, linewidth=lw, alpha=alpha, zorder=0)

    x0, x1 = xlim
    y0, y1 = ylim

    # A light grid every five metres gives the eye a sense of scale,
    # which a bare plane does not.
    for gx in np.arange(np.ceil(x0 / 5) * 5, x1, 5.0):
        line([gx, gx], [y0, y1], colour=GRASS, lw=0.6, alpha=0.7)
    for gy in np.arange(np.ceil(y0 / 5) * 5, y1, 5.0):
        line([x0, x1], [gy, gy], colour=GRASS, lw=0.6, alpha=0.7)

    # Halfway line and centre circle, when visible.
    if x0 < 0 < x1:
        line([0, 0], [y0, y1], colour=GRASS_SHADE, lw=1.2)
        th = np.linspace(0, 2 * np.pi, 120)
        cx, cy = 9.15 * np.cos(th), 9.15 * np.sin(th)
        inside = (cx > x0) & (cx < x1) & (cy > y0) & (cy < y1)
        if np.any(inside):
            ax.plot(cx[inside], cy[inside], [0] * int(np.sum(inside)),
                    color=GRASS_SHADE, linewidth=1.0, zorder=0)

    # Touchlines, when the view reaches them.
    for ty in (-34.0, 34.0):
        if y0 < ty < y1:
            line([x0, x1], [ty, ty], colour=RULE_STRONG, lw=1.4)


def render(clip: Dict[str, object], out_path: str, fps: float = 25.0,
           elev: float = 14.0, azim: float = 52.0, buffer_m: float = 1.55,
           dpi: int = 110) -> str:
    traj = clip["traj"]
    n = clip["n"]
    pid = clip["player_id"]

    speeds = speed_series(traj, fps=fps)["speed_kmh"]
    knees = compute_knee_angles(traj, angle_convention="flexion")
    total_steps, step_frames, cadence, _ = compute_num_steps(traj, fps=fps)
    step_set = set(int(f) for f in step_frames)

    hip = traj["midHip"]
    fig = plt.figure(figsize=(9.6, 6.4), facecolor=PAPER)
    # A 3D axes left to itself keeps enormous margins and the figure ends
    # up a tenth of the frame. Placed by hand: text column on the left,
    # the body given the rest.
    ax = fig.add_axes([0.30, 0.04, 0.69, 0.92], projection="3d",
                      facecolor=PAPER)
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    z_top = 2.25
    try:
        # Proportional to the real extents, so the person is not stretched.
        # zoom enlarges the drawing inside its box: a 3D axes reserves room
        # for panes and ticks that are switched off here, and without this
        # the body sits small in the middle of its own frame.
        ax.set_box_aspect([1.0, 1.0, z_top / (2.0 * buffer_m)], zoom=1.55)
    except (AttributeError, TypeError):
        pass

    bones = Line3DCollection([], linewidths=2.1)
    ax.add_collection(bones)
    joint_dots = {
        group: ax.plot([], [], [], "o", markersize=3.4,
                       color=colour, markeredgecolor=PAPER,
                       markeredgewidth=0.6, zorder=5)[0]
        for group, colour in
        (("left", CLAY), ("right", SLATE), ("center", INK), ("head", FLAG_MARK))
    }
    # The ground shadow is what tells the eye where the body actually is;
    # without it a 3D skeleton floats.
    shadow, = ax.plot([], [], [], color=GRASS_SHADE, linewidth=1.0,
                      alpha=0.55, zorder=1)

    L = 0.045
    kicker = fig.text(L, 0.935, "", family="DejaVu Sans", fontsize=6.6,
                      color=FLAG_MARK)
    title = fig.text(L, 0.885, "", family="DejaVu Sans", fontsize=19,
                     fontweight="bold", color=INK)
    fig.add_artist(plt.Line2D([L, 0.265], [0.855, 0.855], color=INK,
                              linewidth=1.6, transform=fig.transFigure))
    readout = fig.text(L, 0.72, "", family="DejaVu Sans Mono", fontsize=44,
                       fontweight="bold", color=INK, va="top")
    readout_label = fig.text(L, 0.595, "", **LABEL_KW)
    fig.add_artist(plt.Line2D([L, 0.265], [0.565, 0.565], color=RULE_STRONG,
                              linewidth=0.8, transform=fig.transFigure))
    secondary = fig.text(L, 0.515, "", family="DejaVu Sans", fontsize=9.5,
                         color=INK_SOFT, va="top")
    footer = fig.text(L, 0.055, "", **LABEL_KW)

    kicker.set_text(spaced("SKILLCORNER BODY POSE  ·  25 FPS  ·  MEASURED"))
    title.set_text("Player %d" % pid)

    def frame(i: int):
        pts = {j: traj[j][i] for j in ALL_JOINTS}
        segs, colours = [], []
        for a, b in CONNECTIONS:
            pa, pb = pts[a], pts[b]
            if np.isnan(pa).any() or np.isnan(pb).any():
                continue
            segs.append([pa, pb])
            colours.append(bone_colour(a, b))
        bones.set_segments(segs)
        bones.set_color(colours)

        for group, artist in joint_dots.items():
            xs, ys, zs = [], [], []
            for j in ALL_JOINTS:
                if side_of(j) != group:
                    continue
                p = pts[j]
                if np.isnan(p).any():
                    continue
                xs.append(p[0]); ys.append(p[1]); zs.append(p[2])
            artist.set_data(xs, ys)
            artist.set_3d_properties(zs)

        feet = [pts[j] for j in ("lAnkle", "rAnkle", "lBigToe", "rBigToe")
                if not np.isnan(pts[j]).any()]
        if feet:
            fx = [p[0] for p in feet]; fy = [p[1] for p in feet]
            shadow.set_data(fx + [fx[0]], fy + [fy[0]])
            shadow.set_3d_properties([0] * (len(fx) + 1))

        centre = hip[i]
        if not np.isnan(centre).any():
            ax.set_xlim(centre[0] - buffer_m, centre[0] + buffer_m)
            ax.set_ylim(centre[1] - buffer_m, centre[1] + buffer_m)
            ax.set_zlim(0, z_top)
            for coll in list(ax.collections):
                if coll is not bones:
                    continue
            # Pitch is redrawn because the window moves with the player.
            for ln in list(ax.lines):
                if ln not in (shadow,) and ln not in joint_dots.values():
                    ln.remove()
            draw_pitch(ax, ax.get_xlim(), ax.get_ylim())

        v = speeds[i]
        readout.set_text("—" if np.isnan(v) else "%.1f" % v)
        readout_label.set_text(spaced("KM/H  ·  HIP, SMOOTHED 0.6 s"))

        lk, rk = knees["left"][i], knees["right"][i]
        bits = []
        if not np.isnan(lk):
            bits.append("knee L %3.0f°" % lk)
        if not np.isnan(rk):
            bits.append("R %3.0f°" % rk)
        strike = "\nFOOT STRIKE" if i in step_set else ""
        secondary.set_text("   ".join(bits) + strike)

        footer.set_text(spaced("FRAME %d OF %d" % (i + 1, n)) + "\n"
                        + spaced("%d STEPS  ·  %.0f SPM" % (total_steps, cadence)))
        return []

    anim = animation.FuncAnimation(fig, frame, frames=n, interval=1000.0 / fps,
                                   blit=False)
    writer = "pillow" if out_path.endswith(".gif") else "ffmpeg"
    anim.save(out_path, writer=writer, fps=fps, dpi=dpi,
              savefig_kwargs={"facecolor": PAPER})
    plt.close(fig)
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", required=True)
    ap.add_argument("--player", type=int, default=None)
    ap.add_argument("--out", default="pose_clip.gif")
    ap.add_argument("--fps", type=float, default=25.0)
    ap.add_argument("--dpi", type=int, default=110)
    ap.add_argument("--elev", type=float, default=14.0)
    ap.add_argument("--azim", type=float, default=52.0)
    ap.add_argument("--buffer", type=float, default=1.55,
                    help="Half-window in metres around the hip.")
    args = ap.parse_args()

    clip = read_clip(args.file, args.player)
    print("[*] player %s, %d frames" % (clip["player_id"], clip["n"]))
    out = render(clip, args.out, fps=args.fps, elev=args.elev,
                 azim=args.azim, dpi=args.dpi, buffer_m=args.buffer)
    print("[OK] %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
