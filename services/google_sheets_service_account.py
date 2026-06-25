"""
services/google_sheets_service_account.py
==========================================
Connects to Google Sheets via a Service Account JSON key (gspread).
No Apps Script relay needed — reads sheets directly using the Sheets API.

Config is stored in  config/google_sheets.json  with keys:
  spreadsheet_id      — the ID from the Google Sheets URL
  consumption_sheet   — tab name for consumption data  (default: "Main")
  inventory_sheet     — tab name for inventory data    (default: "Inventory")
  abc_sheet           — tab name for ABC master        (default: "ABC Master")
  service_account_path — relative path to the service-account JSON
                         (default: "config/service_account.json")

Usage:
  from services.google_sheets_service_account import fetch_sheets_data, sync_google_sheets
"""

import asyncio
import json
import logging
import os
from typing import Optional

import gspread
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .cache import cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google-sheets-sync", tags=["Google Sheets Sync"])

# ── Paths ─────────────────────────────────────────────────
_BASE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
)
_CONFIG_PATH = os.path.join(_BASE_DIR, "config", "google_sheets.json")


# ── Config helpers ─────────────────────────────────────────
def load_config() -> dict:
    if not os.path.exists(_CONFIG_PATH):
        raise FileNotFoundError(f"Google Sheets config not found at {_CONFIG_PATH}")
    with open(_CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(data: dict):
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    with open(_CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ── gspread client ─────────────────────────────────────────
def _get_client(cfg: dict) -> gspread.Client:
    sa_path = cfg.get("service_account_path", "config/service_account.json")
    if not os.path.isabs(sa_path):
        sa_path = os.path.join(_BASE_DIR, sa_path)
    if not os.path.exists(sa_path):
        raise FileNotFoundError(
            f"Service account JSON not found at '{sa_path}'. "
            "Upload it via the Data Source tab."
        )
    return gspread.service_account(filename=sa_path)


# ── Core fetch ─────────────────────────────────────────────
def fetch_sheets_data(progress_callback=None) -> pd.DataFrame:
    """
    Pull all three sheets from Google Sheets and return a merged DataFrame.
    - consumption sheet  →  primary rows
    - ABC master sheet   →  left-joined on Material
    - Inventory sheet    →  left-joined on Material
    Missing optional sheets are skipped gracefully.
    """
    def _notify(msg: str):
        if progress_callback:
            progress_callback(msg)
        logger.info(msg)

    cfg = load_config()
    spreadsheet_id   = cfg.get("spreadsheet_id", "").strip()
    consumption_name = cfg.get("consumption_sheet", "Main").strip()
    inventory_name   = cfg.get("inventory_sheet", "Inventory").strip()
    abc_name         = cfg.get("abc_sheet", "ABC Master").strip()

    if not spreadsheet_id:
        raise ValueError(
            "No spreadsheet_id configured. "
            "Open the Data Source tab, enter your Spreadsheet ID and save."
        )

    _notify("Connecting to Google Sheets via service account…")
    client      = _get_client(cfg)
    spreadsheet = client.open_by_key(spreadsheet_id)
    _notify(f"Opened spreadsheet: {spreadsheet.title}")

    def _read_sheet(name: str) -> Optional[pd.DataFrame]:
        try:
            ws = spreadsheet.worksheet(name)
            records = ws.get_all_records()
            if not records:
                _notify(f"  Sheet '{name}' is empty — skipping.")
                return None
            df = pd.DataFrame(records)
            df.columns = df.columns.str.strip()
            _notify(f"  Sheet '{name}': {len(df)} rows, {len(df.columns)} cols")
            return df
        except gspread.exceptions.WorksheetNotFound:
            _notify(f"  Sheet '{name}' not found — skipping.")
            return None
        except Exception as exc:
            _notify(f"  ⚠ Could not read '{name}': {exc}")
            return None

    # 1. Primary consumption sheet — required
    _notify(f"Reading consumption sheet '{consumption_name}'…")
    primary_df = _read_sheet(consumption_name)
    if primary_df is None or primary_df.empty:
        raise RuntimeError(
            f"Consumption sheet '{consumption_name}' is empty or missing. "
            "Check the sheet name in your Data Source configuration."
        )

    # 2. ABC master — optional merge
    if abc_name:
        _notify(f"Reading ABC master sheet '{abc_name}'…")
        abc_df = _read_sheet(abc_name)
        if abc_df is not None and "Material" in abc_df.columns and "ABC_Class" in abc_df.columns:
            if "ABC_Class" not in primary_df.columns:
                primary_df = primary_df.merge(
                    abc_df[["Material", "ABC_Class"]].drop_duplicates("Material"),
                    on="Material", how="left",
                )
                _notify("  Merged ABC_Class into primary data.")

    # 3. Inventory — optional merge
    if inventory_name:
        _notify(f"Reading inventory sheet '{inventory_name}'…")
        inv_df = _read_sheet(inventory_name)
        if inv_df is not None and "Material" in inv_df.columns:
            new_cols = [c for c in inv_df.columns if c != "Material" and c not in primary_df.columns]
            if new_cols:
                primary_df = primary_df.merge(
                    inv_df[["Material"] + new_cols].drop_duplicates("Material"),
                    on="Material", how="left",
                )
                _notify(f"  Merged inventory columns: {new_cols}")

    # 4. Normalise posting date
    if "pstng date" in primary_df.columns:
        primary_df["pstng date"] = pd.to_datetime(primary_df["pstng date"], errors="coerce")

    _notify(f"✅ Sync complete — {len(primary_df)} rows, {len(primary_df.columns)} columns.")
    return primary_df


# ── Async wrapper for periodic tasks ──────────────────────
async def sync_google_sheets() -> pd.DataFrame:
    """Fetch from Google Sheets (off the event loop) and store in cache."""
    df = await asyncio.to_thread(fetch_sheets_data)
    await cache.set("df", df)
    return df


# ── FastAPI endpoints ──────────────────────────────────────

@router.post("/manual-sync")
async def manual_sync():
    """Trigger an immediate sync. Returns row/column counts."""
    try:
        df = await sync_google_sheets()
        return {
            "status": "success",
            "rows": len(df),
            "columns": list(df.columns),
        }
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Manual sync failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/manual-sync-stream")
async def manual_sync_stream():
    """SSE endpoint — streams real-time progress while syncing."""
    async def event_generator():
        progress_messages: list[str] = []

        def on_progress(msg: str):
            progress_messages.append(msg)

        try:
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Starting sync…'})}\n\n"
            loop = asyncio.get_event_loop()
            df_future = loop.run_in_executor(None, fetch_sheets_data, on_progress)

            while not df_future.done():
                await asyncio.sleep(0.4)
                while progress_messages:
                    msg = progress_messages.pop(0)
                    yield f"data: {json.dumps({'type': 'progress', 'message': msg})}\n\n"

            df = df_future.result()
            await cache.set("df", df)
            while progress_messages:
                msg = progress_messages.pop(0)
                yield f"data: {json.dumps({'type': 'progress', 'message': msg})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'rows': len(df), 'columns': list(df.columns)})}\n\n"

        except Exception as exc:
            logger.exception("Streaming sync error")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/status")
def sync_status():
    """Return current config state (no credentials exposed)."""
    try:
        cfg = load_config()
        sa_path = cfg.get("service_account_path", "config/service_account.json")
        if not os.path.isabs(sa_path):
            sa_path = os.path.join(_BASE_DIR, sa_path)
        return {
            "configured":        bool(cfg.get("spreadsheet_id")),
            "spreadsheet_id":    cfg.get("spreadsheet_id", ""),
            "consumption_sheet": cfg.get("consumption_sheet", ""),
            "inventory_sheet":   cfg.get("inventory_sheet", ""),
            "abc_sheet":         cfg.get("abc_sheet", ""),
            "has_service_account": os.path.exists(sa_path),
        }
    except FileNotFoundError:
        return {"configured": False, "has_service_account": False}


# ── Config REST endpoints (used by Data Source UI tab) ────

class SheetsConfigPayload(BaseModel):
    spreadsheet_id:   str = ""
    consumption_sheet: str = "Main"
    inventory_sheet:  str = "Inventory"
    abc_sheet:        str = "ABC Master"


@router.get("/config")
def get_config():
    try:
        cfg = load_config()
        return SheetsConfigPayload(
            spreadsheet_id=cfg.get("spreadsheet_id", ""),
            consumption_sheet=cfg.get("consumption_sheet", "Main"),
            inventory_sheet=cfg.get("inventory_sheet", "Inventory"),
            abc_sheet=cfg.get("abc_sheet", "ABC Master"),
        )
    except FileNotFoundError:
        return SheetsConfigPayload()


@router.post("/config")
def set_config(payload: SheetsConfigPayload):
    try:
        existing = {}
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH) as f:
                existing = json.load(f)
        existing.update(payload.dict())
        save_config(existing)
        return {"status": "saved", **payload.dict()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
