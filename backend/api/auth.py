"""
backend/api/auth.py
====================
Authentication and user management endpoints.
"""

import hashlib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.core.config import load_users, save_users, load_app_config, save_app_config

router = APIRouter(prefix="/auth", tags=["Auth"])

# ── Helpers ───────────────────────────────────────────────────────────

def _hash(password: str) -> str:
    return hashlib.sha256((password + "spareai_salt_12345").encode()).hexdigest()


# ── Models ────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    username: str
    password: str
    role:     str
    shop:     Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class PasscodeUpdateRequest(BaseModel):
    username:        str
    current_passcode: str
    new_passcode:    str


# ── Routes ────────────────────────────────────────────────────────────

@router.post("/signup")
def signup(req: SignupRequest):
    users = load_users()
    un = req.username.strip()
    if not un:
        raise HTTPException(400, "Username cannot be empty")
    if len(req.password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")
    if un in users:
        raise HTTPException(400, "Username already exists")
    users[un] = {"username": un, "password_hash": _hash(req.password), "role": req.role, "shop": req.shop}
    save_users(users)
    return {"status": "success", "message": "User registered successfully"}


@router.post("/login")
def login(req: LoginRequest):
    users = load_users()
    un = req.username.strip()
    if un not in users:
        raise HTTPException(400, "Invalid username or password")
    user = users[un]
    if _hash(req.password) != user["password_hash"]:
        raise HTTPException(400, "Invalid username or password")
    return {"status": "success", "user": {"username": user["username"], "role": user["role"], "shop": user["shop"]}}


@router.get("/profile")
def get_profile(username: str):
    users = load_users()
    un = username.strip()
    if un not in users:
        raise HTTPException(404, "User not found")
    user = users[un]
    return {"username": user["username"], "role": user["role"], "shop": user["shop"]}


# ── Config / passcode ──────────────────────────────────────────────────

config_router = APIRouter(prefix="/config", tags=["Config"])


@config_router.get("/budget-passcode")
def get_budget_passcode():
    return {"passcode": load_app_config().get("budget_passcode", "1234")}


@config_router.post("/set-passcode")
def set_budget_passcode(req: PasscodeUpdateRequest):
    users = load_users()
    un = req.username.strip()
    if un not in users:
        raise HTTPException(401, "Unauthorized")
    if users[un]["role"] != "Higher Authority":
        raise HTTPException(403, "Only Higher Authorities can change the budget passcode")
    cfg = load_app_config()
    if cfg.get("budget_passcode", "1234") != req.current_passcode:
        raise HTTPException(400, "Incorrect current passcode")
    cfg["budget_passcode"] = req.new_passcode.strip()
    save_app_config(cfg)
    return {"status": "success", "message": "Budget passcode changed successfully"}


@config_router.post("/budget-passcode")
def set_budget_passcode_alias(req: PasscodeUpdateRequest):
    return set_budget_passcode(req)
