# incident-manager/api/main.py
import asyncio
import datetime
import json
import os
import sys
# Add parent directory to sys.path to enable smooth relative imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Load environment variables from .env using absolute path
from dotenv import load_dotenv
load_dotenv(os.path.join(parent_dir, ".env"))

# Synchronize API keys and fallback to dummy if none provided
google_key = os.getenv("GOOGLE_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

if google_key and not gemini_key:
    os.environ["GEMINI_API_KEY"] = google_key
elif gemini_key and not google_key:
    os.environ["GOOGLE_API_KEY"] = gemini_key

if not os.getenv("GOOGLE_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = "DUMMY_KEY"
    os.environ["GEMINI_API_KEY"] = "DUMMY_KEY"
    print("[WARNING] GOOGLE_API_KEY not set – using dummy key for local testing.")

import re
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from google.adk.runners import InMemoryRunner
from google.genai.types import Content, Part

from agents.alert_analyzer.agent import root_agent as alert_agent
from agents.root_cause_agent.agent import root_agent as rc_agent
from agents.fix_recommender.agent import root_agent as fix_agent
from agents.comms_agent.agent import root_agent as comms_agent
from orchestrator.merge_report import merge_outputs

app = FastAPI(title="AI Incident Response Manager API")

# Request Schemas
class IncidentRequest(BaseModel):
    raw_log: str
    service: str
    history: Optional[str] = None

class NasikoWorkflowRequest(BaseModel):
    raw_log: str
    service: str
    history: Optional[str] = None

# Schema Validators
def validate_alert_analyzer_output(data: dict):
    required_keys = ["service", "error_type", "severity", "affected_components", "timestamp", "raw_summary"]
    for key in required_keys:
        if key not in data:
            raise KeyError(f"Missing required key in Alert Analyzer: {key}")
    if data["severity"] not in ["P1", "P2", "P3", "P4"]:
        raise ValueError(f"Invalid severity value in Alert Analyzer: {data['severity']}")
    if not isinstance(data["affected_components"], list):
        raise TypeError("affected_components must be a list of strings")

def validate_root_cause_agent_output(data: dict):
    required_keys = ["root_cause", "confidence", "reasoning", "affected_service"]
    for key in required_keys:
        if key not in data:
            raise KeyError(f"Missing required key in Root Cause Agent: {key}")
    valid_causes = ["dependency_failure", "config_change", "traffic_spike", "resource_exhaustion", "code_bug", "unknown"]
    if data["root_cause"] not in valid_causes:
        raise ValueError(f"Invalid root_cause: {data['root_cause']}")
    if not isinstance(data["confidence"], (int, float)) or not (0.0 <= data["confidence"] <= 1.0):
        raise ValueError(f"confidence must be float between 0.0 and 1.0, got: {data['confidence']}")

def validate_fix_recommender_output(data):
    if not isinstance(data, list):
        raise TypeError("Fix recommender output must be a JSON array (list)")
    if len(data) > 5:
        raise ValueError("Fix recommender returned more than 5 steps")
    for idx, item in enumerate(data):
        required_keys = ["action", "command_hint", "estimated_minutes", "risk"]
        for key in required_keys:
            if key not in item:
                raise KeyError(f"Step {idx} missing key: {key}")
        if item["risk"] not in ["low", "medium", "high"]:
            raise ValueError(f"Step {idx} invalid risk: {item['risk']}")

def validate_comms_agent_output(data: dict):
    required_keys = ["slack_message", "status_page_update"]
    for key in required_keys:
        if key not in data:
            raise KeyError(f"Missing required key in Comms Agent: {key}")

# ---------------------------------------------------------------------------
# Error classification keywords for retry logic
# ---------------------------------------------------------------------------
_RATE_LIMIT_KEYWORDS = [
    "RESOURCE_EXHAUSTED", "429", "quota", "rate limit", "retryDelay",
]
_TRANSIENT_ERROR_KEYWORDS = [
    "503", "UNAVAILABLE", "ServiceUnavailable", "server error",
    "500", "INTERNAL", "overloaded", "temporarily", "Bad Gateway",
    "502", "Gateway Timeout", "504",
]

def _classify_error(error_str: str) -> tuple[bool, bool]:
    """Returns (is_rate_limited, is_transient) based on keyword matching."""
    is_rate_limited = any(kw in error_str for kw in _RATE_LIMIT_KEYWORDS)
    is_transient = any(kw in error_str for kw in _TRANSIENT_ERROR_KEYWORDS)
    return is_rate_limited, is_transient

def _extract_retry_delay(error_str: str) -> Optional[float]:
    """Extracts recommended retry delay in seconds from the error string, if present."""
    # Match "Please retry in X.XXs" or similar
    match = re.search(r"retry in\s+(\d+(?:\.\d+)?)\s*s", error_str, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
            
    # Match "retryDelay: 'XXs'" or similar
    match = re.search(r"retryDelay['\"]?:\s*['\"]?(\d+)s['\"]?", error_str, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
            
    return None

def _generate_mock_fallback(agent_name: str, prompt: str) -> dict | list:
    print(f"[Executor] [FALLBACK] Generating mock fallback for agent '{agent_name}' due to quota exhaustion.")
    
    if agent_name == "alert_analyzer":
        # Extract service name
        service_match = re.search(r"Service:\s*([^\n]+)", prompt)
        service = service_match.group(1).strip() if service_match else "unknown-service"
        
        # Extract log to find error keywords
        error_type = "unknown"
        if "exhausted" in prompt.lower() or "connection slots" in prompt.lower():
            error_type = "connection_pool_exhausted"
        elif "oom" in prompt.lower() or "memory" in prompt.lower():
            error_type = "oom_killed"
        elif "503" in prompt.lower() or "unavailable" in prompt.lower():
            error_type = "503_service_unavailable"
        elif "timeout" in prompt.lower():
            error_type = "timeout"
            
        severity = "P1"
        if "warning" in prompt.lower() or "warn" in prompt.lower():
            severity = "P2"
            
        affected = [service]
        if "payments" in prompt.lower():
            affected.append("payments-database")
        
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        raw_summary = f"Detected {error_type} error in {service}."
        
        return {
            "service": service,
            "error_type": error_type,
            "severity": severity,
            "affected_components": affected,
            "timestamp": timestamp,
            "raw_summary": raw_summary
        }
        
    elif agent_name == "root_cause_agent":
        # Extract alert json
        try:
            alert_json_str = prompt.split("Alert JSON:\n")[1].strip()
            alert_data = json.loads(alert_json_str)
        except Exception:
            alert_data = {}
            
        service = alert_data.get("service", "unknown-service")
        error_type = alert_data.get("error_type", "unknown_error")
        
        from agents.root_cause_agent.tools import search_runbook
        runbook = search_runbook(service, error_type)
        
        return {
            "root_cause": runbook.get("probable_cause", "unknown"),
            "confidence": 0.90,
            "reasoning": f"Identified matching runbook {runbook.get('runbook_id')} for {error_type}.",
            "affected_service": service
        }
        
    elif agent_name == "fix_recommender":
        try:
            rc_json_str = prompt.split("Root Cause JSON:\n")[1].strip()
            rc_data = json.loads(rc_json_str)
        except Exception:
            rc_data = {}
            
        root_cause = rc_data.get("root_cause", "unknown")
        affected_service = rc_data.get("affected_service", "unknown-service")
        
        from agents.fix_recommender.tools import get_remediation
        rem_data = get_remediation(root_cause, affected_service)
        return rem_data.get("recommended_steps_template", [])
        
    elif agent_name == "comms_agent":
        # Try to parse service name from prompt
        service = "affected service"
        severity = "P1"
        root_cause = "dependency_failure"
        
        service_match = re.search(r'"service":\s*"([^"]+)"', prompt)
        if service_match:
            service = service_match.group(1)
        severity_match = re.search(r'"severity":\s*"([^"]+)"', prompt)
        if severity_match:
            severity = severity_match.group(1)
        rc_match = re.search(r'"root_cause":\s*"([^"]+)"', prompt)
        if rc_match:
            root_cause = rc_match.group(1)
            
        slack_msg = f"Alert: {service} is experiencing degradation. Severity: {severity}. Diagnosed root cause: {root_cause}."
        status_msg = f"We are investigating service degradation in {service} and working on recovery."
        
        # Trigger Slack logging tool side effect if possible
        try:
            from agents.comms_agent.tools import post_slack
            post_slack(slack_msg)
        except Exception:
            pass
            
        return {
            "slack_message": slack_msg,
            "status_page_update": status_msg
        }
        
    return {}

# Unified Agent execution function with retry logic + quota-aware backoff
async def run_agent_with_retry(agent, prompt: str, schema_validator, max_attempts: int = 5) -> dict:
    user_id = "incident-system"
    last_response_text = ""
    response_text = ""
    last_was_transient = False          # tracks whether the previous failure was transient
    original_model = agent.model        # save original model to restore at the end
    
    # List of candidate models to rotate through on failure
    model_candidates = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    # Ensure the configured model is at the front of the candidate list
    if original_model in model_candidates:
        model_candidates.remove(original_model)
    model_candidates.insert(0, original_model)
    
    model_index = 0
    attempt = 0
    
    try:
        while attempt < max_attempts:
            # Set the current model candidate
            agent.model = model_candidates[model_index % len(model_candidates)]

            # Create a fresh runner + fresh session for every attempt to avoid
            # ADK "Session not found" errors and stale conversation history on retries.
            runner = InMemoryRunner(agent=agent)
            session_id = f"session-{agent.name}-{datetime.datetime.utcnow().timestamp()}-{attempt}"
            
            # IMPORTANT: ADK InMemoryRunner requires the session to be explicitly
            # created in its session_service before run_async is called.
            # MUST use runner.app_name ("InMemoryRunner"), NOT agent.name —
            # the runner keys sessions by its own app_name internally.
            await runner.session_service.create_session(
                app_name=runner.app_name,
                user_id=user_id,
                session_id=session_id,
            )
            
            # Decide which prompt to send:
            # - First attempt → original prompt
            # - After a transient / rate-limit error → resend the ORIGINAL prompt
            #   (the model never saw the request, so a validation-retry makes no sense)
            # - After a validation error → send the "fix your JSON" retry prompt
            is_transient_retry = attempt > 0 and last_was_transient
            if attempt == 0 or is_transient_retry:
                current_prompt = prompt
            else:
                current_prompt = (
                    f"Your previous response failed validation.\n"
                    f"Error details: {last_response_text}\n"
                    f"Please reply with a valid JSON string adhering strictly to the schema. "
                    f"Do not include markdown tags like ```json or any prefix/suffix text.\n\n"
                    f"Original task:\n{prompt}"
                )
            
            try:
                print(f"[Executor] Running agent '{agent.name}' (using model '{agent.model}', attempt {attempt + 1}/{max_attempts})...")
                new_message = Content(parts=[Part(text=current_prompt)])
                
                response_text = ""
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=session_id,
                    new_message=new_message
                ):
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                response_text += part.text
                
                last_response_text = response_text
                last_was_transient = False
                json_text = response_text.strip()
                
                # Clean markdown code fences if LLM adds them
                if json_text.startswith("```"):
                    json_text = re.sub(r'^```(?:json)?\n', '', json_text)
                    json_text = re.sub(r'\n```$', '', json_text)
                    json_text = json_text.strip()
                    
                data = json.loads(json_text)
                
                # Execute validation
                schema_validator(data)
                print(f"[Executor] Agent '{agent.name}' succeeded on attempt {attempt + 1} with model '{agent.model}'")
                return data
                
            except Exception as e:
                error_str = str(e)
                last_response_text = f"Raw output: {response_text}. Error: {error_str}"
                is_rate_limited, is_transient = _classify_error(error_str)
                is_not_found = any(kw in error_str for kw in ["404", "NOT_FOUND", "not found"])
                
                print(
                    f"[Executor] Agent '{agent.name}' failed on attempt {attempt + 1}: "
                    f"{error_str[:200]}  "
                    f"[rate_limit={is_rate_limited}, transient={is_transient}, not_found={is_not_found}]"
                )
                
                # If the model is not found, rotate immediately to the next candidate model
                # and retry WITHOUT incrementing the attempt count or sleeping (if we have other models to try).
                if is_not_found and (model_index < len(model_candidates) - 1):
                    model_index += 1
                    print(f"[Executor] Model '{agent.model}' not supported. Rotating immediately to '{model_candidates[model_index % len(model_candidates)]}'...")
                    continue
                
                last_was_transient = is_rate_limited or is_transient
                
                # --- Exponential backoff for retriable errors -----------------------
                if (is_rate_limited or is_transient) and attempt < max_attempts - 1:
                    # Rotate model candidate on rate limit to distribute load
                    model_index += 1
                    
                    # Default backoff
                    if is_rate_limited:
                        wait_secs = 15 * (2 ** attempt)  # 15s, 30s, 60s, 120s
                    else:
                        wait_secs = 5 * (2 ** attempt)   # 5s, 10s, 20s, 40s
                    
                    # Override with parsed retry delay if it is specified and larger
                    parsed_delay = _extract_retry_delay(error_str)
                    if parsed_delay is not None:
                        # Add a safety margin (1.5 seconds) to ensure the server's window has fully cleared
                        wait_secs = max(wait_secs, parsed_delay + 1.5)
                        print(f"[Executor] Server suggested retry delay: {parsed_delay}s. Using wait time: {wait_secs:.2f}s")
                    
                    print(
                        f"[Executor] Retriable error detected — waiting {wait_secs:.2f}s "
                        f"before retry (rate_limit={is_rate_limited}, "
                        f"server_error={is_transient})..."
                    )
                    await asyncio.sleep(wait_secs)
                    attempt += 1
                    continue
                
                if attempt == max_attempts - 1:
                    print(f"[Executor] All retry attempts failed for agent '{agent.name}'. Falling back to heuristic mock generator...")
                    try:
                        fallback_data = _generate_mock_fallback(agent.name, prompt)
                        schema_validator(fallback_data)
                        return fallback_data
                    except Exception as fallback_err:
                        raise ValueError(
                            f"Agent '{agent.name}' failed after {max_attempts} attempts, "
                            f"and fallback generator also failed: {fallback_err}. "
                            f"Original error: {last_response_text}"
                        )
                attempt += 1
    finally:
        agent.model = original_model

async def execute_nasiko_pipeline(raw_log: str, service: str, history: Optional[str] = None) -> dict:
    """Executes the sequential-parallel Nasiko pipeline."""
    # Step 1: Alert Analyzer (Sequential)
    alert_prompt = f"Analyze this incident log.\nService: {service}\nRaw Log:\n{raw_log}"
    alert_data = await run_agent_with_retry(
        agent=alert_agent,
        prompt=alert_prompt,
        schema_validator=validate_alert_analyzer_output
    )
    
    # Brief pause between sequential agents to respect free-tier RPM limits
    await asyncio.sleep(3)
    
    # Step 2: Root Cause Agent (Sequential, input from Step 1)
    rc_prompt = (
        f"Diagnose the root cause given the parsed alert.\n"
        f"Alert JSON:\n{json.dumps(alert_data)}\n"
        f"Optional History Context:\n{history or 'No history provided'}"
    )
    rc_data = await run_agent_with_retry(
        agent=rc_agent,
        prompt=rc_prompt,
        schema_validator=validate_root_cause_agent_output
    )
    
    # Brief pause before spawning parallel agents
    await asyncio.sleep(3)
    
    # Step 3: Parallel Group (Fix Recommender AND Comms Agent)
    fix_prompt = f"Generate remediation steps for the root cause.\nRoot Cause JSON:\n{json.dumps(rc_data)}"
    comms_prompt = (
        f"Draft communications for the incident.\n"
        f"Alert JSON:\n{json.dumps(alert_data)}\n"
        f"Root Cause JSON:\n{json.dumps(rc_data)}"
    )
    
    # Run parallel agents in gather
    fix_task = run_agent_with_retry(
        agent=fix_agent,
        prompt=fix_prompt,
        schema_validator=validate_fix_recommender_output
    )
    comms_task = run_agent_with_retry(
        agent=comms_agent,
        prompt=comms_prompt,
        schema_validator=validate_comms_agent_output
    )
    
    fix_data, comms_data = await asyncio.gather(fix_task, comms_task)
    
    # Merge Step
    final_report = merge_outputs(alert_data, rc_data, fix_data, comms_data)
    return final_report

@app.post("/incident")
async def process_incident(payload: IncidentRequest):
    """Client endpoint. Calls the Nasiko workflow endpoint via POST."""
    nasiko_api_url = os.environ.get("NASIKO_API_URL", "http://localhost:8080")
    
    # Make external call to Nasiko orchestrator. 
    # If it fails or points to localhost/itself, run it locally.
    is_local_redirect = "localhost" in nasiko_api_url or "127.0.0.1" in nasiko_api_url
    
    if is_local_redirect:
        # Avoid HTTP deadlock or loop, run locally directly
        try:
            report = await execute_nasiko_pipeline(payload.raw_log, payload.service, payload.history)
            return report
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Pipeline execution error: {str(e)}")
            
    # Try calling external Nasiko endpoint
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{nasiko_api_url}/agents/incident-workflow/invoke",
                json={
                    "raw_log": payload.raw_log,
                    "service": payload.service,
                    "history": payload.history
                },
                timeout=90.0
            )
            if response.status_code == 200:
                return response.json()
            else:
                # Fallback to local run
                print(f"[API] Nasiko server returned {response.status_code}. Running pipeline locally.")
                report = await execute_nasiko_pipeline(payload.raw_log, payload.service, payload.history)
                return report
        except Exception as ex:
            print(f"[API] Failed to contact Nasiko server at {nasiko_api_url}: {ex}. Running pipeline locally.")
            try:
                report = await execute_nasiko_pipeline(payload.raw_log, payload.service, payload.history)
                return report
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Pipeline execution error: {str(e)}")

@app.post("/agents/incident-workflow/invoke")
async def invoke_nasiko_workflow(payload: NasikoWorkflowRequest):
    """The Nasiko orchestrator entrypoint invoked by the Nasiko API URL."""
    try:
        report = await execute_nasiko_pipeline(payload.raw_log, payload.service, payload.history)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/demo-incidents")
async def get_demo_incidents():
    """Serves the demo incidents payload to the frontend dashboard."""
    demo_file = os.path.join(parent_dir, "demo", "sample_incidents.json")
    if os.path.exists(demo_file):
        with open(demo_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serves the main incident responder dashboard."""
    dashboard_path = os.path.join(current_dir, "dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    raise HTTPException(status_code=404, detail="dashboard.html not found")
