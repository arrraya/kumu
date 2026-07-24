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
            # simple composite rating on a ~0-10 scale
            rating = min(10.0, 5.0 + m_goals * 1.5 + m_assists * 1.0 + m_keyp * 0.3 + completion * 2.0)
            history.append({
                "match_id": int(match_id),
                "rating": round(float(rating), 2),
                "goals": m_goals,
                "assists": m_assists,
                "key_passes": m_keyp,
                "pass_completion": round(float(completion), 3),
            })

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


if __name__ == "__main__":
    events = load_events()
    print(f"Events loaded: {len(events)}")
    print("Training pass difficulty model...")
    model = train_pass_difficulty_model(events)
    print("Aggregating player metrics...")
    players = build_player_metrics(events, model)
    print(f"Players with >=90 minutes: {len(players)}")

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
