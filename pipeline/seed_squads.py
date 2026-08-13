"""Create the squad membership relation and populate it with national teams.

Kumu had no way to say who belongs to a team: squad lookups compared
players.current_team against the club name as strings, so no club ever had a
squad. This introduces a proper relation that three sources can fill without
changing the model: national squads (real, from this data), user-built squads,
and a future provider API.

National teams are stored as teams with team_type='national' so their squads
are real, while transfer destinations stay restricted to clubs.
"""
import os

from sqlalchemy import create_engine, text


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("Set DATABASE_URL first (Railway public Postgres URL).")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE teams ADD COLUMN IF NOT EXISTS team_type VARCHAR DEFAULT 'club'"
        ))
        conn.execute(text("UPDATE teams SET team_type = 'club' WHERE team_type IS NULL"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS squad_memberships (
                id SERIAL PRIMARY KEY,
                player_id INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
                team_id INTEGER NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
                -- where this link came from: national | user | api
                source VARCHAR NOT NULL DEFAULT 'user',
                created_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (player_id, team_id, source)
            )
        """))

        # National teams derived from the players themselves — no invention.
        nations = [
            r[0] for r in conn.execute(text(
                "SELECT DISTINCT current_team FROM players "
                "WHERE current_team IS NOT NULL AND current_team <> '' ORDER BY current_team"
            )).fetchall()
        ]

        for nation in nations:
            conn.execute(text("""
                INSERT INTO teams (external_id, name, league, country, budget,
                                   formation, playing_style, requirements,
                                   team_type, created_at)
                VALUES (:external_id, :name, 'International', :name, 0,
                        '4-3-3', CAST('{}' AS JSON), CAST('{}' AS JSON),
                        'national', NOW())
                ON CONFLICT (external_id) DO NOTHING
            """), {"external_id": f"nat_{nation[:40]}", "name": nation})

        conn.execute(text("DELETE FROM squad_memberships WHERE source = 'national'"))
        result = conn.execute(text("""
            INSERT INTO squad_memberships (player_id, team_id, source)
            SELECT p.id, t.id, 'national'
            FROM players p
            JOIN teams t ON t.name = p.current_team AND t.team_type = 'national'
            ON CONFLICT DO NOTHING
        """))

        counts = conn.execute(text("""
            SELECT t.name, COUNT(m.id) AS squad
            FROM teams t LEFT JOIN squad_memberships m ON m.team_id = t.id
            WHERE t.team_type = 'national'
            GROUP BY t.name ORDER BY squad DESC LIMIT 5
        """)).fetchall()

    print(f"National teams: {len(nations)}")
    print("Planteles mas grandes:")
    for name, squad in counts:
        print(f"  {name:28s} {squad}")


if __name__ == "__main__":
    main()
