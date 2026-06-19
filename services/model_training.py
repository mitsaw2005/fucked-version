import os
import json
import logging
import random
import pandas as pd
import numpy as np
import joblib
from datetime import datetime

from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.linear_model import Ridge
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor


# Derive model artefact paths relative to this file so no cross-package import is needed.
_SERVICES_DIR = os.path.dirname(os.path.abspath(__file__))
_BASE_DIR = os.path.dirname(_SERVICES_DIR)          # project root
MODEL_PATH   = os.path.join(_BASE_DIR, "models", "best_model.pkl")
ENCODER_PATH = os.path.join(_BASE_DIR, "models", "encoder.pkl")
META_PATH    = os.path.join(_BASE_DIR, "models", "meta.json")


logger = logging.getLogger(__name__)

FEATURES = ["Material", "lag_1", "lag_3", "rolling_3", "rolling_6", "month", "quarter", "year"]
TARGET = "Quantity"

def calculate_mape(y_true, y_pred):
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    mask = y_true != 0
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs(y_true[mask] - y_pred[mask]) / y_true[mask]))

def train_model(master_df: pd.DataFrame):
    """
    End-to-end ML training pipeline triggered by new data.
    Takes the raw dataframe synced from Google Sheets, processes it, engineers features,
    trains models, selects the best, and saves the artifacts.
    """
    logger.info("Starting model retraining pipeline with %d rows...", len(master_df))
    
    # --- STEP 1: PREPROCESS ---
    df = master_df.copy()
    df.columns = df.columns.str.strip()
    if "pstng date" in df.columns:
        df["pstng date"] = pd.to_datetime(df["pstng date"], errors="coerce")
    
    if "Mvt" in df.columns:
        consumption_df = df[df["Mvt"].isin([261, 262])].copy()
        consumption_df.loc[consumption_df["Mvt"] == 262, "Quantity"] *= -1
    else:
        consumption_df = df.copy()

    has_shop        = "Shop"         in consumption_df.columns
    has_machine     = "Machine Name" in consumption_df.columns
    has_abc         = "ABC_Class"    in consumption_df.columns
    has_inventory   = "Inventory_Qty"in consumption_df.columns
    has_valtype     = "Val Type"     in consumption_df.columns

    MATERIALS = consumption_df["Material"].unique()
    random.seed(42)

    if not has_abc:
        abc_map = {}
        for m in MATERIALS:
            r = random.random()
            abc_map[m] = "A" if r < 0.20 else ("B" if r < 0.50 else "C")
        consumption_df["ABC_Class"] = consumption_df["Material"].map(abc_map)
    else:
        consumption_df["ABC_Class"] = consumption_df["ABC_Class"].astype(str).str.strip().str.upper()

    if not has_inventory:
        inv_map = {m: random.randint(1000, 2000) for m in MATERIALS}
        consumption_df["Inventory_Qty"] = consumption_df["Material"].map(inv_map)

    if not has_valtype:
        consumption_df["Val Type"] = np.random.choice([1,2,3,4], size=len(consumption_df), p=[0.4,0.2,0.2,0.2])

    SHOPS = ["Body Shop","Paint Shop","Engine Assembly","Trim & Final","Press Shop","Chassis"]
    if not has_shop:
        shop_map = {m: random.choice(SHOPS) for m in MATERIALS}
        consumption_df["Shop"] = consumption_df["Material"].map(shop_map)

    MACHINES = ["CNC Milling M1","Robotic Arm A1","Spray Booth B1","Curing Oven O1","Molding M2","Weld Station W1","Assembly A2"]
    if not has_machine:
        machine_map = {m: random.choice(MACHINES) for m in MATERIALS}
        consumption_df["Machine Name"] = consumption_df["Material"].map(machine_map)

    agg_dict = {"Quantity": "sum"}
    for col in ["ABC_Class","Val Type","Shop","Machine Name","Inventory_Qty"]:
        if col in consumption_df.columns:
            agg_dict[col] = "first"

    monthly = (
        consumption_df
        .groupby([pd.Grouper(key="pstng date", freq="MS"), "Material"])
        .agg(agg_dict)
        .reset_index()
    )

    # --- STEP 2: FEATURE ENGINEERING ---
    df_feat = monthly.sort_values(["Material", "pstng date"]).copy()

    df_feat["lag_1"] = df_feat.groupby("Material")["Quantity"].shift(1)
    df_feat["lag_3"] = df_feat.groupby("Material")["Quantity"].shift(3)

    df_feat["rolling_3"] = df_feat.groupby("Material")["Quantity"].transform(lambda x: x.rolling(3).mean())
    df_feat["rolling_6"] = df_feat.groupby("Material")["Quantity"].transform(lambda x: x.rolling(6).mean())

    df_feat["month"]   = df_feat["pstng date"].dt.month
    df_feat["quarter"] = df_feat["pstng date"].dt.quarter
    df_feat["year"]    = df_feat["pstng date"].dt.year

    df_feat = df_feat.dropna(subset=["lag_1","lag_3","rolling_3","rolling_6"])

    if df_feat.empty:
        logger.warning("Not enough data to train models.")
        return False

    # --- STEP 3: TRAIN MODELS ---
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    
    le = LabelEncoder()
    df_feat["Material"] = le.fit_transform(df_feat["Material"])
    joblib.dump(le, ENCODER_PATH)

    X = df_feat[FEATURES]
    y = df_feat[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    candidates = {
        "XGBoost":          XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.05, random_state=42, verbosity=0),
        "LightGBM":         LGBMRegressor(n_estimators=200, max_depth=5, learning_rate=0.05, random_state=42, verbose=-1),
        "RandomForest":     RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1),
        "ExtraTrees":       ExtraTreesRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1),
        "Ridge":            Ridge(alpha=1.0),
    }

    results = {}
    for name, model in candidates.items():
        try:
            model.fit(X_train, y_train)
            preds = np.clip(model.predict(X_test), 0, None)
            mae = mean_absolute_error(y_test, preds)
            rmse = np.sqrt(mean_squared_error(y_test, preds))
            mape = calculate_mape(y_test, preds)
            results[name] = {
                "model": model,
                "mae": round(float(mae), 4),
                "rmse": round(float(rmse), 4),
                "mape": round(float(mape), 4)
            }
        except Exception as e:
            logger.warning(f"Model {name} failed to train: {e}")

    if not results:
        logger.error("All models failed to train.")
        return False

    best_name  = min(results, key=lambda n: results[n]["mae"])
    best_model = results[best_name]["model"]
    best_mae   = results[best_name]["mae"]

    joblib.dump(best_model, MODEL_PATH)
    meta = {
        "best_model":  best_name,
        "best_mae":    best_mae,
        "best_rmse":   results[best_name]["rmse"],
        "best_mape":   results[best_name]["mape"],
        "features":    FEATURES,
        "all_results": {n: v["mae"] for n, v in results.items()},
        "all_results_rmse": {n: v["rmse"] for n, v in results.items()},
        "all_results_mape": {n: v["mape"] for n, v in results.items()},
        "trained_at":  datetime.utcnow().isoformat(),
        "row_count":   len(master_df),
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    logger.info("Training complete. Best model: %s (MAE: %f)", best_name, best_mae)
    return True
