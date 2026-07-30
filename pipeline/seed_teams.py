"""Seed Kumu's teams table with curated club profiles.

Honesty note: tactical values (possession, pressing intensity, priority positions)
are DECLARED CURATION based on well-known club identities, not scraped data.
They give the matcher real signal to work with; replace with licensed data later.
"""
import json
import os

from sqlalchemy import create_engine, text

TEAMS = [
    {
        "name": "Manchester City", "league": "Premier League", "country": "England",
        "budget": 900_000_000, "formation": "4-3-3",
        "playing_style": {"possession": 0.68, "pressing_intensity": 0.78,
                          "defensive_line": "high", "attacking": True, "high_press": True},
        "requirements": {"positions": ["CAM", "CM", "RW", "LW"],
                         "performance": {"min_pass_completion": 0.85, "min_defensive_actions": 2.5},
                         "style": {"possession": True, "high_press": True}},
    },
    {
        "name": "Liverpool", "league": "Premier League", "country": "England",
        "budget": 700_000_000, "formation": "4-3-3",
        "playing_style": {"possession": 0.58, "pressing_intensity": 0.88,
                          "defensive_line": "high", "attacking": True, "high_press": True},
        "requirements": {"positions": ["ST", "RW", "LW", "CM"],
                         "performance": {"min_pass_completion": 0.78, "min_defensive_actions": 3.5},
                         "style": {"counter_press": True, "vertical": True}},
    },
    {
        "name": "Real Madrid", "league": "La Liga", "country": "Spain",
        "budget": 800_000_000, "formation": "4-3-3",
        "playing_style": {"possession": 0.56, "pressing_intensity": 0.62,
                          "defensive_line": "medium", "attacking": True, "high_press": False},
        "requirements": {"positions": ["CM", "CAM", "ST", "CB"],
                         "performance": {"min_pass_completion": 0.82, "min_defensive_actions": 2.8},
                         "style": {"transition": True, "individual_quality": True}},
    },
    {
        "name": "FC Barcelona", "league": "La Liga", "country": "Spain",
        "budget": 500_000_000, "formation": "4-3-3",
        "playing_style": {"possession": 0.71, "pressing_intensity": 0.74,
                          "defensive_line": "high", "attacking": True, "high_press": True},
        "requirements": {"positions": ["CM", "CAM", "LW", "RB"],
                         "performance": {"min_pass_completion": 0.87, "min_defensive_actions": 2.2},
                         "style": {"possession": True, "positional_play": True}},
    },
    {
        "name": "Atletico Madrid", "league": "La Liga", "country": "Spain",
        "budget": 400_000_000, "formation": "3-5-2",
        "playing_style": {"possession": 0.45, "pressing_intensity": 0.55,
                          "defensive_line": "low", "attacking": False, "high_press": False},
        "requirements": {"positions": ["CB", "CDM", "ST", "LB"],
                         "performance": {"min_pass_completion": 0.75, "min_defensive_actions": 5.0},
                         "style": {"compact_block": True, "counter_attack": True}},
    },
    {
        "name": "Bayern Munich", "league": "Bundesliga", "country": "Germany",
        "budget": 650_000_000, "formation": "4-2-3-1",
        "playing_style": {"possession": 0.64, "pressing_intensity": 0.80,
                          "defensive_line": "high", "attacking": True, "high_press": True},
        "requirements": {"positions": ["CAM", "RW", "CDM", "CB"],
                         "performance": {"min_pass_completion": 0.84, "min_defensive_actions": 3.0},
                         "style": {"possession": True, "high_press": True}},
    },
    {
        "name": "Borussia Dortmund", "league": "Bundesliga", "country": "Germany",
        "budget": 350_000_000, "formation": "4-2-3-1",
        "playing_style": {"possession": 0.55, "pressing_intensity": 0.76,
                          "defensive_line": "medium", "attacking": True, "high_press": True},
        "requirements": {"positions": ["CAM", "LW", "ST", "CDM"],
                         "performance": {"min_pass_completion": 0.79, "min_defensive_actions": 3.2},
                         "style": {"young_talent": True, "vertical": True}},
    },
    {
        "name": "Inter Milan", "league": "Serie A", "country": "Italy",
        "budget": 300_000_000, "formation": "3-5-2",
        "playing_style": {"possession": 0.52, "pressing_intensity": 0.60,
                          "defensive_line": "medium", "attacking": False, "high_press": False},
        "requirements": {"positions": ["CB", "RB", "ST", "CM"],
                         "performance": {"min_pass_completion": 0.80, "min_defensive_actions": 4.0},
                         "style": {"wing_backs": True, "compact_block": True}},
    },
]


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("Set DATABASE_URL first (Railway public Postgres URL).")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        # dependent rows first (FK), then teams
        conn.execute(text("DELETE FROM scouting_reports"))
        conn.execute(text("DELETE FROM player_team_matches"))
        conn.execute(text("DELETE FROM teams"))

        for i, t in enumerate(TEAMS, start=1):
            conn.execute(text("""
                INSERT INTO teams (external_id, name, league, country, budget, formation,
                                   playing_style, requirements, created_at)
                VALUES (:external_id, :name, :league, :country, :budget, :formation,
                        CAST(:playing_style AS JSON), CAST(:requirements AS JSON), NOW())
            """), {
                "external_id": f"club_{i:03d}",
                "name": t["name"], "league": t["league"], "country": t["country"],
                "budget": t["budget"], "formation": t["formation"],
                "playing_style": json.dumps(t["playing_style"]),
                "requirements": json.dumps(t["requirements"]),
            })

    print(f"Seeded {len(TEAMS)} teams with tactical profiles.")


if __name__ == "__main__":
    main()
