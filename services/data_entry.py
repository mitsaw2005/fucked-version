"""
services/data_entry.py
Data Entry API — CRUD for Inventory and ABC Master, backed by Google Sheets.
Falls back to local Excel reads when Sheets is not configured.
"""
import io
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/data-entry", tags=["Data Entry"])

# ── Helpers ────────────────────────────────────────────────────────────────

def _load_sheets_config() -> Optional[dict]:
    cfg_path = Path(__file__).resolve().parent.parent / "config" / "google_sheets.json"
    if not cfg_path.is_file():
        return None
    try:
        return json.loads(cfg_path.read_text())
    except Exception:
        return None


def _get_gspread_spreadsheet():
    """Open the configured Apps Script endpoint. Raises HTTPException if not ready."""
    cfg = _load_sheets_config()
    if not cfg:
        raise HTTPException(
            status_code=503,
            detail="Google Sheets is not configured. Please set up Data Source first.",
        )
    apps_script_url = cfg.get("apps_script_url", "")
    if not apps_script_url:
        raise HTTPException(
            status_code=503,
            detail="Incomplete Google Sheets configuration (missing Apps Script Web App URL).",
        )
    return apps_script_url, cfg


def _ws_to_df(apps_script_url, sheet_name: str) -> pd.DataFrame:
    if not apps_script_url:
        return pd.DataFrame()
    try:
        response = requests.post(
            apps_script_url,
            json={"action": "read_sheets", "sheets": [sheet_name]},
            timeout=30
        )
        if response.status_code != 200:
            logger.warning("Failed to read sheet '%s': HTTP %d", sheet_name, response.status_code)
            return pd.DataFrame()
        res_json = response.json()
        if res_json.get("status") != "success":
            logger.warning("Failed to read sheet '%s': %s", sheet_name, res_json.get("message"))
            return pd.DataFrame()
        
        sheet_data = res_json.get("data", {}).get(sheet_name, [])
        if not sheet_data or len(sheet_data) == 0:
            return pd.DataFrame()
            
        if len(sheet_data) > 1:
            df = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
        else:
            df = pd.DataFrame(columns=sheet_data[0])
            
        if not df.empty:
            df.columns = df.columns.str.strip()
        return df
    except Exception as exc:
        logger.warning("Could not read sheet '%s': %s", sheet_name, exc)
        return pd.DataFrame()


def _df_to_sheet(apps_script_url, sheet_name: str, df: pd.DataFrame) -> None:
    """Overwrite a worksheet with a DataFrame (header + rows) via Apps Script."""
    if not apps_script_url:
        raise HTTPException(status_code=503, detail="Apps Script URL is not configured.")
    try:
        df_clean = df.fillna("")
        data = [df_clean.columns.tolist()] + df_clean.astype(str).values.tolist()
        
        response = requests.post(
            apps_script_url,
            json={"action": "write_sheet", "sheet": sheet_name, "data": data},
            timeout=30
        )
        if response.status_code != 200:
            raise Exception(f"HTTP {response.status_code}: {response.text}")
        res_json = response.json()
        if res_json.get("status") != "success":
            raise Exception(res_json.get("message", "Unknown error from Apps Script"))
    except Exception as exc:
        logger.exception("Failed to write sheet '%s' via Apps Script", sheet_name)
        raise HTTPException(status_code=500, detail=f"Failed to write sheet '{sheet_name}' via Apps Script: {exc}")


def _local_df_for_sheet(sheet_name: str) -> pd.DataFrame:
    """Read a specific sheet from local data.xlsx as fallback."""
    base = Path(__file__).resolve().parent.parent / "data" / "data.xlsx"
    if not base.is_file():
        return pd.DataFrame()
    try:
        sheets = pd.read_excel(base, sheet_name=None, engine="openpyxl")
        for k, v in sheets.items():
            if k.strip().lower() == sheet_name.strip().lower():
                v.columns = v.columns.str.strip()
                return v
    except Exception:
        pass
    return pd.DataFrame()


