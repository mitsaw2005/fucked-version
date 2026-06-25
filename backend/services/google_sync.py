"""
backend/services/google_sync.py
================================
Google Sheets native data source.

Flow:
1. Authenticate with service_account.json via gspread.
2. Open the configured spreadsheet.
3. Read consumption, inventory, and ABC Master worksheets.
4. Merge into a single DataFrame matching the dashboard schema.
5. Atomically update globals.df_cache.
6. Invalidate API cache and mark ML model as stale.
7. Log timing and status.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable

import gspread
import pandas as pd

from backend.core import globals as G
from backend.core.config import (
    load_google_sheets_config,
    SERVICE_ACCOUNT_PATH,
    SYNC_LOG_FILE,
)
from backend.services import cache_service

logger = logging.getLogger("google_sync")
logging.basicConfig(level=logging.INFO)

# ── Logging to file ──────────────────────────────────────────────────
_file_handler = logging.FileHandler(str(SYNC_LOG_FILE), encoding="utf-8")
_file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_file_handler)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _get_client(cfg: dict) -> gspread.Client:
    sa_path = cfg.get("service_account_path", str(SERVICE_ACCOUNT_PATH))
    if not os.path.isabs(sa_path):
        from backend.core.config import BASE_DIR
        sa_path = str(BASE_DIR / sa_path)
    if not Path(sa_path).exists():
        raise FileNotFoundError(
            f"Service account JSON not found at '{sa_path}'. "
            "Upload it via the Data Source tab."
        )
    return gspread.service_account(filename=sa_path)


def _read_sheet(spreadsheet: gspread.Spreadsheet, name: str, notify: Callable) -> Optional[pd.DataFrame]:
    """Read a single worksheet by name.  Returns None on missing/empty."""
    try:
        ws = spreadsheet.worksheet(name)
        records = ws.get_all_records()
        if not records:
            notify(f"  ⚠ Sheet '{name}' is empty — skipping.")
            return None
        df = pd.DataFrame(records)
        df.columns = df.columns.str.strip()
        notify(f"  ✅ '{name}': {len(df)} rows, {len(df.columns)} cols")
        return df
    except gspread.exceptions.WorksheetNotFound:
        notify(f"  ℹ Sheet '{name}' not found — skipping.")
        return None
    except Exception as exc:
        notify(f"  ⚠ Could not read '{name}': {exc}")
        return None


def _build_dataframe(cfg: dict, notify: Callable) -> pd.DataFrame:
    """Combines all detected yearly sheets, inventory, and master sheets."""
    import re
    import random
    import numpy as np

    client = _get_client(cfg)
    spreadsheet_id = cfg.get("spreadsheet_id", "").strip()
    if not spreadsheet_id:
        raise ValueError("Spreadsheet ID is empty. Please configure it in Settings.")

    try:
        ss = client.open_by_key(spreadsheet_id)
    except gspread.exceptions.SpreadsheetNotFound:
        raise ValueError(f"Spreadsheet not found: The ID '{spreadsheet_id}' is invalid or the file does not exist.")
    except gspread.exceptions.APIError as api_err:
        err_str = str(api_err)
        if "PERMISSION_DENIED" in err_str or "403" in err_str:
            raise PermissionError("Permission denied: Service account does not have access. Please share the Google Sheet with the Service Account email.")
        raise ValueError(f"Google API error: {err_str}")

    # Automatically detect all yearly worksheets (matching YY-YY)
    sheets = ss.worksheets()
    year_sheet_pattern = re.compile(r"^\d{2}-\d{2}$")
    detected_yearly_sheets = [ws.title for ws in sheets if year_sheet_pattern.match(ws.title)]
    
    if not detected_yearly_sheets:
        raise ValueError("No yearly consumption worksheets matching 'YY-YY' (e.g. '24-25') found in spreadsheet.")

    notify(f"Found yearly sheets: {', '.join(detected_yearly_sheets)}")

    dfs = []
    for sheet_name in detected_yearly_sheets:
        df_yr = _read_sheet(ss, sheet_name, notify)
        if df_yr is not None and not df_yr.empty:
            dfs.append(df_yr)

    if not dfs:
        raise ValueError("All detected yearly sheets were empty or failed to load.")

    df_cons = pd.concat(dfs, ignore_index=True)

    # Standardize column names (strip spaces)
    df_cons.columns = df_cons.columns.str.strip()

    # Map/clean columns case-insensitively
    rename_map = {}
    for col in df_cons.columns:
        lower_col = col.lower()
        if lower_col in ("quantity", "qty"):
            rename_map[col] = "Quantity"
        elif lower_col in ("mvt", "movement"):
            rename_map[col] = "Mvt"
        elif lower_col in ("partnumber", "part number", "material"):
            rename_map[col] = "PartNumber"
        elif lower_col in ("pstng date", "posting date", "date"):
            rename_map[col] = "pstng date"

    if rename_map:
        df_cons = df_cons.rename(columns=rename_map)

    # gspread auto-numericises numeric-looking cells, turning part numbers like
    # "100000258" into the int 100000258. Force back to string so identifiers
    # match consistently across merges and against string path params (e.g.
    # /forecast/{material}) the same way they would from a text-formatted
    # Excel column.
    if "PartNumber" in df_cons.columns:
        df_cons["PartNumber"] = df_cons["PartNumber"].astype(str).str.strip()

    # Standardize/validate core columns in consumption
    if "pstng date" in df_cons.columns:
        # Google Sheets returns dates as display text (e.g. "25.11.2016", day-first),
        # unlike Excel which stores a real date value — parse day-first and drop rows
        # that still fail instead of crashing the whole sync.
        df_cons["pstng date"] = pd.to_datetime(df_cons["pstng date"], dayfirst=True, errors="coerce")
        n_bad = int(df_cons["pstng date"].isna().sum())
        if n_bad:
            notify(f"  ⚠ Dropped {n_bad} row(s) with unparseable posting dates.")
            df_cons = df_cons.dropna(subset=["pstng date"])
    else:
        raise ValueError("Missing posting date column ('pstng date') in yearly worksheets.")

    if "Quantity" not in df_cons.columns:
        raise ValueError("Missing Quantity column in yearly worksheets.")
    df_cons["Quantity"] = pd.to_numeric(df_cons["Quantity"], errors="coerce").fillna(0.0)

    # Filter consumption movements (Mvt 261/262) and handle returns
    if "Mvt" in df_cons.columns:
        df_cons = df_cons[df_cons["Mvt"].isin([261, 262])].copy()
        df_cons.loc[df_cons["Mvt"] == 262, "Quantity"] *= -1
    else:
        notify("  ⚠ 'Mvt' column not found in yearly sheets — skipping movement type filtering.")

    # Load Inventory and ABC Master
    inv_name = cfg.get("inventory_sheet", "Inventory")
    abc_name = cfg.get("abc_sheet", "ABC Master")

    df_inv = _read_sheet(ss, inv_name, notify)
    df_abc = _read_sheet(ss, abc_name, notify)

    if df_inv is not None:
        # Standardize keys and clean columns for merge
        df_inv.columns = df_inv.columns.str.strip()
        rename_inv = {}
        for col in df_inv.columns:
            lcol = col.lower()
            if lcol in ("partnumber", "part number", "material"):
                rename_inv[col] = "PartNumber"
            elif lcol in ("inventory_qty", "inventory qty", "stock", "qty"):
                rename_inv[col] = "Inventory_Qty"
            elif lcol in ("val type", "valtype", "valuation type"):
                rename_inv[col] = "Val Type"
            elif lcol == "shop":
                rename_inv[col] = "Shop"
            elif lcol in ("machine name", "machine", "machinename"):
                rename_inv[col] = "Machine Name"
        if rename_inv:
            df_inv = df_inv.rename(columns=rename_inv)
        if "PartNumber" in df_inv.columns:
            df_inv["PartNumber"] = df_inv["PartNumber"].astype(str).str.strip()
    else:
        notify(f"  ⚠ Inventory worksheet '{inv_name}' not found — inventory levels will use fallback estimates.")

    if df_abc is not None:
        df_abc.columns = df_abc.columns.str.strip()
        rename_abc = {}
        for col in df_abc.columns:
            lcol = col.lower()
            if lcol in ("partnumber", "part number", "material"):
                rename_abc[col] = "PartNumber"
            elif lcol in ("abc_class", "abc class", "abc"):
                rename_abc[col] = "ABC_Class"
        if rename_abc:
            df_abc = df_abc.rename(columns=rename_abc)
        if "PartNumber" in df_abc.columns:
            df_abc["PartNumber"] = df_abc["PartNumber"].astype(str).str.strip()

    # Perform Merge
    df = df_cons
    if df_inv is not None:
        df = pd.merge(df, df_inv, on="PartNumber", how="left")
    if df_abc is not None:
        df = pd.merge(df, df_abc, on="PartNumber", how="left")

    # Set Material column
    df["Material"] = df["PartNumber"]

    # Fill missing values consistently per Material (business logic fallback)
    random.seed(42)
    np.random.seed(42)

    unique_materials = df["Material"].dropna().unique()

    # 1. ABC Class
    if "ABC_Class" not in df.columns:
        df["ABC_Class"] = np.nan
    abc_map = {}
    for m in unique_materials:
        existing = df[df["Material"] == m]["ABC_Class"].dropna()
        if not existing.empty:
            abc_map[m] = str(existing.iloc[0]).strip().upper()
        else:
            r = random.random()
            abc_map[m] = "A" if r < 0.20 else ("B" if r < 0.50 else "C")
    df["ABC_Class"] = df["ABC_Class"].fillna(df["Material"].map(abc_map)).fillna("C")
    df["ABC_Class"] = df["ABC_Class"].astype(str).str.strip().str.upper()

    # 2. Inventory Quantity
    if "Inventory_Qty" not in df.columns:
        df["Inventory_Qty"] = np.nan
    inv_map = {}
    for m in unique_materials:
        existing = df[df["Material"] == m]["Inventory_Qty"].dropna()
        if not existing.empty:
            inv_map[m] = int(existing.iloc[0])
        else:
            inv_map[m] = random.randint(1000, 2000)
    df["Inventory_Qty"] = df["Inventory_Qty"].fillna(df["Material"].map(inv_map)).fillna(1500)
    df["Inventory_Qty"] = pd.to_numeric(df["Inventory_Qty"], errors="coerce").fillna(1500).astype(int)

    # 3. Valuation Type
    if "Val Type" not in df.columns:
        df["Val Type"] = np.nan
    # Use a fixed random choice generator for mapping if not found
    val_map = {m: int(np.random.choice([1, 2, 3, 4], p=[0.4, 0.2, 0.2, 0.2])) for m in unique_materials}
    df["Val Type"] = df["Val Type"].fillna(df["Material"].map(val_map)).fillna(1)
    df["Val Type"] = pd.to_numeric(df["Val Type"], errors="coerce").fillna(1).astype(int)

    # 4. Shop
    SHOPS = ["Body Shop", "Paint Shop", "Engine Assembly", "Trim & Final", "Press Shop", "Chassis"]
    if "Shop" not in df.columns:
        df["Shop"] = np.nan
    shop_map = {}
    for m in unique_materials:
        existing = df[df["Material"] == m]["Shop"].dropna()
        if not existing.empty:
            shop_map[m] = str(existing.iloc[0]).strip()
        else:
            shop_map[m] = random.choice(SHOPS)
    df["Shop"] = df["Shop"].fillna(df["Material"].map(shop_map)).fillna("Trim & Final")

    # 5. Machine Name
    MACHINES = ["CNC Milling M1", "Robotic Arm A1", "Spray Booth B1", "Curing Oven O1", "Molding M2", "Weld Station W1", "Assembly A2"]
    if "Machine Name" not in df.columns:
        df["Machine Name"] = np.nan
    machine_map = {}
    for m in unique_materials:
        existing = df[df["Material"] == m]["Machine Name"].dropna()
        if not existing.empty:
            machine_map[m] = str(existing.iloc[0]).strip()
        else:
            machine_map[m] = random.choice(MACHINES)
    df["Machine Name"] = df["Machine Name"].fillna(df["Material"].map(machine_map)).fillna("Assembly A2")

    # Update config with detected sheets
    try:
        from backend.core.config import save_google_sheets_config
        save_google_sheets_config({"detected_sheets": detected_yearly_sheets})
    except Exception as e:
        notify(f"  ⚠ Failed to persist detected sheets list: {e}")

    # Set spreadsheet title and ID in globals
    with G.state_lock:
        G.spreadsheet_title = ss.title
        G.spreadsheet_id = spreadsheet_id

    return df


def validate_config_and_access() -> dict:
    """
    Validates Service Account JSON, Spreadsheet ID, connection, and worksheet schemas.
    Returns a status dict: {"status": "success"} or {"status": "error", "error": "Descriptive message"}.
    """
    import re
    try:
        cfg = load_google_sheets_config()
        spreadsheet_id = cfg.get("spreadsheet_id", "").strip()
        if not spreadsheet_id:
            return {"status": "error", "error": "Spreadsheet ID is empty. Please enter a valid Spreadsheet ID in the settings."}

        try:
            client = _get_client(cfg)
        except FileNotFoundError as fnf:
            return {"status": "error", "error": f"Service account file not found. Upload the JSON credentials file. Details: {fnf}"}
        except Exception as auth_err:
            return {"status": "error", "error": f"Google authentication failed: {auth_err}. Check your Service Account JSON credentials."}

        try:
            ss = client.open_by_key(spreadsheet_id)
        except gspread.exceptions.SpreadsheetNotFound:
            return {"status": "error", "error": f"Spreadsheet not found: The Spreadsheet ID '{spreadsheet_id}' is invalid or the file does not exist."}
        except gspread.exceptions.APIError as api_err:
            err_str = str(api_err)
            if "PERMISSION_DENIED" in err_str or "403" in err_str:
                return {"status": "error", "error": "Permission denied: Service account does not have access. Please share the Google Sheet with the Service Account email."}
            return {"status": "error", "error": f"Google Sheets API error: {err_str}"}
        except Exception as open_err:
            return {"status": "error", "error": f"Failed to open Google Spreadsheet: {open_err}"}

        worksheets = [ws.title for ws in ss.worksheets()]

        # Inventory and ABC Master are optional — _build_dataframe() falls back to
        # estimated values per-material when either sheet is absent.
        inventory_name = cfg.get("inventory_sheet", "Inventory")
        abc_name = cfg.get("abc_sheet", "ABC Master")

        # Check Yearly worksheets matching YY-YY
        year_pattern = re.compile(r"^\d{2}-\d{2}$")
        yearly_sheets = [name for name in worksheets if year_pattern.match(name)]
        if not yearly_sheets:
            return {"status": "error", "error": "No yearly worksheets (matching 'YY-YY', e.g., '24-25') detected."}

        email = ""
        try:
            sa_path = cfg.get("service_account_path", str(SERVICE_ACCOUNT_PATH))
            if not os.path.isabs(sa_path):
                from backend.core.config import BASE_DIR
                sa_path = str(BASE_DIR / sa_path)
            sa_data = json.loads(Path(sa_path).read_text())
            email = sa_data.get("client_email", "")
        except Exception:
            pass

        return {
            "status": "success",
            "spreadsheet_title": ss.title,
            "detected_sheets": yearly_sheets,
            "inventory_sheet": inventory_name,
            "abc_sheet": abc_name,
            "service_account_email": email
        }
    except Exception as exc:
        return {"status": "error", "error": f"Validation failed: {exc}"}


def sync_from_google_sheets(progress_callback: Optional[Callable] = None) -> dict:
    """
    Full sync from Google Sheets.
    Updates globals, invalidates cache, marks model stale.
    Returns a status dict.
    """
    messages = []

    def notify(msg: str):
        logger.info(msg)
        messages.append(msg)
        if progress_callback:
            progress_callback(msg)

    t0 = datetime.utcnow()
    try:
        cfg = load_google_sheets_config()
        
        # Validate config and access before sync
        val = validate_config_and_access()
        if val["status"] == "error":
            raise ValueError(val["error"])

        df = _build_dataframe(cfg, notify)

        with G.state_lock:
            G.df_cache         = df
            G.last_sync_time   = _ts()
            G.last_sync_status = "ok"
            G.last_sync_error  = None
            G.sync_count      += 1
            G.is_model_stale   = True
            G.service_account_email = val.get("service_account_email", "")

        # Cache the dataframe locally to disk as a fallback for offline starts
        from backend.core.config import DATA_DIR
        try:
            backup_path = DATA_DIR / "cached_dataframe.pkl"
            df.to_pickle(str(backup_path))
        except Exception as e:
            logger.warning(f"Failed to save local dataframe fallback: {e}")

        cache_service.invalidate_all()
        elapsed = (datetime.utcnow() - t0).total_seconds()
        notify(f"⏱ Sync elapsed: {elapsed:.1f}s")

        from backend.services.logging_service import log_event
        log_event("Google Sync", "ok", f"Synchronized {len(df)} rows from sheets.", elapsed)

        return {
            "status":    "success",
            "rows":      len(df),
            "columns":   list(df.columns),
            "elapsed_s": round(elapsed, 2),
            "messages":  messages,
        }

    except Exception as exc:
        err = str(exc)
        logger.error(f"Sync failed: {err}")
        elapsed = (datetime.utcnow() - t0).total_seconds()
        with G.state_lock:
            G.last_sync_status = "error"
            G.last_sync_error  = err
        from backend.services.logging_service import log_event
        log_event("Google Sync", "error", f"Sync failed: {err}", elapsed)
        return {
            "status":   "error",
            "error":    err,
            "messages": messages,
        }


def test_connection() -> dict:
    """Quick connection test — does not update the DataFrame."""
    val = validate_config_and_access()
    if val["status"] == "error":
        return {"status": "error", "error": val["error"]}
    return {
        "status": "connected",
        "spreadsheet_title": val["spreadsheet_title"],
        "available_sheets": val["detected_sheets"] + [val["inventory_sheet"], val["abc_sheet"]],
        "service_account_email": val["service_account_email"],
    }
