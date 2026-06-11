"""
STEP 3 - TRAIN MODELS
Trains 5 models, picks best by MAE.
Run: python step3_train.py
"""

import os, json
import pandas as pd
import numpy as np
import joblib

from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor
from sklearn.linear_model import Ridge
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH    = os.path.join(BASE_DIR, "data", "model_dataset.csv")
MODELS_DIR   = os.path.join(BASE_DIR, "models")
MODEL_PATH   = os.path.join(MODELS_DIR, "best_model.pkl")
ENCODER_PATH = os.path.join(MODELS_DIR, "encoder.pkl")
META_PATH    = os.path.join(MODELS_DIR, "meta.json")

FEATURES = ["Material","lag_1","lag_3","rolling_3","rolling_6","month","quarter","year"]
TARGET   = "Quantity"

os.makedirs(MODELS_DIR, exist_ok=True)

print("Loading data...")
df = pd.read_csv(DATA_PATH)
print(f"Shape: {df.shape}")

le = LabelEncoder()
df["Material"] = le.fit_transform(df["Material"])
joblib.dump(le, ENCODER_PATH)
print(f"Encoder saved → {ENCODER_PATH}")

X = df[FEATURES]
y = df[TARGET]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
print(f"Train: {len(X_train)} | Test: {len(X_test)}")

def calculate_mape(y_true, y_pred):
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    mask = y_true != 0
    if not np.any(mask):
        return 0.0
    return float(np.mean(np.abs(y_true[mask] - y_pred[mask]) / y_true[mask]))

candidates = {
    "XGBoost":          XGBRegressor(n_estimators=200, max_depth=5, learning_rate=0.05, random_state=42, verbosity=0),
    "LightGBM":         LGBMRegressor(n_estimators=200, max_depth=5, learning_rate=0.05, random_state=42, verbose=-1),
    "RandomForest":     RandomForestRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1),
    "ExtraTrees":       ExtraTreesRegressor(n_estimators=200, max_depth=10, random_state=42, n_jobs=-1),
    "Ridge":            Ridge(alpha=1.0),
}

results = {}
print("\n--- Training 5 Models ---")
for name, model in candidates.items():
    print(f"Training {name}...")
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
    print(f"  MAE: {mae:.4f}  RMSE: {rmse:.4f}  MAPE: {mape:.4f}")

best_name  = min(results, key=lambda n: results[n]["mae"])
best_model = results[best_name]["model"]
best_mae   = results[best_name]["mae"]
print(f"\n✅ Best: {best_name}  MAE: {best_mae}")

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
}
with open(META_PATH, "w") as f:
    json.dump(meta, f, indent=2)

print(f"Model saved → {MODEL_PATH}")
print(f"Meta  saved → {META_PATH}")
print("\n--- Leaderboard ---")
for rank, (name, info) in enumerate(sorted(results.items(), key=lambda x: x[1]["mae"]), 1):
    tag = " ← BEST" if name == best_name else ""
    print(f"  {rank}. {name:20s} MAE: {info['mae']:.4f}  RMSE: {info['rmse']:.4f}  MAPE: {info['mape']:.4f}{tag}")
