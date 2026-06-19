import time
import asyncio
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class InMemoryCache:
    """Thread‑safe in‑memory cache with TTL and manual sync support.
    Stores a pandas DataFrame under key 'df'.
    """
    def __init__(self, ttl_seconds: int = 900):  # 15 minutes
        self._store: Dict[str, Any] = {}
        self._timestamp: Dict[str, float] = {}
        self._ttl = ttl_seconds
        self._lock = asyncio.Lock()
        self._manual_sync_event = asyncio.Event()

    async def get(self, key: str) -> Any:
        async with self._lock:
            return self._store.get(key)

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._store[key] = value
            self._timestamp[key] = time.time()
            self._manual_sync_event.set()

    async def is_stale(self, key: str) -> bool:
        async with self._lock:
            ts = self._timestamp.get(key)
            if ts is None:
                return True
            return (time.time() - ts) > self._ttl

    async def wait_for_manual_sync(self, timeout: int = 30):
        try:
            await asyncio.wait_for(self._manual_sync_event.wait(), timeout)
        except asyncio.TimeoutError:
            logger.warning("Manual sync wait timed out")

# Global cache instance used across the app
cache = InMemoryCache()
