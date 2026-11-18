"""
Kumü — a throwaway database with the real schema
=================================================

Not a test file. Imported by the ones that need a database.

    export KUMU_TEST_DATABASE_URL=postgresql://…/kumu_test
    python3 tests/test_queries.py

WHY
---
Two breakages reached production in one afternoon and both were verified
first. A blind search-and-replace turned `p.performance_index IS NOT NULL`
into `p.(performance_index->>'value') IS NOT NULL` in three queries, and
all 101 reports still generated cleanly in the check — because
`_query_db` fails softly with no database, so the broken SQL never ran.
The budget was exercised against a club invented for the test, carrying a
million, while the endpoint's own eight A-League clubs carry none.

`tests/test_sql.py` now parses every query with libpg_query, which
catches a statement that is not SQL. It cannot catch one that is valid
and asks the wrong question. Only an engine can, and only rows of the
right shape make the answer mean anything.

So this builds the schema from the models the application itself uses —
not a copy, which would drift — and seeds the shapes that have actually
produced defects: a club with no budget, a player with a log too short to
rate, a goalkeeper the source carries no goalkeeping for, a position with
no benchmark, and two tenants whose numbers must not mix.

SAFETY
------
It creates and drops tables. Two guards stand between it and anything
real: the URL must differ from DATABASE_URL, and the database name must
contain "test". Both, every time, with no override. A fixture that can be
pointed at production is a fixture that eventually is.
"""

import os
import sys
from contextlib import contextmanager
from urllib.parse import urlparse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "backend"))

ENV = "KUMU_TEST_DATABASE_URL"

SKIP_REASON = (
    "%s is not set. Point it at a throwaway Postgres whose database name "
    "contains 'test' and these run; without one they skip, because a check "
    "that silently does nothing is worse than no check." % ENV
)


class UnsafeTestDatabase(RuntimeError):
    """Raised rather than touching something that might not be disposable."""


def test_url():
    """The URL, or None. Raises if it is set to something dangerous."""
    url = os.environ.get(ENV)
    if not url:
        return None

    produccion = os.environ.get("DATABASE_URL")
    if produccion and url.strip() == produccion.strip():
        raise UnsafeTestDatabase(
            "%s is the same as DATABASE_URL. This fixture drops tables." % ENV)

    nombre = (urlparse(url).path or "").lstrip("/")
    if "test" not in nombre.lower():
        raise UnsafeTestDatabase(
            "the database in %s is %r, and this fixture only runs against a "
            "name containing 'test'. It drops tables." % (ENV, nombre))
    return url


def available():
    try:
        return test_url() is not None
    except UnsafeTestDatabase:
        raise


@contextmanager
def database():
    """Schema, seed, and a sessionmaker. Everything dropped on the way out.

    Points the application's own engine at the test URL before importing
    it. `app.db.database` builds `engine` and `SessionLocal` at import
    time from settings, so this has to happen first - and it is why the
    imports below are where they are rather than at the top of the file.
    """
    url = test_url()
    if url is None:
        raise RuntimeError(SKIP_REASON)

    previo = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        from app.db import models
        from app.db.database import Base, SessionLocal, engine

        # Base here is the declarative base the models are declared on, so
        # the schema is the application's, not a transcription of it that
        # could fall behind.
        assert models.Player.__table__.metadata is Base.metadata

        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            seed(db, models)
            yield db, models
        finally:
            db.close()
            Base.metadata.drop_all(bind=engine)
            engine.dispose()
    finally:
        if previo is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previo


# ---------------------------------------------------------------- the shapes

def index(value, scaled=True):
    return {"value": value, "raw_value": value, "trend": 0.1,
            "volatility": 0.12, "confidence": 0.88, "scaled": scaled}


def log(*ratings):
    return [{"match_id": str(i), "rating": r, "minutes": 90.0}
            for i, r in enumerate(ratings)]


OUTFIELD = {
    "passing": {"completion_rate": 0.78, "key_passes_per_90": 1.2},
    "shooting": {"shots_per_90": 3.1, "goals_per_90": 0.96},
    "defensive": {"tackles_per_90": 0.96},
}


