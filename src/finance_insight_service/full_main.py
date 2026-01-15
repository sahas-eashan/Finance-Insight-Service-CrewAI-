import argparse
import json
import os
from typing import Any

from dotenv import load_dotenv

from finance_insight_service.crew import FinanceInsightCrew


def _extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    for attr in ("raw", "output", "json"):
        if hasattr(value, attr):
            try:
                return getattr(value, attr)
            except Exception:
                continue
    return str(value)


def _parse_json(text: Any) -> Any:
    raw_text = _extract_text(text)
    stripped = raw_text.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return {"raw_output": stripped}


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(value).strip()]


def _build_csv_string(value: Any) -> str:
    return ", ".join(_normalize_list(value))


def _build_search_query(query: str, tickers: Any, sites: Any) -> str:
    parts = [query.strip()] if query.strip() else []
    tickers_list = _normalize_list(tickers)
    if tickers_list:
        parts.append("(" + " OR ".join(tickers_list) + ")")
    sites_list = _normalize_list(sites)
    if sites_list:
        parts.append("(" + " OR ".join(f"site:{s}" for s in sites_list) + ")")
    return " ".join(parts).strip()


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run the full 4-agent workflow.")
    parser.add_argument("--request", required=True, help="User request text.")
    parser.add_argument(
        "--conversation-summary",
        default="",
        help="Optional short summary of recent conversation.",
    )
    parser.add_argument(
        "--sources-requested",
        action="store_true",
        help="Include sources in final response when requested by user.",
    )
    parser.add_argument("--symbol", default="", help="Default symbol for quant.")
    parser.add_argument("--interval", default="1day", help="Default interval for quant.")
    parser.add_argument("--outputsize", type=int, default=260)
    parser.add_argument("--horizon-days", type=int, default=30)
    parser.add_argument("--provided-data", default="", help="Default JSON data for quant.")
    parser.add_argument("--query", default="", help="Default query for research.")
    parser.add_argument("--tickers", default="", help="Default tickers for research.")
    parser.add_argument("--sites", default="", help="Default sites for research.")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--max-articles", type=int, default=8)
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing. Set it in your environment or .env.")

    runtime_defaults = {
        "user_request": args.request,
        "symbol": args.symbol,
        "interval": args.interval,
        "outputsize": args.outputsize,
        "horizon_days": args.horizon_days,
        "provided_data": args.provided_data,
        "query": args.query or args.request,
        "tickers": args.tickers,
        "sites": args.sites,
        "days": args.days,
        "max_articles": args.max_articles,
    }

    search_query = _build_search_query(
        args.query or args.request, args.tickers, args.sites
    )
    inputs = {
        "user_request": args.request,
        "conversation_summary": args.conversation_summary,
        "runtime_defaults": json.dumps(runtime_defaults),
        "sources_requested": str(args.sources_requested),
        "query": args.query or args.request,
        "tickers": args.tickers,
        "sites": args.sites,
        "days": args.days,
        "max_articles": args.max_articles,
        "search_query": search_query,
        "symbol": args.symbol,
        "interval": args.interval,
        "outputsize": args.outputsize,
        "horizon_days": args.horizon_days,
        "request": args.request,
        "provided_data": args.provided_data,
    }

    crew = FinanceInsightCrew().build_crew()
    result = crew.kickoff(inputs=inputs)
    if result is None:
        return
    text = _extract_text(result)
    parsed = _parse_json(text)
    if isinstance(parsed, dict) and parsed.get("final_response"):
        print(parsed["final_response"])
    else:
        print(text)


if __name__ == "__main__":
    main()
