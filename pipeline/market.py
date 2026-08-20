"""Build a stock-market style price series for every player.

Design
------
* Per-match score is recomputed WITHOUT the old cap at 10, so standout
  performances actually stand out (Messi's 2-goal semifinal used to hit the
  ceiling and flatten).
* Each match produces a return relative to the player's own baseline.
* Returns compound into an index, then the index is scaled so the FINAL price
  equals the player's current estimated value — keeping the market view
  consistent with the value shown everywhere else in Kumu.

Honesty note: prices are derived from Kumu's estimated values and its own
performance model. They are an analytical construct, not observed market data.
"""
import json
import os

import numpy as np
from sqlalchemy import create_engine, text

SENSITIVITY = 0.15   # how strongly one match moves the price
MAX_MATCH_MOVE = 0.10   # cap a single match at +/-10% so outliers stay plausible


def match_score(entry: dict) -> float:
    """Per-match performance score, taken from the rating metrics.py computed.

    This module used to recompute the score with its own copy of the old,
    purely offensive formula (goals, assists, key passes, pass completion).
    When metrics.py moved to role-aware ratings, that copy silently kept the
    retired formula, so defenders were still priced as if only pass completion
    mattered — which is why their prices barely moved. Reading the stored
    rating removes the duplication that caused the drift.
    """
    rating = entry.get("rating")
    if isinstance(rating, (int, float)):
        return float(rating)
    # Pre-rating history: fall back so old rows still produce a series.
    return (
        5.0
        + (entry.get("goals") or 0) * 1.5
        + (entry.get("assists") or 0) * 1.0
        + (entry.get("key_passes") or 0) * 0.3
        + (entry.get("pass_completion") or 0) * 2.0
    )


def build_series(
    history: list, current_value: float, baseline: float, spread: float = 0.0
) -> dict | None:
    """Turn a match history into a price series ending at current_value.

    `baseline` is the average match score of the player's POSITION peers, not
    the player's own average: pricing against your own mean guarantees half your
    matches look like underperformance (a goal-scoring game could drop the
    price). Against peers, the question becomes "did this outperform a typical
    player in this role?", which is what a market actually prices.
    """
    if not history or len(history) < 2 or not current_value or baseline <= 0:
        return None

    scores = [match_score(h) for h in history]

    # Price how UNUSUAL the match was for the role, not the raw gap. Defenders
    # score in a narrow band by nature, so measuring the gap in absolute terms
    # left their prices flat while forwards swung freely. Dividing by the
    # position's own spread puts an exceptional game for a centre-back on the
    # same footing as an exceptional game for a striker.
    unit = spread if spread and spread > 0 else (baseline * 0.15 if baseline else 1.0)

    index, cumulative = [], 1.0
    for s in scores:
        ret = ((s - baseline) / unit) * SENSITIVITY
        ret = max(-MAX_MATCH_MOVE, min(MAX_MATCH_MOVE, ret))
        cumulative *= (1.0 + ret)
        index.append(cumulative)

    final = index[-1] or 1.0
    prices = [round(current_value * (v / final), 2) for v in index]

    points = []
    for i, (h, p, s) in enumerate(zip(history, prices, scores)):
        prev = prices[i - 1] if i > 0 else p
        points.append({
            "match": i + 1,
            "match_id": h.get("match_id"),
            "price": p,
            "score": round(s, 2),
            "change_pct": round(((p - prev) / prev) * 100, 2) if prev else 0.0,
            "goals": h.get("goals") or 0,
            "assists": h.get("assists") or 0,
        })

    opening, closing = prices[0], prices[-1]
    returns = [pt["change_pct"] for pt in points[1:]]

    return {
        "series": points,
        "current_price": closing,
        "opening_price": opening,
        "total_change_pct": round(((closing - opening) / opening) * 100, 2) if opening else 0.0,
        "last_change_pct": points[-1]["change_pct"],
        "high": max(prices),
        "low": min(prices),
        "volatility": round(float(np.std(returns)), 2) if returns else 0.0,
        "matches": len(points),
    }


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("Set DATABASE_URL first.")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS market_series (
                player_id INTEGER PRIMARY KEY,
                current_price DOUBLE PRECISION,
                opening_price DOUBLE PRECISION,
                total_change_pct DOUBLE PRECISION,
                last_change_pct DOUBLE PRECISION,
                high DOUBLE PRECISION,
                low DOUBLE PRECISION,
                volatility DOUBLE PRECISION,
                matches INTEGER,
                series JSON,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))

        rows = conn.execute(text(
            "SELECT id, name, position, market_value, performance_history FROM players"
        )).fetchall()

        # Position baselines: average match score across all peers in that role
        by_position: dict = {}
        for _pid, _name, position, _value, history in rows:
            for h in (history or []):
                by_position.setdefault(position or "?", []).append(match_score(h))
        baselines = {
            pos: float(np.mean(scores)) for pos, scores in by_position.items() if scores
        }
        spreads = {
            pos: float(np.std(scores)) for pos, scores in by_position.items() if len(scores) > 1
        }
        overall = float(np.mean([s for v in by_position.values() for s in v])) if by_position else 0.0
        print("Position baselines:", {k: round(v, 2) for k, v in sorted(baselines.items())})

        conn.execute(text("DELETE FROM market_series"))

        built = 0
        for pid, name, position, value, history in rows:
            baseline = baselines.get(position or "?", overall)
            spread = spreads.get(position or "?", 0.0)
            data = build_series(history or [], float(value or 0), baseline, spread)
            if not data:
                continue
            conn.execute(text("""
                INSERT INTO market_series (player_id, current_price, opening_price,
                    total_change_pct, last_change_pct, high, low, volatility,
                    matches, series)
                VALUES (:pid, :cp, :op, :tc, :lc, :hi, :lo, :vol, :m, CAST(:series AS JSON))
            """), {
                "pid": pid, "cp": data["current_price"], "op": data["opening_price"],
                "tc": data["total_change_pct"], "lc": data["last_change_pct"],
                "hi": data["high"], "lo": data["low"], "vol": data["volatility"],
                "m": data["matches"], "series": json.dumps(data["series"]),
            })
            built += 1

    print(f"Price series built for {built} of {len(rows)} players.")


if __name__ == "__main__":
    main()
