import json
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = CONFIG_DIR / "google_sheets.json"

class GoogleSheetsConfig(BaseModel):
    apps_script_url: str = Field(..., description="Google Apps Script Web App URL")
    consumption_sheet: str = Field(..., description="Name of the consumption sheet")
    inventory_sheet: str = Field(..., description="Name of the inventory sheet")
    abc_sheet: str = Field(..., description="Name of the ABC master sheet")

def _load_config() -> GoogleSheetsConfig:
    if not CONFIG_PATH.is_file():
        return GoogleSheetsConfig(apps_script_url="", consumption_sheet="Main", inventory_sheet="Inventory", abc_sheet="ABC Master")
    try:
        data = json.loads(CONFIG_PATH.read_text())
        # Filter out keys that don't belong to the new model to avoid pydantic errors
        fields = GoogleSheetsConfig.model_fields if hasattr(GoogleSheetsConfig, "model_fields") else GoogleSheetsConfig.__fields__
        valid_keys = {k: v for k, v in data.items() if k in fields}
        # Provide defaults for missing fields
        if "consumption_sheet" not in valid_keys:
            valid_keys["consumption_sheet"] = "Main"
        if "inventory_sheet" not in valid_keys:
            valid_keys["inventory_sheet"] = "Inventory"
        if "abc_sheet" not in valid_keys:
            valid_keys["abc_sheet"] = "ABC Master"
        if "apps_script_url" not in valid_keys:
            valid_keys["apps_script_url"] = ""
        return GoogleSheetsConfig(**valid_keys)
    except Exception as e:
        return GoogleSheetsConfig(apps_script_url="", consumption_sheet="Main", inventory_sheet="Inventory", abc_sheet="ABC Master")

def _save_config(cfg: GoogleSheetsConfig):
    try:
        CONFIG_PATH.write_text(cfg.json(indent=2))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write config: {e}")

@router.get("/settings/google-sheets", response_model=GoogleSheetsConfig)
def get_google_sheets_config():
    """Return the stored Google Sheets configuration."""
    return _load_config()

@router.post("/settings/google-sheets", response_model=GoogleSheetsConfig)
def update_google_sheets_config(cfg: GoogleSheetsConfig):
    """Create or update the Google Sheets configuration.
    The supplied apps_script_url should be the deployed web app URL.
    """
    _save_config(cfg)
    return cfg
