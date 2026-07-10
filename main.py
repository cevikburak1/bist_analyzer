"""
BIST Hisse Senedi Analiz ve Sinyal Sistemi

Ana çalıştırma dosyası. Tüm modülleri orkestre eder:
1. Piyasa rejimi tespit
2. Veri indirme
3. İndikatör hesaplama
4. Skorlama
5. Sinyal üretimi
6. Raporlama (terminal, PNG, HTML, CSV/JSON)
"""

import argparse
import io
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# Windows terminal encoding düzeltmesi
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

# Proje kök dizinini sys.path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    OUTPUT_DIR,
    LOG_FILE,
    LOG_LEVEL,
    MARKET_INDEX_SYMBOL,
    REPORT_DATE_FORMAT,
)
from data.downloader import load_symbols, download_stock, download_intraday_stock
from data.tradingview import fetch_tradingview_snapshots
from analysis.indicators import (
    calculate_all_indicators,
    get_latest_indicators,
    calculate_beta,
)
from analysis.market_regime import detect_market_regime, MarketRegime
from analysis.scoring import calculate_score
from analysis.signals import generate_signal, Signal
from reports.terminal_report import render_terminal_report
from reports.chart_report import generate_table_image, generate_chart_image
from reports.html_report import generate_html_report
from reports.web_snapshot import (
    acquire_analysis_lock,
    clear_analysis_lock,
    save_web_snapshot,
    write_analysis_status,
)

console = Console(force_terminal=True)


