"""
OneDrive Live Sync Engine — SpareAI
=====================================
Streams data.xlsx from OneDrive for Business / SharePoint directly into memory
using Microsoft Graph API + MSAL. No file is ever downloaded to disk.

On change detection (ETag), it:
  1. Instantly refreshes the in-memory DataFrame (API serves new data within seconds)
  2. Triggers background retraining (step1 → step2 → step3)

Usage:
    python onedrive_sync.py --test        # test auth + fetch
    python onedrive_sync.py --status      # show current cache status
    
Import:
    from onedrive_sync import get_df, get_sync_info, force_refresh
"""

import io
import os
import sys
import json
import time
import logging
import threading
import subprocess
from datetime import datetime
from typing import Optional

import msal
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ── LOGGING ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [OneDriveSync] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("onedrive_sync")

# ── CONFIG FROM .env ──────────────────────────────────────
AZURE_CLIENT_ID      = os.getenv("AZURE_CLIENT_ID", "")
AZURE_CLIENT_SECRET  = os.getenv("AZURE_CLIENT_SECRET", "")
AZURE_TENANT_ID      = os.getenv("AZURE_TENANT_ID", "")
ONEDRIVE_ITEM_ID     = os.getenv("ONEDRIVE_ITEM_ID", "")       # File item ID from Graph API
ONEDRIVE_DRIVE_ID    = os.getenv("ONEDRIVE_DRIVE_ID", "")      # Optional: drive ID for SharePoint libs
SHAREPOINT_SITE_ID   = os.getenv("SHAREPOINT_SITE_ID", "")     # Optional: SharePoint site ID
REFRESH_INTERVAL_MIN = int(os.getenv("REFRESH_INTERVAL_MINUTES", "5"))
AUTO_RETRAIN         = os.getenv("AUTO_RETRAIN", "true").lower() == "true"

GRAPH_SCOPES  = ["https://graph.microsoft.com/.default"]
GRAPH_BASE    = "https://graph.microsoft.com/v1.0"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── INTERNAL STATE ────────────────────────────────────────
_lock             = threading.RLock()
_df_cache: Optional[pd.DataFrame] = None
_last_etag: Optional[str]         = None
_last_modified: Optional[str]     = None
_last_sync_time: Optional[str]    = None
_last_error: Optional[str]        = None
_sync_count: int                  = 0
_retrain_running: bool            = False
_retrain_last_time: Optional[str] = None
_retrain_last_error: Optional[str] = None
_msal_app = None


# ── MSAL AUTH ─────────────────────────────────────────────
def _get_msal_app():
    """Create or return cached MSAL confidential client application."""
    global _msal_app
    if _msal_app is None:
        if not all([AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID]):
            raise EnvironmentError(
                "Missing Azure credentials. Set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, "
                "AZURE_TENANT_ID in your .env file. See SETUP_INSTRUCTIONS.md."
            )
        _msal_app = msal.ConfidentialClientApplication(
            client_id=AZURE_CLIENT_ID,
            client_credential=AZURE_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{AZURE_TENANT_ID}",
        )
        log.info("MSAL confidential client app created for tenant: %s", AZURE_TENANT_ID[:8] + "...")
    return _msal_app


def _get_access_token() -> str:
    """Acquire access token using client credentials flow (app-level, no user login needed)."""
    app = _get_msal_app()
    # Try cache first
    result = app.acquire_token_silent(GRAPH_SCOPES, account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=GRAPH_SCOPES)
    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown auth error"))
        raise RuntimeError(f"Failed to acquire access token: {error}")
    return result["access_token"]


def _graph_headers() -> dict:
    """Return headers with a fresh Bearer token."""
    return {
        "Authorization": f"Bearer {_get_access_token()}",
        "Accept": "application/json",
    }