def _get_primary_df() -> pd.DataFrame:
    """Get the primary consumption DataFrame (from cache or local Excel)."""
    try:
        import services as svc
        df = svc._df_cache
        if df is not None:
            return df
    except Exception:
        pass
    base = Path(__file__).resolve().parent.parent / "data" / "data.xlsx"
    if base.is_file():
        try:
            sheets = pd.read_excel(base, sheet_name=None, engine="openpyxl")
            df = pd.concat(sheets.values(), ignore_index=True)
            df.columns = df.columns.str.strip()
            return df
        except Exception:
            pass
    return pd.DataFrame()


# ── Pydantic models ────────────────────────────────────────────────────────

class InventoryRecord(BaseModel):
    material: str
    material_description: str = ""
    inventory_quantity: float = 0.0
    last_updated: str = ""


class ABCRecord(BaseModel):
    material: str
    material_description: str = ""
    abc_class: str  # A, B, or C


class NewMaterialRecord(BaseModel):
    material_code: str
    material_description: str = ""
    abc_class: str  # A, B, or C
    inventory_quantity: float = 0.0


# ── Inventory endpoints ─────────────────────────────────────────────────────

@router.get("/inventory")
def list_inventory(search: str = "", page: int = 1, page_size: int = 50):
    """List all inventory records (from Google Sheets if configured, local Excel otherwise)."""
    cfg = _load_sheets_config()
    if cfg:
        try:
            spreadsheet, cfg_data = _get_gspread_spreadsheet()
            sheet_name = cfg_data.get("inventory_sheet", "Inventory")
            df = _ws_to_df(spreadsheet, sheet_name)
        except HTTPException:
            df = _local_df_for_sheet("Inventory")
    else:
        df = _local_df_for_sheet("Inventory")

    if df.empty:
        return {"records": [], "total": 0, "page": page, "page_size": page_size}

    # Normalize column names
    col_map = {}
    for c in df.columns:
        cl = c.lower().replace(" ", "_").replace("-", "_")
        col_map[c] = cl
    df = df.rename(columns=col_map)

    if search:
        mask = df.apply(lambda row: row.astype(str).str.contains(search, case=False, na=False).any(), axis=1)
        df = df[mask]

    total = len(df)
    start = (page - 1) * page_size
    df = df.iloc[start: start + page_size]
    return {"records": df.to_dict(orient="records"), "total": total, "page": page, "page_size": page_size}


@router.post("/inventory")
def upsert_inventory(record: InventoryRecord):
    """Add or update an inventory record in Google Sheets."""
    spreadsheet, cfg_data = _get_gspread_spreadsheet()
    sheet_name = cfg_data.get("inventory_sheet", "Inventory")
    df = _ws_to_df(spreadsheet, sheet_name)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    new_row = {
        "Material": record.material.strip(),
        "Material_Description": record.material_description,
        "Inventory_Quantity": record.inventory_quantity,
        "Last_Updated": record.last_updated or now,
    }

    if df.empty:
        df = pd.DataFrame([new_row])
    else:
        df.columns = df.columns.str.strip()
        mat_col = next((c for c in df.columns if c.lower() in ("material", "material_code", "mat")), None)
        if mat_col:
            mask = df[mat_col].astype(str).str.strip().str.upper() == record.material.strip().upper()
            if mask.any():
                for k, v in new_row.items():
                    if k in df.columns:
                        df.loc[mask, k] = v
                    else:
                        df[k] = ""
                        df.loc[mask, k] = v
            else:
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    _df_to_sheet(spreadsheet, sheet_name, df)
    return {"status": "success", "material": record.material, "action": "upserted"}


