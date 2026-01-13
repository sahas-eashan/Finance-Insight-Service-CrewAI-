# Finance Insight Service - CrewAI

## Overview
Finance Insight Service uses a plan -> execute -> audit -> repair cycle to deliver finance news, a market snapshot, and bounded scenarios. It prioritizes accuracy over speed and avoids "LLM does math" errors by routing all calculations through a sandboxed Python execution tool.

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
- ScrapeWebsiteTool (CrewAI) to fetch full article content (not just snippets):
  - https://docs.crewai.com/en/tools/search-research/scrapewebsitetool

### 3) Quant Agent (market data + indicators + scenarios via Python)
Responsibilities:
- Fetch OHLCV time series.
- Compute indicators deterministically (returns, volatility, RSI, MAs, drawdown, etc.).
- Generate bounded scenarios (base/bull/bear) from computed stats and explicit assumptions.

Tools (2):
- market_data_fetch (custom tool with provider fallback)
  - Provider order (recommended): Twelve Data -> Stooq else skip.
- safe_python_exec (custom tool): executes agent-written Python, returns either SUCCESS with final_output or CODE ERROR for self-repair.

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
- Auditor checks sanity, recency, citations, and compliance.
- If REJECTED: Planner re-runs only the required portion (e.g., re-fetch data, re-compute RSI, fetch more recent news) and re-audits (bounded retries).
- If APPROVED: Planner synthesizes the final brief.
- If providers are unavailable: return news-only with explicit limitations.
