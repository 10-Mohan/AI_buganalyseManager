# incident-manager/agents/comms_agent/tools.py
import os
import requests

def post_slack(message: str) -> dict:
    """Logs mock Slack message to stdout. If SLACK_WEBHOOK_URL is set, sends a real POST request."""
    print(f"\n--- [Slack Notification] ---\n{message}\n----------------------------\n")
    
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if webhook_url and webhook_url.startswith("http"):
        try:
            response = requests.post(webhook_url, json={"text": message}, timeout=5)
            if response.status_code == 200:
                return {"status": "posted", "channel": "#incidents", "webhook_triggered": True}
            else:
                return {"status": "failed", "error": f"Webhook returned status code {response.status_code}"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
            
    return {"status": "posted", "channel": "#incidents", "webhook_triggered": False}
