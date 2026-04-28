"""
PNG Rapor Modülü (Matplotlib)

İki tür PNG çıktısı üretir:
1. bist_table_YYYYMMDD.png  — Formatlı tablo görseli
2. bist_charts_YYYYMMDD.png — AL sinyali veren hisselerin grafikleri
"""

import logging
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # GUI olmayan backend

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from analysis.market_regime import MarketRegime
from analysis.signals import Signal
from config import OUTPUT_DIR, MAX_BUY_SIGNALS_IN_CHART, REPORT_DATE_FORMAT

logger = logging.getLogger(__name__)

# Stil ayarları
plt.rcParams.update({
    "figure.facecolor": "#1a1a2e",
    "axes.facecolor": "#16213e",
    "axes.edgecolor": "#e94560",
    "axes.labelcolor": "#eee",
    "text.color": "#eee",
    "xtick.color": "#aaa",
    "ytick.color": "#aaa",
    "grid.color": "#333",
    "grid.alpha": 0.3,
    "font.size": 9,
})

SIGNAL_COLORS_MAP = {
    "GÜÇLÜ AL": "#00ff88",
    "AL": "#00ff88",
    "SAT": "#ff4444",
    "BEKLE": "#ffaa00",
    "KAR AL": "#d946ef",
}


def _ensure_output_dir() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def generate_table_image(
    signals: list[Signal],
    regime: MarketRegime,
) -> Path:
    """
    Tüm sinyallerin formatlı tablo görselini PNG olarak kaydeder.
    """
    output_dir = _ensure_output_dir()
    date_str = datetime.now().strftime(REPORT_DATE_FORMAT)
    filepath = output_dir / f"bist_table_{date_str}.png"

    headers = ["#", "Hisse", "Fiyat", "Skor", "Aksiyon", "WR%", "ADX", "V/K", "DZL", "SQZ"]
    rows = []
    cell_colors = []

    for i, sig in enumerate(signals, 1):
        price_str = f"{sig.price:,.2f}" if sig.price < 1000 else f"{sig.price:,.0f}"
        metrics = sig.score_breakdown
        row = [
            str(i),
            sig.symbol,
            price_str,
            f"{sig.score:.0f}",
            sig.action or sig.signal,
            f"{metrics.wr_pct:.0f}",
            f"{metrics.adx:.0f}",
            f"{metrics.v_kat:.1f}",
            "OK" if metrics.dzl_ok else "--",
            "OK" if metrics.sqz_ok else "--",
        ]
        rows.append(row)

        # Satır rengi sinyale göre
        sig_color = SIGNAL_COLORS_MAP.get(sig.action or sig.signal, "#ffaa00")
        base_alpha = "33"  # %20 opaklık
        row_color = [sig_color + base_alpha] * len(headers)
        cell_colors.append(row_color)

    if not rows:
        logger.warning("Tablo için sinyal bulunamadı, PNG oluşturulmadı")
        return filepath

    # Figür boyutunu satır sayısına göre ayarla
    n_rows = len(rows)
    fig_height = max(6, 1.5 + n_rows * 0.35)
    fig, ax = plt.subplots(figsize=(14, fig_height))
    ax.axis("off")

    # Başlık
    regime_color = {"YUKSELIS": "#00ff88", "DUSUS": "#ff4444", "YATAY": "#ffaa00"}
    title = (
        f"BIST Analiz Raporu — {datetime.now().strftime('%d.%m.%Y')}\n"
        f"Piyasa: {regime.label} | XU100: {regime.index_price:,.0f}"
    )
    ax.set_title(
        title,
        fontsize=14,
        fontweight="bold",
        color=regime_color.get(regime.regime, "#eee"),
        pad=20,
    )

    table = ax.table(
        cellText=rows,
        colLabels=headers,
        cellColours=cell_colors,
        colColours=["#0f3460"] * len(headers),
        loc="center",
        cellLoc="center",
    )

    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)

    # Başlık satırı kalın
    for j in range(len(headers)):
        table[0, j].set_text_props(fontweight="bold", color="#eee")
        table[0, j].set_facecolor("#0f3460")

    plt.tight_layout()
    fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    logger.info("Tablo PNG kaydedildi: %s", filepath)
    return filepath


