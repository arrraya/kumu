"""Where a player does what he does, compactly.

Every spatial capability Kumü lacks — heat maps, passing charts, deriving a
club's style instead of declaring it — needs coordinates, and the pipeline used
to compute aggregates and throw them away.

Keeping raw events would mean tens of thousands of rows per tournament per
tenant. Keeping a zone-to-zone matrix costs a few kilobytes and serves all three
uses: the heat map is its origin marginal, the passing chart is its strongest
flows, and a team's matrix IS its playing style. The resolution lost is
resolution none of those uses needs.

The same structure has room for tracking-derived occupancy later, which is why
the profile is a dict with a declared source rather than a bare matrix.
"""
import numpy as np
import pandas as pd

# StatsBomb pitch is 120 x 80. Six columns by four rows: fine enough to tell a
# build-up from a switch, coarse enough to stay stable on a few hundred passes.
COLS, ROWS = 6, 4
N_ZONES = COLS * ROWS
PITCH_X, PITCH_Y = 120.0, 80.0


def zone_of(x: float, y: float) -> int:
    col = min(int(x / PITCH_X * COLS), COLS - 1)
    row = min(int(y / PITCH_Y * ROWS), ROWS - 1)
    return row * COLS + col


def zone_centre(z: int):
    col, row = z % COLS, z // COLS
    return ((col + 0.5) * PITCH_X / COLS, (row + 0.5) * PITCH_Y / ROWS)


def pass_flows(passes: pd.DataFrame) -> dict:
    """Sparse zone-to-zone counts, completed passes only.

    Failed passes are excluded because their destination is where the ball was
    cut off, not where it was aimed — the same contamination that limits the
    difficulty model. A style profile should describe intent, and a completed
    pass is the only evidence of intent this data carries.
    """
    if passes.empty:
        return {}

    origins = np.array(passes["location"].tolist(), dtype=float)
    ends = np.array(passes["pass_end_location"].tolist(), dtype=float)
    completed = passes["pass_outcome"].isna().values

    flows = {}
    for (x1, y1), (x2, y2), ok in zip(origins, ends, completed):
        if not ok:
            continue
        key = f"{zone_of(x1, y1)}-{zone_of(x2, y2)}"
        flows[key] = flows.get(key, 0) + 1
    return flows


def touch_zones(events: pd.DataFrame) -> dict:
    """Where the player was involved at all, not only when passing."""
    located = events.dropna(subset=["location"])
    if located.empty:
        return {}
    coords = np.array(located["location"].tolist(), dtype=float)
    counts = {}
    for x, y in coords:
        z = zone_of(x, y)
        counts[str(z)] = counts.get(str(z), 0) + 1
    return counts


def spatial_profile(player_events: pd.DataFrame, minutes: float) -> dict:
    """The compact spatial fingerprint stored per player."""
    passes = player_events[player_events["type"] == "Pass"].dropna(
        subset=["location", "pass_end_location"])

    flows = pass_flows(passes)
    touches = touch_zones(player_events)
    total = sum(flows.values())

    return {
        "grid": {"cols": COLS, "rows": ROWS, "pitch": [PITCH_X, PITCH_Y]},
        "source": "event",  # tracking-derived occupancy would say so here
        "pass_flows": flows,
        "touch_zones": touches,
        "passes_counted": total,
        # Enough passes for the shape to mean something. Below this the profile
        # is kept but flagged, the same way a thin match log suppresses an index.
        "reliable": total >= 50,
    }


def team_profile(player_profiles: list) -> dict:
    """A club's style, summed from its players rather than declared.

    Club playing styles are curated today: somebody typed possession 0.55 and
    pressing 0.61. Summing the squad's actual pass flows derives the same thing
    from evidence, which is the move that has paid off every time it was made.
    """
    flows = {}
    for p in player_profiles:
        for key, n in (p.get("pass_flows") or {}).items():
            flows[key] = flows.get(key, 0) + n

    total = sum(flows.values()) or 1
    return {
        "grid": {"cols": COLS, "rows": ROWS, "pitch": [PITCH_X, PITCH_Y]},
        "pass_flows": flows,
        "passes_counted": sum(flows.values()),
        "shares": {k: round(v / total, 5) for k, v in flows.items()},
    }
