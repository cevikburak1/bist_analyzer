"""
Terminal Raporu (Rich)

Renkli tablo, piyasa rejimi banner'ı, çoklu zaman dilimi sinyalleri,
3 vadeli hedef, ve detaylı analiz panelleri.
"""

import logging
import shutil
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich import box

from analysis.market_regime import MarketRegime
from analysis.signals import Signal
from analysis.candle_patterns import patterns_summary

logger = logging.getLogger(__name__)

_term_size = shutil.get_terminal_size((140, 40))
_TERM_WIDTH = max(_term_size.columns, 140)
console = Console(force_terminal=True, width=_TERM_WIDTH)

SIGNAL_COLORS = {
    "GÜÇLÜ AL": "bold green",
    "AL": "bold green",
    "SAT": "bold red",
    "BEKLE": "bold yellow",
    "KAR AL": "bold magenta",
}
SHORT_SIGNAL_COLORS = {"AL": "green", "SAT": "red", "BEKLE": "yellow"}
REGIME_STYLES = {
    "YUKSELIS": ("bold white on green", "▲"),
    "DUSUS": ("bold white on red", "▼"),
    "YATAY": ("bold black on yellow", "■"),
}


def _fp(price: float) -> str:
    if price >= 1000:
        return f"{price:,.0f}"
    if price >= 10:
        return f"{price:,.2f}"
    return f"{price:,.3f}"


def _short_sig(s: str) -> str:
    return {"AL": "AL", "SAT": "SAT", "BEKLE": "---"}.get(s, "---")


def print_regime_banner(regime: MarketRegime) -> None:
    style, icon = REGIME_STYLES.get(regime.regime, ("bold", "○"))
    banner_text = (
        f"{icon}  {regime.label}  {icon}\n"
        f"XU100: {regime.index_price:,.0f}   |   "
        f"SMA50: {regime.sma_short:,.0f}   |   "
        f"SMA200: {regime.sma_long:,.0f}   |   "
        f"20G Performans: {regime.performance_20d:+.2f}%"
    )
    console.print()
    console.print(Panel(banner_text, title="[bold]PİYASA REJİMİ[/bold]",
                        style=style, expand=True, padding=(1, 2)))


def print_signals_table(signals: list[Signal]) -> None:
    """Ana sinyal tablosu — tüm hisseler skor sırasına göre."""
    table = Table(
        title=f"BIST TÜM HİSSELER — SKOR SIRASI ({datetime.now().strftime('%d.%m.%Y %H:%M')})",
        box=box.SIMPLE_HEAVY, show_lines=False,
        header_style="bold cyan", title_style="bold white",
        padding=(0, 1), expand=False,
    )

    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("HİSSE", style="bold", width=7)
    table.add_column("FİYAT", justify="right", width=9)
    table.add_column("SKOR", justify="right", width=6)
    table.add_column("AKSİYON", justify="center", width=9)
    table.add_column("NEDEN", width=22)
    table.add_column("KUR%", justify="right", width=6)
    table.add_column("ADX", justify="right", width=5)
    table.add_column("V/K", justify="right", width=5)
    table.add_column("DZL", justify="center", width=4)
    table.add_column("SQZ", justify="center", width=4)
    table.add_column("STOP", justify="right", width=9)
    table.add_column("HEDEF", justify="right", width=9)

    for i, sig in enumerate(signals, 1):
        if sig.score >= 170:
            score_style = "bold green"
        elif sig.score <= 90:
            score_style = "bold red"
        else:
            score_style = "bold yellow"

        sym_style = "bold cyan" if sig.signal == "AL" else ("bold red" if sig.signal == "SAT" else "bold")
        action = sig.action or sig.signal
        reason = sig.reason_factors[0] if sig.reason_factors else sig.reason
        reason = reason[:28] + "…" if len(reason) > 29 else reason
        metrics = sig.score_breakdown
        target = sig.targets.short_target if sig.targets else sig.target

        table.add_row(
            str(i),
            Text(sig.symbol, style=sym_style),
            _fp(sig.price),
            Text(f"{sig.score:.0f}", style=score_style),
            Text(action, style=SIGNAL_COLORS.get(action, "yellow")),
            reason,
            f"{metrics.wr_pct:.0f}",
            f"{metrics.adx:.0f}",
            f"{metrics.v_kat:.1f}",
            "OK" if metrics.dzl_ok else "--",
            "OK" if metrics.sqz_ok else "--",
            _fp(sig.stop_loss) if sig.stop_loss > 0 else "—",
            _fp(target) if target > 0 else "—",
        )

    console.print()
    console.print(table)


