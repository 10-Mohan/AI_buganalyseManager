# incident-manager/agents/alert_analyzer/tools.py
import re

def parse_alert(raw_log: str) -> dict:
    """Pre-processes the raw log string and extracts preliminary indicators."""
    clean_log = raw_log.strip()
    
    # Simple regex to search for standard timestamp
    ts_match = re.search(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?', clean_log)
    timestamp = ts_match.group(0) if ts_match else "unknown"
    
    # Check for general keywords to assist in level detection
    log_level = "INFO"
    log_upper = clean_log.upper()
    if "ERROR" in log_upper or "FATAL" in log_upper or "CRITICAL" in log_upper:
        log_level = "ERROR"
    elif "WARN" in log_upper:
        log_level = "WARNING"
        
    return {
        "cleaned_log": clean_log,
        "extracted_timestamp": timestamp,
        "log_level_hint": log_level
    }
