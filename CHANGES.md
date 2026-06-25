# Changes

## Files Changed

- `services/google_sheets_sync.py`
  - Added fiscal-year sheet discovery using `action=list_sheets` when available.
  - Added `year_sheets` config fallback when `list_sheets` is unavailable.
  - Added paged sheet reads using `action=read_sheet_page` to avoid 500-row or response-size limits.
  - Added `fetch_all_years()` to fetch all year tabs, stack them, and add `Fiscal Year`.
  - Added `fetch_year(year_label)` for single fiscal-year dashboard reads.
  - Added `GET /google-sheets-sync/year/{year_label}` with 400 and 404 handling.
  - Updated ABC and Inventory merges to preserve unmatched rows and avoid duplicate `Material description` suffixes.
  - Kept `fetch_sheets_data()` as a compatibility wrapper around the all-year fetch.
  - Updated manual and streaming sync to refresh the dashboard's in-memory dataframe cache immediately.
  - Added dashboard-compatible column aliases for the new Google Sheet headers.

- `routers/google_sheets_sync.py`
  - Replaced the legacy duplicate implementation with a compatibility re-export of the active service implementation.

- `services/google_sheets_config.py`
  - Replaced the required `consumption_sheet` setting with the fallback `year_sheets` array.

- `routers/google_sheets_config.py`
  - Mirrored the config schema change for legacy router compatibility.

- `services/model_training.py`
  - Allowed the training pipeline to read the new `MvT` and `Pstng date` headers without changing the step scripts.

- `frontend/src/App.jsx`
  - Updated the Data Source Apps Script template to include `list_sheets` and paged `read_sheet_page` reads.
  - Replaced the old single Consumption Sheet config field with a fiscal-year fallback list.
  - Prevented the streamed sync success path from immediately running the fallback sync again.
  - Refetches dashboard API data after a successful sync.

- `config/google_sheets.json`
  - Removed the old `consumption_sheet` key.
  - Added the fallback `year_sheets` list.

- `CHANGES.md`
  - Added this summary.

## Assumptions

- The Apps Script may or may not support `action=list_sheets`; the code tries it first and falls back to `year_sheets`.
- Fiscal-year sheet names follow the `YY-YY` format, such as `24-25`.
- Inventory and ABC Master tabs remain separate tabs in the same spreadsheet and keep their existing names.

## Manual Steps

- If Apps Script does not support `action=list_sheets`, keep `year_sheets` populated in `config/google_sheets.json`.
- Replace the deployed Apps Script with the template shown in the Data Source screen, then redeploy a new Web App version.
