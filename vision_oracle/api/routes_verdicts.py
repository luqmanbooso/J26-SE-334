"""
Verdict ledger and query routes (FR7).
"""

from fastapi import APIRouter, HTTPException
from vision_oracle.services.oracle_service import get_oracle_service

router = APIRouter(prefix="/api/oracle", tags=["Verdicts"])


@router.get("/verdicts")
def list_verdicts(limit: int = 20):
    """Returns recent verdict records in reverse chronological order."""
    service = get_oracle_service()
    return service.list_verdicts(limit=limit)


@router.get("/verdicts/{verdict_id}")
def get_verdict(verdict_id: str):
    """Fetches specific verdict record by ID."""
    service = get_oracle_service()
    verdict = service.get_verdict(verdict_id)
    if verdict is None:
        raise HTTPException(status_code=404, detail=f"Verdict '{verdict_id}' not found.")
    return verdict