@router.delete("/inventory/{material}")
def delete_inventory(material: str):
    """Delete an inventory record from Google Sheets."""
    spreadsheet, cfg_data = _get_gspread_spreadsheet()
    sheet_name = cfg_data.get("inventory_sheet", "Inventory")
    df = _ws_to_df(spreadsheet, sheet_name)
    if df.empty:
        raise HTTPException(status_code=404, detail="Inventory sheet is empty")
    df.columns = df.columns.str.strip()
    mat_col = next((c for c in df.columns if c.lower() in ("material", "material_code", "mat")), None)
    if not mat_col:
        raise HTTPException(status_code=400, detail="No Material column found in inventory sheet")
    mask = df[mat_col].astype(str).str.strip().str.upper() != material.strip().upper()
    df = df[mask].reset_index(drop=True)
    _df_to_sheet(spreadsheet, sheet_name, df)
    return {"status": "success", "material": material, "action": "deleted"}


# ── ABC endpoints ───────────────────────────────────────────────────────────

@router.get("/abc")
def list_abc(search: str = "", page: int = 1, page_size: int = 50):
    """List all ABC mappings."""
    cfg = _load_sheets_config()
    if cfg:
        try:
            spreadsheet, cfg_data = _get_gspread_spreadsheet()
            sheet_name = cfg_data.get("abc_sheet", "ABC Master")
            df = _ws_to_df(spreadsheet, sheet_name)
        except HTTPException:
            df = _local_df_for_sheet("ABC Master")
    else:
        df = _local_df_for_sheet("ABC Master")

    if df.empty:
        return {"records": [], "total": 0, "page": page, "page_size": page_size}

    if search:
        mask = df.apply(lambda row: row.astype(str).str.contains(search, case=False, na=False).any(), axis=1)
        df = df[mask]

    total = len(df)
    df_page = df.iloc[(page - 1) * page_size: page * page_size]
    return {"records": df_page.to_dict(orient="records"), "total": total, "page": page, "page_size": page_size}


@router.post("/abc")
def upsert_abc(record: ABCRecord):
    """Add or update an ABC classification in Google Sheets."""
    if record.abc_class.upper() not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="ABC class must be A, B, or C")
    spreadsheet, cfg_data = _get_gspread_spreadsheet()
    sheet_name = cfg_data.get("abc_sheet", "ABC Master")
    df = _ws_to_df(spreadsheet, sheet_name)

    new_row = {
        "Material": record.material.strip(),
        "Material_Description": record.material_description,
        "ABC_Class": record.abc_class.upper(),
    }

    if df.empty:
        df = pd.DataFrame([new_row])
    else:
        df.columns = df.columns.str.strip()
        mat_col = next((c for c in df.columns if c.lower() in ("material", "material_code", "mat")), None)
        if mat_col:
            mask = df[mat_col].astype(str).str.strip().str.upper() == record.material.strip().upper()
            if mask.any():
                for k, v in new_row.items():
                    if k in df.columns:
                        df.loc[mask, k] = v
                    else:
                        df[k] = ""
                        df.loc[mask, k] = v
            else:
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    _df_to_sheet(spreadsheet, sheet_name, df)
    return {"status": "success", "material": record.material, "abc_class": record.abc_class.upper()}


@router.delete("/abc/{material}")
def delete_abc(material: str):
    """Delete an ABC mapping from Google Sheets."""
    spreadsheet, cfg_data = _get_gspread_spreadsheet()
    sheet_name = cfg_data.get("abc_sheet", "ABC Master")
    df = _ws_to_df(spreadsheet, sheet_name)
    if df.empty:
        raise HTTPException(status_code=404, detail="ABC sheet is empty")
    df.columns = df.columns.str.strip()
    mat_col = next((c for c in df.columns if c.lower() in ("material", "material_code", "mat")), None)
    if not mat_col:
        raise HTTPException(status_code=400, detail="No Material column found in ABC sheet")
    df = df[df[mat_col].astype(str).str.strip().str.upper() != material.strip().upper()].reset_index(drop=True)
    _df_to_sheet(spreadsheet, sheet_name, df)
    return {"status": "success", "material": material, "action": "deleted"}


# ── New Material Registration ───────────────────────────────────────────────

