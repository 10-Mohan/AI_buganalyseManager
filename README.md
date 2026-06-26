# AI_buganalyseManager (AI Incident Response Manager)

AI_buganalyseManager is an agentic, multi-stage incident response automation pipeline built on top of the Google Agent Development Kit (ADK) and FastAPI. It orchestrates a team of specialized AI agents working sequentially and in parallel to parse raw production logs, diagnose root causes against a known runbook database, recommend remediation commands, draft communications, and merge everything into a unified incident report.

![Dashboard Mockup](images/dashboard_mockup.png)

---

## Key Features

1. **Quota-Aware Adaptive Backoff**: Dynamically extracts the exact `retryDelay` or `Please retry in X.XXs` guidelines from Google GenAI API errors, sleeping for the requested duration plus a safety margin to guarantee the next attempt succeeds.
2. **Model Quota Rotation**: Automatically cycles through a candidate list of models (`gemini-2.5-flash`, `gemini-2.0-flash`, `gemini-1.5-flash`) on quota exhaustion (429 errors) or support limitations (404 NOT_FOUND errors) to split load across distinct quota pools.
3. **Heuristic Schema Fallback Mode**: If all model attempts fail due to complete API daily quota exhaustion, the pipeline executes a local parser that uses regex heuristics to generate valid, schema-compliant responses. This keeps the application fully functional for submissions and testing.
4. **Interactive Dashboard**: Serves a live, modern incident response frontend (`/`) showing telemetry metrics, log details, parsed diagnostics, and clickable action plans.

---

## System Architecture

```mermaid
flowchart TD
    subgraph Client Interface
        Dashboard["Dashboard Ingestion (HTML/JS)"]
        CLI["POST /incident Endpoint"]
    end

    subgraph Nasiko Orchestrator Engine
        Pipeline["Nasiko Pipeline Runner"]
        
        subgraph Stage 1: Log Extraction [Sequential]
            AA["Alert Analyzer Agent"]
        end
        
        subgraph Stage 2: Root Cause [Sequential]
            RC["Root Cause Agent"]
            RB[("Runbooks Database")]
            RC <-->|search_runbook| RB
        end
        
        subgraph Stage 3: Remediation & Comms [Parallel]
            FR["Fix Recommender Agent"]
            CM["Comms Agent"]
            Slack["Slack Ingress Webhook"]
            CM -->|post_slack| Slack
        end
        
        subgraph Stage 4: Merge [Script]
            MR["merge_report.py"]
        end
    end

    Dashboard --> Pipeline
    CLI --> Pipeline
    Pipeline --> Stage 1
    Stage 1 -->|parsed log JSON| Stage 2
    Stage 2 -->|diagnosed cause JSON| Stage 3
    Stage 3 -->|remediations + drafts| Stage 4
    Stage 4 -->|final unified report| Dashboard
```

---

## Workflow Step-by-Step

1. **Ingestion**: Raw unstructured service logs are sent to the FastAPI backend.
2. **Alert Analysis**: The `alert_analyzer` agent standardizes the log, identifies the logging level, extracts the timestamp, and labels the service and error signature.
3. **Root Cause Diagnostics**: The `root_cause_agent` executes fuzzy matches against the local runbook database, checking incident context (such as VirtualService mesh changes or DB pool capacity settings) to classify the root cause.
4. **Parallel Fix & Comms Generation**:
   * The `fix_recommender` fetches corresponding remediation steps and maps risk levels, estimated duration, and CLI hints (such as `kubectl scale` or `gcloud deploy`).
   * The `comms_agent` drafts internal Slack alerts and customer-facing status page updates, auto-publishing the Slack alert.
5. **Unified Reporting**: The orchestrator invokes `merge_report.py` to compile the metadata, root cause analysis, fix tasks, and draft messages into a single report schema.

---

## Local Setup & Execution

### Prerequisites
* Python 3.10+
* Active Google AI Studio API Key (set as `GOOGLE_API_KEY` in environment)

### Installation
1. Clone the repository.
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment template and insert your API key:
   ```bash
   cp .env.example .env
   ```

### Running the App
Start the FastAPI server:
```bash
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```
Open [http://localhost:8000/](http://localhost:8000/) in your browser to view the interactive dashboard.
