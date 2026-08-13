"""Compute per-player metrics from StatsBomb event data.

Produces, per player, the structure Kumu's data contract expects:
  metrics.passing / shooting / defensive  (movement requires tracking data -> omitted, not faked)
  performance_history (per-match series -> seed of the performance index / stock market)
  performance_index (value / trend / volatility / confidence)
"""
import os
import pickle

import numpy as np
import pandas as pd
import xgboost as xgb

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")

# StatsBomb's verbose positions grouped by what a match rating should reward.
POSITION_GROUP = {
    "Right Center Forward": "attack", "Left Center Forward": "attack",
    "Center Forward": "attack", "Secondary Striker": "attack",
    "Right Wing": "attack", "Left Wing": "attack",
    "Center Attacking Midfield": "attack",
    "Right Attacking Midfield": "attack", "Left Attacking Midfield": "attack",
    "Center Midfield": "midfield", "Right Center Midfield": "midfield",
    "Left Center Midfield": "midfield",
    "Center Defensive Midfield": "midfield",
    "Right Defensive Midfield": "midfield", "Left Defensive Midfield": "midfield",
    "Right Midfield": "midfield", "Left Midfield": "midfield",
    "Right Back": "defense", "Left Back": "defense",
    "Right Center Back": "defense", "Left Center Back": "defense",
    "Center Back": "defense",
    "Right Wing Back": "defense", "Left Wing Back": "defense",
    "Goalkeeper": "defense",
}


def match_rating(stats: dict, group: str) -> float:
    """Rate one match according to what the role is actually asked to do.

    A single offensive formula (goals, assists, key passes, pass completion)
    left defenders with nothing to vary on but completion rate, which barely
    moves between centre-backs — so every centre-back in the database came out
    with practically the same index. Uncapped on purpose: a hat-trick should
    stand above a one-goal game rather than hitting a ceiling.
    """
    goals = stats.get("goals", 0)
    assists = stats.get("assists", 0)
    key_passes = stats.get("key_passes", 0)
    shots = stats.get("shots", 0)
    completion = stats.get("pass_completion", 0.0)
    progressive = stats.get("progressive_passes", 0)
    defensive = stats.get("tackles", 0) + stats.get("interceptions", 0)

    if group == "attack":
        return (
            5.0 + goals * 1.5 + assists * 1.0 + key_passes * 0.3
            + shots * 0.15 + completion * 1.5
        )
    if group == "midfield":
        return (
            5.0 + completion * 2.0 + progressive * 0.10 + key_passes * 0.4
            + defensive * 0.20 + goals * 1.2 + assists * 0.9
        )
    return (
        5.0 + completion * 2.0 + defensive * 0.25 + progressive * 0.08
        + key_passes * 0.3 + goals * 1.2 + assists * 0.9
    )


def load_events() -> pd.DataFrame:
    with open(os.path.join(CACHE_DIR, "all_events.pkl"), "rb") as f:
        return pickle.load(f)


# ---------------------------------------------------------------- pass difficulty
def train_pass_difficulty_model(events: pd.DataFrame):
    """XGBoost classifier on pass origin/destination coords (handbook approach).

    Target: 1 if the pass was completed (pass_outcome is NaN in StatsBomb data).
    Returns the fitted model. difficulty = 1 - P(complete).
    """
    passes = events[events["type"] == "Pass"].copy()
    passes = passes.dropna(subset=["location", "pass_end_location"])

    xy = np.array(passes["location"].tolist(), dtype=float)
    xy2 = np.array(passes["pass_end_location"].tolist(), dtype=float)
    X = np.hstack([xy, xy2])
    y = passes["pass_outcome"].isna().astype(int).values  # NaN outcome == completed

    model = xgb.XGBClassifier(random_state=0, n_estimators=200, max_depth=5)
    model.fit(X, y)
    return model


def pass_difficulty_scores(model, passes: pd.DataFrame) -> np.ndarray:
    xy = np.array(passes["location"].tolist(), dtype=float)
    xy2 = np.array(passes["pass_end_location"].tolist(), dtype=float)
    X = np.hstack([xy, xy2])
    p_complete = model.predict_proba(X)[:, 1]
    return 1.0 - p_complete  # higher = harder pass


# ---------------------------------------------------------------- per-player aggregation
def minutes_played_approx(events: pd.DataFrame) -> pd.DataFrame:
    """Approximate minutes per player per match from min/max event minute."""
    ev = events.dropna(subset=["player"])
    grp = ev.groupby(["player", "match_id"])["minute"]
    out = (grp.max() - grp.min()).clip(lower=1).rename("minutes").reset_index()
    return out


