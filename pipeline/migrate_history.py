"""Turn squad membership from a snapshot into a record.

Until now a row meant "is in this squad", and moving a player deleted the old
row. That erases exactly the thing Kumu will need to prove its matcher works:
who went where, and how it went afterwards. A transfer is only visible if the
previous spell is kept rather than overwritten.

With `left_at`, a row means "was here from X until Y", and an open end means the
spell is current. Nothing about today's behaviour changes — every existing row
becomes an open spell — but from now on the history accumulates. Adding this
later would mean starting the record from scratch on that day.
"""
import os

from sqlalchemy import create_engine, text


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("Set DATABASE_URL first.")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("""
            ALTER TABLE squad_memberships
            ADD COLUMN IF NOT EXISTS joined_at TIMESTAMP DEFAULT NOW()
        """))
        conn.execute(text("""
            ALTER TABLE squad_memberships
            ADD COLUMN IF NOT EXISTS left_at TIMESTAMP
        """))
        # Where the spell began is better known than "when the row was written",
        # so existing rows inherit created_at.
        conn.execute(text("""
            UPDATE squad_memberships
            SET joined_at = COALESCE(created_at, NOW())
            WHERE joined_at IS NULL
        """))

        # The old uniqueness rule forbade a player ever returning to a club he
        # had left, which happens often enough in football to matter. Uniqueness
        # now applies only to OPEN spells: a player may have many closed spells
        # at a club, but only one current one.
        conn.execute(text("""
            ALTER TABLE squad_memberships
            DROP CONSTRAINT IF EXISTS squad_memberships_player_id_team_id_source_key
        """))
        conn.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS squad_current_spell_key
            ON squad_memberships (player_id, team_id, source)
            WHERE left_at IS NULL
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS squad_open_idx
            ON squad_memberships (team_id) WHERE left_at IS NULL
        """))

        abiertas = conn.execute(text(
            "SELECT count(*) FROM squad_memberships WHERE left_at IS NULL"
        )).scalar()
        cerradas = conn.execute(text(
            "SELECT count(*) FROM squad_memberships WHERE left_at IS NOT NULL"
        )).scalar()

    print(f"pertenencias vigentes: {abiertas}")
    print(f"pertenencias cerradas: {cerradas}")


if __name__ == "__main__":
    main()
