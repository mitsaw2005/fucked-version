"""
SpareAI FastAPI Backend — Google Sheets & Modular Architecture
Run: uvicorn main:app --reload
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Initialize logging before loading backend modules
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# Load backend startup lifespan/startup handler
from backend.core.startup import on_startup

# Load api routers
from backend.api.auth import router as auth_router, config_router
from backend.api.dashboard import router as dashboard_router
from backend.api.forecast import router as forecast_router
from backend.api.model_api import router as model_router
from backend.api.service_account_api import router as sa_router
from backend.api.sync_api import router as sync_router
from backend.api.logs_api import router as logs_router

app = FastAPI(title="SpareAI — Tata Motors", version="6.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include All Modular Routers
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(dashboard_router)
app.include_router(forecast_router)
app.include_router(model_router)
app.include_router(sa_router)
app.include_router(sync_router)
app.include_router(logs_router)

# Register startup handler
@app.on_event("startup")
async def startup_event():
    await on_startup()