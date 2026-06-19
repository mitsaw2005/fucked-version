"""
STEP 1 - PREPROCESS
Reads SAP Excel → produces monthly_consumption.csv
Preserves: Shop, Machine Name, ABC_Class, Inventory_Qty, Val Type
Run: python step1_preprocess.py
"""

import pandas as pd
import numpy as np
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_PATH  = os.path.join(BASE_DIR, "data", "data.xlsx")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "monthly_consumption.csv")

print("Reading Excel sheets...")
excel_file = pd.ExcelFile(EXCEL_PATH)
if "Main" in excel_file.sheet_names:
    sheets_to_read = ["Main"]
else:
    sheets_to_read = [str(y) for y in range(2016, 2027)]

dfs = []
for sheet in sheets_to_read:
    try:
        df = pd.read_excel(EXCEL_PATH, sheet_name=sheet)
        dfs.append(df)
        print(f"  ✅ {sheet}: {len(df)} rows | cols: {df.columns.tolist()}")
    except Exception as e:
        print(f"  ⚠️  {sheet} skipped: {e}")

master_df = pd.concat(dfs, ignore_index=True)
print(f"\nTotal rows: {len(master_df)}")
print(f"Columns: {master_df.columns.tolist()}")

# Standardise column names (strip spaces, lowercase for matching)
master_df.columns = master_df.columns.str.strip()

master_df["pstng date"] = pd.to_datetime(master_df["pstng date"])

# Filter consumption movements
consumption_df = master_df[master_df["Mvt"].isin([261, 262])].copy()
consumption_df.loc[consumption_df["Mvt"] == 262, "Quantity"] *= -1

print(f"Consumption rows: {len(consumption_df)}")

# ── Determine which columns exist ─────────────────────────
has_shop        = "Shop"         in consumption_df.columns
has_machine     = "Machine Name" in consumption_df.columns
has_abc         = "ABC_Class"    in consumption_df.columns
has_inventory   = "Inventory_Qty"in consumption_df.columns
has_valtype     = "Val Type"     in consumption_df.columns
has_sloc        = "SLoc"         in consumption_df.columns
has_order       = "Order"        in consumption_df.columns
has_equip       = "Equip Number" in consumption_df.columns

print(f"\nColumn presence:")
print(f"  Shop={has_shop}, Machine={has_machine}, ABC={has_abc}, Inventory={has_inventory}, ValType={has_valtype}")

# ── ABC Class: assign consistently per Material ───────────
MATERIALS = consumption_df["Material"].unique()
random.seed(42)

if not has_abc:
    print("ABC_Class not in data — generating per material...")
    abc_map = {}
    for m in MATERIALS:
        r = random.random()
        abc_map[m] = "A" if r < 0.20 else ("B" if r < 0.50 else "C")
    consumption_df["ABC_Class"] = consumption_df["Material"].map(abc_map)
else:
    consumption_df["ABC_Class"] = consumption_df["ABC_Class"].astype(str).str.strip().str.upper()

# ── Inventory_Qty: consistent per Material ────────────────
if not has_inventory:
    print("Inventory_Qty not in data — generating per material...")
    inv_map = {m: random.randint(1000, 2000) for m in MATERIALS}
    consumption_df["Inventory_Qty"] = consumption_df["Material"].map(inv_map)

# ── Val Type: fill if missing ─────────────────────────────
if not has_valtype:
    consumption_df["Val Type"] = np.random.choice([1,2,3,4], size=len(consumption_df), p=[0.4,0.2,0.2,0.2])

# ── Shop: fill if missing ─────────────────────────────────
SHOPS = ["Body Shop","Paint Shop","Engine Assembly","Trim & Final","Press Shop","Chassis"]
if not has_shop:
    shop_map = {m: random.choice(SHOPS) for m in MATERIALS}
    consumption_df["Shop"] = consumption_df["Material"].map(shop_map)

# ── Machine Name: fill if missing ────────────────────────
MACHINES = ["CNC Milling M1","Robotic Arm A1","Spray Booth B1","Curing Oven O1","Molding M2","Weld Station W1","Assembly A2"]
if not has_machine:
    machine_map = {m: random.choice(MACHINES) for m in MATERIALS}
    consumption_df["Machine Name"] = consumption_df["Material"].map(machine_map)

# ── Aggregate to monthly ──────────────────────────────────
# For non-numeric cols take first value per group
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

os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
monthly.to_csv(OUTPUT_PATH, index=False)

print(f"\n✅ Saved: {OUTPUT_PATH}")
print(f"   Shape: {monthly.shape}")
print(f"   Columns: {monthly.columns.tolist()}")
print(monthly.head(10))
