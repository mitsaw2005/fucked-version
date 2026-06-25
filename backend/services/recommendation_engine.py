"""
backend/services/recommendation_engine.py
==========================================
Single source of truth for all forecasts.  Wraps recursive ML prediction
with a fallback to simple rolling-average.  Results are cached.
"""

import logging
from datetime import date, timedelta, datetime
from typing import Optional

import numpy as np
import pandas as pd

from backend.core import globals as G
from backend.services import cache_service

logger = logging.getLogger("recommendation_engine")

FEATURES = ["Material", "lag_1", "lag_3", "rolling_3", "rolling_6", "month", "quarter", "year"]


# ── Low-level helpers ────────────────────────────────────────────────

def _get_df() -> pd.DataFrame:
    with G.state_lock:
        return G.df_cache.copy()


def _get_model():
    with G.state_lock:
        return G.model, G.encoder, G.meta, G.features


def fmt(n) -> float:
    return round(float(n), 2) if n is not None else 0.0


def available_years() -> list:
    df = _get_df()
    if df.empty or "pstng date" not in df.columns:
        return []
    return sorted(df["pstng date"].dt.year.dropna().astype(int).unique().tolist())


def latest_year() -> Optional[int]:
    years = available_years()
    return years[-1] if years else None


def filter_by_year(year=None):
    df = _get_df()
    if year is None:
        year = latest_year()
    if year is None:
        return df.copy(), year
    return df[df["pstng date"].dt.year == year].copy(), year


# ── ML forecast ──────────────────────────────────────────────────────

def _build_features(qty_series, encoded, target_date, feat_cols):
    qty  = list(qty_series)
    n    = len(qty)
    lag1 = float(qty[-1]) if n >= 1 else 0.0
    lag3 = float(qty[-3]) if n >= 3 else lag1
    r3   = float(np.mean(qty[-3:])) if n >= 3 else lag1
    r6   = float(np.mean(qty[-6:])) if n >= 6 else r3
    return pd.DataFrame([{
        "Material": encoded, "lag_1": lag1, "lag_3": lag3,
        "rolling_3": r3, "rolling_6": r6,
        "month": target_date.month, "quarter": target_date.quarter,
        "year": target_date.year,
    }])[feat_cols]


def _recursive_ml_forecast(material: str, horizon_days: int) -> dict:
    df = _get_df()
    mdf = df[df["Material"] == material].sort_values("pstng date")
    if mdf.empty:
        raise ValueError(f"Material '{material}' not found")

    model, encoder, _meta, feat_cols = _get_model()
    if model is None or encoder is None:
        raise RuntimeError("ML model not loaded")
    if material not in encoder.classes_:
        raise ValueError(f"Material '{material}' not in training encoder")

    encoded    = int(encoder.transform([material])[0])
    last_date  = mdf["pstng date"].iloc[-1]
    qty_series = mdf["Quantity"].tolist()
    months     = max(1, int(round(horizon_days / 30.0)))
    steps      = max(months, 3)
    preds      = []

    for step in range(1, steps + 1):
        target = last_date + pd.DateOffset(months=step)
        X      = _build_features(qty_series, encoded, target, feat_cols or FEATURES)
        pred   = float(max(model.predict(X)[0], 0))
        preds.append(round(pred, 2))
        qty_series.append(pred)

    return {
        "horizon_days":         horizon_days,
        "months":               months,
        "monthly_forecasts":    preds,
        "predicted_next_month": preds[0],
        "horizon_forecast":     round(sum(preds[:months]), 2),
        "fallback_used":        False,
        "prediction_source":    "ML",
        "forecast_type":        "Recursive Multi-Step Forecasting",
    }


