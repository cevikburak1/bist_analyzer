"""
Optional TradingView public scanner snapshot client.

TradingView does not expose this as a stable public historical API. We only use
it as a best-effort latest snapshot comparison source; the analysis still relies
on the existing historical OHLCV pipeline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

TRADINGVIEW_SCAN_URL = "https://scanner.tradingview.com/turkey/scan"
TRADINGVIEW_COLUMNS = ["name", "close", "high", "low", "volume", "change"]


@dataclass
class TradingViewSnapshot:
    symbol: str
    close: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    change_pct: float | None = None
    source: str = "tradingview_scanner"
    status: str = "unverified"
    price_delta_pct: float | None = None
    volume_delta_pct: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "close": self.close,
            "high": self.high,
            "low": self.low,
            "volume": self.volume,
            "change_pct": self.change_pct,
            "source": self.source,
            "status": self.status,
            "price_delta_pct": self.price_delta_pct,
            "volume_delta_pct": self.volume_delta_pct,
        }


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _delta_pct(reference: float | None, candidate: float | None) -> float | None:
    if reference is None or candidate is None or reference == 0:
        return None
    return round(((candidate - reference) / reference) * 100, 2)


def _request_scan(symbols: list[str], timeout: float) -> dict[str, Any]:
    payload = {
        "markets": ["turkey"],
        "symbols": {
            "tickers": [f"BIST:{symbol.upper().replace('.IS', '')}" for symbol in symbols],
            "query": {"types": []},
        },
        "options": {"lang": "tr"},
        "columns": TRADINGVIEW_COLUMNS,
        "range": [0, len(symbols)],
    }
    request = Request(
        TRADINGVIEW_SCAN_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Origin": "https://tr.tradingview.com",
            "Referer": "https://tr.tradingview.com/",
            "User-Agent": "Mozilla/5.0 bist-analyzer",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_tradingview_snapshots(
    symbols: list[str],
    *,
    latest_indicators: dict[str, dict] | None = None,
    timeout: float = 8.0,
) -> dict[str, TradingViewSnapshot]:
    """Fetch latest TradingView screener snapshots for BIST symbols.

    Returns an empty dict on any endpoint failure so the main analysis remains
    deterministic with the existing yfinance-backed history.
    """
    normalized_symbols = [symbol.upper().replace(".IS", "") for symbol in symbols]
    if not normalized_symbols:
        return {}

    try:
        raw = _request_scan(normalized_symbols, timeout)
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.warning("TradingView snapshot alınamadı: %s", exc)
        return {}

    snapshots: dict[str, TradingViewSnapshot] = {}
    for row in raw.get("data", []):
        ticker = str(row.get("s", "")).replace("BIST:", "").upper()
        values = row.get("d", [])
        by_column = dict(zip(TRADINGVIEW_COLUMNS, values))
        snapshot = TradingViewSnapshot(
            symbol=ticker,
            close=_to_float(by_column.get("close")),
            high=_to_float(by_column.get("high")),
            low=_to_float(by_column.get("low")),
            volume=_to_float(by_column.get("volume")),
            change_pct=_to_float(by_column.get("change")),
        )
        if latest_indicators and ticker in latest_indicators:
            indicators = latest_indicators[ticker]
            snapshot.price_delta_pct = _delta_pct(_to_float(indicators.get("close")), snapshot.close)
            snapshot.volume_delta_pct = _delta_pct(_to_float(indicators.get("volume")), snapshot.volume)
            if snapshot.price_delta_pct is None:
                snapshot.status = "unverified"
                snapshots[ticker] = snapshot
                continue
            price_ok = abs(snapshot.price_delta_pct) <= 3
            volume_ok = snapshot.volume_delta_pct is None or abs(snapshot.volume_delta_pct) <= 35
            snapshot.status = "verified" if price_ok and volume_ok else "diverged"
        snapshots[ticker] = snapshot

    return snapshots