def seed(db, models):
    """The populations these tests ask questions of.

    Every row here exists because something about its shape has produced a
    wrong answer at some point: an absent budget, a log too short to rate,
    a keeper with no goalkeeping, a tenant whose players must not appear in
    another tenant's percentiles.
    """
    publica = models.Organization(
        id=1, name="Kumü Reference", slug="public", kind="public",
        allows_aggregate=True)
    inquilino = models.Organization(
        id=23, name="A-League Men", slug="a-league", kind="client",
        allows_aggregate=False)
    otro = models.Organization(
        id=99, name="Otro Cliente", slug="otro", kind="client",
        allows_aggregate=False)
    db.add_all([publica, inquilino, otro])
    db.flush()

    db.add_all([
        # A club that states its means.
        models.Team(id=7, organization_id=1, external_id="t_dortmund",
                    name="Borussia Dortmund", league="Bundesliga",
                    country="Germany", budget=350_000_000.0,
                    formation="4-2-3-1", team_type="club",
                    playing_style={"possession": 0.58,
                                   "pressing_intensity": 0.72},
                    requirements={"positions_needed": ["ST"]}),
        # A club loaded from a match feed, which records matches and not
        # finances. Eight of these arrived with the A-League and every
        # report generated against one of them returned 500.
        models.Team(id=188, organization_id=23, external_id="t_brisbane",
                    name="Brisbane Roar FC", league="A-League Men",
                    country="Australia", budget=None, formation="4-3-3",
                    team_type="club", playing_style=None, requirements=None),
        models.Team(id=189, organization_id=23, external_id="t_victory",
                    name="Melbourne Victory FC", league="A-League Men",
                    country="Australia", budget=None, formation="4-4-2",
                    team_type="club", playing_style=None, requirements=None),
        # Not a club. In this table because its squad is, and nobody signs
        # a player to it.
        models.Team(id=300, organization_id=1, external_id="t_belgium",
                    name="Belgium", league="International", country="Belgium",
                    budget=None, formation="3-4-2-1", team_type="national",
                    playing_style=None, requirements=None),
        # Another tenant's club, which the first tenant must never read.
        models.Team(id=400, organization_id=99, external_id="t_otro",
                    name="Club Ajeno", league="Liga Ajena", country="Chile",
                    budget=10_000_000.0, formation="4-4-2", team_type="club",
                    playing_style=None, requirements=None),
    ])

    jugadores = [
        # Enough same-position peers for a ranking to exist at all: the
        # percentile declines below five, which is most of the fixtures
        # anyone writes by hand.
        models.Player(id=2533, organization_id=23, external_id="p_jelacic",
                      name="K. Jelacic", age=22, position="ST",
                      nationality="Australia",
                      current_team="Brisbane Roar FC", market_value=None,
                      performance_index=index(71.0), metrics=OUTFIELD,
                      performance_history=log(7.0, 7.3, 7.6, 7.9)),
    ]
    for n, value in enumerate([58.0, 62.5, 66.0, 69.5, 74.0, 77.5, 81.0], 1):
        jugadores.append(models.Player(
            id=2540 + n, organization_id=23, external_id="p_st_%d" % n,
            name="Delantero %d" % n, age=24, position="ST",
            nationality="Australia", current_team="Melbourne Victory FC",
            market_value=None, performance_index=index(value),
            metrics=OUTFIELD, performance_history=log(7.0, 7.1, 7.2, 7.1, 7.0)))

    jugadores += [
        # A log too short to rate: 85 of the 101 real players are here.
        models.Player(id=2600, organization_id=23, external_id="p_corto",
                      name="J. Barnett", age=25, position="CM",
                      nationality="Australia",
                      current_team="Brisbane Roar FC", market_value=None,
                      performance_index=index(64.0), metrics=OUTFIELD,
                      performance_history=log(7.1, 6.9)),
        # A keeper the source carries no goalkeeping for. Kumü declines to
        # rate him, and the refusal mentions the word "percentile" without
        # claiming one - which is what the verifier objected to 24 times.
        models.Player(id=2601, organization_id=23, external_id="p_arquero",
                      name="A. Paulsen", age=23, position="GK",
                      nationality="New Zealand",
                      current_team="Brisbane Roar FC", market_value=None,
                      performance_index=None,
                      metrics={"passing": {"completion_rate": 0.81}},
                      performance_history=log(6.8, 7.0, 7.1)),
        # No index and no price: nothing to rank, nothing to value.
        models.Player(id=2602, organization_id=23, external_id="p_sin_nada",
                      name="Sin Indice", age=None, position="CB",
                      nationality="Australia",
                      current_team="Brisbane Roar FC", market_value=None,
                      performance_index=None, metrics={},
                      performance_history=[]),
        # The other tenant's player, at an index that would change every
        # percentile in the first tenant if the scoping leaked.
        models.Player(id=2700, organization_id=99, external_id="p_ajeno",
                      name="Jugador Ajeno", age=27, position="ST",
                      nationality="Chile", current_team="Club Ajeno",
                      market_value=5_000_000.0,
                      performance_index=index(99.0), metrics=OUTFIELD,
                      performance_history=log(8.9, 9.1, 9.0, 8.8, 9.2)),
    ]
    db.add_all(jugadores)
    db.commit()
