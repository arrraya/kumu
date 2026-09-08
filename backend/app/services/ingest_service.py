"""Turning a client's payload into Kumu players.

The engine never depended on any provider, and this is where that pays off: a
payload that satisfies the contract becomes players, squads and indices without
the pipeline being involved at all.

One decision shapes the rest. A performance index is only meaningful against a
population, and a client uploading thirty players has no population of their own
— three strikers is not a distribution. So the SCALE comes from the reference
tenant and the client's players are measured against it. That makes one client's
numbers comparable to another's, and it is what makes the shared reference set
an asset rather than a demo.
"""
import hashlib
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import scoring
from app.db import models
from app.schemas.ingest import IngestPayload, PlayerRecord

MIN_PEERS_FOR_SCALE = scoring.MIN_PEERS_FOR_SCALE


def stable_external_id(source: str, org_id: int, client_id: str) -> str:
    """An id that survives re-imports and never collides across tenants.

    Two clients may legitimately use the same internal identifier for different
    players, so the tenant is part of the key. Deterministic, so re-uploading
    updates a player instead of duplicating him.
    """
    raw = f"{source}|{org_id}|{client_id}".strip().lower()
    return f"{source[:12]}_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def reference_scales(db: Session, org_ids: List[int]) -> Dict[str, Tuple[float, float]]:
    """Mean and spread of the reference population's raw index, per position.

    Reads `raw_value` where present: that is the figure before normalisation,
    and normalising against already-normalised numbers would compress the scale
    a second time.
    """
    rows = db.execute(text("""
        SELECT position,
               COALESCE(
                   (performance_index->>'raw_value')::float,
                   (performance_index->>'value')::float
               ) AS v
        FROM players
        WHERE performance_index IS NOT NULL
          AND organization_id IN :org_ids
    """).bindparams(), {"org_ids": tuple(org_ids)}).fetchall()

    by_position: Dict[str, List[float]] = {}
    for position, value in rows:
        if position and value is not None:
            by_position.setdefault(position, []).append(float(value))

    scales = {}
    for position, values in by_position.items():
        if len(values) >= MIN_PEERS_FOR_SCALE:
            spread = float(np.std(values))
            scales[position] = (float(np.mean(values)), spread if spread > 0 else 1.0)
    return scales


def _apply_scale(raw: float, scale: Optional[Tuple[float, float]]) -> Dict[str, float]:
    """Place a raw index on the shared scale, tails compressed not clipped."""
    if not scale:
        # No reference for this position: report the raw figure and say so,
        # rather than inventing a scale from too few peers.
        return {"value": round(raw, 1), "raw_value": round(raw, 1), "scaled": False}
    mean, spread = scale
    z = (raw - mean) / spread
    return {
        "value": round(70.0 + 30.0 * float(np.tanh(z / 2.5)), 1),
        "raw_value": round(raw, 1),
        "scaled": True,
    }


def prepare_player(record: PlayerRecord, scales: Dict[str, Tuple[float, float]],
                   source: str, org_id: int) -> Optional[Dict[str, Any]]:
    """Derive everything Kumu computes for itself from what the client supplied."""
    position = scoring.normalize_position(record.position)
    if not position:
        return None

    history = [h.model_dump(exclude_none=True) for h in record.performance_history]
    history = scoring.rate_history(history, position)

    raw = scoring.raw_index(history)
    index = None
    if raw:
        scaled = _apply_scale(raw["value"], scales.get(position))
        index = {**raw, **scaled}

    metrics = record.metrics.model_dump(exclude_none=True)

    return {
        "external_id": stable_external_id(source, org_id, record.external_id),
        "name": record.name,
        "position": position,
        "nationality": record.nationality,
        "current_team": record.current_team,
        "age": record.age,
        "market_value": record.market_value,
        "performance_index": index,
        "metrics": metrics,
        "performance_history": history,
        "organization_id": org_id,
    }


