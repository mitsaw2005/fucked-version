import io
import json
import pandas as pd
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .db import get_dataframe_sync
from .filter_builder import apply_filters

router = APIRouter(prefix="/export", tags=["Export Center"])

class ExportRequest(BaseModel):
    format: str = "csv"  # "csv" or "excel"
    filters: List[Dict[str, Any]] = []
    page: Optional[int] = None
    page_size: Optional[int] = 100

@router.post("/")
def export_data(req: ExportRequest):
    df = get_dataframe_sync()
    
    # 1. Apply filters
    if req.filters:
        df = apply_filters(df, req.filters)
        
    # 2. Apply Pagination
    if req.page is not None and req.page > 0:
        page_size = req.page_size or 100
        start_idx = (req.page - 1) * page_size
        end_idx = start_idx + page_size
        df = df.iloc[start_idx:end_idx]
        
    # 3. Export
    if req.format.lower() == "excel":
        output = io.BytesIO()
        # Requires openpyxl/xlsxwriter
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Export")
        output.seek(0)
        
        headers = {
            "Content-Disposition": "attachment; filename=export.xlsx"
        }
        return StreamingResponse(
            output, 
            headers=headers, 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    elif req.format.lower() == "csv":
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        headers = {
            "Content-Disposition": "attachment; filename=export.csv"
        }
        return StreamingResponse(
            iter([output.getvalue()]), 
            headers=headers, 
            media_type="text/csv"
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported export format. Use 'csv' or 'excel'.")

@router.post("/preview")
def preview_data(req: ExportRequest):
    df = get_dataframe_sync()
    
    # 1. Apply filters
    if req.filters:
        df = apply_filters(df, req.filters)
        
    total_count = len(df)
    
    # 2. Get first 15 rows for preview
    page_size = req.page_size or 15
    page_num = req.page or 1
    start_idx = (page_num - 1) * page_size
    df_page = df.iloc[start_idx : start_idx + page_size]
    
    # 3. Format records to be JSON-serializable
    records = []
    for _, row in df_page.iterrows():
        record = {}
        for col, val in row.items():
            if pd.isnull(val):
                record[col] = ""
            elif hasattr(val, "strftime"):  # covers pd.Timestamp, datetime, date
                record[col] = val.strftime("%Y-%m-%d")
            else:
                # Handle numeric formatting or basic types
                record[col] = val
        records.append(record)
        
    return {
        "records": records,
        "columns": df.columns.tolist(),
        "total": total_count,
        "page": page_num,
        "page_size": page_size
    }

