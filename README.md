# Finance Insight Service - CrewAI

## Use Case Description

**Overview:**
Finance Insight Service is an AI-powered financial research assistant that combines real-time news analysis, market data, and quantitative modeling to deliver validated investment insights.

**The Problem:**
Individual investors and financial analysts waste hours manually researching stocks—reading scattered news articles, checking multiple data sources, calculating metrics, and trying to make sense of conflicting information. Traditional tools either provide raw data without context or AI responses that "hallucinate" numbers and make unverifiable claims.

**Target Users:**
- **Retail investors** who want professional-grade analysis without expensive Bloomberg terminals
- **Financial analysts** who need to validate research quickly before making recommendations
- **Finance students** learning how to conduct proper equity research with citations
- **Portfolio managers** who need to track multiple positions with consistent, auditable analysis

**Key Benefits:**
This system solves the "AI hallucination" problem in financial analysis by:
- **Never letting LLMs do math** - All calculations run through sandboxed Python (no made-up numbers)
- **Requiring citations** - Every claim is backed by scraped sources with timestamps
- **Multi-stage validation** - Dedicated auditor agent rejects outputs that fail quality checks
- **Transparent limitations** - Clearly states what data is missing or uncertain
- **Reproducible results** - Same inputs = same outputs (deterministic calculations)

Instead of spending 2-3 hours researching a stock, users get a comprehensive analysis in 5-10 minutes—with confidence that numbers are real, sources are cited, and limitations are disclosed.

---

## Architecture Overview

