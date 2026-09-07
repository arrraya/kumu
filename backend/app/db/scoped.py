"""Raw queries that cannot forget which tenants they may read.

The matcher and the report generator reach for raw SQL because they compute
percentiles and squad comparisons that do not map cleanly onto the ORM. Those
queries bypass every filter the ORM would apply, so they are exactly the ones
that would quietly mix one client's players into another client's numbers —
worse than showing too much, because the figures would simply be wrong.

Two guards make that hard to do by accident:

* the scope is a required argument, so omitting it raises instead of widening;
* the SQL is rejected unless it actually references :org_ids, so a query that
  forgets the filter fails loudly the first time it runs.
"""
from typing import Any, Dict, List, Sequence

from sqlalchemy import bindparam, text

from app.db.database import SessionLocal

SCOPE_PARAM = "org_ids"


class UnscopedQueryError(RuntimeError):
    """Raised when a raw query would read across tenants."""


def scoped_query(sql: str, params: Dict[str, Any], org_ids: Sequence[int]) -> List[Any]:
    """Run a read-only query restricted to `org_ids`.

    The SQL must filter on the scope itself, e.g.
        WHERE p.organization_id IN :org_ids
    """
    if not org_ids:
        raise UnscopedQueryError(
            "No tenant scope supplied. An empty scope is a bug, not a request "
            "to read everything."
        )
    if f":{SCOPE_PARAM}" not in sql:
        raise UnscopedQueryError(
            f"This query does not reference :{SCOPE_PARAM}, so it would read "
            "across tenants. Add the filter rather than relaxing this check."
        )

    statement = text(sql).bindparams(bindparam(SCOPE_PARAM, expanding=True))
    merged = dict(params or {})
    merged[SCOPE_PARAM] = list(org_ids)

    session = SessionLocal()
    try:
        return session.execute(statement, merged).fetchall()
    finally:
        session.close()
