"""
backend/api/forecast.py
========================
Forecast and consumption history endpoints.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from backend.services.recommendation_engine import recommendation_engine
from backend.core import globals as G

router = APIRouter(prefix="/api", tags=["Forecast"])


@router.get("/forecast/{material}")
def forecast(material: str, horizon: int = 30, shop: Optional[str] = None):
    with G.state_lock:
        df = G.df_cache
    if df.empty:
        raise HTTPException(503, "Data not yet synced from Google Sheets")
    try:
        return recommendation_engine(material, horizon_days=horizon, shop=shop)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/history/{material}")
def history(material: str, shop: Optional[str] = None):
    with G.state_lock:
        df = G.df_cache.copy()
    if df.empty:
        raise HTTPException(503, "Data not yet synced")
    mdf = df[df["Material"] == material].copy()
    if shop and "Shop" in mdf.columns:
        mdf = mdf[mdf["Shop"] == shop]
    if mdf.empty:
        raise HTTPException(404, f"Material '{material}' not found")
    mdf = mdf.sort_values("pstng date")
    records = mdf[["pstng date", "Quantity"]].to_dict(orient="records")
    # Serialise datetime
    for r in records:
        if hasattr(r["pstng date"], "isoformat"):
            r["pstng date"] = r["pstng date"].isoformat()
    return records
