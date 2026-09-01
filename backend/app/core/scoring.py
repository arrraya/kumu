"""Single home for how Kumu turns match data into scores.

These four pieces used to live in `pipeline/metrics.py` alone. Once the ingest
path needed them too, keeping a second copy was not an option: `market.py` did
exactly that with the rating formula, and when the pipeline moved to role-aware
ratings the copy silently kept the retired one, so defenders were priced on pass
completion alone for weeks. Nothing failed; the numbers were just wrong. One
definition, imported by everyone.
"""
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

# Kumu's own position vocabulary. Provider names are mapped onto this.
POSITIONS = ["GK", "CB", "RB", "LB", "CDM", "CM", "CAM", "RW", "LW", "ST"]

# What a match rating should reward, by role.
POSITION_GROUP = {
    "GK": "defense", "CB": "defense", "RB": "defense", "LB": "defense",
    "CDM": "midfield", "CM": "midfield",
    "CAM": "attack", "RW": "attack", "LW": "attack", "ST": "attack",
}

# Verbose provider position names -> Kumu positions. StatsBomb's vocabulary is
# the seed; other providers get their own entries as they are onboarded.
PROVIDER_POSITION_MAP = {
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

MIN_MATCHES_FOR_INDEX = 3
MIN_PEERS_FOR_SCALE = 5


def normalize_position(raw: Optional[str]) -> Optional[str]:
    """Map any provider's position name onto Kumu's vocabulary."""
    if not raw:
        return None
    value = str(raw).strip()
    if value.upper() in POSITION_GROUP:
        return value.upper()
    return PROVIDER_POSITION_MAP.get(value)


def match_rating(stats: Dict[str, Any], group: str) -> float:
    """Rate one match according to what the role is actually asked to do.

    A single offensive formula left defenders with nothing to vary on but pass
    completion, which barely moves between centre-backs, so every centre-back
    scored practically the same. Uncapped on purpose: a hat-trick should stand
    above a one-goal game rather than hitting a ceiling.
    """
    goals = stats.get("goals") or 0
    assists = stats.get("assists") or 0
    key_passes = stats.get("key_passes") or 0
    shots = stats.get("shots") or 0
    completion = stats.get("pass_completion") or 0.0
    progressive = stats.get("progressive_passes") or 0
    defensive = (stats.get("tackles") or 0) + (stats.get("interceptions") or 0)

    if group == "attack":
        return (5.0 + goals * 1.5 + assists * 1.0 + key_passes * 0.3
                + shots * 0.15 + completion * 1.5)
    if group == "midfield":
        return (5.0 + completion * 2.0 + progressive * 0.10 + key_passes * 0.4
                + defensive * 0.20 + goals * 1.2 + assists * 0.9)
    return (5.0 + completion * 2.0 + defensive * 0.25 + progressive * 0.08
            + key_passes * 0.3 + goals * 1.2 + assists * 0.9)


def rate_history(history: List[Dict[str, Any]], position: Optional[str]) -> List[Dict[str, Any]]:
    """Fill in a rating for any appearance that does not carry one.

    Clients with their own rating keep it; the rest get Kumu's, role-aware.
    """
    group = POSITION_GROUP.get(normalize_position(position) or "", "midfield")
    rated = []
    for entry in history:
        record = dict(entry)
        if not isinstance(record.get("rating"), (int, float)):
            record["rating"] = round(match_rating(record, group), 2)
        rated.append(record)
    return rated


def raw_index(history: Iterable[Dict[str, Any]]) -> Optional[Dict[str, float]]:
    """Index before cross-position normalisation, or None if too few matches.

    Absent rather than faked: a player with two appearances has no trend to
    report, and inventing one would be the kind of filled-in number the reports
    exist to avoid.
    """
    ratings = [
        float(h["rating"]) for h in history
        if isinstance(h.get("rating"), (int, float))
    ]
    if len(ratings) < MIN_MATCHES_FOR_INDEX:
        return None

    mean = float(np.mean(ratings))
    vol = float(np.std(ratings) / mean) if mean > 0 else 0.0
    trend = float(np.polyfit(np.arange(len(ratings)), ratings, 1)[0])
    return {
        "value": round(mean * 10, 1),
        "trend": round(trend, 3),
        "volatility": round(vol, 3),
        "confidence": round(max(0.0, min(1.0, 1 - vol)), 3),
    }


def normalize_indices(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Put every position on one comparable scale.

    Role-aware ratings rest on different bases: a centre-back's comes from a
    high, steady floor while a striker goes scoreless most weeks, so defenders'
    medians sat ~17 points above forwards'. Consumers that compare ACROSS
    positions — market price, a club's expected level, top performers — need one
    scale, so each index is rescaled within its own position: 70 is the typical
    player for that role and 10 points is one standard deviation.

    Tails are compressed with tanh rather than clipped. Clamping at 100 stacked
    every outlier on the ceiling and made the best players indistinguishable.

    Each record needs `position` and `performance_index`; the pre-normalisation
    figure is kept as `raw_value`.
    """
    by_position = defaultdict(list)
    for r in records:
        pos = normalize_position(r.get("position"))
        index = (r.get("performance_index") or {}).get("value")
        if pos and isinstance(index, (int, float)):
            by_position[pos].append(float(index))

    scales = {}
    for pos, values in by_position.items():
        if len(values) >= MIN_PEERS_FOR_SCALE:
            spread = float(np.std(values))
            scales[pos] = (float(np.mean(values)), spread if spread > 0 else 1.0)

    for r in records:
        index_data = r.get("performance_index")
        if not index_data:
            continue
        pos = normalize_position(r.get("position"))
        if pos not in scales:
            continue
        mean, spread = scales[pos]
        z = (float(index_data["value"]) - mean) / spread
        index_data["raw_value"] = round(float(index_data["value"]), 1)
        index_data["value"] = round(70.0 + 30.0 * float(np.tanh(z / 2.5)), 1)

    return records


def infer_expected_index(squad_indices: Iterable[float]) -> Optional[float]:
    """The level a club operates at, read from the players it already has.

    Same reasoning that replaced declared position needs with the real squad:
    a club's level is not a number someone types in, it is what its squad shows.
    Uses the upper half of the squad, since a club is defined by the level it
    fields rather than by its fringe players.
    """
    values = sorted(float(v) for v in squad_indices if isinstance(v, (int, float)))
    if not values:
        return None
    top_half = values[len(values) // 2:]
    return round(float(np.mean(top_half)), 1)
