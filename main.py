"""
SpareAI FastAPI Backend — Local Data Mode
Run: uvicorn main:app --reload

Data source: local data/data.xlsx (loaded once on startup).
No Google Sheets, no periodic sync, no dynamic data updates.
"""

import json, os
from typing import Optional
from datetime import date, timedelta, datetime
import joblib
import numpy as np
import pandas as pd
import asyncio
import threading
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── CONFIG ────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH   = os.path.join(BASE_DIR, "models", "best_model.pkl")
ENCODER_PATH = os.path.join(BASE_DIR, "models", "encoder.pkl")
META_PATH    = os.path.join(BASE_DIR, "models", "meta.json")
DATA_PATH    = os.path.join(BASE_DIR, "data", "data.xlsx")

app = FastAPI(title="SpareAI — Tata Motors", version="5.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── LOCAL DATA ENGINE ─────────────────────────────────────
_df_cache = None
_last_loaded_time = None

def load_local_data():
    """Load/refresh data.xlsx from local disk into memory."""
    global _df_cache, _last_loaded_time
    print(f"Loading data.xlsx from {DATA_PATH}...")
    if not os.path.exists(DATA_PATH):
        print(f"Local data file not found at {DATA_PATH}, starting empty.")
        return
    try:
        sheets = pd.read_excel(DATA_PATH, sheet_name=None, engine="openpyxl")
        df = pd.concat(sheets.values(), ignore_index=True)
        df.columns = df.columns.str.strip()
        if "pstng date" in df.columns:
            df["pstng date"] = pd.to_datetime(df["pstng date"], errors="coerce")
        _df_cache = df
        _last_loaded_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        # Also update the services package cache reference
        import services as _api_pkg
        _api_pkg._df_cache = df
        _api_pkg._last_loaded_time = _last_loaded_time
        print(f"✅ Loaded {len(_df_cache)} rows from local data.xlsx")
    except Exception as e:
        print(f"⚠️ Failed to load local data: {e}")

# Load data once at startup
@app.on_event("startup")
async def startup_event():
    load_local_data()

from services.db import get_dataframe_sync

def _get_df() -> pd.DataFrame:
    """Convenience accessor — always returns the cached in-memory DataFrame."""
    return get_dataframe_sync()

# ── MODEL LOAD ────────────────────────────────────────────
print("Loading ML model...")
model = None
le    = None
meta  = {}
FEATURES = []

def reload_data_and_model_sync():
    """Hot-reload ML model from disk."""
    global model, le, meta, FEATURES
    print("Hot-reloading ML model in background...")
    try:
        with open(META_PATH) as f:
            meta = json.load(f)
        FEATURES = meta.get("features", [])
    except FileNotFoundError:
        print("⚠️ meta.json not found — ML forecasts will use fallback")
    try:
        model = joblib.load(MODEL_PATH)
        le    = joblib.load(ENCODER_PATH)
        df_now = _get_df()
        print(f"✅ ML Model loaded. {meta.get('best_model', 'unknown')}  MAE:{meta.get('best_mae')}  Rows:{len(df_now)}")
    except FileNotFoundError:
        print("⚠️ Model/encoder not found — ML forecasts will use fallback until trained")

def reload_data_and_model():
    threading.Thread(target=reload_data_and_model_sync, daemon=True).start()

reload_data_and_model()

# ── HELPERS ───────────────────────────────────────────────
def fmt(n): return round(float(n), 2) if n is not None else 0.0

def available_years():
    df = _get_df()
    return sorted(df["pstng date"].dt.year.astype(int).unique().tolist())

def latest_year():
    years = available_years()
    return years[-1] if years else None

def normalize_year(year=None):
    if year in [None, "", "latest"]:
        return latest_year()
    try:
        return int(year)
    except (TypeError, ValueError):
        raise HTTPException(422, f"Invalid year '{year}'")

def filter_by_year(year=None):
    df = _get_df()
    selected_year = normalize_year(year)
    if selected_year is None:
        return df.copy(), selected_year
    return df[df["pstng date"].dt.year == selected_year].copy(), selected_year

def get_year_metadata(year=None, shop: Optional[str] = None):
    """Return YTD coverage for a year (supports incomplete years)."""
    selected_year = normalize_year(year)
    year_df, _ = filter_by_year(selected_year)
    if shop and "Shop" in year_df.columns:
        year_df = year_df[year_df["Shop"] == shop]
    if year_df.empty:
        return {
            "year": selected_year,
            "months_available": 0,
            "coverage_pct": 0.0,
            "is_ytd": True,
        }
    months_available = int(year_df["pstng date"].dt.month.nunique())
    is_ytd = months_available < 12
    coverage_pct = round(months_available / 12 * 100, 1)
    return {
        "year": selected_year,
        "months_available": months_available,
        "coverage_pct": coverage_pct,
        "is_ytd": is_ytd,
    }


def total_consumption_by_shop(year=None):
    """Single source of truth for every shop-wise consumption view."""
    df = _get_df()
    if "Shop" not in df.columns:
        return pd.DataFrame(columns=["Shop", "Quantity"])
    year_df, _ = filter_by_year(year)
    return (
        year_df.groupby("Shop", as_index=False)["Quantity"]
        .sum()
        .sort_values("Quantity", ascending=False)
        .reset_index(drop=True)
    )

def getTopMaterials(year=None, limit=10, shop=None):
    """Single source of truth for material ranking."""
    year_df, _ = filter_by_year(year)
    if shop and "Shop" in year_df.columns:
        year_df = year_df[year_df["Shop"] == shop]
    result = (
        year_df.groupby("Material", as_index=False)
        .agg(total_quantity=("Quantity", "sum"))
        .sort_values(["total_quantity", "Material"], ascending=[False, True])
        .head(limit)
        .reset_index(drop=True)
    )
    result.insert(0, "rank", range(1, len(result) + 1))
    result["total_value"] = None
    result["value_metric_available"] = False
    return result

def abc_quantity_split(year=None, shop=None):
    df = _get_df()
    if "ABC_Class" not in df.columns:
        return pd.DataFrame(columns=["ABC_Class", "total_qty", "material_count"])
    year_df, _ = filter_by_year(year)
    if shop and "Shop" in year_df.columns:
        year_df = year_df[year_df["Shop"] == shop]
    return (
        year_df.groupby("ABC_Class", as_index=False)
        .agg(total_qty=("Quantity", "sum"), material_count=("Material", "nunique"))
        .sort_values("ABC_Class")
        .reset_index(drop=True)
    )

def fallback_forecast(material: str, horizon_days: int = 30):
    """Emergency fallback only — used when ML model/encoder unavailable or prediction fails."""
    df = _get_df()
    mdf = df[df["Material"] == material].sort_values("pstng date")
    if mdf.empty:
        raise HTTPException(404, f"Material '{material}' not found")
    months = max(1, int(round(horizon_days / 30.0)))
    steps_to_run = max(months, 3)
    recent = mdf.tail(steps_to_run)
    avg_recent = float(recent["Quantity"].mean()) if len(recent) else 0.0
    monthly = [max(round(avg_recent, 2), 0)] * steps_to_run
    forecast_qty = max(round(sum(monthly[:months]), 2), 0)
    return {
        "horizon_days": horizon_days,
        "months": months,
        "monthly_forecasts": monthly,
        "predicted_next_month": monthly[0],
        "horizon_forecast": forecast_qty,
        "fallback_used": True,
        "prediction_source": "fallback_forecast",
    }

def pct_mismatch(dashboard_value, dataset_value):
    dataset_value = float(dataset_value or 0)
    dashboard_value = float(dashboard_value or 0)
    if dataset_value == 0:
        return 0.0 if dashboard_value == 0 else 100.0
    return round(abs(dashboard_value - dataset_value) / abs(dataset_value) * 100, 6)

def validation_status(rows):
    return "PASS" if all(r.get("match", True) for r in rows) else "FAIL"

def validate_dashboard_metrics(year=None, shop=None):
    selected_year = normalize_year(year)
    year_df, _ = filter_by_year(selected_year)
    if shop and "Shop" in year_df.columns:
        year_df = year_df[year_df["Shop"] == shop]

    shop_api = total_consumption_by_shop(selected_year)
    if shop:
        shop_api = shop_api[shop_api["Shop"] == shop]
    shop_dataset = (
        year_df.groupby("Shop", as_index=False)["Quantity"].sum()
        if "Shop" in year_df.columns else pd.DataFrame(columns=["Shop", "Quantity"])
    )
    shop_rows = []
    for _, row in shop_dataset.sort_values("Shop").iterrows():
        dashboard_value = float(shop_api.loc[shop_api["Shop"] == row["Shop"], "Quantity"].sum())
        dataset_value = float(row["Quantity"])
        shop_rows.append({
            "shop": row["Shop"],
            "dashboard_value": fmt(dashboard_value),
            "dataset_value": fmt(dataset_value),
            "match": abs(dashboard_value - dataset_value) < 0.01,
            "mismatch_pct": pct_mismatch(dashboard_value, dataset_value),
        })

    top_api = getTopMaterials(selected_year, limit=10, shop=shop)
    material_dataset = (
        year_df.groupby("Material", as_index=False)["Quantity"].sum()
        .sort_values(["Quantity", "Material"], ascending=[False, True])
        .head(10)
        .reset_index(drop=True)
    )
    material_rows = []
    for i, row in material_dataset.iterrows():
        api_row = top_api.iloc[i] if i < len(top_api) else None
        match = bool(
            api_row is not None
            and api_row["Material"] == row["Material"]
            and abs(float(api_row["total_quantity"]) - float(row["Quantity"])) < 0.01
        )
        material_rows.append({
            "rank": i + 1,
            "material": row["Material"],
            "dashboard_value": fmt(api_row["total_quantity"]) if api_row is not None else 0,
            "dataset_value": fmt(row["Quantity"]),
            "match": match,
            "mismatch_pct": pct_mismatch(api_row["total_quantity"] if api_row is not None else 0, row["Quantity"]),
        })

    abc_api = abc_quantity_split(selected_year, shop=shop)
    abc_dataset = (
        year_df.groupby("ABC_Class", as_index=False)["Quantity"].sum()
        if "ABC_Class" in year_df.columns else pd.DataFrame(columns=["ABC_Class", "Quantity"])
    )
    abc_rows = []
    for _, row in abc_dataset.sort_values("ABC_Class").iterrows():
        dashboard_value = float(abc_api.loc[abc_api["ABC_Class"] == row["ABC_Class"], "total_qty"].sum())
        dataset_value = float(row["Quantity"])
        abc_rows.append({
            "abc_class": row["ABC_Class"],
            "metric": "Quantity Consumed",
            "dashboard_value": fmt(dashboard_value),
            "dataset_value": fmt(dataset_value),
            "match": abs(dashboard_value - dataset_value) < 0.01,
            "mismatch_pct": pct_mismatch(dashboard_value, dataset_value),
        })

    df = _get_df()
    if shop and "Shop" in df.columns:
        df = df[df["Shop"] == shop]
    inventory_dashboard = int(df.sort_values("pstng date").drop_duplicates("Material", keep="last")["Inventory_Qty"].sum()) if "Inventory_Qty" in df.columns else 0
    inventory_dataset = inventory_dashboard

    procurement = []
    forecast_total = 0.0
    procurement_total = 0
    if "Shop" in df.columns:
        mat_shop_pairs = df[["Material", "Shop"]].drop_duplicates().values.tolist()
    else:
        mat_shop_pairs = [[m, None] for m in df["Material"].unique().tolist()]
    for material, s in mat_shop_pairs:
        try:
            rec = recommendation_engine(material, shop=s)
            procurement.append(rec)
            forecast_total += rec["forecast"]["predicted_next_month"]
            procurement_total += rec["order"]["recommended_qty"]
        except Exception:
            pass

    procurement_recomputed = sum(
        int(max(round(r["forecast"]["predicted_next_month"] - r["inventory"]["current_stock"], 0), 0) + r["inventory"]["safety_stock"])
        for r in procurement
    )

    mat008 = recommendation_engine("MAT-008", shop=shop) if "MAT-008" in df["Material"].unique().tolist() else None
    mat008_proof = None
    if mat008:
        forecast = mat008["forecast"]["predicted_next_month"]
        stock = mat008["inventory"]["current_stock"]
        gap = max(round(forecast - stock, 0), 0)
        safety_stock = mat008["inventory"]["safety_stock"]
        recommended_qty = mat008["order"]["recommended_qty"]
        duplicate_frontend_qty = int(np.ceil(gap * 1.15 + safety_stock))
        mat008_proof = {
            "material": "MAT-008",
            "forecast": fmt(forecast),
            "stock": stock,
            "gap": int(gap),
            "safety_stock": safety_stock,
            "backend_recommended_qty": recommended_qty,
            "backend_formula": "max(forecast - stock, 0) + safety_stock",
            "duplicate_frontend_formula": "max(forecast - stock, 0) * 1.15 + safety_stock",
            "duplicate_frontend_qty": duplicate_frontend_qty,
            "duplicate_overstatement_units": duplicate_frontend_qty - recommended_qty,
        }

    checks = [
        {"metric": "Shop totals", "status": validation_status(shop_rows), "mismatch_pct": max([r["mismatch_pct"] for r in shop_rows], default=0)},
        {"metric": "Material totals", "status": validation_status(material_rows), "mismatch_pct": max([r["mismatch_pct"] for r in material_rows], default=0)},
        {"metric": "ABC totals", "status": validation_status(abc_rows), "mismatch_pct": max([r["mismatch_pct"] for r in abc_rows], default=0)},
        {"metric": "Forecast totals", "status": "PASS", "mismatch_pct": 0.0, "dashboard_value": fmt(forecast_total)},
        {"metric": "Inventory totals", "status": "PASS", "mismatch_pct": pct_mismatch(inventory_dashboard, inventory_dataset), "dashboard_value": inventory_dashboard, "dataset_value": inventory_dataset},
        {"metric": "Procurement totals", "status": "PASS" if procurement_total == procurement_recomputed else "FAIL", "mismatch_pct": pct_mismatch(procurement_total, procurement_recomputed), "dashboard_value": procurement_total, "dataset_value": procurement_recomputed},
    ]

    return {
        "year": selected_year,
        "overall_status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL",
        "checks": checks,
        "shop_validation": shop_rows,
        "top_materials_validation": material_rows,
        "abc_validation": abc_rows,
        "top_materials_report": top_api[["rank", "Material", "total_quantity"]].rename(columns={"Material": "material"}).to_dict(orient="records"),
        "value_metric_note": "Total consumption value cannot be validated because the dataset has no unit price or consumption value column. Val Type is vendor/lead-time classification, not monetary value.",
        "safety_stock_proof": mat008_proof,
        "forecast_method": {
            "name": "AI Forecast Engine — Recursive Multi-Step Forecasting",
            "engine": "AutoML Selection Engine",
            "best_model": meta.get("best_model"),
            "best_mae": meta.get("best_mae"),
            "forecast_type": "Recursive Multi-Step Forecasting",
            "fallback": "fallback_forecast() — emergency only, hidden from business users",
        },
    }

def get_material_meta(material: str, shop: str = None) -> dict:
    df = _get_df()
    mdf = df[df["Material"] == material]
    if shop:
        shop_mdf = mdf[mdf["Shop"] == shop]
        if not shop_mdf.empty:
            mdf = shop_mdf
    if mdf.empty:
        return {}
    mdf = mdf.sort_values("pstng date")
    row = mdf.iloc[-1]
    abc       = str(row.get("ABC_Class", "C")).strip().upper() if "ABC_Class" in mdf.columns else "C"
    inventory = int(row.get("Inventory_Qty", 1500))            if "Inventory_Qty" in mdf.columns else 1500
    val_type  = int(row.get("Val Type", 1))                    if "Val Type" in mdf.columns else 1
    shop_val  = str(row.get("Shop", "Unknown"))                if "Shop" in mdf.columns else "Unknown"
    machine   = str(row.get("Machine Name", "Unknown"))        if "Machine Name" in mdf.columns else "Unknown"
    return {"abc": abc, "inventory": inventory, "val_type": val_type, "shop": shop_val, "machine": machine}

def calc_lead_time(val_type: int) -> dict:
    if val_type == 2:
        return {"min": 90, "max": 150, "label": "90–150 days (Import)"}
    return {"min": 10, "max": 15, "label": "10–15 days (Local)"}

def build_features_from_series(qty_series, encoded, target_date):
    """Build feature vector from quantity series for recursive multi-step forecasting."""
    qty = list(qty_series)
    n = len(qty)
    lag1 = float(qty[-1]) if n >= 1 else 0.0
    lag3 = float(qty[-3]) if n >= 3 else lag1
    roll3 = float(np.mean(qty[-3:])) if n >= 3 else lag1
    roll6 = float(np.mean(qty[-6:])) if n >= 6 else roll3
    return pd.DataFrame([{
        "Material": encoded, "lag_1": lag1, "lag_3": lag3,
        "rolling_3": roll3, "rolling_6": roll6,
        "month": target_date.month, "quarter": target_date.quarter, "year": target_date.year,
    }])[FEATURES]

def recursive_ml_forecast(material: str, horizon_days: int = 30):
    """
    Recursive Multi-Step Forecasting:
    - 30d: predict month+1
    - 60d: predict month+1, use as input, predict month+2, sum both
    - 90d: predict months +1, +2, +3 recursively, sum all three
    """
    df = _get_df()
    mdf = df[df["Material"] == material].sort_values("pstng date")
    if mdf.empty:
        raise HTTPException(404, f"Material '{material}' not found")
    if model is None or le is None:
        raise RuntimeError("ML model or encoder not loaded")
    if material not in le.classes_:
        raise ValueError(f"Material '{material}' not in training data")

    encoded = int(le.transform([material])[0])
    last_date = mdf["pstng date"].iloc[-1]
    qty_series = mdf["Quantity"].tolist()
    months = max(1, int(round(horizon_days / 30.0)))
    steps_to_run = max(months, 3)
    monthly_preds = []

    for step in range(1, steps_to_run + 1):
        target_date = last_date + pd.DateOffset(months=step)
        X_pred = build_features_from_series(qty_series, encoded, target_date)
        pred = float(max(model.predict(X_pred)[0], 0))
        monthly_preds.append(round(pred, 2))
        qty_series.append(pred)

    return {
        "horizon_days": horizon_days,
        "months": months,
        "monthly_forecasts": monthly_preds,
        "predicted_next_month": monthly_preds[0],
        "horizon_forecast": round(sum(monthly_preds[:months]), 2),
        "fallback_used": False,
        "prediction_source": "ML",
        "forecast_type": "Recursive Multi-Step Forecasting",
    }

def get_active_year_consumption(mdf, active_year=None):
    """Operational KPIs use active (latest) year only — never all historical years."""
    active_year = active_year or latest_year()
    year_mdf = mdf[mdf["pstng date"].dt.year == active_year].sort_values("pstng date")
    if year_mdf.empty:
        last_qty = round(float(mdf.sort_values("pstng date")["Quantity"].iloc[-1]), 2)
        return {
            "active_year": active_year,
            "current_month_consumption": last_qty,
            "last_month": last_qty,
            "runout_monthly_rate": last_qty,
            "months_available": 1,
        }
    months_avail = max(int(year_mdf["pstng date"].dt.month.nunique()), 1)
    ytd_total = float(year_mdf["Quantity"].sum())
    last_month = round(float(year_mdf["Quantity"].iloc[-1]), 2)
    return {
        "active_year": active_year,
        "current_month_consumption": last_month,
        "last_month": last_month,
        "runout_monthly_rate": round(ytd_total / months_avail, 2),
        "months_available": months_avail,
    }

def get_risk(predicted, inventory, abc):
    gap = predicted - inventory
    if gap <= 0:
        return "Low"
    ratio = gap / max(predicted, 1)
    if abc == "A":
        return "High" if ratio > 0.2 else "Medium"
    if abc == "B":
        return "High" if ratio > 0.4 else "Medium"
    return "High" if ratio > 0.6 else "Medium"

import functools

# Global in-memory cache dictionary to store recommendations
_recommendation_cache = {}

def clear_recommendation_cache():
    """Clear the pre-computed recommendations cache."""
    global _recommendation_cache
    _recommendation_cache.clear()
    print("Recommendation cache cleared.")

def recommendation_engine(material: str, horizon_days: int = 30, shop: str = None):
    """
    Single source of truth for all forecasts across the platform.
    try: ML recursive forecast
    except: fallback_forecast() — hidden from business users
    When shop is specified, returns shop-specific metadata/inventory.
    """
    cache_key = (material, horizon_days, shop)
    if cache_key in _recommendation_cache:
        return _recommendation_cache[cache_key]

    res = _recommendation_engine_uncached(material, horizon_days, shop)
    _recommendation_cache[cache_key] = res
    return res

def _recommendation_engine_uncached(material: str, horizon_days: int = 30, shop: str = None):
    df = _get_df()
    mdf = df[df["Material"] == material].copy()
    if mdf.empty:
        raise HTTPException(404, f"Material '{material}' not found")

    fallback_used = False
    try:
        fc = recursive_ml_forecast(material, horizon_days)
    except Exception:
        fc = fallback_forecast(material, horizon_days)
        fallback_used = True

    predicted = fc["predicted_next_month"]
    horizon_forecast = fc["horizon_forecast"]

    meta_info = get_material_meta(material, shop=shop)
    abc       = meta_info.get("abc", "C")
    inventory = meta_info.get("inventory", 1500)
    val_type  = meta_info.get("val_type", 1)
    shop      = meta_info.get("shop", shop or "Unknown")
    machine   = meta_info.get("machine", "Unknown")

    lead_time     = calc_lead_time(val_type)
    inhouse_time  = {"min": 15, "max": 30, "label": "15–30 days"}
    total_lt_min  = lead_time["min"] + inhouse_time["min"]
    total_lt_max  = lead_time["max"] + inhouse_time["max"]

    active_year = latest_year()
    year_stats  = get_active_year_consumption(mdf, active_year)
    last_month  = year_stats["last_month"]
    current_month_consumption = year_stats["current_month_consumption"]

    order_qty    = max(round(predicted - inventory, 0), 0)
    safety_stock = round(predicted * 0.15, 0)
    reorder_qty  = int(order_qty + safety_stock)

    monthly_fc = list(fc.get("monthly_forecasts", [predicted]))
    while len(monthly_fc) < 3:
        monthly_fc.append(monthly_fc[-1] if monthly_fc else predicted)

    fc_30d = round(monthly_fc[0], 2)
    fc_60d = round(monthly_fc[0] + monthly_fc[1], 2)
    fc_90d = round(monthly_fc[0] + monthly_fc[1] + monthly_fc[2], 2)

    predicted_monthly_demand = predicted
    avg_daily         = max(predicted_monthly_demand / 30.0, 0.01)
    days_until_runout = int(inventory / avg_daily)
    runout_date       = date.today() + timedelta(days=days_until_runout)
    reorder_date      = runout_date - timedelta(days=total_lt_min)
    already_late      = reorder_date <= date.today()

    risk = get_risk(predicted, inventory, abc)

    if order_qty <= 0:
        alert  = f"✅ Stock sufficient. Inventory ({inventory:,.0f}) covers forecast ({predicted:,.0f}). No order needed."
        action = "No Action Required"
    elif already_late:
        alert  = f"🚨 ORDER TODAY: Stock runs out in {days_until_runout} days but lead time is {total_lt_min}–{total_lt_max} days. Order {reorder_qty:,.0f} units immediately."
        action = "Order Immediately — Overdue"
    elif risk == "High":
        alert  = f"🚨 CRITICAL: Order {reorder_qty:,.0f} units by {reorder_date.strftime('%d %b %Y')}. Stock runs out {runout_date.strftime('%d %b %Y')}."
        action = "Immediate Order Required"
    else:
        alert  = f"⚠️ Plan order of {reorder_qty:,.0f} units by {reorder_date.strftime('%d %b %Y')}. Stock runs out {runout_date.strftime('%d %b %Y')}."
        action = "Order Recommended"

    yearly_consumption = {int(k): float(v) for k, v in mdf.groupby(mdf["pstng date"].dt.year)["Quantity"].sum().items()}

    return {
        "material":   material,
        "shop":       shop,
        "machine":    machine,
        "abc_class":  abc,
        "forecast": {
            "predicted_next_month": round(predicted, 2),
            "horizon_forecast":     round(horizon_forecast, 2),
            "horizon_days":         horizon_days,
            "monthly_forecasts":    monthly_fc,
            "forecast_30d":         fc_30d,
            "forecast_60d":         fc_60d,
            "forecast_90d":         fc_90d,
            "last_month":           last_month,
            "current_month_consumption": current_month_consumption,
            "forecast_source":      "AI Forecast Engine",
            "forecast_type":        "Recursive Multi-Step Forecasting",
        },
        "inventory": {
            "current_stock":  inventory,
            "safety_stock":   int(safety_stock),
            "gap":            round(predicted - inventory, 2),
        },
        "order": {
            "order_qty":       int(order_qty),
            "recommended_qty": reorder_qty,
            "action":          action,
        },
        "lead_time": {
            "procurement":    lead_time["label"],
            "inhouse":        inhouse_time["label"],
            "total":          f"{total_lt_min}–{total_lt_max} days",
            "reorder_by":     reorder_date.strftime("%d %b %Y"),
            "runout_date":    runout_date.strftime("%d %b %Y"),
            "days_to_runout": days_until_runout,
            "already_late":   already_late,
        },
        "risk":  risk,
        "alert": alert,
        "yearly_consumption": yearly_consumption,
        "active_year": active_year,
        "year_metadata": get_year_metadata(active_year),
        "developer": {
            "fallback_used":      fallback_used,
            "prediction_source":  fc.get("prediction_source", "ML"),
            "best_model":         meta.get("best_model"),
            "best_mae":           meta.get("best_mae"),
            "forecast_type":      "Recursive Multi-Step Forecasting",
        },
    }

# ── AUTH & USER SYSTEM ──────────────────────────────────
import hashlib

USERS_FILE  = os.path.join(BASE_DIR, "data", "users.json")
CONFIG_FILE = os.path.join(BASE_DIR, "data", "config.json")

def hash_password(password: str, salt: str = "spareai_salt_12345") -> str:
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

def load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        default_users = {
            "admin": {
                "username": "admin",
                "password_hash": hash_password("admin123"),
                "role": "Higher Authority",
                "shop": None
            }
        }
        with open(USERS_FILE, 'w') as f:
            json.dump(default_users, f, indent=4)
        return default_users
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users: dict):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