![Architecture Diagram](https://github.com/sahas-eashan/Finance-Insight-Service-CrewAI-/blob/app/image.png)

The system uses a **sequential multi-agent workflow** with quality gates at each step:

### **Agents:**
1. **Planner** - Orchestrates workflow and decides which modules to run
2. **Researcher** - Gathers news, evidence, and formulas from web sources
3. **Quant** - Fetches market data, calculates metrics, runs scenarios
4. **Auditor** - Validates outputs for quality, accuracy, and compliance

### **Key Design Principles:**
- **Accuracy over speed** - Multiple validation checkpoints ensure quality
- **No LLM math** - All calculations run through sandboxed Python execution
- **Graceful degradation** - Partial data produces responses with clear limitations
- **Context awareness** - Each task sees outputs from all previous tasks
- **Transparency** - Failures are documented, not hidden

---

## Framework: CrewAI

### Why CrewAI?

Built using **CrewAI** for multi-agent orchestration. CrewAI provides:

- **Sequential Process** - Agents execute in defined order, each task waits for previous to complete
- **Context Passing** - Tasks automatically receive outputs from dependent tasks
- **Built-in Tracing** - Event bus emits real-time events (tool usage, task completion, errors)
- **Agent Specialization** - Each agent has role, goal, backstory, and specific tools
- **Task Dependencies** - Explicit context chains ensure data flows correctly
- **LLM Flexibility** - Works with OpenAI, Anthropic, or any LiteLLM-compatible model

### Agent Definition in CrewAI

Each agent is created with:
```python
Agent(
    role="Research Agent (news + evidence)",
    goal="Discover relevant news and extract evidence-backed drivers",
    backstory="You are a meticulous researcher who only uses sources you can access...",
    tools=[SerperDevTool(), ScrapeWebsiteTool()],
    allow_delegation=False  # No agent-to-agent delegation
)
```

- **Role**: Short description of agent's function
- **Goal**: What success looks like for this agent
- **Backstory**: Detailed behavioral instructions and constraints
- **Tools**: List of callable functions the agent can use
- **allow_delegation**: Set to False (planner decides workflow, not agents)

### Task Definition in CrewAI

Each task is created with:
```python
Task(
    description="You are given a research request: {user_request}...",
    expected_output="Return strict JSON with keys: drivers, articles, limitations",
    agent=researcher_agent,
    context=[planner_task]  # Can access planner task output
)
```

- **description**: Instructions with placeholders (`{user_request}`, `{current_date}`)
- **expected_output**: JSON schema the agent must follow
- **agent**: Which agent executes this task
- **context**: List of previous tasks whose outputs are available

### How Context Flows in CrewAI

Tasks declare dependencies via `context` parameter:

```python
research_task.context = [planner_task]
audit_research_task.context = [planner_task, research_task]
quant_task.context = [planner_task, research_task, audit_research_task]
final_report_task.context = [all_7_previous_tasks]
```

CrewAI automatically:
- Waits for context tasks to complete
- Passes outputs to the next task's LLM prompt
- Makes all previous outputs available via task context

This enables rich decision-making without manual state management.

### Why Sequential Process?

CrewAI supports multiple process types (sequential, hierarchical, consensual). We chose **sequential** because:

- **Validation gates**: Auditor can check quality before proceeding
- **Full context**: Each agent sees everything previous agents produced
- **Debuggability**: Linear execution trace, easy to understand what happened
- **Predictability**: No race conditions or parallel conflicts
- **Trade-off**: Slower than parallel, but accuracy and transparency are more important

---

## Complete Execution Flow

### **8 Sequential Tasks:**

#### **1. PLANNER_TASK** (Planner Agent)
**Purpose:** Decides workflow strategy based on user request

**Receives:**
- User request
- Current date/time
- Conversation summary

**Decides:**
- Which modules to use (Research/Quant/Audit)
- Search parameters (query, tickers, sites, days)
- Quantitative parameters (symbol, interval, horizon)

**Outputs:**
- `plan`: Which modules to run and why
- `research_request`: Query parameters for research
- `quant_request`: Parameters for quantitative analysis
- `notes`: Planning considerations

---

#### **2. RESEARCH_NEWS_TASK** (Researcher Agent)
**Purpose:** Gathers news articles and extracts evidence-backed insights

**Tools:**
- SerperDev/SerpApi for web search
- ScrapeWebsiteTool for full article content

**Actions:**
- Searches web for relevant articles (max 8)
- Scrapes full content from URLs
- Extracts headline, timestamp, key points
- Clusters information into 2-4 drivers (earnings, macro, regulation, product news)
- Extracts formulas/metrics when needed

**Outputs:**
- `drivers`: Key themes with explanations and citations
- `articles`: Full article metadata with key points
- `metrics_formulas`: Financial formulas extracted from sources
- `limitations`: Failed URLs, missing data, etc.

**Example Output:**
```json
{
  "drivers": [
    {
      "driver": "AI Infrastructure Growth",
      "why_it_matters": "Data center spending increased 40% YoY driven by GPU demand",
      "citations": [{"url": "...", "evidence": "..."}]
    }
  ]
}
```

---

#### **3. AUDIT_RESEARCH_TASK** (Auditor Agent)
**Purpose:** Validates research quality before proceeding

**Validates:**
- Citations present and valid
- Timestamps not missing or fabricated
- Relevance to user request
- Formula extraction when needed

**Returns:** APPROVED | REJECTED | PARTIAL

**Example REJECTED:**
```json
{
  "audit_status": "REJECTED",
  "issues": [{
    "category": "data_quality",
    "problem": "Research provided no valid citations",
    "fix_action": "Rerun research with at least 2-3 accessible sources"
  }],
  "required_reruns": ["research"]
}
```

**Example PARTIAL:**
```json
{
  "audit_status": "PARTIAL",
  "issues": [{
    "category": "incomplete_data",
    "problem": "Only 1 source scraped, target was 3",
    "fix_action": "Note limitation but proceed with available data"
  }],
  "approved_modules": ["research"],
  "notes": ["2 URLs blocked, 1 succeeded"]
}
```

---

#### **4. QUANT_SNAPSHOT_TASK** (Quant Agent)
**Purpose:** Fetches market data and performs calculations

**Tools:**
- MarketDataFetch (Twelve Data → Stooq fallback)
- FundamentalsFetch (Alpha Vantage)
- SafePythonExec (sandboxed numpy/pandas)

**Actions:**
- Confirms current date via Python datetime
- Fetches market data (price history, volume)
- Fetches fundamentals (P/E, ROE, margins, cash flow)
- Runs calculations using SafePythonExec
- Computes metrics from research formulas
- Generates scenarios (base/bull/bear) if requested

**Outputs:**
- `as_of`: Timestamp and data provider
- `snapshot`: Current metrics and data points
- `scenarios`: Price targets with assumptions (optional)
- `limitations`: Missing data, API failures

**Example Output:**
```json
{
  "as_of": {"timestamp": "2026-01-17", "provider": "TwelveData"},
  "snapshot": {
    "last_close": 150.25,
    "returns_1d": 0.023,
    "volatility_annualized": 0.28
  },
  "scenarios": {
    "base": {"price_target": 165, "assumptions": "Expected return over 30 days"},
    "bull": {"price_target": 180, "assumptions": "+1.0 sigma move"},
    "bear": {"price_target": 140, "assumptions": "-1.0 sigma move"}
  }
}
```

---

#### **5. AUDIT_QUANT_TASK** (Auditor Agent)
**Purpose:** Validates quantitative analysis quality

**Validates:**
- Numeric sanity (no NaN, realistic values)
- Required metrics computed
- Scenario assumptions reasonable
- RSI within 0-100, prices positive, etc.

**Returns:** APPROVED | REJECTED | PARTIAL

---

#### **6. FINAL_DRAFT_TASK** (Planner Agent)
**Purpose:** Creates first draft of response

**Rules:**
- Use only approved outputs
- No citations by default (unless requested)
- Only use numbers from quant output
- Keep concise and aligned with request

**Outputs:**
- `draft_response`: Initial answer text
- `notes`: Drafting considerations

---

#### **7. AUDIT_FINAL_TASK** (Auditor Agent)
**Purpose:** Validates complete response quality

**Validates:**
- Alignment between research + quant + draft
- Completeness for user request
- Compliance (no personalized advice, no guaranteed returns)
- All claims backed by data

**Returns:** APPROVED | REJECTED | PARTIAL

---

#### **8. FINAL_REPORT_TASK** (Planner Agent)
**Purpose:** Produces final user-facing response

**Receives:** ALL previous outputs including audit results

**Formatting:**
- Main answer: 2-3 paragraphs or bullet points
- Conversational tone, direct answer
- No section headers in main response
- Separate sections for details:
  - **Limitations:** Data gaps, caveats
  - **Sources:** Citations if requested
  - **Note/Disclaimer:** Important context

**If audit REJECTED:**
- Surfaces issues in Limitations section
- Does not present results as approved
- Explains what failed and why

**Example Final Response (APPROVED):**
```
BMW sedan prices in 2026 start around $58,000 for the 530i base model, 
with the M340i xDrive priced near $60,000. The top-tier 540i xDrive exceeds 
$62,000. These are MSRP figures and may vary by region and dealer incentives.

Limitations:
- Prices reflect January 2026 estimates without accounting for local dealer 
  incentives or taxes
- Based on 2 sources; direct dealer quotes not available
```

**Example Final Response (REJECTED):**
```
I couldn't complete the full analysis due to data access issues.

Limitations:
- Research audit rejected: No valid citations found. Most URLs failed to load 
  due to bot protection
- Quant analysis skipped due to missing research data
- Unable to provide price projections without fundamental data
```

---

## What Happens When Audit Fails?

### **No Automatic Reruns**
The system is sequential, not a loop. If an audit fails:
1. Audit marks the module as REJECTED or PARTIAL
2. Lists specific issues with fix actions
3. Workflow continues forward (no rerun)
4. Final report receives the failed audit status
5. Response surfaces the issues in Limitations section

### **Three Audit Outcomes:**

#### **APPROVED** ✅
- All checks passed
- Workflow proceeds smoothly
- Minimal limitations (only disclaimers)
- Results presented confidently

#### **PARTIAL** ⚠️
- Some data available but incomplete
- Issues noted but not blocking
- Workflow continues with available data
- Response includes caveats about data gaps

**Example:**
```
Based on limited data, AI infrastructure spending is growing...

Limitations:
- Only 1 source successfully accessed (2 URLs blocked)
- Analysis based on partial data - may not reflect complete picture
```

#### **REJECTED** ❌
- Critical failures detected
- Module outputs unusable
- Workflow continues but marks failure
- Final response explains what went wrong

**Example:**
```
Analysis incomplete due to data access issues.

Limitations:
- Research failed: No citations - all sources blocked by bot protection
- Quant skipped: Cannot analyze without research context
- Recommendation: Try again with different sources or timeframe
```

---

## Context Flow (Task Dependencies)

Each task receives **context** from previous tasks:
- **Research** sees: Planner
- **Audit_Research** sees: Planner, Research
- **Quant** sees: Planner, Research, Audit_Research
- **Audit_Quant** sees: Planner, Research, Audit_Research, Quant
- **Final_Draft** sees: Planner, Research, Audit_Research, Quant, Audit_Quant
- **Audit_Final** sees: All above + Final_Draft
- **Final_Report** sees: **ALL 7 previous tasks**

This enables rich validation and ensures nothing is lost or invented.

---

## Separation of Concerns

1. **Planner** decides strategy (what to run, what parameters)
2. **Specialized agents** execute their domain (research OR quant, not both)
3. **Auditor** validates quality (independent quality gate)
4. **Planner** synthesizes final output (has full context)

This ensures **transparency** (failures documented), **quality** (multiple checkpoints), and **robustness** (partial data doesn't crash the system).

---

## Deployment

### What is WSO2 AI Agent Management Platform (AMP)?

**WSO2 AI Agent Management Platform** is an open-source control plane designed for enterprises to deploy, manage, and govern AI agents at scale. It provides:

- **Deploy at Scale** - Run AI agents on Kubernetes with production-ready configurations
- **Lifecycle Management** - Manage agent versions, configurations, and deployments from a unified control plane
- **Full Observability** - Capture traces, metrics, and logs using OpenTelemetry for complete visibility into agent behavior
- **Governance** - Enforce policies, manage access controls, and ensure compliance across all agents
- **Auto-Instrumentation** - Zero-code instrumentation for AI frameworks (CrewAI, LangChain, LlamaIndex)

AMP is built on **OpenChoreo** for internal agent deployments and leverages **OpenTelemetry** for extensible instrumentation. It allows you to monitor not just your infrastructure, but the actual behavior of AI agents—including LLM calls, tool usage, task execution, and validation checkpoints.

**GitHub Repository:** [WSO2 AI Agent Management Platform](https://github.com/wso2/ai-agent-management-platform)

---

### Deploying Finance Insight Service on AMP

#### Prerequisites

1. **Kubernetes Cluster** - k3d or any Kubernetes cluster (tested on k3d)
2. **AMP Platform Installed** - Follow the [AMP Quick Start Guide](https://github.com/wso2/ai-agent-management-platform)
3. **Docker Registry** - Local or remote registry accessible to your cluster
4. **MongoDB Atlas** - Database connection string (or local MongoDB)

#### Deployment Steps

##### 1. Install AMP Platform

```bash
# Clone AMP repository
git clone https://github.com/wso2/ai-agent-management-platform.git
cd ai-agent-management-platform

# Create k3d cluster with registry
k3d cluster create amp-local \
  --registry-create amp-registry:0.0.0.0:10082 \
  --servers 1

# Install AMP using Helm
helm install wso2-amp deployments/helm-charts/wso2-ai-agent-management-platform \
  --namespace amp-system \
  --create-namespace
```

##### 2. Prepare Your Agent

Create `.choreo/component.yaml` in your project root:

```yaml
schemaVersion: "1.0"
id: finance-insight
name: Finance Insight Service
type: service
description: AI-powered financial research assistant
runtime: python
buildType: dockerfile
image: Dockerfile
ports:
  - port: 8000
    type: http
env:
  - name: OPENAI_API_KEY
    valueFrom: SECRET
  - name: SERPER_API_KEY
    valueFrom: SECRET
  - name: MONGO_URI
    valueFrom: SECRET
```

##### 3. Build and Push Image

```bash
# Build Docker image
docker build -t finance-insight-service:latest .

# Tag for AMP registry
docker tag finance-insight-service:latest \
  localhost:10082/default-finance-insight-image:v1

# Push to registry
docker push localhost:10082/default-finance-insight-image:v1
```

##### 4. Deploy via AMP Console

1. Open AMP Console at `http://default.localhost:9080`
2. Navigate to **Create Agent**
3. Configure agent:
   - **Name:** Finance Insight Service
   - **Description:** AI-powered financial research assistant
   - **Type:** Service
   - **Runtime:** Python
   - **Port:** 8000
4. Add environment variables:
   - `OPENAI_API_KEY` → Your OpenAI API key
   - `SERPER_API_KEY` → Your Serper API key
   - `MONGO_URI` → Your MongoDB connection string
5. Click **Deploy**

##### 5. Verify Deployment

```bash
# Check pod status
kubectl get pods -n dp-default-default-default-<namespace-id>

# Check service endpoint
curl http://default.localhost:9080/finance-insight/health
```

Expected response:
```json
{
  "status": "ok",
  "mongo": "ok",
  "jobs": {"total": 0, "pending": 0, "running": 0, "completed": 0}
}
```

##### 6. Test with a Query

```bash
curl -X POST http://default.localhost:9080/finance-insight/research \
  -H "Content-Type: application/json" \
  -d '{
    "user_request": "Analyze NVIDIA stock performance and AI chip market trends"
  }'
```

Response includes `job_id`. Poll for results:

```bash
curl http://default.localhost:9080/finance-insight/result/<job_id>
```

---

### Observability in AMP - Viewing Traces

The most powerful feature of AMP is **full-stack observability** with OpenTelemetry traces. This allows you to see:

- **Agent-level traces** - Which agents were invoked, in what order
- **Task execution** - How long each task took, what inputs/outputs it had
- **LLM calls** - Which models were called, prompts, responses, token counts
- **Tool usage** - Which tools were executed, parameters, results
- **Validation checkpoints** - Audit outcomes (APPROVED, PARTIAL, REJECTED)

#### Accessing Traces in AMP Console

1. **Navigate to Observability**
   - Open AMP Console at `http://default.localhost:9080`
   - Go to **Observability → Traces**

2. **View Agent Execution**
   - Each query creates a **root span** representing the entire workflow
   - Child spans show individual tasks: Planner → Researcher → Auditor → Quant → Final Report

3. **Inspect Task Details**
   - Click on any span to see:
     - **Duration** - How long the task took
     - **Attributes** - Agent role, task description, expected output
     - **Events** - Tool calls, LLM interactions, validation results

4. **Trace LLM Calls**
   - LLM spans show:
     - **Model** - `gpt-4o`, `gpt-4o-mini`, etc.
     - **Prompt** - Full input to the model
     - **Response** - Generated output
     - **Token Count** - Input tokens, output tokens, total cost

5. **Debug Failures**
   - Failed spans are highlighted in red
   - Error messages show exact failure reason
   - Stack traces available for Python exceptions

#### Example: Tracing a Finance Query

**Query:** "Analyze NVIDIA's AI chip dominance and competition from AMD"

**Trace Structure:**
```
CrewAI Workflow (15.2s)
├─ Planner Task (2.1s)
│  └─ LLM Call: gpt-4o (1.8s) - Decide modules to run
├─ Research Task (4.5s)
│  ├─ Tool: serper_search (1.2s) - "NVIDIA AI chip market share"
│  ├─ Tool: scrape_website (2.1s) - news.nvidia.com article
│  └─ LLM Call: gpt-4o (0.8s) - Extract drivers
├─ Audit Research (1.3s)
│  └─ LLM Call: gpt-4o-mini (1.1s) - Validate citations
├─ Quant Task (5.8s)
│  ├─ Tool: fetch_market_data (2.3s) - NVDA historical prices
│  ├─ Tool: safe_python_exec (2.9s) - Calculate metrics
│  └─ LLM Call: gpt-4o (0.4s) - Format results
├─ Audit Quant (0.9s)
│  └─ LLM Call: gpt-4o-mini (0.7s) - Validate calculations
└─ Final Report (0.6s)
   └─ LLM Call: gpt-4o (0.5s) - Synthesize output
```

**Key Insights from Traces:**
- Research found 3 sources, 2 successfully scraped
- Quant calculated volatility (32% annualized) using safe Python execution
- Both audits passed (APPROVED status)
- Total LLM cost: ~$0.15 (tracked via token counts)
- Bottleneck: Web scraping (2.1s) - could be optimized with parallel fetching

