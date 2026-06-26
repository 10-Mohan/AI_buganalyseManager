# incident-manager/agents/comms_agent/agent.py
import os
from google.adk.agents import Agent
from agents.comms_agent.tools import post_slack

model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

root_agent = Agent(
    name="comms_agent",
    model=model_name,
    description="Drafts incident alerts for Slack (#incidents channel) and the public status page, then publishes Slack updates.",
    instruction=(
        "You are an expert incident communications manager. You will receive alert analysis and root cause JSON.\n"
        "Draft two communications and return them in a strict JSON object with two keys, containing no markdown wrappers or explanation:\n"
        "{\n"
        "  \"slack_message\": \"Plain English message for the team, under 100 words, including service, severity, and root cause.\",\n"
        "  \"status_page_update\": \"Formal message for the public, under 60 words, indicating we are investigating degradation and working on recovery.\"\n"
        "}\n"
        "Once you have finalized the messages, invoke the `post_slack` tool with the text of the `slack_message` before returning."
    ),
    tools=[post_slack]
)