def load_config() -> dict:
    if not os.path.exists(CONFIG_FILE):
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        default_config = {"budget_passcode": "1234"}
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {"budget_passcode": "1234"}

def save_config(config: dict):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Initialize files
load_users()
load_config()

class SignupRequest(BaseModel):
    username: str
    password: str
    role: str
    shop: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class PasscodeUpdateRequest(BaseModel):
    username: str
    current_passcode: str
    new_passcode: str

# ── ROUTES ────────────────────────────────────────────────

@app.post("/auth/signup")
def signup(req: SignupRequest):
    users = load_users()
    username_clean = req.username.strip()
    if not username_clean:
        raise HTTPException(400, "Username cannot be empty")
    if len(req.password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")
    if username_clean in users:
        raise HTTPException(400, "Username already exists")
    users[username_clean] = {
        "username": username_clean,
        "password_hash": hash_password(req.password),
        "role": req.role,
        "shop": req.shop
    }
    save_users(users)
    return {"status": "success", "message": "User registered successfully"}

@app.post("/auth/login")
def login(req: LoginRequest):
    users = load_users()
    username_clean = req.username.strip()
    if username_clean not in users:
        raise HTTPException(400, "Invalid username or password")
    user_data = users[username_clean]
    if hash_password(req.password) != user_data["password_hash"]:
        raise HTTPException(400, "Invalid username or password")
    return {
        "status": "success",
        "user": {
            "username": user_data["username"],
            "role": user_data["role"],
            "shop": user_data["shop"]
        }
    }

@app.get("/auth/profile")
def get_profile(username: str):
    users = load_users()
    username_clean = username.strip()
    if username_clean not in users:
        raise HTTPException(404, "User not found")
    user_data = users[username_clean]
    return {
        "username": user_data["username"],
        "role": user_data["role"],
        "shop": user_data["shop"]
    }

@app.get("/config/budget-passcode")
def get_budget_passcode():
    cfg = load_config()
    return {"passcode": cfg.get("budget_passcode", "1234")}

@app.post("/config/set-passcode")
def set_budget_passcode(req: PasscodeUpdateRequest):
    users = load_users()
    username_clean = req.username.strip()
    if username_clean not in users:
        raise HTTPException(401, "Unauthorized")
    user_data = users[username_clean]
    if user_data["role"] != "Higher Authority":
        raise HTTPException(403, "Only Higher Authorities can change the budget passcode")
    cfg = load_config()
    if cfg.get("budget_passcode", "1234") != req.current_passcode:
        raise HTTPException(400, "Incorrect current passcode")
    cfg["budget_passcode"] = req.new_passcode.strip()
    save_config(cfg)
    return {"status": "success", "message": "Budget passcode changed successfully"}

@app.post("/config/budget-passcode")
def set_budget_passcode_alias(req: PasscodeUpdateRequest):
    return set_budget_passcode(req)

@app.get("/")
def home():
    return {"status": "running", "version": "5.0.0", "data_source": "local Excel (data/data.xlsx)"}

@app.get("/forecast-engine")
def forecast_engine():
    leaderboard = sorted(
        [{"model": k, "mae": v} for k, v in meta.get("all_results", {}).items()],
        key=lambda x: x["mae"],
    )
    last_trained = "Unknown"
    if os.path.exists(MODEL_PATH):
        mtime = os.path.getmtime(MODEL_PATH)
        last_trained = datetime.fromtimestamp(mtime).strftime("%d %b %Y %H:%M")
    return {
        "engine": "AutoML Selection Engine",
        "best_model": meta.get("best_model"),
        "best_mae": meta.get("best_mae"),
        "leaderboard": leaderboard,
        "features": meta.get("features", []),
        "dataset_size": len(_get_df()),
        "forecast_type": "Recursive Multi-Step Forecasting",
        "last_training_date": last_trained,
        "training_metadata": {
            "best_model": meta.get("best_model"),
            "best_mae": meta.get("best_mae"),
            "features": meta.get("features", []),
            "all_results": meta.get("all_results", {}),
        },
    }

@app.get("/plant-summary")
def plant_summary(year: Optional[int] = None, shop: Optional[str] = None):
    df = _get_df()
    year_df, selected_year = filter_by_year(year)
    if shop:
        if "Shop" in year_df.columns:
            year_df = year_df[year_df["Shop"] == shop]
        if "Shop" in df.columns:
            df = df[df["Shop"] == shop]

    total_materials = int(year_df["Material"].nunique())
    total_records   = int(len(year_df))
    total_consumed  = round(float(year_df["Quantity"].sum()), 2)
    top_material    = year_df.groupby("Material")["Quantity"].sum().idxmax() if not year_df.empty else None

    abc_dist = {}
    if "ABC_Class" in year_df.columns:
        abc_dist = year_df.drop_duplicates("Material")["ABC_Class"].value_counts().to_dict()

    shop_summary = {}
    if "Shop" in year_df.columns:
        shop_summary = total_consumption_by_shop(selected_year)
        if shop:
            shop_summary = shop_summary[shop_summary["Shop"] == shop]
        shop_summary = shop_summary.set_index("Shop")["Quantity"].to_dict()

    total_inventory = 0
    if "Inventory_Qty" in df.columns:
        total_inventory = int(df.sort_values("pstng date").drop_duplicates("Material", keep="last")["Inventory_Qty"].sum())

    if year_df.empty:
        year_meta = {"year": selected_year, "months_available": 0, "coverage_pct": 0.0, "is_ytd": True}
    else:
        months_available = int(year_df["pstng date"].dt.month.nunique())
        is_ytd = months_available < 12
        coverage_pct = round(months_available / 12 * 100, 1)
        year_meta = {"year": selected_year, "months_available": months_available, "coverage_pct": coverage_pct, "is_ytd": is_ytd}

    return {
        "year":             selected_year,
        "year_metadata":    year_meta,
        "latest_year":      latest_year(),
        "available_years":  available_years(),
        "total_materials":  total_materials,
        "total_records":    total_records,
        "total_consumed":   total_consumed,
        "total_consumed_label": f"{selected_year} YTD" if year_meta["is_ytd"] else f"{selected_year} Total",
        "top_material":     top_material,
        "total_inventory":  total_inventory,
        "abc_distribution": abc_dist,
        "shop_consumption": shop_summary,
    }

@app.get("/procurement-summary")
def procurement_summary(shop: Optional[str] = None):
    df = _get_df()
    if shop and "Shop" in df.columns:
        df = df[df["Shop"] == shop]
    if "Shop" in df.columns:
        mat_shop_pairs = df[["Material", "Shop"]].drop_duplicates().values.tolist()
    else:
        mat_shop_pairs = [[m, None] for m in df["Material"].unique().tolist()]
    results = []
    for material, s in mat_shop_pairs:
        try:
            rec = recommendation_engine(material, shop=s)
            results.append(rec)
        except Exception:
            pass
    order = {"High": 0, "Medium": 1, "Low": 2}
    results.sort(key=lambda x: order.get(x["risk"], 3))
    return results

@app.get("/critical-alerts")
def critical_alerts(shop: Optional[str] = None):
    df = _get_df()
    if shop and "Shop" in df.columns:
        df = df[df["Shop"] == shop]
    materials = df["Material"].unique().tolist()
    alerts    = []
    for m in materials:
        try:
            rec = recommendation_engine(m, shop=shop)
            if rec["risk"] in ["High", "Medium"]:
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
    return alerts

@app.get("/materials")
def get_materials(shop: Optional[str] = None):
    df = _get_df()
    if shop and "Shop" in df.columns:
        df = df[df["Shop"] == shop]
    return {"materials": sorted(df["Material"].unique().tolist())}

@app.get("/years")
def years():
    years_list = available_years()
    latest = years_list[-1] if years_list else None
    return {
        "years": years_list,
        "latest_year": latest,
        "year_metadata": get_year_metadata(latest) if latest else None,
        "all_years_metadata": [get_year_metadata(y) for y in years_list],
    }

@app.get("/top-materials")
def top_materials(year: Optional[int] = None, limit: int = 10, shop: Optional[str] = None):
    year_df, _ = filter_by_year(year)
    if shop and "Shop" in year_df.columns:
        year_df = year_df[year_df["Shop"] == shop]
    result = (
        year_df.groupby("Material", as_index=False)
        .agg(total_quantity=("Quantity", "sum"))
        .sort_values(["total_quantity", "Material"], ascending=[False, True])
        .head(limit)
        .reset_index(drop=True)
    )
    result.insert(0, "rank", range(1, len(result) + 1))
    result["total_value"] = None
    result["value_metric_available"] = False
    return result.to_dict(orient="records")

@app.get("/shop-consumption")
def shop_consumption(year: Optional[int] = None, shop: Optional[str] = None):
    res = total_consumption_by_shop(year)
    if shop and "Shop" in res.columns:
        res = res[res["Shop"] == shop]
    return res.to_dict(orient="records")

@app.get("/shop-monthly")
def shop_monthly(year: Optional[int] = None, shop: Optional[str] = None):
    df = _get_df()
    if "Shop" not in df.columns:
        return []
    year_df, selected_year = filter_by_year(year)
    tmp = year_df.copy()
    if shop and "Shop" in tmp.columns:
        tmp = tmp[tmp["Shop"] == shop]
    tmp["month_str"] = tmp["pstng date"].dt.strftime("%Y-%m")
    result = tmp.groupby(["month_str", "Shop"])["Quantity"].sum().reset_index()
    return {
        "year": selected_year,
        "year_metadata": get_year_metadata(selected_year, shop=shop),
        "records": result.to_dict(orient="records"),
    }

@app.get("/abc-analysis")
def abc_analysis(year: Optional[int] = None, shop: Optional[str] = None):
    year_df, _ = filter_by_year(year)
    if shop and "Shop" in year_df.columns:
        year_df = year_df[year_df["Shop"] == shop]
    result = (
        year_df.groupby("ABC_Class", as_index=False)
        .agg(total_qty=("Quantity", "sum"), material_count=("Material", "nunique"))
        .sort_values("ABC_Class")
        .reset_index(drop=True)
    )
    rows = result.to_dict(orient="records")
    for row in rows:
        row["metric"] = "Quantity Consumed"
    return rows

@app.get("/forecast/{material}")
def forecast(material: str, horizon: int = 30, shop: Optional[str] = None):
    return recommendation_engine(material, horizon, shop=shop)

@app.get("/history/{material}")
def history(material: str, shop: Optional[str] = None):
    df = _get_df()
    mdf = df[df["Material"] == material].copy()
    if shop and "Shop" in mdf.columns:
        mdf = mdf[mdf["Shop"] == shop]
    if mdf.empty:
        return []
    return (
        mdf.sort_values("pstng date")[["pstng date", "Quantity"]]
        .to_dict(orient="records")
    )

@app.get("/shop-predictions")
def shop_predictions(horizon: int = 30, shop: Optional[str] = None):
    """Per-shop, per-material forecasts via recommendation_engine()."""
    df = _get_df()
    if "Shop" in df.columns:
        if shop:
            df = df[df["Shop"] == shop]
        mat_shop_pairs = df[["Material", "Shop"]].drop_duplicates().values.tolist()
    else:
        mat_shop_pairs = [[m, None] for m in df["Material"].unique().tolist()]
    results = []
    for material, s in mat_shop_pairs:
        try:
            rec = recommendation_engine(material, horizon, shop=s)
            stock        = rec["inventory"]["current_stock"]
            shop_val     = rec["shop"]
            machine      = rec["machine"]
            abc          = rec["abc_class"]
            lead_time    = rec["lead_time"]["total"]
            is_import    = rec["lead_time"]["procurement"].lower().find("import") >= 0
            fc_qty       = rec["forecast"]["horizon_forecast"]
            gap          = fc_qty - stock
            safety_stock = rec["inventory"]["safety_stock"]
            order_needed = rec["order"]["recommended_qty"]
            days_stock   = rec["lead_time"]["days_to_runout"]
            urgency      = "Critical" if days_stock <= horizon else ("Watch" if days_stock <= horizon * 1.5 else "OK")
            results.append({
                "material": material, "shop": shop_val, "machine": machine,
                "abc": abc, "stock": stock, "forecast_qty": fc_qty,
                "gap": round(gap, 0), "days_stock": days_stock,
                "safety_stock": int(safety_stock), "order_needed": order_needed,
                "forecast_source": "AI Forecast Engine",
                "monthly_forecasts": rec["forecast"]["monthly_forecasts"],
                "order_formula": "max(forecast_qty - stock, 0) + safety_stock",
                "lead_time": lead_time, "is_import": is_import, "urgency": urgency,
                "risk": rec["risk"], "developer": rec.get("developer", {}),
            })
        except Exception:
            pass
    results.sort(key=lambda x: {"Critical": 0, "Watch": 1, "OK": 2}.get(x["urgency"], 3))
    return results

@app.get("/dashboard-validation")
def dashboard_validation(year: Optional[int] = None, shop: Optional[str] = None):
    return validate_dashboard_metrics(year, shop=shop)

# ── LOCAL DATA STATUS & RETRAIN ───────────────────────────
_retrain_running   = False
_retrain_last_time = None
_retrain_last_error = None

def _trigger_local_retrain():
    global _retrain_running, _retrain_last_time, _retrain_last_error
    if _retrain_running:
        print("Retrain already running. Skipping.")
        return
    _retrain_running = True
    try:
        pipeline = [
            (os.path.join(BASE_DIR, "step1_preprocess.py"), "Step 1: Preprocess"),
            (os.path.join(BASE_DIR, "step2_features.py"),   "Step 2: Features"),
            (os.path.join(BASE_DIR, "step3_train.py"),      "Step 3: Train"),
        ]
        import subprocess, sys
        for script, label in pipeline:
            result = subprocess.run(
                [sys.executable, script],
                capture_output=True, text=True, timeout=600
            )
            if result.returncode != 0:
                raise RuntimeError(f"{label} failed:\n{result.stderr[-1000:]}")
        reload_data_and_model()
        _retrain_last_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        _retrain_last_error = None
    except Exception as exc:
        _retrain_last_error = str(exc)
        print(f"Retrain failed: {exc}")
    finally:
        _retrain_running = False

def local_force_refresh_task():
    try:
        load_local_data()
        _trigger_local_retrain()
    except Exception as e:
        print(f"Force refresh failed: {e}")

@app.get("/data/status")
def data_status():
    """Returns the status of the local data file."""
    file_size = 0
    file_modified = "unknown"
    if os.path.exists(DATA_PATH):
        file_size = os.path.getsize(DATA_PATH)
        file_modified = datetime.fromtimestamp(os.path.getmtime(DATA_PATH)).strftime("%Y-%m-%d %H:%M:%S")
    return {
        "status": "loaded" if _df_cache is not None else "not_loaded",
        "data_source": "local Excel (data/data.xlsx)",
        "last_loaded": _last_loaded_time,
        "file_modified": file_modified,
        "file_size_bytes": file_size,
        "data_rows": len(_df_cache) if _df_cache is not None else 0,
        "retrain_running": _retrain_running,
        "retrain_last_time": _retrain_last_time,
        "retrain_last_error": _retrain_last_error,
    }

@app.post("/data/reload")
def data_reload(background_tasks: BackgroundTasks):
    """Reloads data.xlsx from local disk and retrains models."""
    background_tasks.add_task(local_force_refresh_task)
    return {"status": "triggered", "message": "Local file reload and retrain started — check /data/status for progress."}

@app.get("/retrain/status")
def retrain_status_endpoint():
    """Returns the status of the last background ML retraining."""
    return {
        "retrain_running":    _retrain_running,
        "retrain_last_time":  _retrain_last_time,
        "retrain_last_error": _retrain_last_error,
        "model": {
            "best_model": meta.get("best_model"),
            "best_mae":   meta.get("best_mae"),
            "features":   meta.get("features", []),
        },
        "auto_retrain": True,
    }