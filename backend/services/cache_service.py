"""
backend/services/cache_service.py
==================================
Lightweight synchronous in-memory cache for pre-computed API results.
Keyed by arbitrary string.  Invalidated atomically on sync/retrain.
"""
import threading
from datetime import datetime
from typing import Any, Optional

_lock  = threading.Lock()
_store: dict = {}
_timestamps: dict = {}


def get(key: str) -> Optional[Any]:
    with _lock:
        return _store.get(key)


def set(key: str, value: Any) -> None:
    with _lock:
        _store[key] = value
        _timestamps[key] = datetime.utcnow().isoformat()


def delete(key: str) -> None:
    with _lock:
        _store.pop(key, None)
        _timestamps.pop(key, None)


def invalidate_all() -> None:
    """Call this after every Google Sheets sync or ML retrain."""
    with _lock:
        _store.clear()
        _timestamps.clear()


def stats() -> dict:
    with _lock:
        return {
            "cached_keys": list(_store.keys()),
            "entry_count": len(_store),
            "timestamps": dict(_timestamps),
        }
