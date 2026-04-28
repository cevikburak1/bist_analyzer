from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.indicators import calculate_all_indicators, get_latest_indicators


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
