"""
backend/api/legacy_dashboard.py
================================
Flat-path routes matching what frontend/src/App.jsx actually calls.

The "modular architecture" refactor consolidated dashboard data behind
/api/dashboard/init and added /api prefixes to forecast/history, but the
frontend was never updated to match — it still calls /years,
/critical-alerts, /procurement-summary, /forecast/{material}, etc. These
routes serve those exact paths, backed by the same dashboard_service /
recommendation_engine logic the prefixed routes use.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException

from backend.core import globals as G
from backend.services import dashboard_service as ds
from backend.services.recommendation_engine import recommendation_engine

router = APIRouter(tags=["Dashboard (legacy paths)"])


@router.get("/years")
def years():
    return ds.get_years_info()


@router.get("/materials")
def materials(shop: Optional[str] = None):
    return {"materials": ds.get_materials_list(shop=shop)}


@router.get("/critical-alerts")
def critical_alerts(shop: Optional[str] = None):
    return ds.get_critical_alerts(shop=shop)


@router.get("/procurement-summary")
def procurement_summary(shop: Optional[str] = None):
    return ds.get_procurement_summary(shop=shop)


@router.get("/plant-summary")
def plant_summary(year: Optional[int] = None, shop: Optional[str] = None):
    return ds.get_plant_summary(year=year, shop=shop)


@router.get("/top-materials")
def top_materials(year: Optional[int] = None, shop: Optional[str] = None):
    return ds.get_top_materials(year=year, shop=shop)


@router.get("/shop-consumption")
def shop_consumption(year: Optional[int] = None, shop: Optional[str] = None):
    return ds.get_shop_consumption(year=year, shop=shop)


@router.get("/abc-analysis")
def abc_analysis(year: Optional[int] = None, shop: Optional[str] = None):
    return ds.get_abc_analysis(year=year, shop=shop)


@router.get("/shop-monthly")
def shop_monthly(year: Optional[int] = None, shop: Optional[str] = None):
    return ds.get_shop_monthly(year=year, shop=shop)


@router.get("/forecast-engine")
def forecast_engine():
    return ds.get_forecast_engine_summary()


@router.get("/dashboard-validation")
def dashboard_validation(year: Optional[int] = None):
    return ds.get_dashboard_validation(year=year)


@router.get("/forecast/{material}")
def forecast(material: str, horizon: int = 30, shop: Optional[str] = None):
    with G.state_lock:
        empty = G.df_cache.empty
    if empty:
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
    for r in records:
        if hasattr(r["pstng date"], "isoformat"):
            r["pstng date"] = r["pstng date"].isoformat()
    return records
