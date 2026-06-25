"""
backend/services/scheduler.py
==============================
Background schedulers for:
  • Google Sheets sync   — every 5 minutes
  • ML model retraining  — every 2 hours (only when model is stale)

Both run in daemon threads so they die with the process.
"""

import asyncio
import logging
import threading
import time

from backend.core import globals as G

logger = logging.getLogger("scheduler")

_sync_interval_s   = 5 * 60    # 5 minutes
_train_interval_s  = 2 * 60 * 60  # 2 hours


def _sync_loop():
    last_known_update = None
    while True:
        # Dynamically load configuration
        try:
            from backend.core.config import load_google_sheets_config
            cfg = load_google_sheets_config()
            auto_sync_enabled = cfg.get("auto_sync", True)
            spreadsheet_id = cfg.get("spreadsheet_id", "").strip()
        except Exception as e:
            logger.error(f"[Scheduler] Failed to read config in sync loop: {e}")
            auto_sync_enabled = False
            spreadsheet_id = ""

        if not auto_sync_enabled:
            logger.info("[Scheduler] Auto Sync is disabled. Skipping cycle.")
        elif not spreadsheet_id:
            logger.warning("[Scheduler] Spreadsheet ID is not configured. Skipping cycle.")
        else:
            try:
                from backend.services.google_sync import _get_client, sync_from_google_sheets
                client = _get_client(cfg)
                ss = client.open_by_key(spreadsheet_id)
                
                # Fetch modification timestamp from spreadsheet metadata
                try:
                    if hasattr(ss, "get_lastUpdateTime"):
                        current_update = ss.get_lastUpdateTime()
                    elif hasattr(ss, "lastUpdateTime"):
                        current_update = ss.lastUpdateTime
                    else:
                        current_update = None
                except Exception:
                    current_update = None

                if current_update and current_update == last_known_update:
                    logger.info(f"[Scheduler] Google Sheet is unchanged (last update: {current_update}). Skipping full sync.")
                else:
                    logger.info(f"[Scheduler] Spreadsheet changed or initial sync (new: {current_update}, old: {last_known_update}). Performing sync.")
                    result = sync_from_google_sheets()
                    logger.info(f"[Scheduler] Sync status: {result.get('status')}")
                    if result.get("status") == "success":
                        last_known_update = current_update
            except Exception as exc:
                logger.error(f"[Scheduler] Sync execution failed: {exc}")
                from backend.services.logging_service import log_event
                log_event("Scheduler", "error", f"Scheduled sync failed: {exc}")

        # Sleep for 5 minutes
        time.sleep(5 * 60)


def _train_loop():
    while True:
        # Determine training sleep duration from configuration
        try:
            from backend.core.config import load_google_sheets_config
            cfg = load_google_sheets_config()
            interval_hours = cfg.get("training_interval_hours", 2)
            sleep_time_s = max(1, interval_hours) * 60 * 60
        except Exception:
            sleep_time_s = 2 * 60 * 60

        time.sleep(sleep_time_s)

        try:
            with G.state_lock:
                stale = G.is_model_stale
                running = G.retrain_running
            if stale and not running:
                from backend.services.model_trainer import train_model
                logger.info("[Scheduler] Model is stale — starting background retraining…")
                result = train_model()
                logger.info(f"[Scheduler] Training status: {result.get('status')}")
            else:
                logger.info(f"[Scheduler] Scheduled retrain skipped (stale={stale}, running={running})")
        except Exception as exc:
            logger.error(f"[Scheduler] Training execution failed: {exc}")
            from backend.services.logging_service import log_event
            log_event("Scheduler", "error", f"Scheduled training failed: {exc}")


def start_schedulers():
    """Spin up both background scheduler threads. Call once at startup."""
    sync_thread  = threading.Thread(target=_sync_loop,  daemon=True, name="sync-scheduler")
    train_thread = threading.Thread(target=_train_loop, daemon=True, name="train-scheduler")
    sync_thread.start()
    train_thread.start()
    logger.info("✅ Background schedulers started (sync=5min, train=interval-configured)")
