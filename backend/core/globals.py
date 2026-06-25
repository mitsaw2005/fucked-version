"""
backend/core/globals.py
=======================
Single in-memory state store shared across all backend modules.
All mutations must hold state_lock for thread-safe atomic updates.
"""
import threading
import pandas as pd

# ── Thread safety ──────────────────────────────────────────────────────
state_lock = threading.Lock()

# ── Live DataFrame ─────────────────────────────────────────────────────
df_cache: pd.DataFrame = pd.DataFrame()

# ── Sync metadata ──────────────────────────────────────────────────────
last_sync_time: str        = "never"
last_sync_status: str      = "unknown"   # "ok" | "error" | "no_change" | "unknown"
last_sync_error: str       = None
sync_count: int            = 0
spreadsheet_title: str     = ""
spreadsheet_id: str        = ""
service_account_email: str = ""

# ── ML model state ────────────────────────────────────────────────────
model                      = None        # sklearn/xgboost/lightgbm regressor
encoder                    = None        # LabelEncoder for Material
meta: dict                 = {}          # training metadata from meta.json
features: list             = []

is_model_stale: bool       = False       # True after a sync; cleared after retrain
retrain_running: bool      = False
retrain_last_time: str     = None
retrain_last_error: str    = None

# ── API result cache (populated by cache_service) ─────────────────────
api_cache: dict            = {}
