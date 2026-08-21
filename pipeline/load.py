"""Load pipeline outputs into Kumu's Postgres database.

Reads DATABASE_URL from the environment (Railway public URL).
- Replaces the players table content with World Cup 2022 players (>=180 min for quality).
- Creates/refreshes a `benchmarks` table with real percentile data.

Honesty notes (contract E.5):
- market_value is Kumu-ESTIMATED from performance index (declared, not scraped).
- age is a neutral estimate (26) until a birth-date source is connected.
"""
import hashlib
import os
import pickle

from sqlalchemy import create_engine, text
from statsbombpy import sb
from tqdm import tqdm

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
MIN_MINUTES = 180          # at least ~2 full matches for stable metrics
ESTIMATED_AGE = 26         # neutral placeholder until a birth-date source exists
LEAGUE_LABEL = "World Cup 2022"
# Namespaces the identifier by source, so a future provider feed can coexist
# with this one without ids colliding.
SOURCE_PREFIX = "wc2022"


def estimate_market_value(perf_index: dict | None) -> float:
    """Kumu-estimated market value (euros) derived from performance index.

    Simple, transparent model: base 5M, up to ~80M for elite index values,
    small bonus for positive trend. This is a product feature (declared
    estimate), not scraped market data.
    """
    if not perf_index:
        return 5_000_000.0
    value = perf_index["value"]            # 0-100
    trend = perf_index.get("trend", 0.0)
    base = 5_000_000 + (max(0.0, value - 50) ** 1.8) * 90_000
    trend_bonus = max(0.0, trend) * 2_000_000
    return round(min(base + trend_bonus, 120_000_000), 0)


def fetch_player_countries() -> dict:
    """Map player full name -> (nickname, country) from all match lineups."""
    cache_path = os.path.join(CACHE_DIR, "lineups.pkl")
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    matches = sb.matches(competition_id=43, season_id=106)
    mapping: dict = {}
    for _, m in tqdm(list(matches.iterrows()), desc="Downloading lineups"):
        try:
            lu = sb.lineups(match_id=m["match_id"])
        except Exception:
            continue
        for team_df in lu.values():
            for _, row in team_df.iterrows():
                nickname = row.get("player_nickname")
                # pandas NaN is truthy-ish; only accept real non-empty strings
                if not isinstance(nickname, str) or not nickname.strip():
                    nickname = row["player_name"]
                country = row.get("country")
                if not isinstance(country, str):
                    country = None
                mapping[row["player_name"]] = (nickname, country)
    with open(cache_path, "wb") as f:
        pickle.dump(mapping, f)
    return mapping


# Reuse the position taxonomy from benchmarks.py
from benchmarks import POSITION_MAP  # noqa: E402


def stable_external_id(full_name: str) -> str:
    """Identifier that stays the same across runs.

    This used to be built from hash(full_name), but Python randomises string
    hashing per process, so every run minted new ids for the same players.
    That made incremental updates impossible — the only way to refresh data was
    to wipe the table, which also destroyed squads and saved reports. A digest
    is deterministic, so the same player keeps his id and can simply be updated.
    """
    digest = hashlib.sha1(full_name.strip().lower().encode("utf-8")).hexdigest()
    return f"{SOURCE_PREFIX}_{digest[:16]}"


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("Set DATABASE_URL to Railway's public Postgres URL first.")

    with open(os.path.join(CACHE_DIR, "player_metrics.pkl"), "rb") as f:
        players = pickle.load(f)
    with open(os.path.join(CACHE_DIR, "benchmarks.pkl"), "rb") as f:
        benchmarks = pickle.load(f)

    names = fetch_player_countries()
    engine = create_engine(db_url)

    rows = []
    for full_name, p in players.items():
        if p["minutes"] < MIN_MINUTES:
            continue
        pos = POSITION_MAP.get(p.get("position") or "")
        if not pos or pos == "GK":
            continue
        nickname, country = names.get(full_name, (full_name, None))
        rows.append({
            "external_id": stable_external_id(full_name),
            "name": nickname,
            "age": ESTIMATED_AGE,
            "position": pos,
            "nationality": country or p.get("team"),
            "current_team": p.get("team"),
            "market_value": estimate_market_value(p.get("performance_index")),
            "performance_index": p.get("performance_index"),
            "metrics": p["metrics"],
            "performance_history": p["performance_history"],
        })

    print(f"Players to load: {len(rows)}")

    import json
    with engine.begin() as conn:
        # Refresh in place instead of wiping. The old version deleted every
        # player on each run, which cascaded into squad_memberships and took
        # user-built squads and saved reports with it. With a stable
        # external_id the same player can simply be updated, so a future
        # provider feed can refresh data without destroying anything.
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS players_external_id_key "
            "ON players (external_id)"
        ))

        for r in rows:
            conn.execute(text("""
                INSERT INTO players (external_id, name, age, position, nationality,
                                     current_team, market_value, performance_index,
                                     metrics, performance_history)
                VALUES (:external_id, :name, :age, :position, :nationality,
                        :current_team, :market_value,
                        CAST(:performance_index AS JSON),
                        CAST(:metrics AS JSON),
                        CAST(:performance_history AS JSON))
                ON CONFLICT (external_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    age = EXCLUDED.age,
                    position = EXCLUDED.position,
                    nationality = EXCLUDED.nationality,
                    current_team = EXCLUDED.current_team,
                    market_value = EXCLUDED.market_value,
                    performance_index = EXCLUDED.performance_index,
                    metrics = EXCLUDED.metrics,
                    performance_history = EXCLUDED.performance_history,
                    updated_at = NOW()
            """), {
                **r,
                "performance_index": json.dumps(r["performance_index"]),
                "metrics": json.dumps(r["metrics"]),
                "performance_history": json.dumps(r["performance_history"]),
            })

        # benchmarks table: one row holding the full JSON (simple + sufficient)
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS benchmarks (
                id SERIAL PRIMARY KEY,
                label VARCHAR UNIQUE,
                data JSON,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text("DELETE FROM benchmarks WHERE label = :label"),
                     {"label": LEAGUE_LABEL})
        conn.execute(text("INSERT INTO benchmarks (label, data) VALUES (:label, CAST(:data AS JSON))"),
                     {"label": LEAGUE_LABEL, "data": json.dumps(benchmarks)})

    print("Load complete: players + benchmarks written to database.")


if __name__ == "__main__":
    main()
