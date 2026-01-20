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
1. **Research** - Gathers news, evidence, and formulas from web sources
2. **Quant** - Fetches market data, calculates metrics, runs scenarios
3. **Audit** - Validates outputs and produces the final response

### **Key Design Principles:**
- **Accuracy over speed** - Multiple validation checkpoints ensure quality
- **No LLM math** - All calculations run through sandboxed Python execution
- **Graceful degradation** - Partial data produces responses with clear limitations
- **Context awareness** - Each task sees outputs from all previous tasks
- **Transparency** - Failures are documented, not hidden

---

## Technology Stack

### Backend Components

#### **Flask Backend (Python 3.12)**
The API server is built with **Flask 3.0+** for handling asynchronous agent workflows:

**Key Features**:
- **Async Job Processing**: Non-blocking architecture allows multiple queries to run concurrently
- **Thread-Safe Job Queue**: In-memory job dictionary with automatic cleanup (10-minute expiration)
- **Health Monitoring**: `/health` endpoint reports system status and job statistics
- **Memory Management**: Background cleanup thread runs every 5 minutes to prevent memory leaks
- **RESTful API Endpoints**:
  - `POST /research` - Submit new financial analysis query
  - `GET /result/<job_id>` - Poll for job completion and retrieve results
  - `GET /health` - System health and resource usage
  - `POST /workflow` - Run specific workflow modules (research/quant/audit)

**Why Flask?**
- **Lightweight & Flexible**: Minimal overhead, easy integration with CrewAI agents
- **Python Ecosystem**: Native compatibility with yfinance, pandas, FAISS, and ML libraries
- **Production-Ready**: Runs under Gunicorn with multiple workers for horizontal scaling
- **OpenTelemetry Support**: Seamless instrumentation via AMP's auto-injection
- **Async Threading**: Handles long-running agent workflows without blocking requests

**Architecture**:
```python
Flask App
├─ Job Submission → Create job_id → Start agent thread → Return job_id
├─ Background Thread → Execute CrewAI workflow → Store result in memory
├─ Cleanup Thread → Remove expired jobs every 5 minutes → gc.collect()
└─ Result Polling → Fetch from memory → Return to client
```

#### **FAISS Vector Database**
The system uses **FAISS (Facebook AI Similarity Search)** for efficient semantic search and document retrieval:

**Full Form**: **F**acebook **A**I **S**imilarity **S**earch

**Why FAISS?**
- **Speed**: Sub-millisecond search over millions of documents using approximate nearest neighbors (ANN)
- **Memory Efficiency**: Compressed vector representations reduce RAM usage by 4-8x compared to raw embeddings
- **No Network Latency**: Runs in-memory within the application (no external database calls)
- **Scalability**: Production-proven at Meta/Facebook for billion-scale vector search
- **Open Source**: No licensing costs, active community, CPU/GPU support

**Use Case in Finance Insight Service**:
When analyzing "NVIDIA's AI chip dominance", FAISS retrieves:
- Historical research reports mentioning "GPU market share"
- News articles about "data center AI accelerators"
- Earnings call transcripts discussing "AI revenue growth"

This provides agents with **domain-specific context** beyond their training data, reducing hallucinations and improving accuracy.

**Implementation Details**:
- **Embedding Model**: OpenAI `text-embedding-3-small` (1536 dimensions)
- **Index Type**: HNSW (Hierarchical Navigable Small World) for fast approximate search
- **Location**: `data/faiss.index` - Pre-built index with 10,000+ financial documents
- **Query Flow**: User query → Embed → FAISS search → Top-K documents → Pass to Researcher agent

**Benefits**:
  - Fast semantic search over large document collections
  - Memory-efficient approximate nearest neighbor search
  - No external database dependency (runs in-memory)
  - Enables RAG (Retrieval-Augmented Generation) for more accurate agent responses
  - Offline operation - no API calls required for document retrieval

#### **uv (Ultra-fast Python Package Manager)**
This project uses **uv** for dependency management instead of traditional `pip` or `poetry`:

**What is uv?**
**uv** is a Rust-based Python package installer and resolver developed by Astral (creators of Ruff). It's a drop-in replacement for `pip`, `pip-tools`, and `virtualenv` but **10-100x faster**.

**Why uv?**
- **Speed**: Installs packages 10-100x faster than pip (Rust-powered parallel downloads)
- **Deterministic Builds**: Lock file ensures identical dependencies across dev/staging/prod
- **Better Resolution**: Solves complex dependency conflicts that break pip
- **Disk Efficiency**: Global cache prevents duplicate downloads across projects
- **Compatible**: Works with PyPI, private registries, and GitHub repos
- **Modern Tooling**: Single binary, no bootstrapping issues

**Usage in This Project**:
```bash
# Install dependencies (equivalent to pip install -r requirements.txt)
uv pip install -r requirements.txt

# Add new package (equivalent to pip install + requirements.txt update)
uv pip install crewai

# Create virtual environment (equivalent to python -m venv)
uv venv
```