@router.post("/register-material")
def register_material(record: NewMaterialRecord):
    """Register a new material in both ABC Master and Inventory sheets."""
    if record.abc_class.upper() not in ("A", "B", "C"):
        raise HTTPException(status_code=400, detail="ABC class must be A, B, or C")
    spreadsheet, cfg_data = _get_gspread_spreadsheet()

    abc_name = cfg_data.get("abc_sheet", "ABC Master")
    inv_name = cfg_data.get("inventory_sheet", "Inventory")
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # Write ABC
    abc_df = _ws_to_df(spreadsheet, abc_name)
    abc_row = {"Material": record.material_code.strip(),
               "Material_Description": record.material_description,
               "ABC_Class": record.abc_class.upper()}
    if abc_df.empty:
        abc_df = pd.DataFrame([abc_row])
    else:
        abc_df = pd.concat([abc_df, pd.DataFrame([abc_row])], ignore_index=True)
    _df_to_sheet(spreadsheet, abc_name, abc_df)

    # Write Inventory
    inv_df = _ws_to_df(spreadsheet, inv_name)
    inv_row = {"Material": record.material_code.strip(),
               "Material_Description": record.material_description,
               "Inventory_Quantity": record.inventory_quantity,
               "Last_Updated": now}
    if inv_df.empty:
        inv_df = pd.DataFrame([inv_row])
    else:
        inv_df = pd.concat([inv_df, pd.DataFrame([inv_row])], ignore_index=True)
    _df_to_sheet(spreadsheet, inv_name, inv_df)

    return {"status": "success", "material_code": record.material_code, "action": "registered"}


# ── Missing Mappings ────────────────────────────────────────────────────────

@router.get("/missing-mappings")
def get_missing_mappings(page: int = 1, page_size: int = 100):
    """Find materials in consumption data missing from ABC or Inventory sheets."""
    primary_df = _get_primary_df()
    if primary_df.empty:
        return {"records": [], "total": 0}

    mat_col = next((c for c in primary_df.columns if c.lower() in ("material", "material_code", "mat")), None)
    if not mat_col:
        return {"records": [], "total": 0, "message": "No Material column in consumption data"}

    consumption_materials = set(primary_df[mat_col].dropna().astype(str).str.strip().unique())

    # Description map
    desc_col = next((c for c in primary_df.columns if "desc" in c.lower() or "name" in c.lower()), None)
    desc_map: Dict[str, str] = {}
    if desc_col:
        for mat, grp in primary_df.groupby(mat_col):
            vals = grp[desc_col].dropna().astype(str)
            desc_map[str(mat).strip()] = vals.iloc[0] if len(vals) else ""

    # Read ABC & Inventory sheets
    cfg = _load_sheets_config()
    abc_materials: set = set()
    inv_materials: set = set()

    if cfg:
        try:
            spreadsheet, cfg_data = _get_gspread_spreadsheet()
            abc_df = _ws_to_df(spreadsheet, cfg_data.get("abc_sheet", "ABC Master"))
            inv_df = _ws_to_df(spreadsheet, cfg_data.get("inventory_sheet", "Inventory"))
            if not abc_df.empty:
                abc_col = next((c for c in abc_df.columns if c.lower() in ("material", "material_code", "mat")), None)
                if abc_col:
                    abc_materials = set(abc_df[abc_col].dropna().astype(str).str.strip())
            if not inv_df.empty:
                inv_col = next((c for c in inv_df.columns if c.lower() in ("material", "material_code", "mat")), None)
                if inv_col:
                    inv_materials = set(inv_df[inv_col].dropna().astype(str).str.strip())
        except Exception as exc:
            logger.warning("Could not read sheets for missing mappings: %s", exc)

    records = []
    for mat in sorted(consumption_materials):
        missing_abc = mat not in abc_materials
        missing_inv = mat not in inv_materials
        if missing_abc or missing_inv:
            records.append({
                "material": mat,
                "description": desc_map.get(mat, ""),
                "missing_abc": missing_abc,
                "missing_inventory": missing_inv,
            })

    total = len(records)
    page_records = records[(page - 1) * page_size: page * page_size]
    return {"records": page_records, "total": total, "page": page, "page_size": page_size}


