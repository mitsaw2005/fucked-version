"""
backend/core/config.py
======================
Static path and configuration helpers.  All code should import
from here instead of hardcoding paths.
"""
import json
import os
from pathlib import Path

# ── Root ──────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # /SpareAI

# ── Model artefacts ───────────────────────────────────────────────────
MODELS_DIR   = BASE_DIR / "models"
MODEL_PATH   = MODELS_DIR / "best_model.pkl"
ENCODER_PATH = MODELS_DIR / "encoder.pkl"
META_PATH    = MODELS_DIR / "meta.json"

# ── Persistent data directory ─────────────────────────────────────────
DATA_DIR     = BASE_DIR / "data"
USERS_FILE   = DATA_DIR / "users.json"
APP_CFG_FILE = DATA_DIR / "config.json"

# ── Google integration ────────────────────────────────────────────────
CONFIG_DIR            = BASE_DIR / "config"
GOOGLE_SHEETS_CFG     = CONFIG_DIR / "google_sheets.json"
SERVICE_ACCOUNT_PATH  = CONFIG_DIR / "service_account.json"

# ── Logs ──────────────────────────────────────────────────────────────
LOGS_DIR = BASE_DIR / "logs"
SYNC_LOG_FILE    = LOGS_DIR / "sync.log"
TRAIN_LOG_FILE   = LOGS_DIR / "training.log"
API_LOG_FILE     = LOGS_DIR / "api.log"

# ── Ensure directories exist ──────────────────────────────────────────
for _d in (MODELS_DIR, DATA_DIR, CONFIG_DIR, LOGS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


# ── Config helpers ─────────────────────────────────────────────────────

def load_google_sheets_config() -> dict:
    if not GOOGLE_SHEETS_CFG.exists():
        return {
            "spreadsheet_id": "",
            "detected_sheets": [],
            "inventory_sheet": "Inventory",
            "abc_sheet": "ABC Master",
            "auto_sync": True,
            "training_interval_hours": 2,
            "service_account_path": str(SERVICE_ACCOUNT_PATH),
        }
    try:
        cfg = json.loads(GOOGLE_SHEETS_CFG.read_text())
    except Exception:
        cfg = {}
    # Ensure default values are populated
    cfg.setdefault("spreadsheet_id", "")
    cfg.setdefault("detected_sheets", [])
    cfg.setdefault("inventory_sheet", "Inventory")
    cfg.setdefault("abc_sheet", "ABC Master")
    cfg.setdefault("auto_sync", True)
    cfg.setdefault("training_interval_hours", 2)
    cfg.setdefault("service_account_path", str(SERVICE_ACCOUNT_PATH))
    return cfg


def save_google_sheets_config(data: dict) -> None:
    existing = load_google_sheets_config()
    existing.update(data)
    GOOGLE_SHEETS_CFG.write_text(json.dumps(existing, indent=2))


def load_app_config() -> dict:
    if not APP_CFG_FILE.exists():
        default = {"budget_passcode": "1234"}
        APP_CFG_FILE.write_text(json.dumps(default, indent=2))
        return default
    return json.loads(APP_CFG_FILE.read_text())


def save_app_config(data: dict) -> None:
    APP_CFG_FILE.write_text(json.dumps(data, indent=2))


def load_users() -> dict:
    if not USERS_FILE.exists():
        import hashlib
        def _hash(p):
            return hashlib.sha256((p + "spareai_salt_12345").encode()).hexdigest()
        default = {"admin": {"username": "admin", "password_hash": _hash("admin123"),
                              "role": "Higher Authority", "shop": None}}
        USERS_FILE.write_text(json.dumps(default, indent=2))
        return default
    return json.loads(USERS_FILE.read_text())


def save_users(users: dict) -> None:
    USERS_FILE.write_text(json.dumps(users, indent=2))
