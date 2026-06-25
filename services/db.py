import pandas as pd
import services as _api_pkg


def get_dataframe_sync() -> pd.DataFrame:
    """Return the cached in-memory DataFrame loaded from local data.xlsx."""
    df = getattr(_api_pkg, "_df_cache", None)
    if df is not None:
        return df
    # Return an empty DataFrame if data hasn't been loaded yet
    return pd.DataFrame()


async def get_dataframe_async() -> pd.DataFrame:
    """Async version — delegates to the synchronous cache lookup."""
    return get_dataframe_sync()