def build_player_metrics(events: pd.DataFrame, model) -> dict:
    """Aggregate per-90 metrics and per-match history for every player."""
    players = {}
    ev = events.dropna(subset=["player"]).copy()

    # Precompute pass difficulty for all valid passes once
    all_passes = ev[(ev["type"] == "Pass")].dropna(subset=["location", "pass_end_location"]).copy()
    all_passes["difficulty"] = pass_difficulty_scores(model, all_passes)

    minutes = minutes_played_approx(ev).groupby("player")["minutes"].sum()

    for player, pev in ev.groupby("player"):
        mins = float(minutes.get(player, 0))
        if mins < 90:   # skip cameo appearances; not enough signal
            continue
        per90 = 90.0 / mins

        passes = pev[pev["type"] == "Pass"]
        completed = passes["pass_outcome"].isna().sum()
        n_passes = len(passes)

        p_diff = all_passes[all_passes["player"] == player]["difficulty"]

        shots = pev[pev["type"] == "Shot"]
        goals = int((shots["shot_outcome"] == "Goal").sum()) if len(shots) else 0
        xg_per_shot = float(shots["shot_statsbomb_xg"].mean()) if len(shots) else None

        # assists: passes flagged as goal assists
        assists = int(passes["pass_goal_assist"].fillna(False).sum()) if "pass_goal_assist" in passes else 0
        key_passes = int(passes["pass_shot_assist"].fillna(False).sum()) if "pass_shot_assist" in passes else 0

        # progressive pass: moves ball >=15 units toward opponent goal (x axis)
        if n_passes:
            px = np.array(passes.dropna(subset=["location", "pass_end_location"])["location"].tolist(), dtype=float)
            px2 = np.array(passes.dropna(subset=["location", "pass_end_location"])["pass_end_location"].tolist(), dtype=float)
            progressive = int(((px2[:, 0] - px[:, 0]) >= 15).sum()) if len(px) else 0
        else:
            progressive = 0

        tackles = len(pev[(pev["type"] == "Duel") & (pev.get("duel_type") == "Tackle")]) if "duel_type" in pev else 0
        interceptions = len(pev[pev["type"] == "Interception"])
        aerials_won = None  # StatsBomb open data lacks a simple aerial-duel-won flag; omitted, not faked

        position = pev["position"].mode().iloc[0] if pev["position"].notna().any() else None
        team = pev["team"].mode().iloc[0] if pev["team"].notna().any() else None

        # ---- per-match history (seed for performance index / stock market)
        history = []
        for match_id, mev in pev.groupby("match_id"):
            m_passes = mev[mev["type"] == "Pass"]
            m_completed = m_passes["pass_outcome"].isna().sum()
            m_shots = mev[mev["type"] == "Shot"]
            m_goals = int((m_shots["shot_outcome"] == "Goal").sum()) if len(m_shots) else 0
            m_assists = int(m_passes["pass_goal_assist"].fillna(False).sum()) if "pass_goal_assist" in m_passes else 0
            m_keyp = int(m_passes["pass_shot_assist"].fillna(False).sum()) if "pass_shot_assist" in m_passes else 0
            completion = (m_completed / len(m_passes)) if len(m_passes) else 0.0

            # Defensive and progressive output per match, so roles that do not
            # score have something real to be judged on.
            m_tackles = len(mev[(mev["type"] == "Duel") & (mev.get("duel_type") == "Tackle")]) if "duel_type" in mev else 0
            m_interceptions = len(mev[mev["type"] == "Interception"])
            m_valid = m_passes.dropna(subset=["location", "pass_end_location"])
            if len(m_valid):
                p_start = np.array(m_valid["location"].tolist(), dtype=float)
                p_end = np.array(m_valid["pass_end_location"].tolist(), dtype=float)
                m_progressive = int(((p_end[:, 0] - p_start[:, 0]) >= 15).sum())
            else:
                m_progressive = 0

            entry = {
                "match_id": int(match_id),
                "goals": m_goals,
                "assists": m_assists,
                "key_passes": m_keyp,
                "shots": len(m_shots),
                "tackles": m_tackles,
                "interceptions": m_interceptions,
                "progressive_passes": m_progressive,
                "pass_completion": round(float(completion), 3),
            }
            entry["rating"] = round(float(match_rating(entry, POSITION_GROUP.get(position, "midfield"))), 2)
            history.append(entry)

        ratings = [h["rating"] for h in history]
        if len(ratings) >= 3:
            x = np.arange(len(ratings))
            trend = float(np.polyfit(x, ratings, 1)[0])
            vol = float(np.std(ratings) / np.mean(ratings)) if np.mean(ratings) > 0 else 0.0
            perf_index = {
                "value": round(float(np.mean(ratings)) * 10, 1),  # 0-100 scale
                "trend": round(trend, 3),
                "volatility": round(vol, 3),
                "confidence": round(max(0.0, min(1.0, 1 - vol)), 3),
            }
        else:
            perf_index = None  # not enough matches -> absent, not faked

        players[player] = {
            "name": player,
            "team": team,
            "position": position,
            "minutes": round(mins, 0),
            "metrics": {
                "passing": {
                    "completion_rate": round(completed / n_passes, 3) if n_passes else None,
                    "key_passes_per_90": round(key_passes * per90, 2),
                    "progressive_passes_per_90": round(progressive * per90, 2),
                    "pass_difficulty_score": round(float(p_diff.mean()), 3) if len(p_diff) else None,
                },
                "shooting": {
                    "shots_per_90": round(len(shots) * per90, 2),
                    "xG_per_shot": round(xg_per_shot, 3) if xg_per_shot is not None else None,
                    "conversion_rate": round(goals / len(shots), 3) if len(shots) else None,
                    "goals_per_90": round(goals * per90, 2),
                    "assists_per_90": round(assists * per90, 2),
                },
                "defensive": {
                    "tackles_per_90": round(tackles * per90, 2),
                    "interceptions_per_90": round(interceptions * per90, 2),
                    "aerial_duels_won": aerials_won,  # None: not available in open data
                },
                # movement: requires tracking data -> intentionally absent (contract E.5)
            },
            "performance_history": history,
            "performance_index": perf_index,
        }

    return players


