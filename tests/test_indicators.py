from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.indicators import (
    calculate_all_indicators,
    calculate_beta,
    calculate_rsi,
    get_latest_indicators,
)


def make_ohlcv(rows: int = 260) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=rows, freq="B")
    base = np.linspace(10, 40, rows)
    close = pd.Series(base + np.sin(np.arange(rows) / 7) * 0.3, index=index)
    open_ = close * 0.995
    high = close * 1.02
    low = close * 0.98
    volume = pd.Series(np.linspace(1_000_000, 1_500_000, rows), index=index)
    volume.iloc[-1] = volume.tail(20).mean() * 2
    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def test_morpheus_indicators_are_exposed():
    df = calculate_all_indicators(make_ohlcv())
    latest = get_latest_indicators(df)

    assert latest["ema20"] > latest["ema50"] > latest["ema200"]
    assert latest["perfect_order"] is True
    assert latest["adx"] > 0
    assert latest["v_kat"] > 1.5
    assert "bb_width_pct" in latest
    assert "squeeze_on" in latest
    assert "ema_distance_pct" in latest


def test_wilder_rsi_uses_sma_seed_and_handles_boundaries():
    mixed = calculate_rsi(pd.Series([10, 11, 9, 12, 11], dtype=float), period=3)
    rising = calculate_rsi(pd.Series([1, 2, 3, 4, 5], dtype=float), period=3)
    falling = calculate_rsi(pd.Series([5, 4, 3, 2, 1], dtype=float), period=3)
    flat = calculate_rsi(pd.Series([2, 2, 2, 2, 2], dtype=float), period=3)

    assert mixed.iloc[:3].isna().all()
    assert mixed.iloc[3] == pytest.approx(66.6666667)
    assert mixed.iloc[4] == pytest.approx(53.3333333)
    assert rising.iloc[-1] == 100.0
    assert falling.iloc[-1] == 0.0
    assert flat.iloc[-1] == 50.0


def test_beta_requires_enough_timestamp_aligned_returns():
    stock_index = pd.date_range("2025-01-01", periods=60, freq="D")
    market_index = pd.date_range("2026-01-01", periods=60, freq="D")
    stock = pd.Series(np.linspace(100, 130, 60), index=stock_index)
    market = pd.Series(np.linspace(100, 120, 60), index=market_index)

    assert calculate_beta(stock, market) == 1.0


def test_beta_is_finite_and_uses_aligned_observations():
    index = pd.date_range("2025-01-01", periods=80, freq="D")
    market_returns = np.array([0.01, -0.006, 0.004, -0.002] * 20)
    stock_returns = market_returns * 2
    market = pd.Series(100 * np.cumprod(1 + market_returns), index=index)
    stock = pd.Series(100 * np.cumprod(1 + stock_returns), index=index)

    beta = calculate_beta(stock, market)

    assert np.isfinite(beta)
    assert beta == pytest.approx(2.0, rel=1e-10)
