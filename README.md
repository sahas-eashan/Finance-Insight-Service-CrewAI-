# Finance Insight Service - CrewAI

## Overview
Finance Insight Service uses a plan -> execute -> audit -> repair cycle to deliver finance news, a market snapshot, and bounded scenarios. It prioritizes accuracy over speed and avoids "LLM does math" errors by routing all calculations through a sandboxed Python execution tool.

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB running locally
- Required API keys (see Configuration below)

### One-Command Start
```bash
./run.sh
```

This will start both:
- **Backend API** on http://localhost:5000
- **Frontend UI** on http://localhost:3000

### Manual Start
If you prefer to run them separately:

**Backend:**
```bash
uv run finance_insight_api --host 0.0.0.0 --port 5000
```

**Frontend:**
```bash
cd UI
npm run dev
```

## Configuration

Copy `.env.example` to `.env` and add: `OPENAI_API_KEY` plus either `SERPER_API_KEY` or `SERPAPI_API_KEY`. Optionally add `TWELVE_DATA_API_KEY` (falls back to Stooq when missing) and `ALPHAVANTAGE_API_KEY` for fundamentals/ratios. For the Flask API, set `MONGO_URI`, `MONGO_DB`, and optional `API_KEY`.

Limitation: Some sources (for example, Reuters or Bloomberg) may block scraping due to JavaScript or bot protection, so results may fall back to headlines/snippets.
Improvement: Add a JS-capable scraper or a paid content API to increase full-text coverage.

## Goals and constraints
- Deliver finance news + stock brief + bounded scenarios + non-personalized "watch/monitor/avoid" outputs.
- Prioritize maximum accuracy over speed via review loops.
- Avoid "LLM does math" mistakes by performing all calculations through a sandboxed Python execution tool.

## Orchestration approach
This is not a rigid deterministic pipeline. It is a plan -> execute -> audit -> repair cycle:
- A planning agent decides which steps are needed (news only vs market + indicators vs scenarios).
- A dedicated auditor approves or rejects results.
- If rejected, only the failed parts are rerun (bounded retries).
- Within each step, work is deterministic where possible.

## Agent stack

### 1) Planner and Report Synthesizer (Manager)
Responsibilities:
- Parse request (tickers, horizon, modules).
- Assign tasks to Research and Quant.
- Trigger audit, apply repair loop if needed.
- Produce final response only from audited and approved facts.

### 2) Research Agent (news + evidence)
Responsibilities:
- Discover and read relevant articles.
- Extract the "why it matters" with timestamps and citations.
- Cluster headlines into 2 to 4 drivers (earnings, macro, regulation, product news, etc.).

Tools (2):
- SerperDevTool (CrewAI) or SerpApiGoogleSearchTool (CrewAI) for web/news discovery (free keys).
  - Serper tool: https://docs.crewai.com/en/tools/search-research/serperdevtool
  - SerpApi tool: https://docs.crewai.com/en/tools/search-research/serpapi-googlesearchtool
- Requires `SERPER_API_KEY` for Serper or `SERPAPI_API_KEY` for SerpApi (different services).
- Searches can be scoped to specific domains using `site:example.com` filters (for example: `site:reuters.com OR site:bloomberg.com`).
- ScrapeWebsiteTool (CrewAI) to fetch full article content (not just snippets):
  - https://docs.crewai.com/en/tools/search-research/scrapewebsitetool

### 3) Quant Agent (market data + indicators + scenarios via Python)
Responsibilities:
- Decide which computations are needed based on the request (not all metrics by default).
- Use provided data when supplied; fetch market data only when needed.
- Compute indicators deterministically (returns, volatility, RSI, MAs, drawdown, etc.).
- Generate bounded scenarios (base/bull/bear) when the request calls for them.

Tools (3):
- market_data_fetch (custom tool with provider fallback)
  - Provider order (recommended): Twelve Data -> Stooq else skip.
- fundamentals_fetch (custom tool)
  - Provider: Alpha Vantage (requires `ALPHAVANTAGE_API_KEY`, free tier is rate-limited).
- safe_python_exec (custom tool): executes small, calculator-style Python scripts with numpy/pandas allowed; returns SUCCESS with final_output or CODE ERROR for self-repair.

### 4) Auditor (logic + compliance gate)
Responsibilities:
- Reject impossible metrics (e.g., RSI outside 0 to 100).
- Check freshness (dates) and that every factual claim has a citation.
- Ensure output is informational and uncertainty-aware (no guaranteed returns or personalized advice).

Tools (3):
- numeric_sanity_check (custom): range checks + missing-field checks.
- cross_source_check: compare two data sources when available.
- policy_lint (custom): bans "buy now", "guaranteed profit", etc., and enforces disclaimers.

## Response (expected outputs)
- as_of: timestamp + provider(s) used
- news_brief: clustered drivers + citations (URLs + published time)
- snapshot: last price/return + computed indicators (from Python) + provenance
- scenarios: base/bull/bear ranges + assumptions
- stance: watch | monitor | avoid + thesis, catalysts, risks (non-personalized)
- limitations: rate-limit/delay notes + disclaimers
- audit_status: APPROVED / PARTIAL (news-only)

## Flow summary (what happens, explicitly)
- Planner parses input and decides required modules.
- Research searches and scrapes 1 to 3 key sources; outputs drivers + citations.
- Quant fetches price series (with provider fallback), computes indicators/scenarios via safe_python_exec.
- Quant can also operate on planner-provided data without fetching market data.
- Auditor checks sanity, recency, citations, and compliance.
- If REJECTED: Planner re-runs only the required portion (e.g., re-fetch data, re-compute RSI, fetch more recent news) and re-audits (bounded retries).
- If APPROVED: Planner synthesizes the final brief.
- If providers are unavailable: return news-only with explicit limitations.

## Flask API (Mongo + FAISS)
The UI expects a backend with these endpoints:
- `GET /health` returns `{status:"ok"}`
- `GET /history` returns a list of messages
- `POST /chat` accepts `{message, threadId}` and returns `{reply, threadId}`
- `GET /trace?threadId=...` returns human-readable trace events

Run the API server:
```bash
uv run finance_insight_api --host 0.0.0.0 --port 5000
```

Or use the convenient startup script:
```bash
./run.sh
```

## UI Features

The Next.js frontend includes:
- **Real-time chat interface** for finance queries
- **Trace viewer** - Click "View trace" while thinking to see agent execution steps
- **Dark/light mode** toggle
- **Conversation history** with semantic search
- **Settings page** for API configuration

### Why Separate Frontend/Backend?

The frontend and backend are separate services because:

1. **Technology Independence**: Backend uses Python/CrewAI for AI agents; frontend uses Next.js/React for modern UI
2. **Scalability**: Can scale backend (compute-heavy) and frontend (serve static) independently
3. **Development**: Teams can work on UI and AI logic separately
4. **Deployment Flexibility**: 
   - Backend can run on GPU servers
   - Frontend can be deployed to CDN/edge networks
5. **API-First Design**: Backend serves as an API for multiple clients (web, mobile, CLI)

The `run.sh` script makes local development seamless by starting both together.

Mongo stores threads/messages; FAISS stores semantic memory and is fed into
`conversation_summary` for follow-ups.
