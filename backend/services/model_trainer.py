"""
backend/services/model_trainer.py
===================================
In-process ML training pipeline.

1. Reads the live in-memory DataFrame from globals.
2. Applies feature engineering (lags, rolling windows, date parts).
3. Trains 5 candidate regressors.
4. Evaluates on a held-out test set.
5. Compares against current production model.
6. Swaps only if new model is better (lower MAE).
7. Persists model artefacts to disk.
8. Hot-swaps globals.model / encoder / meta.
9. Clears is_model_stale and invalidates API cache.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from backend.core import globals as G
from backend.core.config import MODEL_PATH, ENCODER_PATH, META_PATH, TRAIN_LOG_FILE
from backend.services import cache_service

logger = logging.getLogger("model_trainer")
_fh = logging.FileHandler(str(TRAIN_LOG_FILE), encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_fh)

FEATURES = ["Material", "lag_1", "lag_3", "rolling_3", "rolling_6", "month", "quarter", "year"]
TARGET   = "Quantity"


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Monthly aggregation + lag/rolling feature engineering."""
    if "pstng date" not in df.columns or "Material" not in df.columns:
        raise ValueError("DataFrame missing required columns: 'pstng date', 'Material'")

    agg_dict = {"Quantity": "sum"}
    for col in ["ABC_Class", "Val Type", "Shop", "Machine Name", "Inventory_Qty"]:
        if col in df.columns:
            agg_dict[col] = "first"

    monthly = (
        df
        .groupby([pd.Grouper(key="pstng date", freq="MS"), "Material"])
        .agg(agg_dict)
        .reset_index()
        .sort_values(["Material", "pstng date"])
    )

    monthly["lag_1"]     = monthly.groupby("Material")["Quantity"].shift(1)
    monthly["lag_3"]     = monthly.groupby("Material")["Quantity"].shift(3)
    monthly["rolling_3"] = monthly.groupby("Material")["Quantity"].transform(lambda x: x.rolling(3).mean())
    monthly["rolling_6"] = monthly.groupby("Material")["Quantity"].transform(lambda x: x.rolling(6).mean())
    monthly["month"]     = monthly["pstng date"].dt.month
    monthly["quarter"]   = monthly["pstng date"].dt.quarter
    monthly["year"]      = monthly["pstng date"].dt.year

    return monthly.dropna(subset=["lag_1", "lag_3", "rolling_3", "rolling_6"])


def _mape(y_true, y_pred) -> float:
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    mask = y_true != 0
    return float(np.mean(np.abs(y_true[mask] - y_pred[mask]) / y_true[mask])) if mask.any() else 0.0


