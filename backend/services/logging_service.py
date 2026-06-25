"""
backend/services/logging_service.py
==================================
Centralized structured logging service.
Logs events in JSON format containing category, timestamp, duration, status, and message.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
import threading

from backend.core.config import LOGS_DIR

STRUCTURED_LOG_FILE = LOGS_DIR / "structured_api.log"
_log_lock = threading.Lock()

def log_event(category: str, status: str, message: str, duration_s: Optional[float] = None) -> None:
    """
    Log a structured event.
    Categories: "Google Sync", "Scheduler", "Model Training", "API", "Authentication", "Errors"
    """
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": category,
        "status": status,
        "message": message,
        "duration": duration_s if duration_s is not None else 0.0
    }
    
    with _log_lock:
        try:
            with open(STRUCTURED_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            # Fallback to standard print if file logging fails
            print(f"Failed to write structured log: {e}")

def get_recent_logs(limit: int = 100, category: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetch recent structured logs."""
    logs = []
    if not STRUCTURED_LOG_FILE.exists():
        return logs
        
    with _log_lock:
        try:
            with open(STRUCTURED_LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # Read backwards to get most recent first
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if category and entry.get("category") != category:
                            continue
                        logs.append(entry)
                        if len(logs) >= limit:
                            break
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Failed to read structured logs: {e}")
            
    return logs
