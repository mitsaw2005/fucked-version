"""
backend/api/model_api.py
=========================
ML model management endpoints.
"""

import threading
from fastapi import APIRouter
from backend.core import globals as G
from backend.services.model_trainer import train_model

router = APIRouter(prefix="/api/model", tags=["Model"])


@router.get("/status")
def model_status():
    with G.state_lock:
        return {
            "has_model":       G.model is not None,
            "best_model":      G.meta.get("best_model"),
            "best_mae":        G.meta.get("best_mae"),
            "best_rmse":       G.meta.get("best_rmse"),
            "best_mape":       G.meta.get("best_mape"),
            "all_results":     G.meta.get("all_results"),
            "features":        G.meta.get("features", []),
            "trained_at":      G.meta.get("trained_at"),
            "row_count":       G.meta.get("row_count"),
            "is_model_stale":  G.is_model_stale,
            "retrain_running": G.retrain_running,
            "last_retrain":    G.retrain_last_time,
            "last_error":      G.retrain_last_error,
        }


@router.post("/train")
def trigger_training(force: bool = False):
    """Trigger ML retraining in the background."""
    def _run():
        train_model(force=force)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return {"status": "started", "force": force}
