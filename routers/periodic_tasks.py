import asyncio
import logging
from fastapi import FastAPI
from .google_sheets_sync import sync_google_sheets
from . import api as api_module
from .cache import cache
from .api import reload_data_and_model
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
                api_module._df_cache = df
                api_module._last_loaded_time = None  # optional reset
                logger.info("Cache updated with latest Google Sheets data (%d rows)", len(df))
                
                # Check if new data has been entered (proxy: row count has changed)
                current_rows = len(df)
                if current_rows != _last_trained_rows:
                    logger.info(f"New data detected ({current_rows} rows vs previously trained {_last_trained_rows}). Starting training pipeline...")
                    
                    # Run the ML training pipeline in a background thread to prevent blocking the event loop
                    success = await asyncio.to_thread(train_model, df)
                    
                    if success:
                        _last_trained_rows = current_rows
                        logger.info("Training pipeline completed successfully.")
                    else:
                        logger.warning("Training pipeline did not complete successfully.")
            else:
                logger.warning("Google Sheets sync returned None – cache not updated")

            # Reload the ML model to pick up any new training data
            reload_data_and_model()
            logger.info("ML model reloaded after sync")
        except Exception as e:
            logger.exception("Error during periodic sync task: %s", e)
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)

def start_periodic_tasks(app: FastAPI):
    """Attach the background sync task to the FastAPI application.
    This should be called from the app's startup event.
    """
    asyncio.create_task(_periodic_sync_task())
    logger.info("Periodic sync task scheduled (interval=%s seconds)", SYNC_INTERVAL_SECONDS)
