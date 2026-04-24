"""
Piyasa Rejimi Tespiti

XU100.IS (BIST-100 endeksi) verilerine bakarak genel piyasa rejimini belirler:
- YÜKSELİŞ: 50 SMA > 200 SMA
- DÜŞÜŞ:    50 SMA < 200 SMA
- YATAY:     Fark küçük (bant içinde)
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from analysis.indicators import calculate_sma, calculate_linear_regression_slope
from config import (
    SMA_SHORT,
    SMA_LONG,
    MARKET_REGIME_PERIOD,
)

logger = logging.getLogger(__name__)


@dataclass
class MarketRegime:
    """Piyasa rejimi bilgisi"""
    regime: str          # "YUKSELIS", "DUSUS", "YATAY"
    label: str           # Türkçe etiket (gösterim için)
    color: str           # Renk kodu
    sma_short: float     # 50 SMA değeri
    sma_long: float      # 200 SMA değeri
    index_price: float   # Endeks kapanış fiyatı
    performance_20d: float  # Son 20 günlük performans (%)
    trend_slope: float   # Trend eğimi


# Golden/death cross bandı: iki SMA arasındaki fark bu yüzdenin altındaysa YATAY
_FLAT_BAND_PCT = 1.0


def detect_market_regime(index_df: pd.DataFrame) -> MarketRegime:
    """
    Endeks verisinden piyasa rejimini tespit eder.

    Kurallar:
    - 50 SMA > 200 SMA (ve fark %1'den büyük) → YÜKSELİŞ
    - 50 SMA < 200 SMA (ve fark %1'den büyük) → DÜŞÜŞ
    - Fark %1 bandı içinde → YATAY
    """
    close = index_df["close"]

    sma_short = calculate_sma(close, SMA_SHORT)
    sma_long = calculate_sma(close, SMA_LONG)

    last_sma_short = sma_short.iloc[-1]
    last_sma_long = sma_long.iloc[-1]
    last_close = close.iloc[-1]

    # Son 20 günlük performans
    if len(close) >= MARKET_REGIME_PERIOD:
        perf_start = close.iloc[-MARKET_REGIME_PERIOD]
        performance_20d = ((last_close - perf_start) / perf_start) * 100
    else:
        performance_20d = 0.0

    # Trend eğimi
    trend_slope = calculate_linear_regression_slope(close, MARKET_REGIME_PERIOD)

    # SMA fark yüzdesi
    if last_sma_long > 0:
        sma_diff_pct = ((last_sma_short - last_sma_long) / last_sma_long) * 100
    else:
        sma_diff_pct = 0.0

    # Rejim tespiti
    if np.isnan(last_sma_short) or np.isnan(last_sma_long):
        regime = "YATAY"
        label = "YATAY REJİM (veri yetersiz)"
        color = "yellow"
    elif sma_diff_pct > _FLAT_BAND_PCT:
        regime = "YUKSELIS"
        label = "YÜKSELİŞ REJİMİ"
        color = "green"
    elif sma_diff_pct < -_FLAT_BAND_PCT:
        regime = "DUSUS"
        label = "DÜŞÜŞ REJİMİ"
        color = "red"
    else:
        regime = "YATAY"
        label = "YATAY REJİM"
        color = "yellow"

    logger.info(
        "Piyasa rejimi: %s (SMA50=%.2f, SMA200=%.2f, fark=%.2f%%)",
        regime, last_sma_short, last_sma_long, sma_diff_pct,
    )

    return MarketRegime(
        regime=regime,
        label=label,
        color=color,
        sma_short=last_sma_short,
        sma_long=last_sma_long,
        index_price=last_close,
        performance_20d=round(performance_20d, 2),
        trend_slope=round(trend_slope, 4),
    )


def should_filter_buy_signals(regime: MarketRegime) -> bool:
    """Düşüş rejiminde AL sinyallerini filtrele."""
    return regime.regime == "DUSUS"