def _fallback_forecast(material: str, horizon_days: int) -> dict:
    df  = _get_df()
    mdf = df[df["Material"] == material].sort_values("pstng date")
    if mdf.empty:
        raise ValueError(f"Material '{material}' not found")
    months  = max(1, int(round(horizon_days / 30.0)))
    steps   = max(months, 3)
    recent  = mdf.tail(steps)
    avg     = float(recent["Quantity"].mean()) if len(recent) else 0.0
    monthly = [max(round(avg, 2), 0)] * steps
    return {
        "horizon_days":         horizon_days,
        "months":               months,
        "monthly_forecasts":    monthly,
        "predicted_next_month": monthly[0],
        "horizon_forecast":     max(round(sum(monthly[:months]), 2), 0),
        "fallback_used":        True,
        "prediction_source":    "fallback",
        "forecast_type":        "Rolling Average Fallback",
    }


# ── Supporting enrichment helpers ────────────────────────────────────

def _get_material_meta(material: str, shop: Optional[str]) -> dict:
    df  = _get_df()
    mdf = df[df["Material"] == material]
    if shop:
        s = mdf[mdf["Shop"] == shop]
        if not s.empty:
            mdf = s
    if mdf.empty:
        return {}
    row = mdf.sort_values("pstng date").iloc[-1]
    return {
        "abc":       str(row.get("ABC_Class",  "C")).strip().upper() if "ABC_Class"   in mdf.columns else "C",
        "inventory": int(row.get("Inventory_Qty", 1500))            if "Inventory_Qty" in mdf.columns else 1500,
        "val_type":  int(row.get("Val Type", 1))                    if "Val Type"     in mdf.columns else 1,
        "shop":      str(row.get("Shop",     "Unknown"))            if "Shop"          in mdf.columns else "Unknown",
        "machine":   str(row.get("Machine Name", "Unknown"))        if "Machine Name"  in mdf.columns else "Unknown",
    }


def _calc_lead_time(val_type: int) -> dict:
    if val_type == 2:
        return {"min": 90, "max": 150, "label": "90–150 days (Import)"}
    return {"min": 10, "max": 15, "label": "10–15 days (Local)"}


def _get_risk(predicted, inventory, abc) -> str:
    gap = predicted - inventory
    if gap <= 0:
        return "Low"
    ratio = gap / max(predicted, 1)
    if abc == "A":
        return "High" if ratio > 0.2 else "Medium"
    if abc == "B":
        return "High" if ratio > 0.4 else "Medium"
    return "High" if ratio > 0.6 else "Medium"


def _get_active_year_consumption(mdf, active_year) -> dict:
    year_mdf = mdf[mdf["pstng date"].dt.year == active_year].sort_values("pstng date")
    if year_mdf.empty:
        last_qty = round(float(mdf.sort_values("pstng date")["Quantity"].iloc[-1]), 2)
        return {"active_year": active_year, "current_month_consumption": last_qty,
                "last_month": last_qty, "runout_monthly_rate": last_qty, "months_available": 1}
    months_avail = max(int(year_mdf["pstng date"].dt.month.nunique()), 1)
    ytd_total    = float(year_mdf["Quantity"].sum())
    last_month   = round(float(year_mdf["Quantity"].iloc[-1]), 2)
    return {"active_year": active_year, "current_month_consumption": last_month,
            "last_month": last_month, "runout_monthly_rate": round(ytd_total / months_avail, 2),
            "months_available": months_avail}


# ── Main recommendation engine ───────────────────────────────────────