# ── GRAPH API HELPERS ─────────────────────────────────────
def _build_file_url(endpoint: str = "") -> str:
    """
    Build the Graph API URL for the Excel file.
    Supports:
      - Item ID only:              /me/drive/items/{item_id}
      - Drive + Item ID:           /drives/{drive_id}/items/{item_id}
      - Site + Drive + Item ID:    /sites/{site_id}/drives/{drive_id}/items/{item_id}
    """
    if not ONEDRIVE_ITEM_ID:
        raise EnvironmentError(
            "ONEDRIVE_ITEM_ID not set. Run: python onedrive_sync.py --find-file "
            "to locate your file ID."
        )
    if SHAREPOINT_SITE_ID and ONEDRIVE_DRIVE_ID:
        base = f"{GRAPH_BASE}/sites/{SHAREPOINT_SITE_ID}/drives/{ONEDRIVE_DRIVE_ID}/items/{ONEDRIVE_ITEM_ID}"
    elif ONEDRIVE_DRIVE_ID:
        base = f"{GRAPH_BASE}/drives/{ONEDRIVE_DRIVE_ID}/items/{ONEDRIVE_ITEM_ID}"
    else:
        base = f"{GRAPH_BASE}/me/drive/items/{ONEDRIVE_ITEM_ID}"
    return base + endpoint


