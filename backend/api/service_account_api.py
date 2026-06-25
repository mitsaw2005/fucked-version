"""
backend/api/service_account_api.py
====================================
Endpoint for uploading the service account JSON via the browser.
"""

import json
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.core.config import SERVICE_ACCOUNT_PATH

router = APIRouter(prefix="/api/service-account", tags=["ServiceAccount"])


@router.post("/upload")
async def upload_service_account(file: UploadFile = File(...)):
    """Accept a Google Service Account JSON file and persist it."""
    if not file.filename.endswith(".json"):
        raise HTTPException(400, "Only JSON files accepted")
    contents = await file.read()
    try:
        sa = json.loads(contents)
        required = {"type", "project_id", "private_key", "client_email"}
        missing  = required - set(sa.keys())
        if missing:
            raise ValueError(f"Missing fields in service account JSON: {missing}")
        if sa.get("type") != "service_account":
            raise ValueError("JSON 'type' must be 'service_account'")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(400, f"Invalid service account JSON: {exc}")

    SERVICE_ACCOUNT_PATH.write_bytes(contents)
    return {
        "status":         "saved",
        "client_email":   sa.get("client_email"),
        "project_id":     sa.get("project_id"),
        "path":           str(SERVICE_ACCOUNT_PATH),
    }


@router.get("/info")
def sa_info():
    if not SERVICE_ACCOUNT_PATH.exists():
        return {"exists": False}
    try:
        sa = json.loads(SERVICE_ACCOUNT_PATH.read_text())
        return {
            "exists":       True,
            "client_email": sa.get("client_email"),
            "project_id":   sa.get("project_id"),
        }
    except Exception:
        return {"exists": True, "error": "Could not parse file"}