def print_buy_signals_detail(signals: list[Signal]) -> None:
    """AL sinyali veren hisseler — 3 vadeli hedef tablosu."""
    buys = [s for s in signals if s.signal == "AL"]
    if not buys:
        return

    table = Table(
        title=f"AL SİNYALİ — 3 VADELİ HEDEF ({len(buys)} HİSSE)",
        box=box.DOUBLE_EDGE, show_lines=False,
        header_style="bold green", title_style="bold green",
        padding=(0, 1), expand=False,
    )

    table.add_column("HİSSE", style="bold cyan", width=7)
    table.add_column("SKOR", justify="center", width=5)
    table.add_column("ENTRY", justify="right", width=10)
    table.add_column("STOP", justify="right", style="red", width=10)
    table.add_column("KISA", justify="right", style="green", width=10)
    table.add_column("ORTA", justify="right", style="green", width=10)
    table.add_column("UZUN", justify="right", style="green", width=10)
    table.add_column("R/R K", justify="center", width=5)
    table.add_column("R/R O", justify="center", width=5)
    table.add_column("FİB D", justify="right", width=9)
    table.add_column("MUM", justify="center", width=8)
    table.add_column("EW", justify="center", width=5)

    for sig in buys:
        tgt = sig.targets
        fib = sig.fibonacci
        ew = sig.elliott_wave

        rr_k = f"{tgt.short_rr:.1f}" if tgt and tgt.short_rr > 0 else "—"
        rr_o = f"{tgt.medium_rr:.1f}" if tgt and tgt.medium_rr > 0 else "—"
        fib_d = _fp(fib.nearest_support) if fib and fib.nearest_support > 0 else "—"

        bias = sig.candle_bias
        bias_text = {"BULLISH": "YÜK↑", "BEARISH": "DÜŞ↓", "MIXED": "MIX~"}.get(bias, "—")
        bias_style = {"BULLISH": "green", "BEARISH": "red", "MIXED": "yellow"}.get(bias, "dim")

        ew_text = f"W{ew.current_wave}" if ew and ew.current_wave != "?" else "—"

        table.add_row(
            sig.symbol,
            f"{sig.score:.0f}",
            _fp(sig.entry),
            _fp(sig.stop_loss),
            _fp(tgt.short_target) if tgt and tgt.short_target > 0 else "—",
            _fp(tgt.medium_target) if tgt and tgt.medium_target > 0 else "—",
            _fp(tgt.long_target) if tgt and tgt.long_target > 0 else "—",
            Text(rr_k, style="green" if tgt and tgt.short_rr >= 1.5 else "yellow"),
            Text(rr_o, style="green" if tgt and tgt.medium_rr >= 1.5 else "yellow"),
            fib_d,
            Text(bias_text, style=bias_style),
            Text(ew_text, style="cyan"),
        )

    console.print()
    console.print(table)


