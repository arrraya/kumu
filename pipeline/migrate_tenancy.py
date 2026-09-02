"""Introduce organisations and give every row an owner.

Kumu has run so far as a single implicit dataset. Selling it as software means
each client sees only their own players, squads and reports. The existing World
Cup data does not disappear into a private account: it becomes the PUBLIC
tenant — readable by everyone, and the reference population every client's
percentiles are measured against on day one.

A client therefore reads their own rows plus the public ones, and writes only
their own.
"""
import os

from sqlalchemy import create_engine, text

PUBLIC_SLUG = "public"

# Every table that holds client-owned data.
OWNED_TABLES = [
    "players",
    "teams",
    "squad_memberships",
    "market_series",
    "scouting_reports",
    "player_team_matches",
    "benchmarks",
]


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("Set DATABASE_URL first.")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS organizations (
                id SERIAL PRIMARY KEY,
                name VARCHAR NOT NULL,
                slug VARCHAR UNIQUE NOT NULL,
                -- 'public' holds the shared reference population; 'client' is a
                -- paying organisation with private data.
                kind VARCHAR NOT NULL DEFAULT 'client',
                -- Consent for the aggregate benchmark. Off unless granted:
                -- asking later is far harder than asking at sign-up.
                allows_aggregate BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                email VARCHAR UNIQUE NOT NULL,
                password_hash VARCHAR NOT NULL,
                full_name VARCHAR,
                role VARCHAR NOT NULL DEFAULT 'member',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS users_org_idx ON users (organization_id)"
        ))

        conn.execute(text("""
            INSERT INTO organizations (name, slug, kind, allows_aggregate)
            VALUES ('Kumu reference data', :slug, 'public', TRUE)
            ON CONFLICT (slug) DO NOTHING
        """), {"slug": PUBLIC_SLUG})

        public_id = conn.execute(
            text("SELECT id FROM organizations WHERE slug = :slug"), {"slug": PUBLIC_SLUG}
        ).scalar()

        for table in OWNED_TABLES:
            conn.execute(text(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS organization_id INTEGER"
            ))
            # Everything that predates tenancy belongs to the public tenant.
            conn.execute(text(
                f"UPDATE {table} SET organization_id = :oid WHERE organization_id IS NULL"
            ), {"oid": public_id})
            conn.execute(text(
                f"CREATE INDEX IF NOT EXISTS {table}_org_idx ON {table} (organization_id)"
            ))

        counts = {
            t: conn.execute(text(
                f"SELECT count(*) FROM {t} WHERE organization_id = :oid"
            ), {"oid": public_id}).scalar()
            for t in OWNED_TABLES
        }

    print(f"Public tenant id: {public_id}")
    for t, n in counts.items():
        print(f"  {t:22s} {n}")


if __name__ == "__main__":
    main()
