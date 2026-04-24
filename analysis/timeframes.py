"""
Çoklu Zaman Dilimi Analiz Modülü

Aynı OHLCV verisini farklı zaman dilimlerinde yeniden örnekler
(haftalık, aylık) ve her dilim için bağımsız bir AL/SAT/BEKLE
sinyali üretir.

Yıllık sinyal, günlük veriden uzun-vadeli SMA pozisyonu ile hesaplanır.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from analysis.indicators import (
    calculate_sma,
    calculate_rsi,
    calculate_linear_regression_slope,
)


@dataclass
class TimeframeSignals:
    """Hisse için çoklu zaman dilimi sinyalleri"""
    daily: str       # AL / SAT / BEKLE (ana skorlama tabanlı)
    weekly: str      # haftalık trend tabanlı
    monthly: str     # aylık trend tabanlı
    yearly: str      # yıllık trend (uzun-vadeli SMA)


def _resample(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """OHLCV verisini farklı zaman dilimine yeniden örnekler."""
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    return df.resample(rule).agg(agg).dropna()


def _signal_from_trend(close: pd.Series, fast: int, slow: int) -> str:
    """
    Basit trend sinyali:
    - SMA fast > SMA slow + RSI > 50 + son hareket pozitif → AL
    - SMA fast < SMA slow + RSI < 50 + son hareket negatif → SAT
    - aksi → BEKLE
    """
    if len(close) < slow + 5:
        return "BEKLE"

    sma_fast = calculate_sma(close, fast)
    sma_slow = calculate_sma(close, slow)
    rsi = calculate_rsi(close, 14)
    slope = calculate_linear_regression_slope(close, min(20, len(close) // 2))

    last_close = close.iloc[-1]
    last_fast = sma_fast.iloc[-1]
    last_slow = sma_slow.iloc[-1]
    last_rsi = rsi.iloc[-1] if not np.isnan(rsi.iloc[-1]) else 50.0

    # Anahtar koşullar
    bullish = (
        last_fast > last_slow
        and last_close > last_fast
        and last_rsi > 50
        and slope > 0
    )
    bearish = (
        last_fast < last_slow
        and last_close < last_fast
        and last_rsi < 50
        and slope < 0
    )

    if bullish:
        return "AL"
    if bearish:
        return "SAT"
    return "BEKLE"


def _yearly_signal(close: pd.Series) -> str:
    """
    Yıllık sinyal: uzun-vadeli trend
    - 200 SMA üzerinde + 12 aylık eğim pozitif → AL
    - 200 SMA altında + 12 aylık eğim negatif → SAT
    - aksi → BEKLE
    """
    if len(close) < 200:
        return "BEKLE"

    sma200 = calculate_sma(close, 200)
    last_close = close.iloc[-1]
    last_sma = sma200.iloc[-1]

    if np.isnan(last_sma):
        return "BEKLE"

    # 12 aylık (≈252 iş günü) eğim
    yearly_slope = calculate_linear_regression_slope(close, min(252, len(close)))

    if last_close > last_sma and yearly_slope > 0:
        return "AL"
    if last_close < last_sma and yearly_slope < 0:
        return "SAT"
    return "BEKLE"


def calculate_timeframe_signals(
    df: pd.DataFrame,
    daily_signal: str,
) -> TimeframeSignals:
    """
    Aynı veriden 4 farklı zaman dilimi sinyali üretir.

    Args:
        df: günlük OHLCV verisi (datetime index)
        daily_signal: ana skorlama motorundan gelen günlük sinyal
    """
    # Haftalık: 10 hafta hızlı, 30 hafta yavaş SMA
    weekly_df = _resample(df, "W")
    weekly_sig = _signal_from_trend(weekly_df["close"], fast=10, slow=30)

    # Aylık: 6 ay hızlı, 12 ay yavaş SMA
    monthly_df = _resample(df, "ME")
    monthly_sig = _signal_from_trend(monthly_df["close"], fast=6, slow=12)

    # Yıllık: günlük veride 200 SMA + uzun trend
    yearly_sig = _yearly_signal(df["close"])

    return TimeframeSignals(
        daily=daily_signal,
        weekly=weekly_sig,
        monthly=monthly_sig,
        yearly=yearly_sig,
    )
