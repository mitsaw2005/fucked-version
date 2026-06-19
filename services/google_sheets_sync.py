import os
import json
import time
import asyncio
import logging
from typing import Optional, List

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .cache import cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/google-sheets-sync", tags=["Google Sheets Sync"])

# Configuration file path (resolved relative to this file → project root / config /)
_CONFIG_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "google_sheets.json")
)

# ── Tuning knobs ──────────────────────────────────────────
HTTP_TIMEOUT       = 120          # seconds — Apps Script cold starts can be slow
MAX_RETRIES        = 3
BACKOFF_FACTOR     = 2            # 2s → 4s → 8s between retries
CONNECT_TIMEOUT    = 10           # seconds for TCP handshake


def _build_session() -> requests.Session:
    """Build a requests Session with automatic retry on transient errors."""
    session = requests.Session()
    retries = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def load_config() -> dict:
    if not os.path.exists(_CONFIG_PATH):
        raise FileNotFoundError(f"Google Sheets config not found at {_CONFIG_PATH}")
    with open(_CONFIG_PATH, "r") as f:
        return json.load(f)


# ── Low-level: fetch ONE sheet at a time ──────────────────
def _fetch_single_sheet(session: requests.Session, url: str, sheet_name: str) -> list:
    """Fetch a single sheet via Apps Script GET endpoint.
    Falls back to POST with a single-sheet payload if GET is not supported.
    """
    try:
        # Try GET first (lighter, cacheable by Apps Script)
        resp = session.get(
            url,
            params={"action": "read", "sheet": sheet_name},
            timeout=(CONNECT_TIMEOUT, HTTP_TIMEOUT),
        )
        if resp.status_code == 200:
            data = resp.json()
            # GET returns the sheet data directly (array of arrays)
            if isinstance(data, list):
                return data
            # Or wrapped in a response object
            if isinstance(data, dict) and data.get("status") == "success":
                return data.get("data", [])
    except Exception:
        pass  # Fall through to POST

    # POST fallback — request a single sheet
    resp = session.post(
        url,
        json={"action": "read_sheets", "sheets": [sheet_name]},
        timeout=(CONNECT_TIMEOUT, HTTP_TIMEOUT),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    res_json = resp.json()
    if res_json.get("status") != "success":
        raise RuntimeError(res_json.get("message", "Unknown Apps Script error"))
    return res_json.get("data", {}).get(sheet_name, [])


def _fetch_all_sheets_bulk(session: requests.Session, url: str, sheet_names: List[str]) -> dict:
    """Fetch all sheets in a single POST (original strategy, used as fallback)."""
    resp = session.post(
        url,
        json={"action": "read_sheets", "sheets": sheet_names},
        timeout=(CONNECT_TIMEOUT, HTTP_TIMEOUT),
    )
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    res_json = resp.json()
    if res_json.get("status") != "success":
        raise RuntimeError(res_json.get("message", "Unknown Apps Script error"))
    return res_json.get("data", {})


# ── Main fetch function ──────────────────────────────────
def fetch_sheets_data(progress_callback=None) -> pd.DataFrame:
    """
    Pull data from Google Sheets via Apps Script and return a cleaned DataFrame.

    Strategy:
    • Fetch sheets individually so one slow/large sheet doesn't block everything.
    • Retry on transient failures with exponential backoff.
    • The *consumption sheet* is the primary source (mirrors data.xlsx).
    • Inventory and ABC-master sheets are merged by material number.
    • Missing optional sheets are skipped gracefully.
    """
    cfg = load_config()

    apps_script_url  = cfg.get("apps_script_url", "").strip()
    consumption_name = cfg.get("consumption_sheet", "").strip() or "data"
    inventory_name   = cfg.get("inventory_sheet", "").strip()
    abc_name         = cfg.get("abc_sheet", "").strip()

    if not apps_script_url:
        raise ValueError("apps_script_url is not set in the configuration.")

    session = _build_session()

    def _notify(msg):
        if progress_callback:
            progress_callback(msg)
        logger.info(msg)

    # ── 1. Fetch primary (consumption) sheet — required ───────
    _notify(f"Fetching primary sheet '{consumption_name}'…")
    t0 = time.time()
    try:
        primary_list = _fetch_single_sheet(session, apps_script_url, consumption_name)
    except Exception as exc:
        # Fallback: try bulk fetch if individual fetch fails
        _notify("Individual fetch failed, trying bulk fetch…")
        sheets_to_fetch = [consumption_name]
        if inventory_name:
            sheets_to_fetch.append(inventory_name)
        if abc_name:
            sheets_to_fetch.append(abc_name)
        all_data = _fetch_all_sheets_bulk(session, apps_script_url, sheets_to_fetch)
        primary_list = all_data.get(consumption_name, [])

        # Build DataFrames from bulk response
        if not primary_list or len(primary_list) == 0:
            raise RuntimeError(
                f"Primary sheet '{consumption_name}' is empty or missing. "
                "Check the sheet name in your configuration."
            )
        primary_df = _list_to_df(primary_list)
        if abc_name and abc_name in all_data:
            primary_df = _merge_abc(primary_df, all_data[abc_name], abc_name)
        if inventory_name and inventory_name in all_data:
            primary_df = _merge_inventory(primary_df, all_data[inventory_name], inventory_name)
        _normalise_dates(primary_df)
        _notify(f"Bulk sync complete: {len(primary_df)} rows in {time.time()-t0:.1f}s")
        return primary_df

    elapsed = time.time() - t0
    _notify(f"Primary sheet fetched in {elapsed:.1f}s ({len(primary_list)} rows)")

    if not primary_list or len(primary_list) == 0:
        raise RuntimeError(
            f"Primary sheet '{consumption_name}' is empty or missing. "
            "Check the sheet name in your configuration."
        )

    primary_df = _list_to_df(primary_list)

    # ── 2. Fetch ABC master (optional) ────────────────────────
    if abc_name:
        _notify(f"Fetching ABC sheet '{abc_name}'…")
        try:
            t1 = time.time()
            abc_list = _fetch_single_sheet(session, apps_script_url, abc_name)
            _notify(f"ABC sheet fetched in {time.time()-t1:.1f}s")
            primary_df = _merge_abc(primary_df, abc_list, abc_name)
        except Exception as e:
            _notify(f"⚠ Skipping ABC sheet (error: {e})")

    # ── 3. Fetch Inventory (optional) ─────────────────────────
    if inventory_name:
        _notify(f"Fetching Inventory sheet '{inventory_name}'…")
        try:
            t2 = time.time()
            inv_list = _fetch_single_sheet(session, apps_script_url, inventory_name)
            _notify(f"Inventory sheet fetched in {time.time()-t2:.1f}s")
            primary_df = _merge_inventory(primary_df, inv_list, inventory_name)
        except Exception as e:
            _notify(f"⚠ Skipping Inventory sheet (error: {e})")

    # ── 4. Normalise dates ────────────────────────────────────
    _normalise_dates(primary_df)

    total_elapsed = time.time() - t0
    _notify(f"Sync complete: {len(primary_df)} rows, {len(primary_df.columns)} cols in {total_elapsed:.1f}s")
    return primary_df


# ── Helper functions ──────────────────────────────────────
def _list_to_df(raw_list: list) -> pd.DataFrame:
    if len(raw_list) > 1:
        df = pd.DataFrame(raw_list[1:], columns=raw_list[0])
    else:
        df = pd.DataFrame(columns=raw_list[0] if raw_list else [])
    df.columns = df.columns.str.strip()
    return df


def _merge_abc(primary_df: pd.DataFrame, abc_list: list, abc_name: str) -> pd.DataFrame:
    if abc_list and len(abc_list) > 0:
        abc_df = _list_to_df(abc_list)
        if "Material" in abc_df.columns and "ABC_Class" in abc_df.columns and "Material" in primary_df.columns:
            if "ABC_Class" not in primary_df.columns:
                primary_df = primary_df.merge(
                    abc_df[["Material", "ABC_Class"]].drop_duplicates("Material"),
                    on="Material",
                    how="left",
                )
                logger.info("Merged ABC_Class from '%s' into primary data.", abc_name)
    return primary_df


def _merge_inventory(primary_df: pd.DataFrame, inv_list: list, inv_name: str) -> pd.DataFrame:
    if inv_list and len(inv_list) > 0:
        inv_df = _list_to_df(inv_list)
        stock_cols = [c for c in inv_df.columns if c != "Material"]
        if "Material" in inv_df.columns and stock_cols and "Material" in primary_df.columns:
            new_cols = [c for c in stock_cols if c not in primary_df.columns]
            if new_cols:
                primary_df = primary_df.merge(
                    inv_df[["Material"] + new_cols].drop_duplicates("Material"),
                    on="Material",
                    how="left",
                )
                logger.info("Merged inventory columns %s from '%s'.", new_cols, inv_name)
    return primary_df


def _normalise_dates(df: pd.DataFrame):
    if "pstng date" in df.columns:
        df["pstng date"] = pd.to_datetime(df["pstng date"], errors="coerce")


# ── Async helper called by the periodic task ───────────────────────────────
async def sync_google_sheets() -> pd.DataFrame:
    """Fetch from Google Sheets (off the event loop), store in cache, return DataFrame."""
    df = await asyncio.to_thread(fetch_sheets_data)
    await cache.set("df", df)
    return df


# ── Manual-sync endpoint ───────────────────────────────────────────────────
@router.post("/manual-sync")
async def manual_sync():
    """Trigger an immediate sync from the UI. Returns row count on success."""
    try:
        df = await sync_google_sheets()
        return {
            "status": "success",
            "rows": len(df),
            "columns": list(df.columns),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.exception("Unexpected error during manual sync")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")


# ── SSE streaming sync endpoint (real-time progress) ──────────────────────
@router.post("/manual-sync-stream")
async def manual_sync_stream():
    """
    Server-Sent Events endpoint: streams progress messages while syncing.
    The frontend can use EventSource or fetch + ReadableStream to show live status.
    """
    async def event_generator():
        progress_messages = []

        def on_progress(msg: str):
            progress_messages.append(msg)

        try:
            yield f"data: {json.dumps({'type': 'progress', 'message': 'Starting sync…'})}\n\n"

            # Run the blocking sync in a thread, collecting progress messages
            loop = asyncio.get_event_loop()
            df_future = loop.run_in_executor(None, fetch_sheets_data, on_progress)

            # Poll for progress messages while the sync is running
            while not df_future.done():
                await asyncio.sleep(0.5)
                while progress_messages:
                    msg = progress_messages.pop(0)
                    yield f"data: {json.dumps({'type': 'progress', 'message': msg})}\n\n"

            df = df_future.result()
            await cache.set("df", df)

            # Flush remaining progress messages
            while progress_messages:
                msg = progress_messages.pop(0)
                yield f"data: {json.dumps({'type': 'progress', 'message': msg})}\n\n"

            yield f"data: {json.dumps({'type': 'done', 'rows': len(df), 'columns': list(df.columns)})}\n\n"

        except Exception as exc:
            logger.exception("Error during streaming sync")
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Diagnostic endpoint ────────────────────────────────────────────────────
@router.get("/status")
def sync_status():
    """Return the current config (without the credentials) for debugging."""
    try:
        cfg = load_config()
        return {
            "configured": True,
            "spreadsheet_id": cfg.get("spreadsheet_id"),
            "consumption_sheet": cfg.get("consumption_sheet"),
            "inventory_sheet": cfg.get("inventory_sheet"),
            "abc_sheet": cfg.get("abc_sheet"),
            "has_credentials": bool(cfg.get("credentials_json")),
        }
    except FileNotFoundError:
        return {"configured": False}
