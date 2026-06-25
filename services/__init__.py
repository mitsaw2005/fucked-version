# services/__init__.py — SpareAI services package
# Shared mutable state: _df_cache holds the pandas DataFrame loaded
# from data/data.xlsx at startup. All service modules read from here.

_df_cache = None           # type: ignore[assignment]
_last_loaded_time = None   # type: ignore[assignment]
