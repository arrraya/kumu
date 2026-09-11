"""Applying tenant scope to ORM queries.

The raw queries are guarded in `scoped.py`, which refuses SQL that forgets the
filter. ORM queries cannot be policed the same way — there is no text to
inspect — so the defence here is convenience: scoping through these helpers is
shorter than writing the filter by hand, which is what makes it the path taken.

Two shapes, because they fail differently:

* a LISTING that forgets the scope shows another client's rows;
* a FETCH BY ID that forgets it lets one client read a specific row of
  another's by guessing a number, which is worse.
"""
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Query


class MissingScopeError(RuntimeError):
    """Raised when a query would run without knowing whose data it may read.

    This used to return nothing instead of raising, which was safe but silent:
    a forgotten scope looked exactly like a client with no data. Empty results
    are indistinguishable from a bug, so the bug now announces itself.
    """


def scope(query: Query, model: Any, org_ids: Optional[Sequence[int]]) -> Query:
    """Restrict a listing to the given tenants.

    An empty scope yields nothing rather than everything: a caller that failed
    to resolve its scope has a bug, and the safe reading of a bug is silence.
    """
    if not org_ids:
        raise MissingScopeError(
            f"A {model.__name__} listing was built without a tenant scope. "
            "Pass org_ids from the endpoint rather than relaxing this check."
        )
    return query.filter(model.organization_id.in_(list(org_ids)))


def get_scoped(db, model: Any, row_id: Any, org_ids: Optional[Sequence[int]]):
    """Fetch one row by id, but only if it belongs to the caller.

    Returns None for a row owned by someone else, so the caller's existing
    "not found" handling covers it — a client should not be able to tell
    another tenant's ids apart from ids that do not exist.
    """
    if not org_ids:
        raise MissingScopeError(
            f"A {model.__name__} was fetched by id without a tenant scope."
        )
    if row_id is None:
        return None
    return (
        db.query(model)
        .filter(model.id == row_id, model.organization_id.in_(list(org_ids)))
        .first()
    )


def owned_by(row: Any, org_id: Optional[int]) -> bool:
    """Whether this row may be modified by that organisation.

    Reading and writing are not symmetrical. A client reads its own rows AND
    the public reference set, but may only ever write its own: the public data
    is shared by every tenant, so letting one client edit it would break the
    baseline everyone else measures against.
    """
    if row is None or not org_id:
        return False
    return getattr(row, "organization_id", None) == org_id
