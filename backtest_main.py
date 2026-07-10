"""Run a point-in-time Morpheus backtest for one BIST symbol."""

from __future__ import annotations

import argparse
import json

from analysis.backtest import BacktestConfig, run_morpheus_backtest
from config import MARKET_INDEX_SYMBOL
from data.downloader import download_stock


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Next-bar, cost-aware long-only Morpheus backtest",
    )
    parser.add_argument("symbol", help="BIST symbol, for example THYAO")
    parser.add_argument("--period", default="5y", help="yfinance history period")
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--commission-bps", type=float, default=10.0)
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--allocation", type=float, default=0.95)
    parser.add_argument("--warmup-bars", type=int, default=220)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--include-equity-curve", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    symbol = args.symbol.upper().replace(".IS", "")
    index_symbol = MARKET_INDEX_SYMBOL.upper().replace(".IS", "")
    stock = download_stock(symbol, period=args.period, force=args.force_download)
    market = download_stock(index_symbol, period=args.period, force=args.force_download)
    if stock is None or stock.empty or market is None or market.empty:
        raise SystemExit("Stock or XU100 history could not be downloaded")

    config = BacktestConfig(
        initial_capital=args.capital,
        allocation=args.allocation,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        warmup_bars=args.warmup_bars,
    )
    result = run_morpheus_backtest(stock, market, config)
    print(
        json.dumps(
            result.as_dict(include_equity_curve=args.include_equity_curve),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
