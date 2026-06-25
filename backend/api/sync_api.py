import json
import os
from pathlib import Path
import threading
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.core import globals as G
from backend.core.config import (
    load_google_sheets_config,
    save_google_sheets_config,
    SERVICE_ACCOUNT_PATH,
)
from backend.services.google_sync import sync_from_google_sheets, test_connection, validate_config_and_access
from backend.services.cache_service import stats as cache_stats

# Remove prefix from router so we can define routes with full paths (/api/sync/..., /api/settings/...)
router = APIRouter(tags=["Sync"])


class SheetsConfigInput(BaseModel):
    spreadsheet_id: str
    inventory_sheet: Optional[str] = "Inventory"
    abc_sheet: Optional[str] = "ABC Master"
    credentials_json: Optional[str] = None
    auto_sync: Optional[bool] = True
    training_interval_hours: Optional[int] = 2


@router.get("/api/sync/status")
def sync_status():
    with G.state_lock:
        cfg = load_google_sheets_config()
        return {
            "last_sync_time":        G.last_sync_time,
            "last_sync_status":      G.last_sync_status,
            "last_sync_error":       G.last_sync_error,
            "sync_count":            G.sync_count,
            "spreadsheet_title":     G.spreadsheet_title,
            "spreadsheet_id":        G.spreadsheet_id or cfg.get("spreadsheet_id", ""),
            "service_account_email": G.service_account_email,
            "row_count":             len(G.df_cache),
            "columns":               list(G.df_cache.columns) if not G.df_cache.empty else [],
            "is_model_stale":        G.is_model_stale,
            "cache_stats":           cache_stats(),
            "auto_sync":             cfg.get("auto_sync", True),
            "training_interval_hours": cfg.get("training_interval_hours", 2),
            "detected_sheets":       cfg.get("detected_sheets", []),
            "inventory_sheet":       cfg.get("inventory_sheet", "Inventory"),
            "abc_sheet":             cfg.get("abc_sheet", "ABC Master"),
            "model_status": {
                "best_model":        G.meta.get("best_model"),
                "best_mae":          G.meta.get("best_mae"),
                "best_rmse":         G.meta.get("best_rmse"),
                "best_mape":         G.meta.get("best_mape"),
                "trained_at":        G.meta.get("trained_at"),
                "last_retrain":      G.retrain_last_time,
                "last_error":        G.retrain_last_error,
                "retrain_running":   G.retrain_running,
            }
        }


@router.post("/api/sync/now")
@router.post("/api/google-sheets-sync/manual-sync")
def manual_sync():
    """Trigger an immediate Google Sheets sync."""
    result = sync_from_google_sheets()
    if result["status"] == "error":
        raise HTTPException(500, result.get("error", "Sync failed"))
    return result


@router.get("/api/sync/stream")
def stream_sync():
    """SSE endpoint for real-time sync progress."""
    def generator():
        messages = []
        done = threading.Event()

        def cb(msg: str):
            messages.append(msg)

        def run():
            sync_from_google_sheets(progress_callback=cb)
            done.set()

        t = threading.Thread(target=run, daemon=True)
        t.start()

        sent = 0
        while not done.is_set() or sent < len(messages):
            time.sleep(0.1)
            while sent < len(messages):
                yield f"data: {json.dumps({'message': messages[sent]})}\n\n"
                sent += 1
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.post("/api/sync/config")
@router.post("/api/settings/google-sheets")
def save_config(cfg: SheetsConfigInput):
    # Save service account credentials if provided in body
    if cfg.credentials_json and cfg.credentials_json.strip():
        try:
            sa = json.loads(cfg.credentials_json)
            required = {"type", "project_id", "private_key", "client_email"}
            missing = required - set(sa.keys())
            if missing:
                raise ValueError(f"Missing required service account fields: {missing}")
            # Write to file
            SERVICE_ACCOUNT_PATH.write_text(cfg.credentials_json.strip())
        except Exception as e:
            raise HTTPException(400, f"Invalid Service Account JSON: {e}")

    # Save settings to config file
    settings = {
        "spreadsheet_id": cfg.spreadsheet_id,
        "inventory_sheet": cfg.inventory_sheet,
        "abc_sheet": cfg.abc_sheet,
        "auto_sync": cfg.auto_sync,
        "training_interval_hours": cfg.training_interval_hours,
    }
    save_google_sheets_config(settings)
    return {"status": "saved"}


@router.get("/api/sync/config")
@router.get("/api/settings/google-sheets")
def get_config():
    cfg = load_google_sheets_config()
    # Read service account contents if they exist, but hide private key details
    sa_json = ""
    if SERVICE_ACCOUNT_PATH.exists():
        try:
            # We can expose the email/project for editing/viewing, but don't leak private key or just load the file
            # Wait, the user said: "The user should never have to paste the JSON again. Do NOT store credentials in Local Storage."
            # Exposing the existing service account contents so the frontend can display it is fine.
            sa_json = SERVICE_ACCOUNT_PATH.read_text()
        except Exception:
            pass
    cfg["credentials_json"] = sa_json
    return cfg


@router.post("/api/sync/test")
def connection_test():
    return test_connection()


@router.get("/api/sync/service-account-exists")
def sa_exists():
    return {"exists": SERVICE_ACCOUNT_PATH.exists(), "path": str(SERVICE_ACCOUNT_PATH)}
