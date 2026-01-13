import argparse
import os

from dotenv import load_dotenv

from finance_insight_service.crew import FinanceInsightResearchCrew


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Run the Finance Insight Research Agent with a search query."
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Search query (company, ticker, or topic).",
    )
    parser.add_argument(
        "--tickers",
        default="",
        help="Comma-separated tickers to include in the search context.",
    )
    parser.add_argument(
        "--sites",
        default="",
        help="Comma-separated domains to scope search (e.g., reuters.com,bloomberg.com).",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=10,
        help="Maximum number of articles to include.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Lookback window in days for news search.",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing. Set it in your environment or .env.")
    if not (os.getenv("SERPER_API_KEY") or os.getenv("SERPAPI_API_KEY")):
        raise SystemExit("Set SERPER_API_KEY or SERPAPI_API_KEY for news search.")

    tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    sites = [s.strip() for s in args.sites.split(",") if s.strip()]
    query = args.query.strip()

    query_parts = [query]
    if tickers:
        query_parts.append("(" + " OR ".join(tickers) + ")")
    if sites:
        query_parts.append("(" + " OR ".join(f"site:{site}" for site in sites) + ")")

    inputs = {
        "query": query,
        "tickers": ", ".join(tickers),
        "sites": ", ".join(sites),
        "max_articles": args.max_articles,
        "days": args.days,
        "search_query": " ".join(query_parts).strip(),
    }

    if not inputs["query"]:
        raise SystemExit("--query must be non-empty.")

    result = FinanceInsightResearchCrew().crew().kickoff(inputs=inputs)
    print(result)


if __name__ == "__main__":
    main()
