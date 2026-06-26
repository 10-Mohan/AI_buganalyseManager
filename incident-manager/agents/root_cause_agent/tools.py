# incident-manager/agents/root_cause_agent/tools.py

# A hardcoded database of 6 runbook entries covering common failure patterns
RUNBOOKS = {
    ("payments-service", "connection_pool_exhausted"): {
        "runbook_id": "RB-PAY-001",
        "title": "PostgreSQL Connection Pool Exhaustion",
        "remediation_hint": "Increase connection pool size in Helm values or terminate idle connections.",
        "probable_cause": "resource_exhaustion"
    },
    ("payments-service", "database_error"): {
        "runbook_id": "RB-PAY-002",
        "title": "Database Connection Issue",
        "remediation_hint": "Check database credentials, verify database host availability, and check network security groups.",
        "probable_cause": "dependency_failure"
    },
    ("recommendation-engine", "oom_killed"): {
        "runbook_id": "RB-REC-001",
        "title": "Out Of Memory (OOM) Killed Pod",
        "remediation_hint": "Increase memory limits in the deployment manifest or check for memory leaks.",
        "probable_cause": "resource_exhaustion"
    },
    ("recommendation-engine", "timeout"): {
        "runbook_id": "RB-REC-002",
        "title": "Model Inference Timeout",
        "remediation_hint": "Scale the deployment replica count or optimize batch size settings.",
        "probable_cause": "traffic_spike"
    },
    ("api-gateway", "503_service_unavailable"): {
        "runbook_id": "RB-GW-001",
        "title": "API Gateway 503 Spike After Deployment",
        "remediation_hint": "Rollback the latest deployment or check service mesh routing rules.",
        "probable_cause": "config_change"
    },
    ("api-gateway", "rate_limit_exceeded"): {
        "runbook_id": "RB-GW-002",
        "title": "API Rate Limit Exceeded",
        "remediation_hint": "Verify IP rate limiting config or scale up gateway instances.",
        "probable_cause": "traffic_spike"
    }
}

def search_runbook(service: str, error_type: str) -> dict:
    """Retrieves runbooks from knowledge base for common incident patterns."""
    service_lower = (service or "").lower()
    error_lower = (error_type or "").lower()
    
    # Fuzzy match
    for (s_key, e_key), runbook in RUNBOOKS.items():
        if s_key in service_lower or service_lower in s_key:
            if e_key in error_lower or error_lower in e_key:
                return runbook
                
    # Fallback match by service name
    for (s_key, e_key), runbook in RUNBOOKS.items():
        if s_key in service_lower:
            return runbook
            
    # Default fallback
    return {
        "runbook_id": "RB-GEN-999",
        "title": "General System Failure",
        "remediation_hint": "Analyze system metrics, check logs for recent changes, and ensure dependent services are healthy.",
        "probable_cause": "unknown"
    }
