import pandas as pd
from typing import Optional
from fastapi import HTTPException
from .cache import cache
from . import api as api_module

async def get_dataframe_async() -> pd.DataFrame:
    """
    Abstract data access layer.
    Currently returns the Pandas DataFrame from the in-memory cache.
    Prepared for future PostgreSQL migration where this might return a SQLAlchemy session or execute a query.
    """
    df = await cache.get("df")
    if df is None:
        # Fallback to the legacy global cache if available
        df = api_module._df_cache
        if df is None:
            raise HTTPException(status_code=503, detail="Data source not ready. Please try again or force a manual sync.")
    return df

def get_dataframe_sync() -> pd.DataFrame:
    """
    Synchronous wrapper for getting the DataFrame.
    Returns the legacy global _df_cache.
    Use this in existing synchronous routes to avoid making them async.
    """
    if api_module._df_cache is None:
        raise HTTPException(status_code=503, detail="Data source not ready. Please try again or force a manual sync.")
    return api_module._df_cache
