# SpareAI — OneDrive Live Sync Setup Guide

## Overview

This guide sets up a **live, automatic sync** between your OneDrive for Business Excel file and the SpareAI system.

- ✅ No file is ever downloaded to disk
- ✅ Data refreshes automatically every 5 minutes
- ✅ ML model retrains in the background when data changes
- ✅ Requires a one-time Azure App Registration (~5–10 minutes)

---

## Step 1: Create an Azure App Registration

> This gives SpareAI a secure identity to access your OneDrive file — no passwords are stored.

1. Open [portal.azure.com](https://portal.azure.com) and sign in with your **Tata Motors work account**.

2. In the search bar, search for **"App registrations"** and click it.

3. Click **"+ New registration"**:
   - **Name**: `SpareAI OneDrive Sync`
   - **Supported account types**: Select **"Accounts in this organizational directory only (Tata Motors only - Single tenant)"**
   - **Redirect URI**: Leave blank
   - Click **Register**

4. After registering, note down:
   - **Application (client) ID** → this is your `AZURE_CLIENT_ID`
   - **Directory (tenant) ID** → this is your `AZURE_TENANT_ID`

---

## Step 2: Create a Client Secret

1. In your App Registration, click **"Certificates & secrets"** (left sidebar).
2. Click **"+ New client secret"**:
   - **Description**: `SpareAI Secret`
   - **Expires**: Choose 24 months
   - Click **Add**
3. **IMMEDIATELY copy the "Value"** (it only shows once!) → this is your `AZURE_CLIENT_SECRET`

---

## Step 3: Grant API Permissions

1. Click **"API permissions"** (left sidebar).
2. Click **"+ Add a permission"** → Select **"Microsoft Graph"**.
3. Select **"Application permissions"** (NOT Delegated).
4. Search for and add these permissions:
   - `Files.Read.All`
   - `Sites.Read.All`
5. Click **"Add permissions"**.
6. Click **"Grant admin consent for Tata Motors"** → Confirm **Yes**.

> ⚠️ If you don't see the "Grant admin consent" button, ask your IT admin to grant it.

---

## Step 4: Get Your OneDrive File IDs

**Option A: Automatic (recommended)**

After setting up your `.env` file with the credentials from Steps 1–3, run:

```bash
cd /Users/mitanshsawant/Documents/Tata/SpareAI
source venv/bin/activate
python onedrive_sync.py --find-file
```

This will print your `ONEDRIVE_ITEM_ID` and `ONEDRIVE_DRIVE_ID` automatically.

**Option B: Manual (via SharePoint browser)**

1. Open your SharePoint/OneDrive site in a browser.
2. Right-click on `data.xlsx` → **"Details"** → Copy the **"Path"**.
3. Navigate to: `https://graph.microsoft.com/v1.0/me/drive/root/search(q='data.xlsx')`
   (Use [Graph Explorer](https://developer.microsoft.com/en-us/graph/graph-explorer) to run this query)
4. Find the `id` field in the response — that is your `ONEDRIVE_ITEM_ID`.
5. Find the `parentReference.driveId` — that is your `ONEDRIVE_DRIVE_ID`.

---

## Step 5: Configure the .env File

1. Copy the template file:
   ```bash
   cp /Users/mitanshsawant/Documents/Tata/SpareAI/.env.example \
      /Users/mitanshsawant/Documents/Tata/SpareAI/.env
   ```

2. Edit `.env` and fill in your values:
   ```
   AZURE_CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   AZURE_CLIENT_SECRET=your~secret~value~here
   AZURE_TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
   ONEDRIVE_ITEM_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx!xxx
   ONEDRIVE_DRIVE_ID=b!xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   SHAREPOINT_SITE_ID=tatamotors.sharepoint.com,xxxxxx,xxxxxx
   REFRESH_INTERVAL_MINUTES=5
   AUTO_RETRAIN=true
   ```

> ⚠️ Never share your `.env` file. Add it to `.gitignore`.

---

## Step 6: Install Dependencies

```bash
cd /Users/mitanshsawant/Documents/Tata/SpareAI
source venv/bin/activate
pip install msal python-dotenv requests openpyxl
```

---

## Step 7: Test the Connection

```bash
python onedrive_sync.py --test
```

Expected output:
```
✅ Auth OK. Token starts with: EwBIA8l6BAAU...
✅ File metadata:
   Name:          data.xlsx
   Size:          1,666,565 bytes
   Last Modified: 2026-06-11T04:30:00Z
   ETag:          "{XXXXXXXX-XXXX}..."
✅ Fetched 1,666,565 bytes into memory
✅ Parsed DataFrame: 35820 rows × 12 cols
```

---

## Step 8: Start the API

```bash
uvicorn api:app --reload
```

The API will:
1. Immediately sync from OneDrive (first load)
2. Start the background polling thread (every 5 min)
3. Auto-retrain the ML model when file changes

---

## Monitoring Sync Status

### Check current sync state:
```bash
curl http://localhost:8000/sync/status
```

```json
{
  "status": "synced",
  "last_sync_time": "2026-06-11 10:30:00 UTC",
  "last_modified_onedrive": "2026-06-11T09:15:00Z",
  "sync_count": 12,
  "data_rows": 35820,
  "retrain_running": false,
  "retrain_last_time": "2026-06-11 09:20:00 UTC"
}
```

### Force an immediate refresh:
```bash
curl -X POST http://localhost:8000/sync/force-refresh
```

### Check retrain status:
```bash
curl http://localhost:8000/retrain/status
```

---

## How It Works

```
OneDrive Excel (data.xlsx)
      │
      │  Microsoft Graph API
      │  GET /drives/{driveId}/items/{itemId}/content
      │  → io.BytesIO (in-memory, never saved to disk)
      ▼
onedrive_sync.py — background thread polls every 5 min
      │
      ├── ETag unchanged? → Skip (no reload)
      │
      └── ETag changed? → Parse DataFrame → Update cache
                │
                └── AUTO_RETRAIN=true?
                          │
                          └── Background thread:
                              step1_preprocess.py
                              step2_features.py
                              step3_train.py
                              → New model hot-loaded
```

---

## Troubleshooting

| Error | Solution |
|-------|----------|
| `Missing Azure credentials` | Check `.env` file has all 3 Azure fields set |
| `Failed to acquire access token` | Verify CLIENT_ID and CLIENT_SECRET are correct |
| `ONEDRIVE_ITEM_ID not set` | Run `python onedrive_sync.py --find-file` |
| `403 Forbidden` | Admin consent not granted — ask IT admin |
| `File not found` | Verify ONEDRIVE_ITEM_ID and ONEDRIVE_DRIVE_ID are correct |
| `Token expired` | MSAL handles this automatically — no action needed |

---

## Security Notes

- The app uses **Client Credentials flow** — no user login required after setup
- Credentials are stored only in your local `.env` file
- The access token is cached in memory and auto-refreshed by MSAL
- The Excel file bytes are never written to disk — processed in RAM only
- Add `.env` to your `.gitignore` to prevent accidental commits
