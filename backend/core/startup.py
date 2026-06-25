"""
backend/core/startup.py
========================
Executed once on FastAPI startup.

1. Initial Google Sheets sync (blocking — dashboard is not served until data is ready).
2. Load existing ML model from disk.
3. Launch background schedulers.
"""

import json
import logging

import joblib

from backend.core import globals as G
from backend.core.config import MODEL_PATH, ENCODER_PATH, META_PATH
from backend.services.google_sync import sync_from_google_sheets
from backend.services.scheduler import start_schedulers

logger = logging.getLogger("startup")


def _load_model_from_disk():
    """Load best_model.pkl + encoder.pkl + meta.json into globals if they exist."""
    try:
        with G.state_lock:
            G.model   = joblib.load(str(MODEL_PATH))
            G.encoder = joblib.load(str(ENCODER_PATH))
        if META_PATH.exists():
            m = json.loads(META_PATH.read_text())
            with G.state_lock:
                G.meta     = m
                G.features = m.get("features", [])
        logger.info(f"✅ ML model loaded from disk: {G.meta.get('best_model')} MAE={G.meta.get('best_mae')}")
    except FileNotFoundError:
        logger.warning("⚠️  No trained model found on disk — ML forecasts will use fallback until first training.")
    except Exception as exc:
        logger.error(f"⚠️  Could not load model: {exc}")


async def on_startup():
    """Called by FastAPI @app.on_event('startup')."""
    import pandas as pd
    from backend.core.config import DATA_DIR
    from backend.services.logging_service import log_event
    
    logger.info("━━━ SpareAI v6 Startup ━━━")
    log_event("Scheduler", "info", "SpareAI starting up...")

    # 1. Load existing model
    _load_model_from_disk()

    # 2. Initial Google Sheets sync
    logger.info("Performing initial Google Sheets sync…")
    result = sync_from_google_sheets()
    if result["status"] == "success":
        logger.info(f"✅ Initial sync: {result['rows']} rows loaded.")
        with G.state_lock:
            G.is_model_stale = False  # Already loaded model is valid for existing data
    else:
        logger.warning(f"⚠️  Initial sync failed: {result.get('error')} — checking local backup cache.")
        # Load local backup if available
        backup_path = DATA_DIR / "cached_dataframe.pkl"
        if backup_path.exists():
            try:
                df = pd.read_pickle(str(backup_path))
                with G.state_lock:
                    G.df_cache = df
                    G.last_sync_time = "loaded from local backup cache"
                    G.last_sync_status = "ok"
                logger.info(f"✅ Loaded {len(df)} rows from local backup cache '{backup_path}'.")
                log_event("Google Sync", "ok", f"Fallback loaded {len(df)} rows from local backup.")
            except Exception as e:
                logger.error(f"⚠️ Failed to load local backup cache: {e}")
                log_event("Errors", "error", f"Failed to load backup cache: {e}")
        else:
            logger.warning("⚠️ No local backup cache found. Serving empty data.")

    # 3. Start background schedulers
    start_schedulers()
    logger.info("━━━ API Ready ━━━")
    log_event("Scheduler", "ok", "Schedulers started, API is ready.")
