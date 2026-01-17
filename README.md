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
- numeric_sanity_check (custom): range checks + missing-field checks.
- cross_source_check: compare two data sources when available.
- policy_lint (custom): bans "buy now", "guaranteed profit", etc., and enforces disclaimers.
