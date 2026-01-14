import argparse
import os

from dotenv import load_dotenv

from finance_insight_service.crew import FinanceInsightCrew


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Run the Finance Insight Quant Agent."
    )
    parser.add_argument(
        "--symbol",
        required=True,
        help="Ticker or symbol to analyze.",
    )
    parser.add_argument(
        "--interval",
        default="1day",
        help="Interval for OHLCV data (1day, 1week, 1month).",
    )
    parser.add_argument(
        "--outputsize",
        type=int,
        default=365,
        help="Number of data points to fetch.",
    )
    parser.add_argument(
        "--horizon-days",
        type=int,
        default=30,
        help="Scenario horizon in days.",
    )
    parser.add_argument(
        "--request",
        default="",
        help="Optional request text to guide which metrics to compute.",
    )
    parser.add_argument(
        "--provided-data",
        default="",
        help="Optional JSON string with data to analyze (overrides fetch).",
    )
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is missing. Set it in your environment or .env.")

    inputs = {
        "symbol": args.symbol.strip(),
        "interval": args.interval.strip(),
        "outputsize": args.outputsize,
        "horizon_days": args.horizon_days,
        "request": args.request.strip(),
        "provided_data": args.provided_data.strip(),
    }

    if not inputs["symbol"]:
        raise SystemExit("--symbol must be non-empty.")

    crew = FinanceInsightCrew().build_crew(["quant"])
    result = crew.kickoff(inputs=inputs)
    print(result)


if __name__ == "__main__":
    main()
