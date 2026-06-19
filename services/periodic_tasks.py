import asyncio
import logging
from fastapi import FastAPI
from .google_sheets_sync import sync_google_sheets
import services as _api_pkg       # package __init__ — holds shared _df_cache
from .cache import cache
from .model_training import train_model

logger = logging.getLogger(__name__)

SYNC_INTERVAL_SECONDS = 5 * 60  # 5 minutes
_last_trained_rows = -1


async def _periodic_sync_task():
    """Continuously sync Google Sheets and refresh the ML model.
    Runs indefinitely in the background once the FastAPI app starts.
    """
    global _last_trained_rows
    while True:
        try:
            logger.info("Starting periodic Google Sheets sync and model refresh")
            # Sync sheets and update the in-memory cache
            df = await sync_google_sheets()
            if df is not None:
                await cache.set("df", df)
                # Also update legacy global cache variables for compatibility
                _api_pkg._df_cache = df
                _api_pkg._last_loaded_time = None  # optional reset
                logger.info(
                    "Cache updated with latest Google Sheets data (%d rows)", len(df)
                )

                # Check if new data has been entered (proxy: row count has changed)
                current_rows = len(df)
                if current_rows != _last_trained_rows:
                    logger.info(
                        f"New data detected ({current_rows} rows vs previously trained "
                        f"{_last_trained_rows}). Starting training pipeline..."
                    )

                    # Run the ML training pipeline in a background thread
                    success = await asyncio.to_thread(train_model, df)

                    if success:
                        _last_trained_rows = current_rows
                        logger.info("Training pipeline completed successfully.")
                    else:
                        logger.warning("Training pipeline did not complete successfully.")
            else:
                logger.warning("Google Sheets sync returned None – cache not updated")

            # Reload the ML model to pick up any new training data
            # Import lazily to avoid circular import at module load time
            import importlib
            api_module = importlib.import_module("api")  # top-level api.py entry point
            reload_fn = getattr(api_module, "reload_data_and_model", None)
            if reload_fn:
                reload_fn()
                logger.info("ML model reloaded after sync")
        except Exception as e:
            logger.exception("Error during periodic sync task: %s", e)
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)


def start_periodic_tasks(app: FastAPI):
    """Attach the background sync task to the FastAPI application.
    This should be called from the app's startup event.
    """
    asyncio.create_task(_periodic_sync_task())
    logger.info(
        "Periodic sync task scheduled (interval=%s seconds)", SYNC_INTERVAL_SECONDS
    )
