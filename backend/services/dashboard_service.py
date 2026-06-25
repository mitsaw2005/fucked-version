"""
backend/services/dashboard_service.py
======================================
Dashboard data builders. Each `get_*` function backs one of the flat
REST endpoints the frontend calls (backend/api/legacy_dashboard.py) and
is also composed into the unified `/api/dashboard/init` payload below.
"""

from typing import Optional
import numpy as np
import pandas as pd

from backend.core import globals as G
from backend.services import cache_service
from backend.services.recommendation_engine import (
    available_years, latest_year, filter_by_year,
    recommendation_engine, recommend_for_materials, fmt,
)

_CACHE_KEY = "dashboard::init"


def _native(v):
    """numpy scalars (int64/float64) aren't JSON-serialisable by FastAPI."""
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if pd.isna(v):
        return None
    return v


def _records(df: pd.DataFrame) -> list:
    if df.empty:
        return []
    return [{k: _native(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def _get_df() -> pd.DataFrame:
    with G.state_lock:
        return G.df_cache.copy()


def _year_meta(year, df):
    if df.empty:
        return {"year": year, "months_available": 0, "coverage_pct": 0.0, "is_ytd": True}
    mo = int(df["pstng date"].dt.month.nunique())
    return {"year": year, "months_available": mo, "coverage_pct": round(mo / 12 * 100, 1), "is_ytd": mo < 12}


def _year_shop_slice(year: Optional[int], shop: Optional[str]):
    year_df, resolved_year = filter_by_year(year)
    if shop and "Shop" in year_df.columns:
        year_df = year_df[year_df["Shop"] == shop]
    return year_df, resolved_year


# ── Years ──────────────────────────────────────────────────────────────

def get_years_info() -> dict:
    years = available_years()
    ly = latest_year()
    all_years_meta = []
    for y in years:
        ydf, _ = filter_by_year(y)
        all_years_meta.append(_year_meta(y, ydf))
    return {"years": years, "latest_year": ly, "all_years_metadata": all_years_meta}


# ── Materials ──────────────────────────────────────────────────────────

def get_materials_list(shop: Optional[str] = None) -> list:
    df = _get_df()
    if df.empty or "Material" not in df.columns:
        return []
    if shop and "Shop" in df.columns:
        df = df[df["Shop"] == shop]
    return sorted(df["Material"].dropna().unique().tolist())


# ── Plant summary ────────────────────────────────────────────────────────

def get_plant_summary(year: Optional[int] = None, shop: Optional[str] = None) -> dict:
    df = _get_df()
    year_df, resolved_year = _year_shop_slice(year, shop)

    total_materials = int(year_df["Material"].nunique()) if not year_df.empty else 0
    total_consumed  = round(float(year_df["Quantity"].sum()), 2) if not year_df.empty else 0

    total_inventory = 0
    if "Inventory_Qty" in df.columns and not df.empty:
        inv_df = df[df["Shop"] == shop] if (shop and "Shop" in df.columns) else df
        if not inv_df.empty:
            total_inventory = int(inv_df.sort_values("pstng date").drop_duplicates("Material", keep="last")["Inventory_Qty"].sum())

    top_material = None
    if not year_df.empty:
        totals = year_df.groupby("Material")["Quantity"].sum().sort_values(ascending=False)
        if len(totals):
            top_material = _native(totals.index[0])

    abc_distribution = {}
    if "ABC_Class" in year_df.columns and not year_df.empty:
        abc_distribution = {k: _native(v) for k, v in year_df.groupby("ABC_Class")["Material"].nunique().items()}

    return {
        "total_materials":  total_materials,
        "total_consumed":   total_consumed,
        "total_inventory":  total_inventory,
        "top_material":     top_material,
        "latest_year":      latest_year(),
        "year_metadata":    _year_meta(resolved_year, year_df),
        "abc_distribution": abc_distribution,
    }


# ── Top materials ────────────────────────────────────────────────────────

def get_top_materials(year: Optional[int] = None, shop: Optional[str] = None, limit: int = 10) -> list:
    year_df, _ = _year_shop_slice(year, shop)
    if year_df.empty or "Material" not in year_df.columns:
        return []
    top = (
        year_df.groupby("Material", as_index=False)
        .agg(total_quantity=("Quantity", "sum"))
        .sort_values("total_quantity", ascending=False)
        .head(limit)
        .reset_index(drop=True)
    )
    top.insert(0, "rank", range(1, len(top) + 1))
    return _records(top)


# ── Shop consumption ──────────────────────────────────────────────────────

def get_shop_consumption(year: Optional[int] = None, shop: Optional[str] = None) -> list:
    year_df, _ = _year_shop_slice(year, shop)
    if year_df.empty or "Shop" not in year_df.columns:
        return []
    shops_df = (
        year_df.groupby("Shop", as_index=False)["Quantity"].sum()
        .sort_values("Quantity", ascending=False)
    )
    return _records(shops_df)


# ── ABC analysis ──────────────────────────────────────────────────────────

def get_abc_analysis(year: Optional[int] = None, shop: Optional[str] = None) -> list:
    year_df, _ = _year_shop_slice(year, shop)
    if year_df.empty or "ABC_Class" not in year_df.columns:
        return []
    abc_df = (
        year_df.groupby("ABC_Class", as_index=False)
        .agg(total_qty=("Quantity", "sum"), material_count=("Material", "nunique"))
    )
    out = []
    for r in _records(abc_df):
        r["metric"] = "Quantity Consumed"
        out.append(r)
    return out


# ── Shop monthly trend ────────────────────────────────────────────────────

def get_shop_monthly(year: Optional[int] = None, shop: Optional[str] = None) -> dict:
    year_df, resolved_year = _year_shop_slice(year, shop)
    if year_df.empty or "Shop" not in year_df.columns:
        return {"records": [], "year_metadata": _year_meta(resolved_year, year_df)}
    tmp = year_df.copy()
    tmp["month_str"] = tmp["pstng date"].dt.strftime("%Y-%m")
    records = _records(
        tmp.groupby(["month_str", "Shop"])["Quantity"].sum().reset_index()
    )
    return {"records": records, "year_metadata": _year_meta(resolved_year, year_df)}


# ── Critical alerts (High/Medium risk only) ───────────────────────────────

def get_critical_alerts(shop: Optional[str] = None) -> list:
    year_df, _ = _year_shop_slice(None, shop)
    if year_df.empty:
        return []
    mats = sorted(year_df["Material"].unique().tolist())
    recs = recommend_for_materials(mats, shop=shop)

    alerts = []
    for rec in recs:
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
    return alerts


# ── Procurement summary (every material, every risk level) ───────────────

def get_procurement_summary(shop: Optional[str] = None) -> list:
    year_df, _ = _year_shop_slice(None, shop)
    if year_df.empty or "Material" not in year_df.columns:
        return []
    mats = sorted(year_df["Material"].unique().tolist())
    return recommend_for_materials(mats, shop=shop)


# ── Forecast engine summary (Developer tab) ───────────────────────────────

def get_forecast_engine_summary() -> dict:
    meta = G.meta or {}
    all_results = meta.get("all_results", {}) or {}
    leaderboard = sorted(
        ({"model": k, "mae": v} for k, v in all_results.items()),
        key=lambda r: r["mae"],
    )
    return {
        "best_model":         meta.get("best_model"),
        "best_mae":           meta.get("best_mae"),
        "dataset_size":       meta.get("row_count"),
        "last_training_date": meta.get("trained_at"),
        "forecast_type":      "Recursive Multi-Step Forecasting",
        "features":           meta.get("features", []),
        "leaderboard":        leaderboard,
    }


# ── Dashboard validation (Developer tab self-check) ───────────────────────

def get_dashboard_validation(year: Optional[int] = None) -> dict:
    df = _get_df()
    year_df, _ = _year_shop_slice(year, None)

    checks = []

    def add_check(name, passed, detail):
        checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})

    add_check("Data loaded", not df.empty, f"{len(df)} rows in cache" if not df.empty else "No data synced yet")
    required_cols = [c for c in ("Material", "Quantity", "pstng date") if c not in df.columns]
    add_check("Required columns present", not required_cols,
               f"Missing: {required_cols}" if required_cols else "Material, Quantity, pstng date present")
    add_check("Model loaded", G.model is not None, G.meta.get("best_model") or "No trained model on disk")
    add_check("Latest sync status OK", G.last_sync_status == "ok", G.last_sync_error or G.last_sync_status)

    shop_validation = []
    if not year_df.empty and "Shop" in year_df.columns:
        shop_validation = _records(
            year_df.groupby("Shop", as_index=False)
            .agg(rows=("Quantity", "count"), total_qty=("Quantity", "sum"))
        )

    safety_stock_proof = None
    if not year_df.empty and "Material" in year_df.columns:
        sample_material = year_df["Material"].iloc[0]
        try:
            rec = recommendation_engine(sample_material)
            backend_qty   = rec["order"]["recommended_qty"]
            predicted     = rec["forecast"]["predicted_next_month"]
            duplicate_qty = round(predicted * 1.15, 0)
            safety_stock_proof = {
                "material":                     sample_material,
                "backend_recommended_qty":      backend_qty,
                "backend_formula":               "max(predicted - inventory, 0) + round(predicted * 0.15)",
                "duplicate_frontend_qty":        duplicate_qty,
                "duplicate_frontend_formula":    "predicted * 1.15",
                "duplicate_overstatement_units": round(duplicate_qty - backend_qty, 2),
            }
        except Exception:
            safety_stock_proof = None

    overall_status = "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL"

    return {
        "overall_status":  overall_status,
        "checks":           checks,
        "shop_validation":  shop_validation,
        "forecast_method": {
            "name":       "Recursive Multi-Step ML Forecast",
            "engine":     G.meta.get("best_model") or "Rolling Average Fallback",
            "best_model": G.meta.get("best_model"),
            "best_mae":   G.meta.get("best_mae"),
            "fallback":   "Rolling average of last 3-6 months when the ML model or material encoding is unavailable",
        },
        "value_metric_note":   "All quantities are summed in base unit (EA) as recorded in the source sheet.",
        "safety_stock_proof":  safety_stock_proof,
    }


# ── Unified init payload (kept for /api/dashboard/init) ───────────────────

def build_dashboard_init(shop: Optional[str] = None) -> dict:
    """
    Return everything the dashboard needs on first load.
    Cached until invalidated.
    """
    cache_key = f"{_CACHE_KEY}::{shop}"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    df  = _get_df()
    ly  = latest_year()
    plant_summary = get_plant_summary(ly, shop)

    result = {
        "years":              get_years_info()["years"],
        "latest_year":        ly,
        "all_years_metadata": get_years_info()["all_years_metadata"],
        "year_metadata":      plant_summary["year_metadata"],
        "dashboard_summary": {
            "total_materials":  plant_summary["total_materials"],
            "total_consumed":   plant_summary["total_consumed"],
            "total_inventory":  plant_summary["total_inventory"],
            "top_material":     plant_summary["top_material"],
            "abc_distribution": plant_summary["abc_distribution"],
        },
        "top_materials": get_top_materials(ly, shop),
        "shops":         get_shop_consumption(ly, shop),
        "shop_monthly":  get_shop_monthly(ly, shop)["records"],
        "abc":           get_abc_analysis(ly, shop),
        "alerts":        get_critical_alerts(shop),
        "sync_status": {
            "last_sync": G.last_sync_time,
            "rows":      len(df),
            "status":    G.last_sync_status,
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