def _fetch_file_metadata() -> dict:
    """Get file metadata (ETag, lastModifiedDateTime, size) without downloading."""
    url = _build_file_url("")
    resp = requests.get(url, headers=_graph_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def _fetch_file_bytes() -> bytes:
    """Stream the Excel file bytes directly into memory — no disk write."""
    url = _build_file_url("/content")
    resp = requests.get(url, headers=_graph_headers(), timeout=120, stream=True)
    resp.raise_for_status()
    # Consume the stream into a bytes object in memory
    buf = io.BytesIO()
    for chunk in resp.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
        buf.write(chunk)
    return buf.getvalue()


def _parse_excel_bytes(raw_bytes: bytes) -> pd.DataFrame:
    """Parse Excel bytes (all sheets) into a unified DataFrame."""
    buf = io.BytesIO(raw_bytes)
    sheets: dict = pd.read_excel(buf, sheet_name=None, engine="openpyxl")
    if not sheets:
        raise ValueError("Excel file is empty — no sheets found.")
    frames = list(sheets.values())
    df = pd.concat(frames, ignore_index=True)
    # Standardise columns
    df.columns = df.columns.str.strip()
    if "pstng date" in df.columns:
        df["pstng date"] = pd.to_datetime(df["pstng date"], errors="coerce")
    log.info("Parsed Excel → %d rows, %d cols | sheets: %s", len(df), len(df.columns), list(sheets.keys()))
    return df


# ── MAIN SYNC LOGIC ───────────────────────────────────────
def _do_sync() -> bool:
    """
    Check if file has changed on OneDrive and refresh in-memory cache if so.
    Returns True if data was refreshed, False if unchanged.
    """
    global _df_cache, _last_etag, _last_modified, _last_sync_time, _last_error, _sync_count

    try:
        meta = _fetch_file_metadata()
        new_etag     = meta.get("eTag", meta.get("cTag", ""))
        new_modified = meta.get("lastModifiedDateTime", "")

        _last_sync_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        with _lock:
            unchanged = (new_etag and new_etag == _last_etag)

        if unchanged:
            log.debug("File unchanged (ETag: %s). No reload needed.", new_etag[:16])
            _last_error = None
            return False

        # File changed — fetch and parse
        log.info("File change detected (ETag: %s → %s). Streaming from OneDrive...",
                 (_last_etag or "none")[:16], (new_etag or "?")[:16])
        raw = _fetch_file_bytes()
        new_df = _parse_excel_bytes(raw)

        with _lock:
            _df_cache     = new_df
            _last_etag    = new_etag
            _last_modified = new_modified
            _sync_count   += 1
            _last_error    = None

        log.info("✅ Data refreshed in memory. Rows: %d | Last modified: %s", len(new_df), new_modified)
        return True

    except Exception as exc:
        _last_error = str(exc)
        log.error("❌ Sync failed: %s", exc)
        raise


def _background_poll_loop():
    """Background thread: poll OneDrive every REFRESH_INTERVAL_MIN minutes."""
    log.info("Background sync started — polling every %d min", REFRESH_INTERVAL_MIN)
    interval_sec = REFRESH_INTERVAL_MIN * 60

    while True:
        try:
            changed = _do_sync()
            if changed and AUTO_RETRAIN:
                _trigger_retrain()
        except Exception:
            pass  # Errors already logged in _do_sync
        time.sleep(interval_sec)


def _trigger_retrain():
    """Run step1→step2→step3 in a background thread so API stays responsive."""
    global _retrain_running, _retrain_last_time, _retrain_last_error

    def _run():
        global _retrain_running, _retrain_last_time, _retrain_last_error
        with _lock:
            if _retrain_running:
                log.warning("Retrain already in progress — skipping trigger.")
                return
            _retrain_running = True

        log.info("🔄 Starting background retrain: step1 → step2 → step3")
        try:
            pipeline = [
                (os.path.join(BASE_DIR, "step1_preprocess.py"), "Step 1: Preprocess"),
                (os.path.join(BASE_DIR, "step2_features.py"),   "Step 2: Features"),
                (os.path.join(BASE_DIR, "step3_train.py"),      "Step 3: Train"),
            ]
            for script, label in pipeline:
                log.info("  ▶ %s...", label)
                result = subprocess.run(
                    [sys.executable, script],
                    capture_output=True, text=True, timeout=600
                )
                if result.returncode != 0:
                    raise RuntimeError(f"{label} failed:\n{result.stderr[-2000:]}")
                log.info("  ✅ %s done.", label)

            _retrain_last_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            _retrain_last_error = None
            log.info("✅ Retrain pipeline complete. New model is live.")

            # Hot-reload model in api.py
            _hot_reload_model()

        except Exception as exc:
            _retrain_last_error = str(exc)
            log.error("❌ Retrain failed: %s", exc)
        finally:
            _retrain_running = False

    t = threading.Thread(target=_run, daemon=True, name="retrain-pipeline")
    t.start()


def _hot_reload_model():
    """Signal api.py to reload the model from disk after retraining."""
    try:
        import importlib
        import api as _api
        _api.reload_data_and_model()
        log.info("✅ Model hot-reloaded into api.py")
    except Exception as exc:
        log.warning("Hot-reload signal failed (non-fatal): %s", exc)


# ── PUBLIC API ────────────────────────────────────────────
def get_df() -> pd.DataFrame:
    """
    Return the current in-memory DataFrame.
    Falls back to local data.xlsx if OneDrive sync not yet initialised.
    """
    with _lock:
        if _df_cache is not None:
            return _df_cache.copy()

    # Fallback: load from local file while sync initialises
    local_path = os.path.join(BASE_DIR, "data", "data.xlsx")
    if os.path.exists(local_path):
        log.warning("OneDrive cache not ready — loading from local data.xlsx (fallback)")
        sheets = pd.read_excel(local_path, sheet_name=None, engine="openpyxl")
        df = pd.concat(sheets.values(), ignore_index=True)
        df.columns = df.columns.str.strip()
        if "pstng date" in df.columns:
            df["pstng date"] = pd.to_datetime(df["pstng date"], errors="coerce")
        return df

    raise RuntimeError("No data available: OneDrive not synced and no local data.xlsx found.")


def get_sync_info() -> dict:
    """Return current sync status for API endpoints."""
    with _lock:
        return {
            "status":               "error" if _last_error else ("synced" if _df_cache is not None else "initialising"),
            "last_sync_time":       _last_sync_time,
            "last_modified_onedrive": _last_modified,
            "last_etag":            _last_etag,
            "sync_count":           _sync_count,
            "last_error":           _last_error,
            "data_rows":            len(_df_cache) if _df_cache is not None else 0,
            "refresh_interval_min": REFRESH_INTERVAL_MIN,
            "auto_retrain":         AUTO_RETRAIN,
            "retrain_running":      _retrain_running,
            "retrain_last_time":    _retrain_last_time,
            "retrain_last_error":   _retrain_last_error,
            "source":               "OneDrive for Business (Microsoft Graph API)",
        }


def force_refresh(retrain: bool = True) -> dict:
    """Manually force an immediate sync check (ignores ETag cache)."""
    global _last_etag
    with _lock:
        _last_etag = None  # Force re-fetch even if unchanged
    changed = _do_sync()
    if changed and retrain and AUTO_RETRAIN:
        _trigger_retrain()
    return get_sync_info()


def start_background_sync():
    """Start the background polling thread. Call once at app startup."""
    # Do an immediate sync first (blocks until first data is loaded)
    log.info("Running initial OneDrive sync...")
    try:
        _do_sync()
        log.info("Initial sync complete.")
    except Exception as exc:
        log.warning("Initial sync failed (%s) — will use local fallback.", exc)

    # Launch background poller
    t = threading.Thread(target=_background_poll_loop, daemon=True, name="onedrive-sync-poll")
    t.start()
    log.info("Background sync thread started (interval: %d min).", REFRESH_INTERVAL_MIN)


# ── FILE DISCOVERY HELPER ─────────────────────────────────
def find_file_in_onedrive(filename: str = "data.xlsx"):
    """
    Search OneDrive/SharePoint for a file by name and print its IDs.
    Run: python onedrive_sync.py --find-file
    """
    log.info("Searching OneDrive for '%s'...", filename)
    token = _get_access_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Search in user's drive first
    url = f"{GRAPH_BASE}/me/drive/root/search(q='{filename}')"
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.ok:
        items = resp.json().get("value", [])
        print(f"\n{'─'*60}")
        print(f"Found {len(items)} result(s) for '{filename}' in OneDrive:")
        for item in items:
            print(f"\n  Name:     {item.get('name')}")
            print(f"  Item ID:  {item.get('id')}   ← set as ONEDRIVE_ITEM_ID")
            print(f"  Drive ID: {item.get('parentReference', {}).get('driveId', 'N/A')}   ← set as ONEDRIVE_DRIVE_ID")
            print(f"  Path:     {item.get('parentReference', {}).get('path', 'N/A')}/{item.get('name')}")
        print(f"{'─'*60}\n")
    else:
        print(f"Search failed: {resp.status_code} — {resp.text}")

    # Also try SharePoint sites if configured
    if SHAREPOINT_SITE_ID:
        url2 = f"{GRAPH_BASE}/sites/{SHAREPOINT_SITE_ID}/drive/root/search(q='{filename}')"
        resp2 = requests.get(url2, headers=headers, timeout=30)
        if resp2.ok:
            items2 = resp2.json().get("value", [])
            print(f"Found {len(items2)} result(s) in SharePoint site:")
            for item in items2:
                print(f"  Name: {item.get('name')} | Item ID: {item.get('id')}")


# ── CLI ───────────────────────────────────────────────────
if __name__ == "__main__":
    if "--find-file" in sys.argv:
        find_file_in_onedrive()
    elif "--test" in sys.argv:
        print("Testing OneDrive auth + file fetch...")
        try:
            token = _get_access_token()
            print(f"✅ Auth OK. Token starts with: {token[:20]}...")
            meta = _fetch_file_metadata()
            print(f"✅ File metadata:")
            print(f"   Name:          {meta.get('name')}")
            print(f"   Size:          {meta.get('size', 0):,} bytes")
            print(f"   Last Modified: {meta.get('lastModifiedDateTime')}")
            print(f"   ETag:          {meta.get('eTag', meta.get('cTag', 'N/A'))}")
            print("\nFetching file bytes...")
            raw = _fetch_file_bytes()
            print(f"✅ Fetched {len(raw):,} bytes into memory")
            df = _parse_excel_bytes(raw)
            print(f"✅ Parsed DataFrame: {df.shape[0]} rows × {df.shape[1]} cols")
            print(f"   Columns: {df.columns.tolist()[:8]}...")
        except Exception as e:
            print(f"❌ Test failed: {e}")
            sys.exit(1)
    elif "--status" in sys.argv:
        info = get_sync_info()
        print(json.dumps(info, indent=2, default=str))
    else:
        print("Usage: python onedrive_sync.py [--test | --find-file | --status]")
        print("\nOptions:")
        print("  --test       Test Azure auth and file fetch")
        print("  --find-file  Search OneDrive for data.xlsx and print item IDs")
        print("  --status     Show current cache status")