def generate_chart_image(
    signals: list[Signal],
    stock_data: dict[str, pd.DataFrame],
    regime: MarketRegime,
) -> Path:
    """
    AL sinyali veren hisselerin fiyat grafiklerini PNG olarak kaydeder.
    Her hisse için: Fiyat + SMA + Hacim + RSI subplotları.
    """
    output_dir = _ensure_output_dir()
    date_str = datetime.now().strftime(REPORT_DATE_FORMAT)
    filepath = output_dir / f"bist_charts_{date_str}.png"

    buy_signals = [s for s in signals if s.signal == "AL"][:MAX_BUY_SIGNALS_IN_CHART]

    if not buy_signals:
        # AL sinyali yoksa en yüksek skorlu 4 hisseyi göster
        buy_signals = signals[:min(4, len(signals))]

    if not buy_signals:
        logger.warning("Grafik için yeterli sinyal yok")
        return filepath

    n_stocks = len(buy_signals)
    n_cols = min(3, n_stocks)
    n_rows = (n_stocks + n_cols - 1) // n_cols

    fig, axes = plt.subplots(
        n_rows * 3, n_cols,  # Her hisse 3 subplot: fiyat, hacim, RSI
        figsize=(7 * n_cols, 5 * n_rows),
        squeeze=False,
    )

    for idx, sig in enumerate(buy_signals):
        col = idx % n_cols
        row_base = (idx // n_cols) * 3

        df = stock_data.get(sig.symbol)
        if df is None or df.empty:
            continue

        # Son 120 günlük veri
        plot_df = df.tail(120).copy()
        dates = plot_df.index

        # --- Subplot 1: Fiyat + SMA ---
        ax_price = axes[row_base, col]
        ax_price.plot(dates, plot_df["close"], color="#00d2ff", linewidth=1.5, label="Fiyat")

        if "sma_short" in plot_df.columns:
            sma50 = plot_df["sma_short"]
            ax_price.plot(dates, sma50, color="#ff6b6b", linewidth=1, alpha=0.8, label="SMA50")

        if "sma_long" in plot_df.columns:
            sma200 = plot_df["sma_long"]
            valid = sma200.dropna()
            if len(valid) > 0:
                ax_price.plot(dates, sma200, color="#ffd93d", linewidth=1, alpha=0.8, label="SMA200")

        if "bb_upper" in plot_df.columns:
            ax_price.fill_between(
                dates,
                plot_df["bb_lower"],
                plot_df["bb_upper"],
                alpha=0.1,
                color="#888",
                label="BB",
            )

        signal_color = SIGNAL_COLORS_MAP.get(sig.signal, "#ffaa00")
        ax_price.set_title(
            f"{sig.symbol}  |  {sig.signal}  |  Skor: {sig.score:.0f}",
            fontsize=11,
            fontweight="bold",
            color=signal_color,
        )
        ax_price.legend(loc="upper left", fontsize=7)
        ax_price.grid(True, alpha=0.2)
        ax_price.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        ax_price.tick_params(labelbottom=False)

        # --- Subplot 2: Hacim ---
        ax_vol = axes[row_base + 1, col]
        colors = ["#00ff88" if c >= o else "#ff4444"
                  for c, o in zip(plot_df["close"], plot_df["open"])]
        ax_vol.bar(dates, plot_df["volume"], color=colors, alpha=0.6, width=0.8)
        if "volume_avg" in plot_df.columns:
            ax_vol.plot(dates, plot_df["volume_avg"], color="#ffaa00", linewidth=1, label="Ort.")
            ax_vol.legend(loc="upper left", fontsize=7)
        ax_vol.set_ylabel("Hacim", fontsize=8)
        ax_vol.grid(True, alpha=0.2)
        ax_vol.tick_params(labelbottom=False)

        # --- Subplot 3: RSI ---
        ax_rsi = axes[row_base + 2, col]
        if "rsi" in plot_df.columns:
            rsi_vals = plot_df["rsi"]
            ax_rsi.plot(dates, rsi_vals, color="#e94560", linewidth=1.2)
            ax_rsi.axhline(y=70, color="#ff4444", linestyle="--", alpha=0.5, linewidth=0.8)
            ax_rsi.axhline(y=30, color="#00ff88", linestyle="--", alpha=0.5, linewidth=0.8)
            ax_rsi.axhline(y=50, color="#888", linestyle=":", alpha=0.3, linewidth=0.8)
            ax_rsi.fill_between(dates, 30, 70, alpha=0.05, color="#888")
            ax_rsi.set_ylim(0, 100)
        ax_rsi.set_ylabel("RSI", fontsize=8)
        ax_rsi.grid(True, alpha=0.2)
        ax_rsi.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
        plt.setp(ax_rsi.xaxis.get_majorticklabels(), rotation=45, fontsize=7)

    # Kullanılmayan eksenleri gizle
    total_subplot_rows = n_rows * 3
    for r in range(total_subplot_rows):
        for c in range(n_cols):
            idx = (r // 3) * n_cols + c
            if idx >= n_stocks:
                axes[r, c].set_visible(False)

    fig.suptitle(
        f"BIST Analiz Grafikleri — {datetime.now().strftime('%d.%m.%Y')}",
        fontsize=16,
        fontweight="bold",
        color="#00d2ff",
        y=1.01,
    )

    plt.tight_layout()
    fig.savefig(filepath, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)

    logger.info("Grafik PNG kaydedildi: %s", filepath)
    return filepath
