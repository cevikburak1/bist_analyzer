from __future__ import annotations

import argparse
import io
import logging
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysis.indicators import calculate_all_indicators
from analysis.silent_accumulation import DEFAULT_HORIZON, MIN_HORIZON, group_symbols, scan_symbol
from config import LOG_FILE, LOG_LEVEL, MARKET_INDEX_SYMBOL
from data.downloader import download_stock, load_symbols
from reports.silent_accumulation_snapshot import save_silent_accumulation_snapshot


def setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8")],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smart Money Silent Accumulation Scanner")
    parser.add_argument("--symbols", nargs="*", default=None, help="Sadece bu sembolleri tara")
    parser.add_argument("--group", type=int, default=None, help="Sadece belirli UI grubunu tara")
    def horizon_value(raw: str) -> int:
        value = int(raw)
        if value < MIN_HORIZON:
            raise argparse.ArgumentTypeError(f"horizon en az {MIN_HORIZON} olmalı")
        return value

    parser.add_argument("--horizon", type=horizon_value, default=DEFAULT_HORIZON, help="Long-term tarama penceresi")
    parser.add_argument("--force", action="store_true", help="Cache'i yoksay")
    return parser.parse_args()


def main() -> int:
    setup_logging()
    logger = logging.getLogger("silent_accumulation")
    args = parse_args()
    symbols = [s.upper().replace(".IS", "") for s in (args.symbols or load_symbols())]
    groups = group_symbols(symbols)
    if args.group is not None:
        symbols = groups.get(args.group, [])

    index_symbol = MARKET_INDEX_SYMBOL.replace(".IS", "")
    index_df = download_stock(index_symbol, force=args.force)
    if index_df is None or index_df.empty:
        logger.error("XU100 verisi alınamadı")
        return 1
    index_df = calculate_all_indicators(index_df)

    results = []
    for symbol in symbols:
        try:
            df = download_stock(symbol, force=args.force)
            if df is None or df.empty:
                continue
            df = calculate_all_indicators(df)
            group_no = next((group for group, members in groups.items() if symbol in members), 0)
            result = scan_symbol(symbol, df, index_df, group=group_no, horizon=args.horizon)
            if result is not None:
                results.append(result)
        except Exception as exc:
            logger.exception("Silent accumulation hata [%s]: %s", symbol, exc)

    save_silent_accumulation_snapshot(results, requested_symbols=len(symbols), groups=groups)
    return 0


if __name__ == "__main__":
    sys.exit(main())
