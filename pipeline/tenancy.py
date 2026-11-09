"""Which tenant a pipeline script is allowed to touch.

Kumu is multi-tenant: the public reference population and every client's own
data live in the same tables, separated only by organization_id. The seeding
and derivation scripts rewrite the public set, and for a long time they said
so only in their names. Their statements said nothing:

    DELETE FROM scouting_reports
    DELETE FROM market_series
    DELETE FROM teams WHERE team_type = 'club' OR team_type IS NULL
    UPDATE teams SET team_type = 'club' WHERE team_type IS NULL

On a single-tenant database all four are correct. On this one they mean that
re-seeding the public catalogue deletes whatever a client has loaded. The
assumption held on the day it was written and stops holding on the day Kumu
does the thing it was built to do.

Nothing here defaults to organization 1. Guessing the tenant is the same
unscoped assumption wearing a number, so an absent public organization stops
the script instead.
"""
from sqlalchemy import text

# As backend/app/core/security.py defines it.
PUBLIC_SLUG = "public"


def resolve_public_org(conn) -> int:
    """The public tenant's id, or refuse to run."""
    row = conn.execute(
        text("SELECT id FROM organizations WHERE slug = :slug"),
        {"slug": PUBLIC_SLUG},
    ).fetchone()
    if not row:
        raise SystemExit(
            "No organization with slug '%s'. Run migrate_tenancy.py first; "
            "this script will not guess which tenant it may rewrite."
            % PUBLIC_SLUG
        )
    return int(row[0])
