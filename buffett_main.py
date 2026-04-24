"""
Buffett (Temel Analiz) Hattı CLI

Kullanım:
    python buffett_main.py                       # tüm semboller (cache aktif)
    python buffett_main.py --symbols AKBNK GARAN # sadece belirtilen semboller
    python buffett_main.py --force               # cache atla, yeniden indir
    python buffett_main.py --quiet               # konsol çıktısı kapalı

Üretilen dosyalar:
    output/web/buffett/latest.json
    output/web/buffett/stocks/{SYMBOL}.json
    output/web/buffett/status.json
"""

from __future__ import annotations

import argparse
import io
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from analysis.buffett_score import calculate_buffett_score
from analysis.buffett_signal import build_buffett_signal
from analysis.intrinsic_value import DCFAssumptions, calculate_intrinsic_value
from config import LOG_FILE, LOG_LEVEL
from fundamentals.downloader import download_fundamentals, load_symbols
from reports.buffett_snapshot import (
    BuffettStockResult,
    acquire_buffett_lock,
    clear_buffett_lock,
    save_buffett_snapshot,
    write_buffett_status,
)


console = Console(force_terminal=True)


def setup_logging(quiet: bool = False) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
    if not quiet:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Buffett tarzı temel analiz pipeline")
    p.add_argument("--symbols", nargs="*", help="Sadece bu sembolleri işle")
    p.add_argument("--force", action="store_true", help="Cache'i atla, yeniden indir")
    p.add_argument("--quiet", action="store_true", help="Konsol çıktısını kapat")
    p.add_argument("--discount", type=float, default=0.20,
                   help="DCF iskonto oranı (varsayılan 0.20)")
    p.add_argument("--terminal-growth", type=float, default=0.03,
                   help="Terminal büyüme oranı (varsayılan 0.03)")
    return p.parse_args()


def _print_summary_table(results: list[BuffettStockResult]) -> None:
    if not results:
        return
    table = Table(title="Buffett Skor Özeti")
    table.add_column("Sembol", style="cyan", no_wrap=True)
    table.add_column("Sektör", style="dim")
    table.add_column("Skor", justify="right")
    table.add_column("MoS", justify="right")
    table.add_column("Etiket")

    sorted_results = sorted(
        results,
        key=lambda r: (
            r.signal.label_key != "HARIKA_IS_UCUZ",
            -r.score.total_score,
        ),
    )
    for r in sorted_results[:30]:
        mos = r.signal.margin_of_safety
        mos_str = f"{mos*100:+.1f}%" if mos is not None else "-"
        table.add_row(
            r.bundle.symbol,
            r.bundle.sector.get("label", "-"),
            f"{r.score.total_score:.1f}",
            mos_str,
            r.signal.label,
        )
    console.print(table)


def main() -> int:
    args = parse_args()
    setup_logging(quiet=args.quiet)
    logger = logging.getLogger("buffett")

    symbols = args.symbols if args.symbols else load_symbols()
    symbols = [s.upper().replace(".IS", "") for s in symbols]

    run_id = str(uuid4())
    started_at = datetime.now().isoformat()

    if not acquire_buffett_lock(run_id, len(symbols)):
        console.print("[yellow]Buffett analizi zaten çalışıyor. Çıkılıyor.[/yellow]")
        return 1

    try:
        write_buffett_status(
            state="running",
            run_id=run_id,
            requested_symbols=len(symbols),
            started_at=started_at,
        )

        assumptions = DCFAssumptions(
            discount_rate=args.discount,
            terminal_growth=args.terminal_growth,
        )

        results: list[BuffettStockResult] = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.completed]{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            console=console,
            disable=args.quiet,
        ) as progress:
            task = progress.add_task("Buffett analizi", total=len(symbols))
            for sym in symbols:
                progress.update(task, description=f"İşleniyor: {sym}")
                try:
                    bundle = download_fundamentals(sym, force=args.force)
                    if bundle is None:
                        progress.advance(task)
                        continue

                    current_price = (
                        bundle.info.get("currentPrice")
                        or bundle.info.get("previousClose")
                    )
                    intrinsic = calculate_intrinsic_value(
                        bundle, current_price=current_price, assumptions=assumptions,
                    )
                    score = calculate_buffett_score(
                        bundle,
                        intrinsic_value_per_share=intrinsic.intrinsic_value_per_share,
                        current_price=current_price,
                    )
                    signal = build_buffett_signal(bundle, score, intrinsic)

                    results.append(BuffettStockResult(
                        bundle=bundle, score=score, intrinsic=intrinsic, signal=signal,
                    ))
                except Exception as e:
                    logger.exception("Buffett pipeline hata [%s]: %s", sym, e)
                progress.advance(task)

        save_buffett_snapshot(results)
        finished_at = datetime.now().isoformat()
        write_buffett_status(
            state="idle",
            run_id=run_id,
            requested_symbols=len(symbols),
            successful_symbols=len(results),
            started_at=started_at,
            finished_at=finished_at,
        )

        if not args.quiet:
            _print_summary_table(results)
            console.print(
                f"[green]Buffett snapshot kaydedildi:[/green] "
                f"{len(results)}/{len(symbols)} sembol"
            )
        return 0

    except Exception as e:
        logger.exception("Buffett ana hata: %s", e)
        write_buffett_status(
            state="error",
            run_id=run_id,
            requested_symbols=len(symbols),
            started_at=started_at,
            finished_at=datetime.now().isoformat(),
            error=str(e),
        )
        return 2

    finally:
        clear_buffett_lock()


if __name__ == "__main__":
    sys.exit(main())