def recommendation_engine(material: str, horizon_days: int = 30, shop: Optional[str] = None) -> dict:
    """
    Cached single source of truth for forecasts and procurement recommendations.
    """
    cache_key = f"rec::{material}::{horizon_days}::{shop}"
    cached = cache_service.get(cache_key)
    if cached is not None:
        return cached

    df   = _get_df()
    mdf  = df[df["Material"] == material].copy()
    if mdf.empty:
        raise ValueError(f"Material '{material}' not found")

    fallback_used = False
    try:
        fc = _recursive_ml_forecast(material, horizon_days)
    except Exception:
        fc = _fallback_forecast(material, horizon_days)
        fallback_used = True

    predicted        = fc["predicted_next_month"]
    horizon_forecast = fc["horizon_forecast"]

    m_meta    = _get_material_meta(material, shop)
    abc       = m_meta.get("abc", "C")
    inventory = m_meta.get("inventory", 1500)
    val_type  = m_meta.get("val_type", 1)
    shop_val  = m_meta.get("shop", shop or "Unknown")
    machine   = m_meta.get("machine", "Unknown")

    lead_time    = _calc_lead_time(val_type)
    inhouse_time = {"min": 15, "max": 30, "label": "15–30 days"}
    total_lt_min = lead_time["min"] + inhouse_time["min"]
    total_lt_max = lead_time["max"] + inhouse_time["max"]

    active_year = latest_year()
    year_stats  = _get_active_year_consumption(mdf, active_year)
    last_month  = year_stats["last_month"]

    order_qty    = max(round(predicted - inventory, 0), 0)
    safety_stock = round(predicted * 0.15, 0)
    reorder_qty  = int(order_qty + safety_stock)

    monthly_fc = list(fc.get("monthly_forecasts", [predicted]))
    while len(monthly_fc) < 3:
        monthly_fc.append(monthly_fc[-1] if monthly_fc else predicted)

    avg_daily         = max(predicted / 30.0, 0.01)
    days_until_runout = int(inventory / avg_daily)
    runout_date       = date.today() + timedelta(days=days_until_runout)
    reorder_date      = runout_date - timedelta(days=total_lt_min)
    already_late      = reorder_date <= date.today()
    risk              = _get_risk(predicted, inventory, abc)

    if order_qty <= 0:
        alert  = f"✅ Stock sufficient. Inventory ({inventory:,.0f}) covers forecast ({predicted:,.0f}). No order needed."
        action = "No Action Required"
    elif already_late:
        alert  = f"🚨 ORDER TODAY: Stock runs out in {days_until_runout}d but lead time is {total_lt_min}–{total_lt_max}d."
        action = "Order Immediately — Overdue"
    elif risk == "High":
        alert  = f"🚨 CRITICAL: Order {reorder_qty:,.0f} units by {reorder_date.strftime('%d %b %Y')}."
        action = "Immediate Order Required"
    else:
        alert  = f"⚠️ Plan order of {reorder_qty:,.0f} units by {reorder_date.strftime('%d %b %Y')}."
        action = "Order Recommended"

    yearly_consumption = {int(k): float(v)
                          for k, v in mdf.groupby(mdf["pstng date"].dt.year)["Quantity"].sum().items()}
    _meta = G.meta

    result = {
        "material":  material, "shop": shop_val, "machine": machine, "abc_class": abc,
        "forecast": {
            "predicted_next_month":      round(predicted, 2),
            "horizon_forecast":          round(horizon_forecast, 2),
            "horizon_days":              horizon_days,
            "monthly_forecasts":         monthly_fc,
            "forecast_30d":              round(monthly_fc[0], 2),
            "forecast_60d":              round(monthly_fc[0] + monthly_fc[1], 2),
            "forecast_90d":              round(sum(monthly_fc[:3]), 2),
            "last_month":                last_month,
            "current_month_consumption": year_stats["current_month_consumption"],
            "forecast_source":           "AI Forecast Engine",
            "forecast_type":             fc.get("forecast_type", ""),
        },
        "inventory": {
            "current_stock": inventory,
            "safety_stock":  int(safety_stock),
            "gap":           round(predicted - inventory, 2),
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
        "risk":                risk,
        "alert":               alert,
        "yearly_consumption":  yearly_consumption,
        "active_year":         active_year,
        "developer": {
            "fallback_used":     fallback_used,
            "prediction_source": fc.get("prediction_source", "ML"),
            "best_model":        _meta.get("best_model"),
            "best_mae":          _meta.get("best_mae"),
            "forecast_type":     "Recursive Multi-Step Forecasting",
        },
    }

    cache_service.set(cache_key, result)
    return result
