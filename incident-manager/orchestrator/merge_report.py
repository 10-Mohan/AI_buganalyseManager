# incident-manager/orchestrator/merge_report.py
import datetime
import json
import sys

def merge_outputs(alert_data: dict, root_cause_data: dict, fix_data: list, comms_data: dict) -> dict:
    """Merges outputs from all four incident agents into a unified, formatted response."""
    return {
        "service": alert_data.get("service"),
        "severity": alert_data.get("severity"),
        "error_type": alert_data.get("error_type"),
        "timestamp": alert_data.get("timestamp"),
        "raw_summary": alert_data.get("raw_summary"),
        "root_cause_analysis": {
            "root_cause": root_cause_data.get("root_cause"),
            "confidence": root_cause_data.get("confidence"),
            "reasoning": root_cause_data.get("reasoning"),
            "affected_service": root_cause_data.get("affected_service")
        },
        "remediation": fix_data,
        "communications": {
            "slack_message": comms_data.get("slack_message"),
            "status_page_update": comms_data.get("status_page_update")
        },
        "metadata": {
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
            "orchestrated_by": "Nasiko Workflow Engine"
        }
    }

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python merge_report.py <alert_json_path> <root_cause_json_path> <fix_json_path> <comms_json_path>")
        sys.exit(1)
        
    try:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            alert = json.load(f)
        with open(sys.argv[2], 'r', encoding='utf-8') as f:
            rc = json.load(f)
        with open(sys.argv[3], 'r', encoding='utf-8') as f:
            fix = json.load(f)
        with open(sys.argv[4], 'r', encoding='utf-8') as f:
            comms = json.load(f)
            
        merged = merge_outputs(alert, rc, fix, comms)
        print(json.dumps(merged, indent=2))
    except Exception as e:
        print(f"Error merging reports: {e}", file=sys.stderr)
        sys.exit(2)
