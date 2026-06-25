"""
backend/services/dashboard_service.py
======================================
Pre-computes and returns the unified dashboard init payload.
Result is cached until the next sync / retrain cycle.
"""

from typing import Optional
import pandas as pd

from backend.core import globals as G
from backend.services import cache_service
from backend.services.recommendation_engine import (
    available_years, latest_year, filter_by_year,
    recommendation_engine, fmt,
)

_CACHE_KEY = "dashboard::init"


def _get_df() -> pd.DataFrame:
    with G.state_lock:
        return G.df_cache.copy()


def _year_meta(year, df):
    if df.empty:
        return {"year": year, "months_available": 0, "coverage_pct": 0.0, "is_ytd": True}
    mo = int(df["pstng date"].dt.month.nunique())
    return {"year": year, "months_available": mo, "coverage_pct": round(mo / 12 * 100, 1), "is_ytd": mo < 12}


def build_dashboard_init(shop: Optional[str] = None) -> dict:
    """
    Return everything the dashboard needs on first load.
    Cached until invalidated.
    """
    cache_key = f"{_CACHE_KEY}::{shop}"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    df      = _get_df()
    years   = available_years()
    ly      = latest_year()

    year_df, _ = filter_by_year(ly)
    if shop and "Shop" in year_df.columns:
        year_df = year_df[year_df["Shop"] == shop]

    # ── KPIs ────────────────────────────────────────────────────────
    total_materials = int(year_df["Material"].nunique()) if not year_df.empty else 0
    total_consumed  = round(float(year_df["Quantity"].sum()), 2) if not year_df.empty else 0
    total_inventory = 0
    if "Inventory_Qty" in df.columns:
        total_inventory = int(df.sort_values("pstng date").drop_duplicates("Material", keep="last")["Inventory_Qty"].sum())

    # ── Top materials ────────────────────────────────────────────────
    top_mats = (
        year_df.groupby("Material", as_index=False)
        .agg(total_quantity=("Quantity", "sum"))
        .sort_values("total_quantity", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )
    top_mats.insert(0, "rank", range(1, len(top_mats) + 1))

    # ── Shop consumption ─────────────────────────────────────────────
    shops = []
    if "Shop" in year_df.columns:
        shops_df = (
            year_df.groupby("Shop", as_index=False)["Quantity"].sum()
            .sort_values("Quantity", ascending=False)
        )
        shops = shops_df.to_dict(orient="records")

    # ── ABC distribution ─────────────────────────────────────────────
    abc_data = []
    if "ABC_Class" in year_df.columns:
        abc_df = (
            year_df.groupby("ABC_Class", as_index=False)
            .agg(total_qty=("Quantity", "sum"), material_count=("Material", "nunique"))
        )
        for r in abc_df.to_dict(orient="records"):
            r["metric"] = "Quantity Consumed"
            abc_data.append(r)

    # ── Shop monthly trend ───────────────────────────────────────────
    shop_monthly = []
    if "Shop" in year_df.columns:
        tmp = year_df.copy()
        tmp["month_str"] = tmp["pstng date"].dt.strftime("%Y-%m")
        shop_monthly = (
            tmp.groupby(["month_str", "Shop"])["Quantity"].sum()
            .reset_index()
            .to_dict(orient="records")
        )

    # ── Year metadata map ─────────────────────────────────────────────
    all_years_meta = []
    for y in years:
        ydf, _ = filter_by_year(y)
        all_years_meta.append(_year_meta(y, ydf))

    # ── Critical alerts (procurement) ─────────────────────────────────
    alerts = []
    mats   = sorted(year_df["Material"].unique().tolist()) if not year_df.empty else []
    for m in mats:
        try:
            rec = recommendation_engine(m, shop=shop)
            if rec["risk"] in ("High", "Medium"):
                alerts.append({
                    "material":       rec["material"],
                    "shop":           rec["shop"],
                    "abc_class":      rec["abc_class"],
                    "risk":           rec["risk"],
                    "action":         rec["order"]["action"],
                    "order_qty":      rec["order"]["recommended_qty"],
                    "reorder_by":     rec["lead_time"]["reorder_by"],
                    "runout_date":    rec["lead_time"]["runout_date"],
                    "days_to_runout": rec["lead_time"]["days_to_runout"],
                    "already_late":   rec["lead_time"]["already_late"],
                    "lead_time":      rec["lead_time"]["total"],
                    "alert":          rec["alert"],
                    "current_stock":  rec["inventory"]["current_stock"],
                    "forecast":       rec["forecast"]["predicted_next_month"],
                })
        except Exception:
            pass

    result = {
        "years":        years,
        "latest_year":  ly,
        "all_years_metadata": all_years_meta,
        "year_metadata": _year_meta(ly, year_df),
        "dashboard_summary": {
            "total_materials":       total_materials,
            "total_consumed":        total_consumed,
            "total_inventory":       total_inventory,
            "top_material":          top_mats.iloc[0]["Material"] if not top_mats.empty else None,
            "abc_distribution":      {r["ABC_Class"]: r["material_count"] for r in abc_data} if abc_data else {},
        },
        "top_materials": top_mats.to_dict(orient="records"),
        "shops":         shops,
        "shop_monthly":  shop_monthly,
        "abc":           abc_data,
        "alerts":        alerts,
        "sync_status": {
            "last_sync":    G.last_sync_time,
            "rows":         len(df),
            "status":       G.last_sync_status,
        },
        "model_status": {
            "best_model":     G.meta.get("best_model"),
            "best_mae":       G.meta.get("best_mae"),
            "trained_at":     G.meta.get("trained_at"),
            "is_model_stale": G.is_model_stale,
        },
    }

    cache_service.set(cache_key, result)
    return result
