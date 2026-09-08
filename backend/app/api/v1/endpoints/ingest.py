"""Loading a client's own data."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core import security
from app.db.database import get_db
from app.schemas.ingest import IngestPayload, describe_capabilities
from app.services import ingest_service

router = APIRouter()


@router.post("/validate")
def validate(payload: IngestPayload):
    """Check a payload without writing anything.

    Says what the data unlocks and what it leaves unavailable, so a client
    finds out before uploading rather than after wondering why a section is
    empty. Deliberately open: judging a file should not require an account.
    """
    return describe_capabilities(payload)


@router.post("/players")
def ingest_players(
    payload: IngestPayload,
    db: Session = Depends(get_db),
    org_id: int = Depends(security.writable_org_id),
    org_ids: list = Depends(security.readable_org_ids),
):
    """Load players and, optionally, the buying club and its squad."""
    if not payload.players:
        raise HTTPException(status_code=400, detail="No players in the payload")

    result = ingest_service.ingest(db, payload, org_id, org_ids)
    return {
        "capabilities": describe_capabilities(payload),
        "result": result,
    }
