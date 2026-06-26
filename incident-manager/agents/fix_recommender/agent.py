# incident-manager/agents/fix_recommender/agent.py
import os
from google.adk.agents import Agent
from agents.fix_recommender.tools import get_remediation

model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

root_agent = Agent(
    name="fix_recommender",
    model=model_name,
    description="Suggests remediation steps and executable CLI command hints.",
    instruction=(
        "You are an expert recovery coordinator. You will receive root cause analysis JSON.\n"
        "First, invoke the `get_remediation` tool to fetch candidate remediation steps.\n"
        "Refine these steps for the specific service and issue. Return a strict JSON array of up to 5 steps.\n"
        "Each item in the array MUST be an object with the following keys, containing no markdown wrappers or explanation:\n"
        "[\n"
        "  {\n"
        "    \"action\": \"clear description of action\",\n"
        "    \"command_hint\": \"kubectl/gcloud/bash command if applicable, else null\",\n"
        "    \"estimated_minutes\": 5,\n"
        "    \"risk\": \"low|medium|high\"\n"
        "  }\n"
        "]\n"
    ),
    tools=[get_remediation]
)