def setup_logging(quiet: bool = False) -> None:
    """Loglama ayarları"""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
    if not quiet:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def parse_args() -> argparse.Namespace:
    """CLI argümanlarını işler."""
    parser = argparse.ArgumentParser(
        description="BIST Hisse Senedi Analiz ve Sinyal Sistemi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Kullanım örnekleri:
  python main.py                        # Tüm BIST hisselerini analiz et
  python main.py --symbols THYAO ASELS  # Belirli hisseler
  python main.py --quiet                # Sessiz mod (sadece dosya çıktısı)
  python main.py --no-html              # HTML raporu oluşturma
        """,
    )
    parser.add_argument(
        "--symbols", nargs="+", type=str, default=None,
        help="Analiz edilecek hisse sembolleri (boşlukla ayrılmış)",
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Sessiz mod: terminal çıktısı yok, sadece dosyalar oluşturulur",
    )
    parser.add_argument(
        "--no-charts", action="store_true",
        help="PNG grafik raporu oluşturma",
    )
    parser.add_argument(
        "--no-html", action="store_true",
        help="HTML interaktif rapor oluşturma",
    )
    parser.add_argument(
        "--force-download", action="store_true",
        help="Cache'i yoksay, tüm verileri yeniden indir",
    )
    parser.add_argument(
        "--dashboard", action="store_true",
        help="Analiz sonrası React dashboard'u başlatır",
    )
    return parser.parse_args()


def save_csv_json(signals: list[Signal], regime: MarketRegime) -> tuple[Path, Path]:
    """Sinyalleri CSV ve JSON formatında kaydeder."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime(REPORT_DATE_FORMAT)

    # CSV
    rows = []
    for sig in signals:
        tf = sig.timeframes
        tgt = sig.targets
        fib = sig.fibonacci
        ew = sig.elliott_wave
        comm = sig.commentary

        from analysis.candle_patterns import patterns_summary as _ps
        rows.append({
            "symbol": sig.symbol,
            "price": round(sig.price, 2),
            "score": sig.score,
            "summary": sig.summary,
            "signal_daily": sig.signal,
            "action": sig.action or sig.signal,
            "signal_weekly": tf.weekly if tf else "",
            "signal_monthly": tf.monthly if tf else "",
            "signal_yearly": tf.yearly if tf else "",
            "rsi": sig.rsi,
            "trend": sig.trend,
            "volume_status": sig.volume_status,
            "entry": sig.entry,
            "stop_loss": sig.stop_loss,
            "target_short": tgt.short_target if tgt else 0,
            "target_medium": tgt.medium_target if tgt else 0,
            "target_long": tgt.long_target if tgt else 0,
            "rr_short": tgt.short_rr if tgt else 0,
            "rr_medium": tgt.medium_rr if tgt else 0,
            "rr_long": tgt.long_rr if tgt else 0,
            "risk_pct": sig.risk_pct,
            "fib_support": fib.nearest_support if fib else 0,
            "fib_resistance": fib.nearest_resistance if fib else 0,
            "fib_zone": fib.current_zone if fib else "",
            "candle_patterns": _ps(sig.candle_patterns) if sig.candle_patterns else "",
            "candle_bias": sig.candle_bias,
            "elliott_wave": ew.current_wave if ew else "",
            "elliott_phase": ew.phase if ew else "",
            "elliott_confidence": ew.confidence if ew else "",
            "commentary_summary": comm.summary if comm else "",
            "reason": sig.reason,
            "score_trend": sig.score_breakdown.trend,
            "score_momentum": sig.score_breakdown.momentum,
            "score_volume": sig.score_breakdown.volume,
            "score_price_position": sig.score_breakdown.price_position,
            "score_squeeze_breakout": sig.score_breakdown.squeeze_breakout,
            "wr_pct": sig.score_breakdown.wr_pct,
            "adx": sig.score_breakdown.adx,
            "v_kat": sig.score_breakdown.v_kat,
            "dzl_ok": sig.score_breakdown.dzl_ok,
            "sqz_ok": sig.score_breakdown.sqz_ok,
            "ema_distance_pct": sig.score_breakdown.ema_distance_pct,
            "overextended": sig.score_breakdown.overextended,
        })

    df = pd.DataFrame(rows)
    csv_path = OUTPUT_DIR / f"signals_{date_str}.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    # JSON
    json_data = {
        "date": datetime.now().isoformat(),
        "market_regime": {
            "regime": regime.regime,
            "label": regime.label,
            "index_price": regime.index_price,
            "sma_short": regime.sma_short,
            "sma_long": regime.sma_long,
            "performance_20d": regime.performance_20d,
        },
        "summary": {
            "total": len(signals),
            "buy": sum(1 for s in signals if s.signal == "AL"),
            "sell": sum(1 for s in signals if s.signal == "SAT"),
            "hold": sum(1 for s in signals if s.signal == "BEKLE"),
        },
        "signals": rows,
    }
    json_path = OUTPUT_DIR / f"signals_{date_str}.json"
    json_path.write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return csv_path, json_path


def resolve_symbols(args: argparse.Namespace) -> list[str]:
    if args.symbols:
        return [s.upper().replace(".IS", "") for s in args.symbols]
    return load_symbols()


def run_pipeline(
    args: argparse.Namespace,
    logger: logging.Logger,
    symbols: list[str],
) -> tuple[list[Signal], MarketRegime, dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    if not args.quiet:
        console.print("\n[bold cyan]━━━ BIST Hisse Senedi Analiz Sistemi ━━━[/bold cyan]\n")

    # ── 1. Piyasa Rejimi Tespiti ─────────────────────────────────────
    if not args.quiet:
        console.print("[cyan]▸ Piyasa rejimi tespit ediliyor...[/cyan]")

    index_symbol = MARKET_INDEX_SYMBOL.replace(".IS", "")
    index_df = download_stock(index_symbol)

    if index_df is None or index_df.empty:
        console.print("[red]HATA: XU100 endeks verisi çekilemedi![/red]")
        logger.error("XU100 endeks verisi çekilemedi, çıkılıyor")
        sys.exit(1)

    index_df = calculate_all_indicators(index_df)
    regime = detect_market_regime(index_df)

    if not args.quiet:
        regime_icon = {"YUKSELIS": "🟢", "DUSUS": "🔴", "YATAY": "🟡"}.get(regime.regime, "⚪")
        console.print(f"  {regime_icon} {regime.label}")

    if not args.quiet:
        console.print(f"\n[cyan]▸ {len(symbols)} hisse analiz edilecek[/cyan]")

    # ── 3. Veri İndirme ─────────────────────────────────────────────
    stock_data_raw: dict[str, pd.DataFrame] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        disable=args.quiet,
    ) as progress:
        task = progress.add_task("Veriler indiriliyor", total=len(symbols))

        for symbol in symbols:
            df = download_stock(symbol, force=args.force_download)
            if df is not None and not df.empty:
                stock_data_raw[symbol] = df
            progress.update(task, advance=1, description=f"[cyan]{symbol}[/cyan]")

    if not args.quiet:
        console.print(f"  ✓ {len(stock_data_raw)}/{len(symbols)} hisse verisi alındı")

    if not stock_data_raw:
        console.print("[red]HATA: Hiçbir hisse verisi alınamadı![/red]")
        sys.exit(1)

    # ── 3b. Intraday Veri İndirme (AMD Model) ─────────────────────────
    if not args.quiet:
        console.print("\n[cyan]▸ AMD intraday verileri indiriliyor...[/cyan]")

    stock_intraday_raw: dict[str, pd.DataFrame] = {}
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
        disable=args.quiet,
    ) as progress:
        task = progress.add_task("Intraday veriler indiriliyor", total=len(stock_data_raw))
        for symbol in stock_data_raw:
            intraday_df = download_intraday_stock(symbol, force=args.force_download)
            if intraday_df is not None and not intraday_df.empty:
                stock_intraday_raw[symbol] = intraday_df
            progress.update(task, advance=1, description=f"[cyan]{symbol} intraday[/cyan]")

    if not args.quiet:
        console.print(f"  ✓ {len(stock_intraday_raw)}/{len(stock_data_raw)} hisse için intraday veri alındı")

    # ── 4. İndikatör Hesaplama ───────────────────────────────────────
    if not args.quiet:
        console.print("\n[cyan]▸ Teknik göstergeler hesaplanıyor...[/cyan]")

    stock_data: dict[str, pd.DataFrame] = {}
    stock_intraday: dict[str, pd.DataFrame] = {}
    all_indicators: dict[str, dict] = {}

    for symbol, df in stock_data_raw.items():
        try:
            df_ind = calculate_all_indicators(df)
            stock_data[symbol] = df_ind
            indicators = get_latest_indicators(df_ind)
            indicators["data_as_of"] = pd.Timestamp(df_ind.index[-1]).isoformat()

            # Beta hesapla
            beta = calculate_beta(df["close"], index_df["close"])
            indicators["beta"] = beta

            all_indicators[symbol] = indicators
        except Exception as e:
            logger.error("İndikatör hatası [%s]: %s", symbol, str(e))
            continue

    for symbol, df in stock_intraday_raw.items():
        try:
            stock_intraday[symbol] = calculate_all_indicators(df)
        except Exception as e:
            logger.warning("Intraday indikatör hatası [%s]: %s", symbol, str(e))

    if not args.quiet:
        console.print(f"  ✓ {len(all_indicators)} hisse için göstergeler hesaplandı")

    tv_snapshots = fetch_tradingview_snapshots(
        list(all_indicators.keys()),
        latest_indicators=all_indicators,
    )
    for symbol, snapshot in tv_snapshots.items():
        if symbol in all_indicators:
            all_indicators[symbol]["tradingview_snapshot"] = snapshot.as_dict()
    if tv_snapshots and not args.quiet:
        verified_count = sum(1 for item in tv_snapshots.values() if item.status == "verified")
        console.print(
            f"  ✓ TradingView snapshot doğrulandı: {verified_count}/{len(tv_snapshots)}"
        )

    # ── 5. Skorlama ──────────────────────────────────────────────────
    if not args.quiet:
        console.print("\n[cyan]▸ Skorlar hesaplanıyor...[/cyan]")

    all_scores = {}
    for symbol, indicators in all_indicators.items():
        try:
            score = calculate_score(indicators, regime, stock_data.get(symbol))
            all_scores[symbol] = score
        except Exception as e:
            logger.error("Skorlama hatası [%s]: %s", symbol, str(e))

    # ── 6. Sinyal Üretimi ────────────────────────────────────────────
    if not args.quiet:
        console.print("\n[cyan]▸ Sinyaller üretiliyor...[/cyan]")

    signals: list[Signal] = []
    for symbol in all_indicators:
        if symbol not in all_scores:
            continue
        try:
            sig = generate_signal(
                symbol,
                all_indicators[symbol],
                all_scores[symbol],
                regime,
                df=stock_data.get(symbol),
                intraday_df=stock_intraday.get(symbol),
            )
            signals.append(sig)
        except Exception as e:
            logger.error("Sinyal hatası [%s]: %s", symbol, str(e))

    signals.sort(key=lambda s: s.score, reverse=True)

    al_count = sum(1 for s in signals if s.signal == "AL")
    sat_count = sum(1 for s in signals if s.signal == "SAT")

    if not args.quiet:
        console.print(f"  ✓ {len(signals)} sinyal üretildi "
                       f"([green]{al_count} AL[/green] / "
                       f"[red]{sat_count} SAT[/red])")

    return signals, regime, stock_data, stock_intraday


