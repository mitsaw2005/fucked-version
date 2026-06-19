import io
import pandas as pd
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from .db import get_dataframe_sync

router = APIRouter(prefix="/export", tags=["Export Center"])

class ExportRequest(BaseModel):
    format: str = "csv"
    filters: List[Dict[str, Any]] = []
    page: Optional[int] = None
    page_size: Optional[int] = 100


def apply_spareai_filters(df: pd.DataFrame, filters: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Apply frontend filters to the DataFrame.
    Frontend sends: year, month, day, shop
    Actual columns:  pstng date (YYYY-MM-DD), Shop
    """
    out = df.copy()

    # Ensure pstng date is parsed as datetime for date-part filtering
    date_col = None
    for c in out.columns:
        if c.lower().strip() in ("pstng date", "pstng_date", "posting date", "posting_date"):
            date_col = c
            break

    if date_col:
        out["_date_parsed"] = pd.to_datetime(out[date_col], errors="coerce")

    shop_col = None
    for c in out.columns:
        if c.lower().strip() == "shop":
            shop_col = c
            break

    for rule in filters:
        field = rule.get("field", "")
        val   = rule.get("value", "")
        if not val:
            continue

        try:
            if field == "year" and date_col:
                out = out[out["_date_parsed"].dt.year == int(val)]

            elif field == "month" and date_col:
                out = out[out["_date_parsed"].dt.month == int(val)]

            elif field == "day" and date_col:
                out = out[out["_date_parsed"].dt.day == int(val)]

            elif field == "shop" and shop_col:
                out = out[out[shop_col].astype(str).str.lower() == str(val).lower()]

            else:
                # Generic fallback: match exact column name
                if field in out.columns:
                    out = out[out[field].astype(str).str.lower() == str(val).lower()]
        except Exception:
            pass

    # Drop helper column
    if "_date_parsed" in out.columns:
        out = out.drop(columns=["_date_parsed"])

    return out


def build_excel_multisheet(df: pd.DataFrame, filename: str) -> io.BytesIO:
    """Build a multi-sheet Excel file from filtered consumption data."""
    output = io.BytesIO()

    # Identify column names flexibly
    date_col = next((c for c in df.columns if c.lower().strip() in ("pstng date","pstng_date","posting date")), None)
    shop_col = next((c for c in df.columns if c.lower().strip() == "shop"), None)
    mat_col  = next((c for c in df.columns if c.lower().strip() == "material"), None)
    qty_col  = next((c for c in df.columns if c.lower().strip() == "quantity"), None)
    abc_col  = next((c for c in df.columns if c.lower().strip() in ("abc_class","abc class","abc correlation")), None)
    inv_col  = next((c for c in df.columns if c.lower().strip() in ("inventory_qty","inventory qty","inventory")), None)

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet 1 – Consumption Data (full filtered set)
        df.to_excel(writer, index=False, sheet_name="Consumption Data")

        # Sheet 2 – Inventory Data
        inv_cols = [c for c in [mat_col, "material Description", inv_col, abc_col, shop_col] if c and c in df.columns]
        inv_df = df[inv_cols].drop_duplicates(subset=[mat_col] if mat_col else None) if inv_cols else df.copy()
        inv_df.to_excel(writer, index=False, sheet_name="Inventory Data")

        # Sheet 3 – Forecast Data (monthly aggregation)
        if date_col and mat_col and qty_col:
            tmp = df.copy()
            tmp["_month"] = pd.to_datetime(tmp[date_col], errors="coerce").dt.to_period("M").astype(str)
            forecast_df = tmp.groupby([mat_col, "_month"] + ([shop_col] if shop_col else []))[qty_col].sum().reset_index()
            forecast_df.columns = [mat_col, "Month"] + ([shop_col] if shop_col else []) + ["Total_Qty"]
            forecast_df.to_excel(writer, index=False, sheet_name="Forecast Data")
        else:
            df.head(0).to_excel(writer, index=False, sheet_name="Forecast Data")

        # Sheet 4 – Procurement Recommendations
        if mat_col and qty_col and inv_col:
            tmp2 = df.copy()
            grp_cols = [mat_col] + ([shop_col] if shop_col else [])
            proc_df = tmp2.groupby(grp_cols).agg(
                Total_Consumed=(qty_col, "sum"),
                Current_Stock=(inv_col, "last") if inv_col else (qty_col, "count"),
            ).reset_index()
            proc_df["Recommended_Order"] = (proc_df["Total_Consumed"] - proc_df["Current_Stock"]).clip(lower=0)
            proc_df.to_excel(writer, index=False, sheet_name="Procurement Recommendations")
        else:
            df.head(0).to_excel(writer, index=False, sheet_name="Procurement Recommendations")

        # Sheet 5 – Critical Alerts (materials with stock < avg monthly usage)
        if mat_col and qty_col and inv_col:
            alert_df = proc_df[proc_df["Recommended_Order"] > 0].copy() if "proc_df" in dir() else df.head(0).copy()
            alert_df.to_excel(writer, index=False, sheet_name="Critical Alerts")
        else:
            df.head(0).to_excel(writer, index=False, sheet_name="Critical Alerts")

        # Sheet 6 – Executive Summary
        summary_rows = [
            {"Metric": "Total Records Exported",   "Value": len(df)},
            {"Metric": "Unique Materials",          "Value": df[mat_col].nunique() if mat_col else "—"},
            {"Metric": "Unique Shops",              "Value": df[shop_col].nunique() if shop_col else "—"},
            {"Metric": "Total Quantity Consumed",   "Value": df[qty_col].sum() if qty_col else "—"},
            {"Metric": "Date Range Start",          "Value": str(pd.to_datetime(df[date_col], errors="coerce").min().date()) if date_col else "—"},
            {"Metric": "Date Range End",            "Value": str(pd.to_datetime(df[date_col], errors="coerce").max().date()) if date_col else "—"},
            {"Metric": "Export Filename",           "Value": filename},
        ]
        pd.DataFrame(summary_rows).to_excel(writer, index=False, sheet_name="Executive Summary")

    output.seek(0)
    return output


@router.post("/preview")
def preview_data(req: ExportRequest):
    df = get_dataframe_sync()
    if req.filters:
        df = apply_spareai_filters(df, req.filters)
    total = len(df)
    preview = df.head(20)
    return JSONResponse({
        "total":   total,
        "columns": list(preview.columns),
        "records": preview.fillna("").astype(str).to_dict(orient="records"),
    })


@router.post("/")
def export_data(req: ExportRequest):
    df = get_dataframe_sync()
    if req.filters:
        df = apply_spareai_filters(df, req.filters)

    if req.format.lower() == "excel":
        # Build dynamic filename from filters
        year_f  = next((r["value"] for r in req.filters if r.get("field") == "year"),  "")
        month_f = next((r["value"] for r in req.filters if r.get("field") == "month"), "")
        shop_f  = next((r["value"] for r in req.filters if r.get("field") == "shop"),  "AllShops")
        month_names = ["","January","February","March","April","May","June","July","August","September","October","November","December"]
        month_name  = month_names[int(month_f)] if month_f and str(month_f).isdigit() else (month_f or "")
        fname = f"SpareAI_{str(shop_f).replace(' ','')}_{month_name}{year_f}.xlsx"

        output = build_excel_multisheet(df, fname)
        return StreamingResponse(
            output,
            headers={"Content-Disposition": f"attachment; filename={fname}"},
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    elif req.format.lower() == "csv":
        # Pagination for CSV
        if req.page and req.page > 0:
            ps    = req.page_size or 100
            start = (req.page - 1) * ps
            df    = df.iloc[start:start + ps]

        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            headers={"Content-Disposition": "attachment; filename=spareai_export.csv"},
            media_type="text/csv",
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported format. Use 'csv' or 'excel'.")