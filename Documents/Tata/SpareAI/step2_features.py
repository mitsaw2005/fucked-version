"""
STEP 2 - FEATURE ENGINEERING
Reads monthly_consumption.csv → produces model_dataset.csv
Run: python step2_features.py
"""

import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_PATH  = os.path.join(BASE_DIR, "data", "monthly_consumption.csv")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "model_dataset.csv")

print("Loading data...")
df = pd.read_csv(INPUT_PATH)
df["pstng date"] = pd.to_datetime(df["pstng date"])
df = df.sort_values(["Material", "pstng date"])

print(f"Shape: {df.shape} | Columns: {df.columns.tolist()}")

# Lag features
df["lag_1"] = df.groupby("Material")["Quantity"].shift(1)
df["lag_3"] = df.groupby("Material")["Quantity"].shift(3)

# Rolling features
df["rolling_3"] = df.groupby("Material")["Quantity"].transform(lambda x: x.rolling(3).mean())
df["rolling_6"] = df.groupby("Material")["Quantity"].transform(lambda x: x.rolling(6).mean())

# Date features
df["month"]   = df["pstng date"].dt.month
df["quarter"] = df["pstng date"].dt.quarter
df["year"]    = df["pstng date"].dt.year

before = len(df)
df = df.dropna(subset=["lag_1","lag_3","rolling_3","rolling_6"])
print(f"Dropped {before - len(df)} rows with NaN")

df.to_csv(OUTPUT_PATH, index=False)
print(f"\n✅ Saved: {OUTPUT_PATH}")
print(f"   Shape: {df.shape}")
print(f"   Columns: {df.columns.tolist()}")
