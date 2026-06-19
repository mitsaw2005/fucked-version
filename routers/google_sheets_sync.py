import os
import json
import logging
from typing import List

import pandas as pd
import gspread
from fastapi import APIRouter, HTTPException

from .cache import cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google-sheets-sync", tags=["Google Sheets Sync"])

# Configuration file path (relative to this file)
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "google_sheets.json")

def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Google Sheets config not found at {CONFIG_PATH}")
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def get_service_client(creds_json: str):
    try:
        creds = json.loads(creds_json)
        client = gspread.service_account_from_dict(creds)
        return client
    except Exception as e:
        logger.exception("Failed to create Google Sheets client")
        raise

def fetch_sheets_data() -> pd.DataFrame:
    cfg = load_config()
    spreadsheet_id = cfg.get("spreadsheet_id")
    consumption_sheet = cfg.get("consumption_sheet", "Consumption Data")
    inventory_sheet = cfg.get("inventory_sheet", "Inventory")
    abc_sheet = cfg.get("abc_sheet", "ABC Master")
    credentials = cfg.get("credentials_json")
    
    sheet_names = [consumption_sheet, inventory_sheet, abc_sheet]
    # Filter empty ones
    sheet_names = [s for s in sheet_names if s]

    if not spreadsheet_id or not sheet_names or not credentials:
        raise ValueError("Incomplete Google Sheets configuration")
    client = get_service_client(credentials)
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
    except Exception as e:
        logger.exception("Unable to open spreadsheet")
        raise HTTPException(status_code=500, detail="Failed to open Google Spreadsheet")
    dfs = []
    for name in sheet_names:
        try:
            ws = spreadsheet.worksheet(name)
            data = ws.get_all_records()
            df = pd.DataFrame(data)
            dfs.append(df)
        except Exception as e:
            logger.error(f"Failed to read sheet '{name}': {e}")
            raise HTTPException(status_code=500, detail=f"Error reading sheet {name}")
    if not dfs:
        return pd.DataFrame()
    full_df = pd.concat(dfs, ignore_index=True)
    # Standard clean‑up to match previous local loader
    full_df.columns = full_df.columns.str.strip()
    if "pstng date" in full_df.columns:
        full_df["pstng date"] = pd.to_datetime(full_df["pstng date"], errors="coerce")
    return full_df

# Exported async helper used by the periodic task
async def sync_google_sheets() -> pd.DataFrame:
    """Fetch data from Google Sheets and store it in the in‑memory cache.
    Returns the DataFrame for further processing.
    """
    df = fetch_sheets_data()
    await cache.set("df", df)
    return df

@router.post("/manual-sync")
async def manual_sync():
    """Endpoint to trigger a manual sync from the UI.
    Returns a simple status payload.
    """
    try:
        df = await sync_google_sheets()
        return {"status": "success", "rows": len(df)}
    except Exception as e:
        logger.exception("Manual sync failed")
        raise HTTPException(status_code=500, detail=str(e))