def generate_reports(
    args: argparse.Namespace,
    signals: list[Signal],
    regime: MarketRegime,
    stock_data: dict[str, pd.DataFrame],
    stock_intraday: dict[str, pd.DataFrame],
    requested_symbols: int,
) -> None:

    # ── 7. Raporlama ────────────────────────────────────────────────
    if not args.quiet:
        console.print("\n[cyan]▸ Raporlar oluşturuluyor...[/cyan]")

    # 7a. CSV / JSON
    csv_path, json_path = save_csv_json(signals, regime)
    if not args.quiet:
        console.print(f"  ✓ CSV: {csv_path}")
        console.print(f"  ✓ JSON: {json_path}")

    web_snapshot_path = save_web_snapshot(
        signals,
        stock_data,
        stock_intraday,
        regime,
        requested_symbols=requested_symbols,
        expected_symbol_names=symbols,
    )
    if not args.quiet:
        console.print(f"  ✓ Web Snapshot: {web_snapshot_path}")

    # 7b. Terminal
    if not args.quiet:
        render_terminal_report(signals, regime)

    # 7c. PNG
    if not args.no_charts:
        try:
            table_png = generate_table_image(signals, regime)
            chart_png = generate_chart_image(signals, stock_data, regime)
            if not args.quiet:
                console.print(f"\n  ✓ Tablo PNG: {table_png}")
                console.print(f"  ✓ Grafik PNG: {chart_png}")
        except Exception as e:
            logger.error("PNG rapor hatası: %s", str(e))
            if not args.quiet:
                console.print(f"[yellow]  ⚠ PNG rapor hatası: {e}[/yellow]")

    # 7d. HTML
    if not args.no_html:
        try:
            html_path = generate_html_report(signals, stock_data, regime)
            if not args.quiet:
                console.print(f"  ✓ HTML: {html_path}")
        except Exception as e:
            logger.error("HTML rapor hatası: %s", str(e))
            if not args.quiet:
                console.print(f"[yellow]  ⚠ HTML rapor hatası: {e}[/yellow]")


