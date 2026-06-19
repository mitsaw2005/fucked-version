import pandas as pd
from fastapi import HTTPException
from .cache import cache
import services as _api_pkg  # references the package __init__ which holds _df_cache


async def get_dataframe_async() -> pd.DataFrame:
    """
    Abstract data access layer.
    Currently returns the Pandas DataFrame from the in-memory cache.
    Prepared for future PostgreSQL migration where this might return a SQLAlchemy
    session or execute a query.
    """
    df = await cache.get("df")
    if df is None:
        # Fallback to the legacy global cache if available
        df = _api_pkg._df_cache
        if df is None:
            raise HTTPException(
                status_code=503,
                detail="Data source not ready. Please try again or force a manual sync.",
            )
    return df


def get_dataframe_sync() -> pd.DataFrame:
    """
    Synchronous wrapper for getting the DataFrame.
    Returns the legacy global _df_cache stored in the api package namespace.
    Use this in existing synchronous routes to avoid making them async.
    """
    df = _api_pkg._df_cache
    if df is None:
        raise HTTPException(
            status_code=503,
            detail="Data source not ready. Please try again or force a manual sync.",
        )
    return df
