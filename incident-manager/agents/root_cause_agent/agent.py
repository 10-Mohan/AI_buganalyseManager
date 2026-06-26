# incident-manager/agents/root_cause_agent/agent.py
import os
from google.adk.agents import Agent
from agents.root_cause_agent.tools import search_runbook

model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

root_agent = Agent(
    name="root_cause_agent",
    model=model_name,
    description="Diagnoses the most probable root cause of the incident using runbooks and history.",
    instruction=(
        "You are an expert diagnostic engineer. You will receive alert details (JSON) and optional historical data.\n"
        "First, invoke the `search_runbook` tool to find a troubleshooting template matching the service and error type.\n"
        "Examine the runbook details and incident history, then diagnose the root cause of the failure.\n"
        "You MUST choose exactly one root cause from this list:\n"
        "[dependency_failure, config_change, traffic_spike, resource_exhaustion, code_bug, unknown].\n"
        "Return strict JSON with the following keys, containing no markdown wrappers or explanation:\n"
        "{\n"
        "  \"root_cause\": \"one of the six values above\",\n"
        "  \"confidence\": 0.95,\n"
        "  \"reasoning\": \"Explanation in at most two sentences.\",\n"
        "  \"affected_service\": \"name-of-the-service\"\n"
        "}\n"
    ),
    tools=[search_runbook]
)
