"""Player market endpoints: stock-market style pricing derived from performance.

Prices come from the offline pipeline (pipeline/market.py) and are stored in
the market_series table. They are an analytical construct built on Kumu's own
estimated values, not observed market transactions.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import get_db

router = APIRouter()

SORT_COLUMNS = {
    "change": "m.total_change_pct",
    "price": "m.current_price",
    "volatility": "m.volatility",
    "last": "m.last_change_pct",
    "name": "p.name",
}


@router.get("/")
def list_market(
    sort: str = Query("change", description="change | price | volatility | last | name"),
    order: str = Query("desc", description="asc | desc"),
    position: str | None = None,
    search: str | None = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
):
    """Market table: one row per player with current price and movement."""
    column = SORT_COLUMNS.get(sort, "m.total_change_pct")
    direction = "ASC" if order.lower() == "asc" else "DESC"

    filters, params = [], {"limit": limit}
    if position:
        filters.append("p.position = :position")
        params["position"] = position
    if search:
        filters.append("p.name ILIKE :search")
        params["search"] = f"%{search}%"
    where = f"WHERE {' AND '.join(filters)}" if filters else ""

    rows = db.execute(text(f"""
        SELECT p.id, p.name, p.position, p.current_team, p.nationality,
               m.current_price, m.opening_price, m.total_change_pct,
               m.last_change_pct, m.high, m.low, m.volatility, m.matches,
               p.performance_index
        FROM market_series m
        JOIN players p ON p.id = m.player_id
        {where}
        ORDER BY {column} {direction} NULLS LAST
        LIMIT :limit
    """), params).fetchall()

    return [
        {
            "player_id": r[0], "name": r[1], "position": r[2],
            "team": r[3], "nationality": r[4],
            "current_price": r[5], "opening_price": r[6],
            "total_change_pct": r[7], "last_change_pct": r[8],
            "high": r[9], "low": r[10], "volatility": r[11], "matches": r[12],
            "performance_index": (r[13] or {}).get("value") if isinstance(r[13], dict) else None,
        }
        for r in rows
    ]


@router.get("/summary")
def market_summary(db: Session = Depends(get_db)):
    """Aggregate market state: totals, average move, best and worst."""
    row = db.execute(text("""
        SELECT COUNT(*), SUM(current_price), AVG(total_change_pct),
               SUM(CASE WHEN total_change_pct > 0 THEN 1 ELSE 0 END),
               SUM(CASE WHEN total_change_pct < 0 THEN 1 ELSE 0 END)
        FROM market_series
    """)).fetchone()

    return {
        "listed_players": row[0] or 0,
        "total_market_cap": float(row[1] or 0),
        "average_change_pct": round(float(row[2] or 0), 2),
        "risers": row[3] or 0,
        "fallers": row[4] or 0,
    }


@router.get("/{player_id}")
def market_detail(player_id: int, db: Session = Depends(get_db)):
    """Full price series for one player."""
    row = db.execute(text("""
        SELECT p.id, p.name, p.position, p.current_team, p.nationality,
               m.current_price, m.opening_price, m.total_change_pct,
               m.last_change_pct, m.high, m.low, m.volatility, m.matches, m.series,
               p.performance_index
        FROM market_series m
        JOIN players p ON p.id = m.player_id
        WHERE p.id = :pid
    """), {"pid": player_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Player not listed in market")

    return {
        "player_id": row[0], "name": row[1], "position": row[2],
        "team": row[3], "nationality": row[4],
        "current_price": row[5], "opening_price": row[6],
        "total_change_pct": row[7], "last_change_pct": row[8],
        "high": row[9], "low": row[10], "volatility": row[11],
        "matches": row[12], "series": row[13] or [],
        "performance_index": (row[14] or {}).get("value") if isinstance(row[14], dict) else None,
    }