def train_model(force: bool = False) -> dict:
    """
    Train a new model against the current in-memory DataFrame.
    Only replaces production model if MAE improves (or force=True).
    """
    with G.state_lock:
        if G.retrain_running:
            return {"status": "skipped", "reason": "retrain already running"}
        if not G.is_model_stale and not force:
            return {"status": "skipped", "reason": "model not stale"}
        G.retrain_running = True
        df = G.df_cache.copy()

    try:
        logger.info("Starting ML training pipeline…")
        t0 = datetime.utcnow()

        if df.empty:
            raise ValueError("DataFrame is empty — sync from Google Sheets first.")

        # Feature engineering
        dataset = _build_features(df)
        if len(dataset) < 20:
            raise ValueError(f"Insufficient data for training ({len(dataset)} rows after feature engineering).")

        logger.info(f"  Dataset: {len(dataset)} rows")

        # Label-encode Material
        from sklearn.preprocessing import LabelEncoder
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_absolute_error, mean_squared_error
        from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
        from sklearn.linear_model import Ridge
        from xgboost import XGBRegressor
        from lightgbm import LGBMRegressor

        le = LabelEncoder()
        dataset["Material"] = le.fit_transform(dataset["Material"])

        X = dataset[FEATURES]
        y = dataset[TARGET]
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

        candidates = {
            "XGBoost":      XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.05, random_state=42, verbosity=0),
            "LightGBM":     LGBMRegressor(n_estimators=200, max_depth=5, learning_rate=0.05, random_state=42, verbose=-1),
            "RandomForest": RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1),
            "ExtraTrees":   ExtraTreesRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1),
            "Ridge":        Ridge(alpha=1.0),
        }

        results = {}
        for name, m in candidates.items():
            logger.info(f"  Training {name}…")
            m.fit(X_train, y_train)
            preds = np.clip(m.predict(X_test), 0, None)
            mae  = float(mean_absolute_error(y_test, preds))
            rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
            mape = _mape(y_test, preds)
            results[name] = {"model": m, "mae": round(mae, 4), "rmse": round(rmse, 4), "mape": round(mape, 4)}
            logger.info(f"    {name}: MAE={mae:.4f}  RMSE={rmse:.4f}  MAPE={mape:.4f}")

        best_name  = min(results, key=lambda n: results[n]["mae"])
        best_model = results[best_name]["model"]
        new_mae    = results[best_name]["mae"]
        logger.info(f"  ✅ Best: {best_name}  MAE={new_mae}")

        # Compare with current model
        current_mae = G.meta.get("best_mae", float("inf"))
        if new_mae >= current_mae and not force:
            elapsed = (datetime.utcnow() - t0).total_seconds()
            logger.info(f"  Model NOT replaced (new MAE {new_mae} >= current {current_mae})")
            with G.state_lock:
                G.is_model_stale   = False
                G.retrain_running  = False
                G.retrain_last_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                G.retrain_last_error = None
            return {
                "status": "not_replaced",
                "reason": f"new MAE {new_mae} >= current {current_mae}",
                "new_mae": new_mae,
                "current_mae": current_mae,
                "elapsed_s": round(elapsed, 2),
            }

        # Persist artefacts
        joblib.dump(best_model, str(MODEL_PATH))
        joblib.dump(le, str(ENCODER_PATH))

        new_meta = {
            "best_model":  best_name,
            "best_mae":    new_mae,
            "best_rmse":   results[best_name]["rmse"],
            "best_mape":   results[best_name]["mape"],
            "features":    FEATURES,
            "all_results": {n: v["mae"]  for n, v in results.items()},
            "all_results_rmse": {n: v["rmse"] for n, v in results.items()},
            "all_results_mape": {n: v["mape"] for n, v in results.items()},
            "trained_at":  datetime.utcnow().isoformat(),
            "row_count":   len(dataset),
        }
        META_PATH.write_text(json.dumps(new_meta, indent=2))

        # Hot-swap globals
        with G.state_lock:
            G.model            = best_model
            G.encoder          = le
            G.meta             = new_meta
            G.features         = FEATURES
            G.is_model_stale   = False
            G.retrain_running  = False
            G.retrain_last_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            G.retrain_last_error = None

        cache_service.invalidate_all()
        elapsed = (datetime.utcnow() - t0).total_seconds()
        logger.info(f"✅ Training complete in {elapsed:.1f}s — {best_name} deployed")

        from backend.services.logging_service import log_event
        log_event("Model Training", "ok", f"Trained model. Best: {best_name} (MAE: {new_mae}).", elapsed)

        return {
            "status":      "success",
            "best_model":  best_name,
            "best_mae":    new_mae,
            "old_mae":     current_mae,
            "elapsed_s":   round(elapsed, 2),
            "all_results": {n: v["mae"] for n, v in results.items()},
        }

    except Exception as exc:
        err = str(exc)
        logger.error(f"Training failed: {err}")
        elapsed = (datetime.utcnow() - t0).total_seconds() if 't0' in locals() else 0.0
        with G.state_lock:
            G.retrain_running    = False
            G.retrain_last_error = err
            G.retrain_last_time  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        from backend.services.logging_service import log_event
        log_event("Model Training", "error", f"Training failed: {err}", elapsed)
        return {"status": "error", "error": err}
