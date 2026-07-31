"""Seed Kumu's teams table with curated clubs across tiers and markets.

Honesty note: tactical profiles, budgets and expected_index are DECLARED
CURATION based on well-known club identities and standing — not scraped data.
`expected_index` is the performance level a club realistically targets, and is
what lets the matcher ask "is this player at this club's level?".
"""
import json
import os

from sqlalchemy import create_engine, text

# name, league, country, budget(M), formation, possession, pressing, positions, expected_index
CLUBS = [
    # ---- Elite
    ("Manchester City", "Premier League", "England", 900, "4-3-3", 0.68, 0.78, ["CAM","CM","RW","LW"], 80),
    ("Real Madrid", "La Liga", "Spain", 800, "4-3-3", 0.56, 0.62, ["CM","CAM","ST","CB"], 80),
    ("FC Barcelona", "La Liga", "Spain", 500, "4-3-3", 0.71, 0.74, ["CM","CAM","LW","RB"], 79),
    ("Bayern Munich", "Bundesliga", "Germany", 650, "4-2-3-1", 0.64, 0.80, ["CAM","RW","CDM","CB"], 79),
    ("Liverpool", "Premier League", "England", 700, "4-3-3", 0.58, 0.88, ["ST","RW","LW","CM"], 79),
    ("Paris Saint-Germain", "Ligue 1", "France", 750, "4-3-3", 0.62, 0.70, ["ST","LW","CDM","CB"], 79),

    # ---- Strong
    ("Atletico Madrid", "La Liga", "Spain", 400, "3-5-2", 0.45, 0.55, ["CB","CDM","ST","LB"], 73),
    ("Borussia Dortmund", "Bundesliga", "Germany", 350, "4-2-3-1", 0.55, 0.76, ["CAM","LW","ST","CDM"], 72),
    ("Inter Milan", "Serie A", "Italy", 300, "3-5-2", 0.52, 0.60, ["CB","RB","ST","CM"], 72),
    ("Napoli", "Serie A", "Italy", 280, "4-3-3", 0.57, 0.68, ["CM","LW","ST","CB"], 71),
    ("Benfica", "Primeira Liga", "Portugal", 180, "4-2-3-1", 0.58, 0.70, ["CAM","ST","CB","RB"], 69),
    ("Ajax", "Eredivisie", "Netherlands", 150, "4-3-3", 0.66, 0.74, ["CM","LW","CB","RB"], 68),

    # ---- Mid
    ("Sevilla", "La Liga", "Spain", 130, "4-3-3", 0.54, 0.62, ["CM","RW","CB","LB"], 66),
    ("Olympique Lyonnais", "Ligue 1", "France", 120, "4-3-3", 0.56, 0.64, ["CAM","LW","CDM","LB"], 65),
    ("Fiorentina", "Serie A", "Italy", 110, "4-2-3-1", 0.55, 0.61, ["CAM","ST","CM","RB"], 65),
    ("Real Betis", "La Liga", "Spain", 100, "4-2-3-1", 0.57, 0.60, ["CAM","LW","CDM","CB"], 64),
    ("Feyenoord", "Eredivisie", "Netherlands", 80, "4-3-3", 0.58, 0.72, ["ST","CM","LB","CB"], 63),

    # ---- Developing / other markets
    ("Al Hilal", "Saudi Pro League", "Saudi Arabia", 250, "4-2-3-1", 0.55, 0.55, ["ST","CAM","CB","CDM"], 64),
    ("CF Monterrey", "Liga MX", "Mexico", 70, "4-3-3", 0.53, 0.60, ["ST","CM","RB","CB"], 61),
    ("LA Galaxy", "MLS", "United States", 60, "4-2-3-1", 0.52, 0.58, ["CAM","ST","CB","LB"], 59),
]


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("Set DATABASE_URL first (Railway public Postgres URL).")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM scouting_reports"))
        conn.execute(text("DELETE FROM player_team_matches"))
        conn.execute(text("DELETE FROM teams"))

        for i, (name, league, country, budget_m, formation, poss, press, positions, expected) in enumerate(CLUBS, start=1):
            playing_style = {
                "possession": poss,
                "pressing_intensity": press,
                "defensive_line": "high" if press > 0.72 else "medium" if press > 0.58 else "low",
                "attacking": poss > 0.55,
                "high_press": press > 0.72,
            }
            requirements = {
                "positions": positions,
                "expected_index": expected,
                "performance": {
                    "min_pass_completion": round(0.70 + (expected - 55) * 0.006, 2),
                    "min_defensive_actions": round(2.0 + (expected - 55) * 0.06, 1),
                },
                "style": {"possession": poss > 0.6, "high_press": press > 0.72},
            }
            conn.execute(text("""
                INSERT INTO teams (external_id, name, league, country, budget, formation,
                                   playing_style, requirements, created_at)
                VALUES (:external_id, :name, :league, :country, :budget, :formation,
                        CAST(:playing_style AS JSON), CAST(:requirements AS JSON), NOW())
            """), {
                "external_id": f"club_{i:03d}", "name": name, "league": league,
                "country": country, "budget": budget_m * 1_000_000, "formation": formation,
                "playing_style": json.dumps(playing_style),
                "requirements": json.dumps(requirements),
            })

    print(f"Seeded {len(CLUBS)} clubs across tiers "
          f"(expected_index {min(c[8] for c in CLUBS)}–{max(c[8] for c in CLUBS)}).")


if __name__ == "__main__":
    main()
