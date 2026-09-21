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
    "international": 30_000_000,  # national-team data with no club market
}

DEFAULT_MARKET = "international"
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
    return DEFAULT_MARKET


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
              AND p.performance_index IS NOT NULL
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


def anchor_for(market: str, db=None) -> Dict[str, Any]:
    """The anchor to use for a market, measured if possible, curated if not."""
    if db is not None:
        measured = derive_anchor(db, market)
        if measured:
            return {**measured, "market": market}
    return {
        "value": CURATED_ANCHORS.get(market, CURATED_ANCHORS[DEFAULT_MARKET]),
        "source": "curated",
        "samples": 0,
        "market": market,
    }


def player_market(db, player_id) -> str:
    """The market a player would be bought FROM: his current club's league.

    Read through the open squad spell, the same record that tracks transfers.
    Players with no club spell — the national-team data — fall back to the
    international market rather than being priced as if they played anywhere
    in particular.
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
        return DEFAULT_MARKET
    if not row or row[2] == "national":
        return DEFAULT_MARKET
    return market_of(row[0], row[1])