def print_detailed_analysis(signals: list[Signal], max_count: int = 10) -> None:
    """TOP N AL sinyali veren hisselerin detaylı yorum panelleri."""
    buys = [s for s in signals if s.signal == "AL"][:max_count]
    if not buys:
        # AL yoksa en yüksek skorlu 3 tanesini göster
        buys = signals[:min(3, len(signals))]

    console.print()
    console.print("[bold cyan]━━━ DETAYLI ANALİZ ━━━[/bold cyan]")

    for sig in buys:
        comm = sig.commentary
        tgt = sig.targets
        fib = sig.fibonacci
        ew = sig.elliott_wave

        # Başlık rengi
        sig_color = {"AL": "green", "SAT": "red", "BEKLE": "yellow"}.get(sig.signal, "white")
        summary_text = comm.summary if comm else sig.signal
        title = f"[bold {sig_color}]{sig.symbol} — {summary_text} (Skor: {sig.score:.0f})[/bold {sig_color}]"

        # Satır 1: Fiyat + Stop + R/R
        line1 = f"Fiyat: {_fp(sig.price)}"
        if sig.stop_loss > 0:
            line1 += f"  |  Stop: [red]{_fp(sig.stop_loss)}[/red] (-{sig.risk_pct:.1f}%)"
        if sig.rr_ratio > 0:
            line1 += f"  |  R/Ö: {sig.rr_ratio:.1f}"

        # Satır 2: 3 Hedef
        line2 = ""
        if tgt and tgt.short_target > 0:
            line2 = (
                f"Hedefler:  "
                f"[green]K {_fp(tgt.short_target)}[/green] (+{tgt.short_reward_pct:.1f}%)  |  "
                f"[green]O {_fp(tgt.medium_target)}[/green] (+{tgt.medium_reward_pct:.1f}%)  |  "
                f"[green]U {_fp(tgt.long_target)}[/green] (+{tgt.long_reward_pct:.1f}%)"
            )

        # Satır 3: Fibonacci
        line3 = ""
        if fib and (fib.nearest_support > 0 or fib.nearest_resistance > 0):
            parts = []
            if fib.nearest_support > 0:
                parts.append(f"Destek {_fp(fib.nearest_support)}")
            if fib.nearest_resistance > 0:
                parts.append(f"Direnç {_fp(fib.nearest_resistance)}")
            zone = f" ({fib.current_zone})" if fib.current_zone else ""
            line3 = f"Fibonacci: {' | '.join(parts)}{zone}"

        # Satır 4: Mum + EW
        line4_parts = []
        if sig.candle_patterns:
            line4_parts.append(f"Mum: {patterns_summary(sig.candle_patterns)}")
        if ew and ew.current_wave != "?":
            conf = {"HIGH": "yüksek", "MEDIUM": "orta", "LOW": "düşük"}.get(ew.confidence, "?")
            line4_parts.append(f"EW: Wave {ew.current_wave} ({conf})")
        line4 = "  |  ".join(line4_parts)

        # Yorum paragrafı
        paragraph = comm.paragraph if comm else ""

        # Riskler
        risk_text = ""
        if comm and comm.risks:
            risk_lines = [f"  [red]![/red] {r}" for r in comm.risks]
            risk_text = "\n" + "\n".join(risk_lines)

        # Panel birleştir
        body_lines = [line1]
        if line2:
            body_lines.append(line2)
        if line3:
            body_lines.append(line3)
        if line4:
            body_lines.append(line4)
        body_lines.append("")
        if paragraph:
            body_lines.append(paragraph)
        if risk_text:
            body_lines.append(risk_text)

        console.print()
        console.print(Panel(
            "\n".join(body_lines),
            title=title,
            border_style=sig_color,
            padding=(1, 2),
            expand=True,
        ))


def print_summary(signals: list[Signal], regime: MarketRegime) -> None:
    al_count = sum(1 for s in signals if s.signal == "AL")
    sat_count = sum(1 for s in signals if s.signal == "SAT")
    bekle_count = sum(1 for s in signals if s.signal == "BEKLE")
    total = len(signals)
    avg_score = sum(s.score for s in signals) / total if total > 0 else 0

    weekly_buy = sum(1 for s in signals if s.timeframes and s.timeframes.weekly == "AL")
    monthly_buy = sum(1 for s in signals if s.timeframes and s.timeframes.monthly == "AL")
    yearly_buy = sum(1 for s in signals if s.timeframes and s.timeframes.yearly == "AL")

    bullish_candles = sum(1 for s in signals if s.candle_bias == "BULLISH")
    bearish_candles = sum(1 for s in signals if s.candle_bias == "BEARISH")

    summary = Table(box=box.SIMPLE, show_header=False, padding=(0, 2), expand=False)
    summary.add_column("label", style="bold")
    summary.add_column("value")

    summary.add_row("Toplam Hisse:", str(total))
    summary.add_row("Günlük AL:", Text(f"{al_count}", style="bold green"))
    summary.add_row("Günlük SAT:", Text(f"{sat_count}", style="bold red"))
    summary.add_row("Günlük BEKLE:", Text(f"{bekle_count}", style="bold yellow"))
    summary.add_row("", "")
    summary.add_row("Haftalık AL:", Text(f"{weekly_buy}", style="green"))
    summary.add_row("Aylık AL:", Text(f"{monthly_buy}", style="green"))
    summary.add_row("Yıllık AL:", Text(f"{yearly_buy}", style="green"))
    summary.add_row("", "")
    summary.add_row("Bullish Formasyon:", Text(f"{bullish_candles}", style="green"))
    summary.add_row("Bearish Formasyon:", Text(f"{bearish_candles}", style="red"))
    summary.add_row("", "")
    summary.add_row("Ortalama Skor:", f"{avg_score:.1f}")

    console.print()
    console.print(Panel(summary, title="[bold]ÖZET[/bold]", border_style="cyan",
                        padding=(1, 2), expand=False))


def render_terminal_report(signals: list[Signal], regime: MarketRegime) -> None:
    """Tam terminal raporunu oluşturur."""
    print_regime_banner(regime)
    print_signals_table(signals)
    print_buy_signals_detail(signals)
    print_detailed_analysis(signals)
    print_summary(signals, regime)
    console.print()
