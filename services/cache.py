"""
services/cache.py
==================
Simple in-memory cache with async interface for compatibility.
"""

import asyncio
from typing import Any, Optional


class Cache:
    def __init__(self):
        self._data = {}
        self._lock = asyncio.Lock()

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._data[key] = value

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            return self._data.get(key)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._data.pop(key, None)

    async def clear(self) -> None:
        async with self._lock:
            self._data.clear()


# Global cache instance
cache = Cache()