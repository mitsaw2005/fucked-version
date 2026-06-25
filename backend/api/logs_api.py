"""
backend/api/logs_api.py
========================
Endpoint for exposing recent structured logs.
"""

from fastapi import APIRouter, Query
from typing import Optional
from backend.services.logging_service import get_recent_logs

router = APIRouter(prefix="/datasource", tags=["Logs"])

@router.get("/logs")
def get_logs(limit: int = Query(100, ge=1, le=1000), category: Optional[str] = None):
    """
    Expose recent structured logs.
    Supported categories: "Google Sync", "Scheduler", "Model Training", "API", "Authentication", "Errors"
    """
    return get_recent_logs(limit=limit, category=category)