# ── Bulk Upload ─────────────────────────────────────────────────────────────

def _validate_and_parse(file_bytes: bytes, required_cols: List[str]) -> pd.DataFrame:
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
    except Exception:
        try:
            df = pd.read_csv(io.BytesIO(file_bytes))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Cannot parse file: {exc}")
    df.columns = df.columns.str.strip()
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {missing}")
    return df


@router.post("/bulk-upload/abc")
async def bulk_upload_abc(file: UploadFile = File(...)):
    """Upload an Excel/CSV of ABC mappings. Columns required: Material, ABC_Class."""
    content = await file.read()
    df = _validate_and_parse(content, ["Material", "ABC_Class"])
    df["ABC_Class"] = df["ABC_Class"].astype(str).str.upper().str.strip()
    invalid = df[~df["ABC_Class"].isin(["A", "B", "C"])]
    errors = [f"Row {i+2}: ABC_Class '{row.ABC_Class}' is invalid" for i, row in invalid.iterrows()]

    df = df[df["ABC_Class"].isin(["A", "B", "C"])].copy()

    spreadsheet, cfg_data = _get_gspread_spreadsheet()
    sheet_name = cfg_data.get("abc_sheet", "ABC Master")
    existing = _ws_to_df(spreadsheet, sheet_name)

    if existing.empty:
        merged = df
        new_count, updated_count = len(df), 0
    else:
        existing.columns = existing.columns.str.strip()
        mat_col = next((c for c in existing.columns if c.lower() in ("material", "material_code")), "Material")
        merged = existing.copy()
        new_count, updated_count = 0, 0
        for _, row in df.iterrows():
            mat = str(row["Material"]).strip().upper()
            mask = merged[mat_col].astype(str).str.strip().str.upper() == mat
            if mask.any():
                merged.loc[mask, "ABC_Class"] = row["ABC_Class"]
                updated_count += 1
            else:
                merged = pd.concat([merged, pd.DataFrame([row])], ignore_index=True)
                new_count += 1

    _df_to_sheet(spreadsheet, sheet_name, merged)
    return {"status": "success", "new": new_count, "updated": updated_count, "errors": errors}


@router.post("/bulk-upload/inventory")
async def bulk_upload_inventory(file: UploadFile = File(...)):
    """Upload an Excel/CSV of inventory records. Columns required: Material, Inventory_Quantity."""
    content = await file.read()
    df = _validate_and_parse(content, ["Material", "Inventory_Quantity"])
    df["Inventory_Quantity"] = pd.to_numeric(df["Inventory_Quantity"], errors="coerce").fillna(0)

    spreadsheet, cfg_data = _get_gspread_spreadsheet()
    sheet_name = cfg_data.get("inventory_sheet", "Inventory")
    existing = _ws_to_df(spreadsheet, sheet_name)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    df["Last_Updated"] = now

    if existing.empty:
        merged = df
        new_count, updated_count = len(df), 0
    else:
        existing.columns = existing.columns.str.strip()
        mat_col = next((c for c in existing.columns if c.lower() in ("material", "material_code")), "Material")
        merged = existing.copy()
        new_count, updated_count = 0, 0
        for _, row in df.iterrows():
            mat = str(row["Material"]).strip().upper()
            mask = merged[mat_col].astype(str).str.strip().str.upper() == mat
            if mask.any():
                merged.loc[mask, "Inventory_Quantity"] = row["Inventory_Quantity"]
                merged.loc[mask, "Last_Updated"] = now
                updated_count += 1
            else:
                merged = pd.concat([merged, pd.DataFrame([row])], ignore_index=True)
                new_count += 1

    _df_to_sheet(spreadsheet, sheet_name, merged)
    return {"status": "success", "new": new_count, "updated": updated_count, "errors": []}
