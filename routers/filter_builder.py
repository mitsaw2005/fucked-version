import pandas as pd
from typing import Any, Dict, List

def apply_filters(df: pd.DataFrame, filters: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Apply a list of advanced filter rules to the given pandas DataFrame.
    
    Each filter rule should be a dictionary:
    {
        "field": "ColumnName",
        "operator": "equals" | "contains" | "greater_than" | "less_than" | "not_equals",
        "value": "ValueToMatch",
        "type": "string" | "number" | "date"
    }
    """
    filtered_df = df.copy()
    
    for rule in filters:
        field = rule.get("field")
        op = rule.get("operator")
        val = rule.get("value")
        
        if not field or field not in filtered_df.columns:
            continue
            
        try:
            if op == "equals":
                filtered_df = filtered_df[filtered_df[field].astype(str).str.lower() == str(val).lower()]
            elif op == "not_equals":
                filtered_df = filtered_df[filtered_df[field].astype(str).str.lower() != str(val).lower()]
            elif op == "contains":
                filtered_df = filtered_df[filtered_df[field].astype(str).str.contains(str(val), case=False, na=False)]
            elif op == "greater_than":
                filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce') > float(val)]
            elif op == "less_than":
                filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce') < float(val)]
        except Exception:
            # If a filter fails (e.g., trying to compare string to float), simply ignore it
            pass
            
    return filtered_df
