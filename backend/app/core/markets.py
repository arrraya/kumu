"""What a point of performance is worth, market by market.

Kumü is meant to serve clubs in Latin America and in Europe at once, and a
single anchor cannot do that. The old design priced every player against
European elite football, so a Chilean midfielder valued at €0.5M came out with
a 6632% return: sporting value in Premier League euros divided by a fee in
Chilean-league euros. Neither figure was false; comparing them was.

So each figure is computed on the scale of the market it belongs to:
  * the FEE, on the scale of the market the player is leaving;
  * the SPORTING VALUE, on the scale of the market the buyer plays in.

Same-market moves then show modest returns, as they should, and a move from a
smaller market to a bigger one shows a large return that finally means
something: the arbitrage between markets that Kumü exists to surface.

The anchors start as declared curation. They are designed to be replaced by
measurement: once a league has enough client-supplied observed values, its
anchor is derived from them and curation becomes the fallback. Values Kumü
estimated itself are never used for that, since they were computed from the
index and deriving an anchor from them would be circular.
"""
from typing import Any, Dict, Optional

# What an index of 100 is worth as sporting contribution, in euros, per market.
# Declared curation: orders of magnitude, not measurements, pending licensed
# data with observed transfer values.
CURATED_ANCHORS = {
    "premier_league": 50_000_000,
    "la_liga": 40_000_000,
    "serie_a": 38_000_000,
    "bundesliga": 38_000_000,
    "ligue_1": 30_000_000,
    "saudi_pro_league": 25_000_000,
    "eredivisie": 15_000_000,
    "primeira_liga": 15_000_000,
    "belgian_pro_league": 12_000_000,
    "mls": 10_000_000,
    "liga_mx": 10_000_000,
    "brasileirao": 10_000_000,
    "argentina_primera": 6_000_000,
    "chile_primera": 2_000_000,
    "a_league": 2_500_000,
    "international": 30_000_000,  # national-team data with no club market
}

DEFAULT_MARKET = "international"

# What `market_of` answers when it does not recognise a league. It used to
# answer DEFAULT_MARKET, and "international" is the World Cup scale at
# €30M per index 100 - the third highest anchor of fifteen. So the value
# standing for "Kumü does not know this market" was nearly the most
# expensive one in the table, and the 101 A-League players were priced on
# it: K. Jelacic came out at €11.2M in a league whose record fees are
# around €3M. Everything downstream moved with it - the ROI, the opening
# offer, the ceiling, the wage.
#
# None says what is true, and the sections that publish money now decline
# rather than guess. The market can be declared at load; see ClubRecord.
UNKNOWN_MARKET = None
MIN_OBSERVED_FOR_DERIVATION = 15

# Loose keywords, because league names arrive however each feed spells them.
_ALIASES = {
    "premier_league": ["premier league", "epl"],
    "la_liga": ["la liga", "laliga", "primera division de espana", "spain"],
    "serie_a": ["serie a"],
    "bundesliga": ["bundesliga"],
    "ligue_1": ["ligue 1", "ligue1"],
    "saudi_pro_league": ["saudi", "roshn"],
    "eredivisie": ["eredivisie"],
    "primeira_liga": ["primeira", "liga portugal"],
    "belgian_pro_league": ["belgian", "jupiler", "pro league"],
    "mls": ["mls", "major league soccer"],
    "liga_mx": ["liga mx"],
    "brasileirao": ["brasileir", "serie a brasil", "campeonato brasileiro"],
    "argentina_primera": ["argentina", "liga profesional"],
    "chile_primera": ["chile", "campeonato nacional"],
    # The 101 players Kumü actually holds from a client source, priced as
    # international at €30M per index 100 until this line existed.
    "a_league": ["a-league", "a league", "australia"],
}


def market_of(league: Optional[str], country: Optional[str] = None) -> str:
    """Resolve a free-text league (and optionally country) to a market key."""
    text = f"{league or ''} {country or ''}".lower()
    # Longer, more specific aliases first, so "serie a brasil" beats "serie a".
    pares = sorted(
        ((k, a) for k, lista in _ALIASES.items() for a in lista),
        key=lambda x: -len(x[1]),
    )
    for key, alias in pares:
        if alias in text:
            return key
    # Not DEFAULT_MARKET. See UNKNOWN_MARKET above for what that cost.
    return UNKNOWN_MARKET