def ingest(db: Session, payload: IngestPayload, org_id: int,
           org_ids: List[int]) -> Dict[str, Any]:
    """Write a payload into the caller's tenant and report what landed."""
    import json

    scales = reference_scales(db, org_ids)
    prepared, skipped = [], []
    for record in payload.players:
        row = prepare_player(record, scales, payload.source, org_id)
        (prepared if row else skipped).append(row or record.external_id)

    db.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS players_external_id_key "
        "ON players (external_id)"
    ))

    for row in prepared:
        db.execute(text("""
            INSERT INTO players (external_id, name, age, position, nationality,
                                 current_team, market_value, performance_index,
                                 metrics, performance_history, organization_id)
            VALUES (:external_id, :name, :age, :position, :nationality,
                    :current_team, :market_value,
                    CAST(:performance_index AS JSON), CAST(:metrics AS JSON),
                    CAST(:performance_history AS JSON), :organization_id)
            ON CONFLICT (external_id) DO UPDATE SET
                name = EXCLUDED.name, age = EXCLUDED.age,
                position = EXCLUDED.position, nationality = EXCLUDED.nationality,
                current_team = EXCLUDED.current_team,
                market_value = EXCLUDED.market_value,
                performance_index = EXCLUDED.performance_index,
                metrics = EXCLUDED.metrics,
                performance_history = EXCLUDED.performance_history,
                updated_at = NOW()
        """), {
            **row,
            "performance_index": json.dumps(row["performance_index"]),
            "metrics": json.dumps(row["metrics"]),
            "performance_history": json.dumps(row["performance_history"]),
        })

    club_result = None
    if payload.club:
        club_result = _ingest_club(db, payload, org_id)

    db.commit()

    unscaled = [p["name"] for p in prepared
                if p["performance_index"] and not p["performance_index"].get("scaled")]

    return {
        "players_written": len(prepared),
        "players_skipped": skipped,
        "club": club_result,
        "positions_without_reference": sorted({
            p["position"] for p in prepared
            if p["performance_index"] and not p["performance_index"].get("scaled")
        }),
        "unscaled_players": unscaled[:10],
    }


def _ingest_club(db: Session, payload: IngestPayload, org_id: int) -> Dict[str, Any]:
    """Create or update the buying club and its squad."""
    import json

    club = payload.club
    external_id = stable_external_id(payload.source, org_id, club.external_id)

    style = {}
    if club.possession is not None:
        style["possession"] = club.possession
    if club.pressing_intensity is not None:
        style["pressing_intensity"] = club.pressing_intensity

    db.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS teams_external_id_key "
        "ON teams (external_id)"
    ))
    db.execute(text("""
        INSERT INTO teams (external_id, name, league, country, budget, formation,
                           playing_style, requirements, team_type,
                           organization_id, created_at)
        VALUES (:external_id, :name, :league, :country, :budget, :formation,
                CAST(:playing_style AS JSON), CAST(:requirements AS JSON),
                'club', :organization_id, NOW())
        ON CONFLICT (external_id) DO UPDATE SET
            name = EXCLUDED.name, league = EXCLUDED.league,
            country = EXCLUDED.country, budget = EXCLUDED.budget,
            formation = EXCLUDED.formation,
            playing_style = EXCLUDED.playing_style
    """), {
        "external_id": external_id, "name": club.name, "league": club.league,
        "country": club.country, "budget": club.budget,
        "formation": club.formation or "4-3-3",
        "playing_style": json.dumps(style),
        "requirements": json.dumps({}),
        "organization_id": org_id,
    })

    team = db.query(models.Team).filter(models.Team.external_id == external_id).first()
    if not team:
        return {"name": club.name, "squad_size": 0}

    squad_ids = [stable_external_id(payload.source, org_id, p) for p in club.squad]
    members = []
    if squad_ids:
        members = db.query(models.Player).filter(
            models.Player.external_id.in_(squad_ids),
            models.Player.organization_id == org_id,
        ).all()

        db.query(models.SquadMembership).filter(
            models.SquadMembership.team_id == team.id,
            models.SquadMembership.organization_id == org_id,
        ).delete(synchronize_session=False)

        for player in members:
            db.add(models.SquadMembership(
                player_id=player.id, team_id=team.id,
                source="client", organization_id=org_id,
            ))

    # The club's level is read from the squad rather than declared, the same
    # way positional need is.
    if club.expected_index is None and members:
        indices = [(p.performance_index or {}).get("value") for p in members]
        inferred = scoring.infer_expected_index([i for i in indices if i])
        if inferred:
            db.execute(text(
                "UPDATE teams SET requirements = CAST(:req AS JSON) WHERE id = :id"
            ), {"req": json.dumps({"expected_index": inferred}), "id": team.id})

    return {
        "name": club.name,
        "team_id": team.id,
        "squad_size": len(members),
        "expected_index": club.expected_index,
    }
