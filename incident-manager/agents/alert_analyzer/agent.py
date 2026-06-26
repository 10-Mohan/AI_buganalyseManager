# incident-manager/agents/alert_analyzer/agent.py
import os
from google.adk.agents import Agent
from agents.alert_analyzer.tools import parse_alert

model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

root_agent = Agent(
    name="alert_analyzer",
    model=model_name,
    description="Pre-processes raw logs, parses timestamps and log levels, and extracts incident metadata into JSON.",
    instruction=(
        "You are an expert incident response coordinator. Analyze raw service log details.\n"
        "First, invoke the `parse_alert` tool with the raw log string to clean and preprocess it.\n"
        "Then, analyze the preprocessed log details and return a strict JSON payload.\n"
        "The output JSON MUST follow this schema exactly, and contain no markdown wrappers or explanation:\n"
        "{\n"
        "  \"service\": \"name-of-the-service-generating-log\",\n"
        "  \"error_type\": \"specific-error-identifier\",\n"
        "  \"severity\": \"P1\",\n"
        "  \"affected_components\": [\"component-1\", \"component-2\"],\n"
        "  \"timestamp\": \"iso-timestamp\",\n"
        "  \"raw_summary\": \"A single-sentence description of the issue.\"\n"
        "}\n"
    ),
    tools=[parse_alert]
)