def normalize_indices(players: dict) -> dict:
    """Put every position on the same index scale.

    Role-aware ratings fixed the compression among defenders, but left the
    scales incomparable across roles: a centre-back's rating rests on a high,
    steady base (pass completion, constant defensive actions) while a striker
    goes scoreless in most matches, so defenders' medians sat ~17 points above
    forwards'. Several consumers compare across positions — the market price,
    the club's expected_index, the dashboard's top performers — so the index is
    rescaled within each position: 70 is the typical player for that role and
    each 10 points is one standard deviation. Ordering inside a position is
    untouched, and the pre-normalisation figure is kept as raw_value.
    """
    from collections import defaultdict
    from benchmarks import POSITION_MAP

    by_position = defaultdict(list)
    for p in players.values():
        pos = POSITION_MAP.get(p.get("position") or "")
        index = (p.get("performance_index") or {}).get("value")
        if pos and isinstance(index, (int, float)):
            by_position[pos].append(float(index))

    scales = {}
    for pos, values in by_position.items():
        if len(values) >= 5:
            spread = float(np.std(values))
            scales[pos] = (float(np.mean(values)), spread if spread > 0 else 1.0)

    for p in players.values():
        index_data = p.get("performance_index")
        if not index_data:
            continue
        pos = POSITION_MAP.get(p.get("position") or "")
        if pos not in scales:
            continue
        mean, spread = scales[pos]
        z = (float(index_data["value"]) - mean) / spread
        index_data["raw_value"] = round(float(index_data["value"]), 1)
        # Clamping at 100 stacked every outlier on the ceiling: Messi and
        # Mbappé both read exactly 100.0 and stopped being distinguishable.
        # tanh compresses instead of cutting — inside roughly two standard
        # deviations the scale is nearly linear, beyond that it eases off and
        # approaches the bounds without ever reaching them, so ordering among
        # extreme players survives.
        scaled = 70.0 + 30.0 * float(np.tanh(z / 2.5))
        index_data["value"] = round(scaled, 1)

    return players


if __name__ == "__main__":
    events = load_events()
    print(f"Events loaded: {len(events)}")
    print("Training pass difficulty model...")
    model = train_pass_difficulty_model(events)
    print("Aggregating player metrics...")
    players = build_player_metrics(events, model)
    print(f"Players with >=90 minutes: {len(players)}")
    players = normalize_indices(players)
    print("Indices normalised within position")

    out = os.path.join(CACHE_DIR, "player_metrics.pkl")
    with open(out, "wb") as f:
        pickle.dump(players, f)
    print(f"Saved to {out}")

    # sanity peek: a known star
    for name in players:
        if "Messi" in name:
            import json
            print(json.dumps(players[name], indent=2, default=str)[:1200])
            break