**Impact on Deployment**:
- **Docker Build Speed**: `uv pip install` in Dockerfile reduces image build time from 5 minutes → 30 seconds
- **CI/CD Pipelines**: Faster dependency installation speeds up automated testing
- **Kubernetes Startup**: Pods start faster with pre-cached dependencies
- **Development**: Developers iterate faster with instant package installs

**Comparison**:
| Tool | Install Time | Lock File | Dependency Resolution | Written In |
|------|--------------|-----------|----------------------|------------|
| pip | ~2-3 min | ❌ | Basic (can break) | Python |
| poetry | ~1-2 min | ✅ | Good | Python |
| **uv** | **~10-20 sec** | ✅ | Excellent | **Rust** |

### Frontend

#### **Agent Chat UI**
The web interface is a forked and customized version of an open-source agent chat platform:

**Repository**: [sahas-eashan/Agent-chat](https://github.com/sahas-eashan/Agent-chat)

**Key Features**:
- **Scenario-based chat** - Start from curated prompts or type your own
- **Job status polling** - Shows pending/running/completed states
- **Live status cues** - See progress while the agent runs
- **Single-session focus** - No persistent chat history
- **Settings configuration** - Manage API base URL, API key, and service status

**Technology Stack**:
- **Framework**: Next.js 14 with TypeScript
- **Styling**: Custom CSS with CSS variables for theming
- **Components**: Custom React components for chat and settings
- **API Integration**: REST client communicating with Flask backend at `/chat/async`

**Deployment**: Runs separately from backend, typically on `http://localhost:3000` during development or deployed to Vercel/Netlify for production

**Customizations**:
- Scenario cards and quick-start prompts
- Minimal, single-chat layout with new chat action
- Service status indicators on the settings screen

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
    tools=[SerpApiNewsSearchTool(), ScrapeWebsiteTool()],
    allow_delegation=False  # No agent-to-agent delegation
)
```

- **Role**: Short description of agent's function
- **Goal**: What success looks like for this agent
- **Backstory**: Detailed behavioral instructions and constraints
- **Tools**: List of callable functions the agent can use
- **allow_delegation**: Set to False (agents do not delegate tasks)

### Task Definition in CrewAI

Each task is created with:
```python
Task(
    description="You are given a research request: {user_request}...",
    expected_output="Return strict JSON with keys: drivers, articles, limitations",
    agent=researcher_agent,
    context=[]  # No planner; research runs first
)
```

- **description**: Instructions with placeholders (`{user_request}`, `{current_date}`)
- **expected_output**: JSON schema the agent must follow
- **agent**: Which agent executes this task
- **context**: List of previous tasks whose outputs are available

### How Context Flows in CrewAI

Tasks declare dependencies via `context` parameter:

```python
research_task.context = []
quant_task.context = [research_task]
audit_task.context = [research_task, quant_task]
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

### 3 Sequential Tasks

1. **Research Task** - gathers recent news, evidence, and formulas (with citations).
2. **Quant Task** - fetches market data and fundamentals, computes metrics and scenarios via safe_python_exec.
3. **Audit Task** - validates outputs and produces the final response.

**Context Flow**:
- Quant sees Research.
- Audit sees Research + Quant.

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
4. **API Keys** - OpenAI, SerpAPI, Twelve Data, Alpha Vantage ([Setup Guide](API_KEYS.md))

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
  - name: SERPAPI_API_KEY
    valueFrom: SECRET
  - name: TWELVE_DATA_API_KEY
    valueFrom: SECRET
  - name: ALPHAVANTAGE_API_KEY
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
   - `SERPAPI_API_KEY` → Your SerpAPI key
   - `TWELVE_DATA_API_KEY` → Your Twelve Data API key
   - `ALPHAVANTAGE_API_KEY` → Your Alpha Vantage API key
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
  "jobs": {"total": 0, "pending": 0, "running": 0, "completed": 0}
}
```

##### 6. Test with a Query

```bash
curl -X POST http://default.localhost:9080/finance-insight/chat/async \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Analyze NVIDIA stock performance and AI chip market trends"
  }'
```

Response includes `jobId`. Poll for results:

```bash
curl http://default.localhost:9080/finance-insight/chat/async/<job_id>/result
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
   - Child spans show individual tasks: Research → Quant → Audit

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
CrewAI Workflow (12.4s)
├─ Research Task (4.2s)
│  ├─ Tool: serpapi_news_search (1.1s) - "NVIDIA AI chip market share"
│  ├─ Tool: scrape_website (2.0s) - news.nvidia.com article
│  └─ LLM Call: gpt-4o (0.7s) - Extract drivers
├─ Quant Task (5.1s)
│  ├─ Tool: price_history_fetch (2.0s) - NVDA historical prices
│  ├─ Tool: safe_python_exec (2.6s) - Calculate metrics
│  └─ LLM Call: gpt-4o (0.5s) - Format results
└─ Audit Task (2.1s)
   └─ LLM Call: gpt-4o-mini (1.8s) - Validate and finalize response
```

**Key Insights from Traces:**
- Research found 3 sources, 2 successfully scraped
- Quant calculated volatility using safe Python execution
- Audit passed (APPROVED status)
- Total LLM cost: ~$0.15 (tracked via token counts)
- Bottleneck: Web scraping (2.0s) - could be optimized with parallel fetching