def derive_anchor(db, market: str) -> Optional[Dict[str, Any]]:
    """Anchor measured from client-supplied values, or None if too few.

    Uses only players outside the public tenant, whose values were supplied
    rather than estimated, placed in a market through their current squad.
    """
    from sqlalchemy import text

    try:
        rows = db.execute(text("""
            SELECT p.market_value,
                   (p.performance_index->>'value')::float AS idx,
                   t.league, t.country
            FROM players p
            JOIN squad_memberships m ON m.player_id = p.id AND m.left_at IS NULL
            JOIN teams t ON t.id = m.team_id
            JOIN organizations o ON o.id = p.organization_id
            WHERE o.kind <> 'public'
              AND p.market_value IS NOT NULL AND p.market_value > 0
              AND (p.performance_index->>'value') IS NOT NULL
        """)).fetchall()
    except Exception:  # noqa: BLE001 - measurement is optional, curation remains
        return None

    implied = [
        float(v) / (float(idx) / 100.0)
        for v, idx, league, country in rows
        if idx and float(idx) > 0 and market_of(league, country) == market
    ]
    if len(implied) < MIN_OBSERVED_FOR_DERIVATION:
        return None

    implied.sort()
    median = implied[len(implied) // 2]
    return {"value": round(median, 0), "source": "observed", "samples": len(implied)}


def anchor_for(market: Optional[str], db=None) -> Optional[Dict[str, Any]]:
    """The anchor for a market, measured if possible, curated if not.

    None in, None out. `CURATED_ANCHORS.get(market, CURATED_ANCHORS[
    DEFAULT_MARKET])` used to turn an unrecognised market into the most
    expensive anchor on the list without anybody asking.
    """
    if market is None:
        return None
    if db is not None:
        measured = derive_anchor(db, market)
        if measured:
            return {**measured, "market": market}
    value = CURATED_ANCHORS.get(market)
    if value is None:
        return None
    return {
        "value": value,
        "source": "curated",
        "samples": 0,
        "market": market,
    }


def player_origin(db, player_id) -> Optional[Dict[str, Any]]:
    """Where a player plays now: his club's league, country and kind.

    Read through the open squad spell, the same record that tracks
    transfers. `players` has no league column of its own - which is worth
    saying plainly, because the report asked for one anyway and got None
    every time. See `_assess_adaptation_risk`.
    """
    from sqlalchemy import text

    try:
        row = db.execute(text("""
            SELECT t.league, t.country, t.team_type
            FROM squad_memberships m JOIN teams t ON t.id = m.team_id
            WHERE m.player_id = :pid AND m.left_at IS NULL
            ORDER BY (t.team_type = 'club') DESC
            LIMIT 1
        """), {"pid": int(player_id)}).fetchone()
    except Exception:  # noqa: BLE001
        return None
    if not row:
        return None
    return {"league": row[0], "country": row[1], "team_type": row[2]}


def player_market(db, player_id) -> str:
    """The market a player would be bought FROM: his current club's league.

    Players with no club spell — the national-team data — fall back to the
    international market rather than being priced as if they played anywhere
    in particular.
    """
    origin = player_origin(db, player_id)
    if not origin or origin["team_type"] == "national":
        return DEFAULT_MARKET
    return market_of(origin["league"], origin["country"])


# How demanding each league is, relative to the Premier League. A match rating
# earned against weaker opposition is worth less than the same rating against
# stronger opposition, and the index cannot see that on its own: a Chilean
# midfielder's stats, normalised against World Cup players, came out at 79.9
# as though he had earned them against that standard.
#
# Declared curation, pending data. Deriving it needs a player's index measured
# separately at each club, so that a move shows what the jump cost him; the
# record of moves is already kept, but the index is still one figure per player.
# Season-by-season licensed data supplies the missing half.
CURATED_STRENGTH = {
    "premier_league": 1.00,
    "la_liga": 0.95,
    "bundesliga": 0.92,
    "serie_a": 0.92,
    "ligue_1": 0.86,
    "international": 0.90,
    "eredivisie": 0.76,
    "primeira_liga": 0.76,
    "belgian_pro_league": 0.73,
    "brasileirao": 0.73,
    "saudi_pro_league": 0.70,
    "mls": 0.68,
    "liga_mx": 0.68,
    "argentina_primera": 0.68,
    "chile_primera": 0.58,
    "a_league": 0.62,
}


def strength_for(market: str) -> float:
    return CURATED_STRENGTH.get(market, CURATED_STRENGTH[DEFAULT_MARKET])


def project_index(index: float, from_market: str, to_market: str) -> dict:
    """The index a player would be expected to post in another league.

    Performance scales with the ratio of the two leagues' strength: a player
    moving up is expected to post less, one moving down more. Capped at 100 so
    a dominant player dropping a level cannot read as superhuman. Same-league
    moves return the index untouched.
    """
    if index is None:
        return {"value": None, "factor": 1.0, "adjusted": False}
    # An unnamed market has no strength to divide by. Substituting one would
    # project the player into a league nobody chose, and the factor would
    # look like a measurement.
    if from_market is None or to_market is None:
        return {"value": None, "factor": None, "adjusted": False,
                "basis": "Not projected: %s market is not known."
                         % ("the player's" if from_market is None
                            else "the buying club's")}
    factor = strength_for(from_market) / strength_for(to_market)
    return {
        "value": round(min(100.0, float(index) * factor), 1),
        "factor": round(factor, 3),
        "adjusted": from_market != to_market,
        "source": "curated",
    }
