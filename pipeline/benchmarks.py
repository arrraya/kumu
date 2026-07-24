"""Compute real percentile benchmarks per position from the tournament population.

Output shape matches what ScoutingReportGenerator._load_benchmarks expects:
  {position: {league: {metric: {10: v, 25: v, 50: v, 75: v, 90: v}}}}
"""
import os
import pickle

import numpy as np

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
LEAGUE_LABEL = "World Cup 2022"
PERCENTILES = [10, 25, 50, 75, 90]

# Map StatsBomb verbose positions to Kumu's position taxonomy
POSITION_MAP = {
    "Goalkeeper": "GK",
    "Right Back": "RB", "Left Back": "LB",
    "Right Center Back": "CB", "Left Center Back": "CB", "Center Back": "CB",
    "Right Wing Back": "RB", "Left Wing Back": "LB",
    "Center Defensive Midfield": "CDM",
    "Right Defensive Midfield": "CDM", "Left Defensive Midfield": "CDM",
    "Center Midfield": "CM", "Right Center Midfield": "CM", "Left Center Midfield": "CM",
    "Center Attacking Midfield": "CAM",
    "Right Attacking Midfield": "CAM", "Left Attacking Midfield": "CAM",
    "Right Midfield": "RW", "Left Midfield": "LW",
    "Right Wing": "RW", "Left Wing": "LW",
    "Center Forward": "ST", "Right Center Forward": "ST", "Left Center Forward": "ST",
    "Secondary Striker": "ST",
}

METRIC_PATHS = {
    "pass_completion": ("passing", "completion_rate"),
    "key_passes_per_90": ("passing", "key_passes_per_90"),
    "progressive_passes_per_90": ("passing", "progressive_passes_per_90"),
    "pass_difficulty_score": ("passing", "pass_difficulty_score"),
    "shots_per_90": ("shooting", "shots_per_90"),
    "goals_per_90": ("shooting", "goals_per_90"),
    "assists_per_90": ("shooting", "assists_per_90"),
    "xG_per_shot": ("shooting", "xG_per_shot"),
    "tackles_per_90": ("defensive", "tackles_per_90"),
    "interceptions_per_90": ("defensive", "interceptions_per_90"),
}


def kumu_position(sb_position: str) -> str | None:
    return POSITION_MAP.get(sb_position)


def build_benchmarks(players: dict) -> dict:
    # collect values per (position, metric)
    values: dict = {}
    for p in players.values():
        pos = kumu_position(p.get("position") or "")
        if not pos or pos == "GK":
            continue
        for metric, (cat, key) in METRIC_PATHS.items():
            v = p["metrics"].get(cat, {}).get(key)
            if v is None:
                continue
            values.setdefault(pos, {}).setdefault(metric, []).append(float(v))

    benchmarks: dict = {}
    for pos, metrics in values.items():
        for metric, vals in metrics.items():
            if len(vals) < 10:   # too few players for meaningful percentiles
                continue
            pct = np.percentile(vals, PERCENTILES)
            benchmarks.setdefault(pos, {}).setdefault(LEAGUE_LABEL, {})[metric] = {
                p: round(float(v), 3) for p, v in zip(PERCENTILES, pct)
            }
    return benchmarks


if __name__ == "__main__":
    with open(os.path.join(CACHE_DIR, "player_metrics.pkl"), "rb") as f:
        players = pickle.load(f)

    benchmarks = build_benchmarks(players)
    positions = list(benchmarks.keys())
    print(f"Positions covered: {positions}")
    for pos in positions:
        n_metrics = len(benchmarks[pos][LEAGUE_LABEL])
        print(f"  {pos}: {n_metrics} metrics benchmarked")

    out = os.path.join(CACHE_DIR, "benchmarks.pkl")
    with open(out, "wb") as f:
        pickle.dump(benchmarks, f)
    print(f"Saved to {out}")

    # peek: CAM goals_per_90 distribution
    import json
    sample = benchmarks.get("CAM", {}).get(LEAGUE_LABEL, {}).get("goals_per_90")
    print("CAM goals_per_90 percentiles:", json.dumps(sample))