def launch_dashboard() -> None:
    import subprocess
    import webbrowser

    console.print("\n[bold cyan]▸ React Dashboard Başlatılıyor...[/bold cyan]")
    dashboard_dir = Path(__file__).resolve().parent / "dashboard"

    if not dashboard_dir.exists():
        console.print("[red]Dashboard dizini bulunamadı![/red]")
        return

    try:
        import threading
        import time

        def open_browser() -> None:
            time.sleep(3)
            webbrowser.open("http://localhost:3000")

        threading.Thread(target=open_browser, daemon=True).start()
        subprocess.run("npm run dev", cwd=dashboard_dir, shell=True)
    except KeyboardInterrupt:
        console.print("\n[yellow]Dashboard durduruldu.[/yellow]")
    except Exception as exc:
        console.print(f"[red]Dashboard başlatılamadı: {exc}[/red]")


def main() -> None:
    args = parse_args()
    setup_logging(quiet=args.quiet)
    logger = logging.getLogger("main")
    symbols = resolve_symbols(args)
    run_id = uuid4().hex
    started_at = datetime.now().isoformat()

    if not acquire_analysis_lock(run_id, len(symbols)):
        message = "Başka bir analiz çalışıyor. Mevcut çalışma bitmeden yeni run başlatılmadı."
        logger.warning(message)
        if not args.quiet:
            console.print(f"[yellow]{message}[/yellow]")
        sys.exit(1)

    write_analysis_status(
        state="running",
        run_id=run_id,
        requested_symbols=len(symbols),
        started_at=started_at,
    )

    exit_code = 0
    # Bitiş
    try:
        signals, regime, stock_data, stock_intraday = run_pipeline(args, logger, symbols)
        generate_reports(
            args,
            signals,
            regime,
            stock_data,
            stock_intraday,
            requested_symbols=len(symbols),
        )
        finished_at = datetime.now().isoformat()
        write_analysis_status(
            state="idle",
            run_id=run_id,
            requested_symbols=len(symbols),
            successful_symbols=len(signals),
            started_at=started_at,
            finished_at=finished_at,
        )

        if not args.quiet:
            console.print("\n[bold green]✓ Analiz tamamlandı![/bold green]\n")
    except Exception as exc:
        exit_code = 1
        finished_at = datetime.now().isoformat()
        write_analysis_status(
            state="error",
            run_id=run_id,
            requested_symbols=len(symbols),
            started_at=started_at,
            finished_at=finished_at,
            error=str(exc),
        )
        logger.exception("Analiz akışı beklenmeyen bir hatayla sonlandı")
        if not args.quiet:
            console.print(f"[red]Beklenmeyen hata: {exc}[/red]")
    finally:
        clear_analysis_lock()

    if exit_code == 0 and args.dashboard:
        launch_dashboard()

    if exit_code != 0:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
