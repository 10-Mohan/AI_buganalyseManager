# incident-manager/agents/fix_recommender/tools.py

REMEDIATIONS = {
    "resource_exhaustion": [
        {"action": "Check active database connections and terminate idle ones", "command_hint": "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle';", "estimated_minutes": 5, "risk": "medium"},
        {"action": "Scale up deployment replicas to distribute load", "command_hint": "kubectl scale deployment/payments-service --replicas=5 -n production", "estimated_minutes": 3, "risk": "low"},
        {"action": "Increase pod memory/CPU limits", "command_hint": "kubectl set resources deployment/recommendation-engine --limits=memory=2Gi -n production", "estimated_minutes": 5, "risk": "low"}
    ],
    "config_change": [
        {"action": "Rollback the latest service deployment to the previous stable replica", "command_hint": "kubectl rollout undo deployment/api-gateway -n production", "estimated_minutes": 4, "risk": "medium"},
        {"action": "Audit recent configuration changes in the main Git repository", "command_hint": "git log --since='1 hour ago' -p", "estimated_minutes": 10, "risk": "low"}
    ],
    "dependency_failure": [
        {"action": "Check health endpoint of the downstream database/API dependency", "command_hint": "curl -I https://dependency-api.production/healthz", "estimated_minutes": 3, "risk": "low"},
        {"action": "Restart the affected pod to re-establish connection pool state", "command_hint": "kubectl rollout restart deployment/payments-service -n production", "estimated_minutes": 5, "risk": "low"}
    ],
    "traffic_spike": [
        {"action": "Enable horizontal pod autoscaler (HPA) to auto-scale", "command_hint": "kubectl autoscale deployment/api-gateway --cpu-percent=80 --min=3 --max=10", "estimated_minutes": 5, "risk": "low"},
        {"action": "Apply rate limiting policy in Cloud Armor/Gateway config", "command_hint": "gcloud compute security-policies update prod-policy --src-ip-ranges='*' --action='rate-limit'", "estimated_minutes": 8, "risk": "medium"}
    ],
    "code_bug": [
        {"action": "Rollback to the previous stable release container image", "command_hint": "gcloud run deploy payments-service --image=gcr.io/my-project/payments-service:stable", "estimated_minutes": 6, "risk": "medium"},
        {"action": "Capture logs and stack traces from the failing pod", "command_hint": "kubectl logs -l app=payments-service --tail=200 -n production", "estimated_minutes": 5, "risk": "low"}
    ],
    "unknown": [
        {"action": "Check system metrics dashboard and JVM/heap usage", "command_hint": "kubectl exec -it <pod-name> -n production -- jcmd 1 GC.heap_dump /tmp/heap.hprof", "estimated_minutes": 15, "risk": "low"},
        {"action": "Restart pod and monitor error logs", "command_hint": "kubectl rollout restart deployment/payments-service -n production", "estimated_minutes": 5, "risk": "low"}
    ]
}

def get_remediation(root_cause: str, affected_service: str) -> dict:
    """Retrieves standard remediation steps based on the identified root cause."""
    cause = (root_cause or "unknown").lower().strip()
    steps = REMEDIATIONS.get(cause, REMEDIATIONS["unknown"])
    return {
        "service": affected_service,
        "root_cause": cause,
        "recommended_steps_template": steps
    }
