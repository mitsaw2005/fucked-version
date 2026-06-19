# api/__init__.py — SpareAI API package
# Exposes shared mutable state so sub-modules can reference the top-level _df_cache
# without a circular import. The actual cache variables live in api.py (the FastAPI
# entry-point) but are injected here at startup so any module importing from this
# package can reach them.

_df_cache = None          # type: ignore[assignment]
_last_loaded_time = None  # type: ignore[assignment]
