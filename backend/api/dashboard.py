"""
backend/api/dashboard.py
=========================
Unified dashboard initialisation endpoint.
"""

from fastapi import APIRouter
from typing import Optional

from backend.services.dashboard_service import build_dashboard_init

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/init")
def dashboard_init(shop: Optional[str] = None):
    """
    Single endpoint that returns everything the dashboard needs on first load:
    - years, year metadata
    - dashboard summary KPIs
    - top materials
    - shops list with consumption
    - shop monthly breakdown
    - ABC distribution
    - critical alerts

    Frontend caches this response locally and lazy-loads heavy tabs separately.
    """
    return build_dashboard_init(shop=shop)
