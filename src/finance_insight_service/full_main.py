import argparse
import ast
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
        pass
    for start in (stripped.find("{"), stripped.find("[")):
        if start == -1:
            continue
        try:
            return json.loads(stripped[start:])
        except json.JSONDecodeError:
            continue
    try:
        return ast.literal_eval(stripped)
    except (ValueError, SyntaxError):
        return {"raw_output": stripped}


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1"}
    return bool(value)


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


def _run_task(task_name: str, inputs: dict) -> str:
    crew = FinanceInsightCrew().build_crew([task_name])
    result = crew.kickoff(inputs=inputs)
    return _extract_text(result)


def _normalize_research_request(request: dict, defaults: dict) -> dict:
    query = request.get("query") or defaults.get("query") or ""
    tickers_raw = request.get("tickers") or defaults.get("tickers") or ""
    sites_raw = request.get("sites") or defaults.get("sites") or ""
    user_request = request.get("user_request") or defaults.get("user_request") or ""
    days = int(request.get("days") or defaults.get("days") or 7)
    max_articles = int(request.get("max_articles") or defaults.get("max_articles") or 8)
    search_query = request.get("search_query") or _build_search_query(
        query, tickers_raw, sites_raw
    )
    return {
        "user_request": user_request,
        "query": query,
        "tickers": _build_csv_string(tickers_raw),
        "sites": _build_csv_string(sites_raw),
        "days": days,
        "max_articles": max_articles,
        "search_query": search_query,
    }


def _normalize_quant_request(request: dict, defaults: dict, user_request: str) -> dict:
    symbol_raw = request.get("symbol") or defaults.get("symbol") or ""
    symbols = _normalize_list(symbol_raw)
    symbol = symbols[0] if symbols else ""

    req_text = request.get("request") or user_request
    if symbols and len(symbols) > 1:
        req_text = (
            f"{req_text} (multiple symbols requested; analyzing {symbol} only)"
        )

    return {
        "symbol": symbol,
        "interval": request.get("interval") or defaults.get("interval") or "1day",
        "outputsize": int(request.get("outputsize") or defaults.get("outputsize") or 260),
        "horizon_days": int(
            request.get("horizon_days") or defaults.get("horizon_days") or 30
        ),
        "request": req_text,
        "provided_data": request.get("provided_data") or defaults.get("provided_data") or "",
    }


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

    planner_input = {
        "user_request": args.request,
        "conversation_summary": args.conversation_summary,
        "runtime_defaults": json.dumps(runtime_defaults),
        "research_output": "",
        "quant_output": "",
        "audit_output": "",
        "sources_requested": str(args.sources_requested),
    }

    planner_raw = _run_task("planner", planner_input)
    planner_output = _parse_json(planner_raw)

    plan = planner_output.get("plan", {})
    use_research = _as_bool(plan.get("use_research"))
    use_quant = _as_bool(plan.get("use_quant"))
    use_audit = _as_bool(plan.get("use_audit", True))

    research_output = ""
    quant_output = ""

    if use_research:
        research_req = planner_output.get("research_request") or {}
        research_inputs = _normalize_research_request(research_req, runtime_defaults)
        research_output = _run_task("research", research_inputs)

    if use_quant:
        quant_req = planner_output.get("quant_request") or {}
        quant_inputs = _normalize_quant_request(quant_req, runtime_defaults, args.request)
        if not quant_inputs["symbol"] and not quant_inputs["provided_data"]:
            quant_output = json.dumps(
                {
                    "as_of": {},
                    "snapshot": {"data_points": 0},
                    "limitations": ["Quant request missing symbol or provided_data."],
                },
                ensure_ascii=True,
            )
        else:
            quant_output = _run_task("quant", quant_inputs)

    audit_output = ""
    if (research_output or quant_output):
        use_audit = True

    max_retries = 2
    for _ in range(max_retries + 1):
        if use_audit and (research_output or quant_output):
            audit_input = {
                "user_request": args.request,
                "research_output": research_output,
                "quant_output": quant_output,
                "draft_response": "",
            }
            audit_raw = _run_task("audit", audit_input)
            audit_output = _parse_json(audit_raw)
        else:
            audit_output = ""

        audit_status = (
            (audit_output.get("audit_status") or "").upper()
            if isinstance(audit_output, dict)
            else ""
        )
        required_reruns = (
            audit_output.get("required_reruns") or []
            if isinstance(audit_output, dict)
            else []
        )

        if audit_status != "REJECTED" or not required_reruns:
            break

        planner_repair_input = {
            "user_request": args.request,
            "conversation_summary": args.conversation_summary,
            "runtime_defaults": json.dumps(runtime_defaults),
            "research_output": research_output,
            "quant_output": quant_output,
            "audit_output": json.dumps(audit_output),
            "sources_requested": str(args.sources_requested),
        }
        planner_raw = _run_task("planner", planner_repair_input)
        planner_output = _parse_json(planner_raw)
        plan = planner_output.get("plan", {}) if isinstance(planner_output, dict) else {}
        use_research = _as_bool(plan.get("use_research"))
        use_quant = _as_bool(plan.get("use_quant"))
        use_audit = True

        if "research" in required_reruns and use_research:
            research_req = planner_output.get("research_request") or {}
            research_inputs = _normalize_research_request(research_req, runtime_defaults)
            research_output = _run_task("research", research_inputs)
        if "quant" in required_reruns and use_quant:
            quant_req = planner_output.get("quant_request") or {}
            quant_inputs = _normalize_quant_request(
                quant_req, runtime_defaults, args.request
            )
            quant_output = _run_task("quant", quant_inputs)

    final_planner_input = {
        "user_request": args.request,
        "conversation_summary": args.conversation_summary,
        "runtime_defaults": json.dumps(runtime_defaults),
        "research_output": research_output,
        "quant_output": quant_output,
        "audit_output": json.dumps(audit_output) if audit_output else "",
        "sources_requested": str(args.sources_requested),
    }

    final_raw = _run_task("planner", final_planner_input)
    final_output = _parse_json(final_raw)
    final_response = final_output.get("final_response") if isinstance(final_output, dict) else None

    if not final_response:
        print(final_raw)
        return

    print(final_response)


if __name__ == "__main__":
    main()
