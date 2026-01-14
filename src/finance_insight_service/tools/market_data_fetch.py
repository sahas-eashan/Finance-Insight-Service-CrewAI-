import csv
import json
import os
from datetime import datetime
from io import StringIO
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field

from crewai.tools import BaseTool


class MarketDataFetchArgs(BaseModel):
    symbol: str = Field(..., description="Ticker or symbol to fetch.")
    interval: str = Field("1day", description="Interval (1day, 1week, 1month).")
    outputsize: int = Field(365, description="Number of data points to return.")


class MarketDataFetchTool(BaseTool):
    name: str = "market_data_fetch"
    description: str = (
        "Fetches OHLCV time series with provider fallback. "
        "Uses Twelve Data when TWELVE_DATA_API_KEY is set; otherwise falls back to Stooq."
    )
    args_schema: type[BaseModel] = MarketDataFetchArgs

    def _run(self, symbol: str, interval: str = "1day", outputsize: int = 365) -> str:
        symbol = (symbol or "").strip()
        if not symbol:
            return _error_payload("symbol is required")

        interval = (interval or "1day").strip().lower()
        outputsize = max(10, min(int(outputsize), 2000))

        if os.getenv("TWELVE_DATA_API_KEY"):
            payload = _fetch_twelve_data(symbol, interval, outputsize)
            if not payload.get("error"):
                return json.dumps(payload, ensure_ascii=True)

        payload = _fetch_stooq(symbol, interval, outputsize)
        return json.dumps(payload, ensure_ascii=True)


def _error_payload(message: str, provider: str = "") -> str:
    return json.dumps(
        {
            "provider": provider,
            "symbol": "",
            "interval": "",
            "fetched_at": datetime.utcnow().isoformat() + "Z",
            "data": [],
            "error": message,
        },
        ensure_ascii=True,
    )


def _fetch_twelve_data(symbol: str, interval: str, outputsize: int) -> dict[str, Any]:
    api_key = os.getenv("TWELVE_DATA_API_KEY")
    if not api_key:
        return {"error": "TWELVE_DATA_API_KEY missing"}

    query = urlencode(
        {
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": api_key,
            "format": "JSON",
        }
    )
    url = f"https://api.twelvedata.com/time_series?{query}"
    request = Request(url, headers={"User-Agent": "FinanceInsightBot/1.0"})

    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return _error_dict("twelve_data", symbol, interval, f"request failed: {exc}")

    if "values" not in payload:
        return _error_dict(
            "twelve_data",
            symbol,
            interval,
            payload.get("message", "unexpected response"),
        )

    values = payload["values"]
    data = []
    for row in values:
        try:
            data.append(
                {
                    "date": row["datetime"],
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row.get("volume") or 0),
                }
            )
        except (KeyError, ValueError):
            continue

    data.reverse()
    return {
        "provider": "twelve_data",
        "symbol": symbol,
        "interval": interval,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "data": data[-outputsize:],
        "error": "",
    }


def _fetch_stooq(symbol: str, interval: str, outputsize: int) -> dict[str, Any]:
    interval_map = {"1day": "d", "1week": "w", "1month": "m"}
    stooq_interval = interval_map.get(interval, "d")

    stooq_symbol = symbol.strip().lower()
    if "." not in stooq_symbol:
        stooq_symbol = f"{stooq_symbol}.us"

    url = f"https://stooq.com/q/d/l/?s={stooq_symbol}&i={stooq_interval}"
    request = Request(url, headers={"User-Agent": "FinanceInsightBot/1.0"})

    try:
        with urlopen(request, timeout=15) as response:
            payload = response.read().decode("utf-8")
    except Exception as exc:
        return _error_dict("stooq", symbol, interval, f"request failed: {exc}")

    reader = csv.DictReader(StringIO(payload))
    data = []
    for row in reader:
        if not row.get("Date"):
            continue
        try:
            data.append(
                {
                    "date": row["Date"],
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row.get("Volume") or 0),
                }
            )
        except (KeyError, ValueError):
            continue

    if not data:
        return _error_dict("stooq", symbol, interval, "no data returned")

    return {
        "provider": "stooq",
        "symbol": symbol,
        "interval": interval,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "data": data[-outputsize:],
        "error": "",
    }


def _error_dict(provider: str, symbol: str, interval: str, message: str) -> dict[str, Any]:
    return {
        "provider": provider,
        "symbol": symbol,
        "interval": interval,
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "data": [],
        "error": message,
    }
