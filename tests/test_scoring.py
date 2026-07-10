from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.indicators import calculate_all_indicators, get_latest_indicators
from analysis.market_regime import MarketRegime
from analysis.scoring import calculate_score, score_momentum, score_squeeze_breakout, score_trend
from analysis.signals import generate_signal


def make_trending_df(rows: int = 260) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=rows, freq="B")
    close = pd.Series(np.linspace(10, 45, rows), index=index)
    open_ = close * 0.99
    high = close * 1.02
    low = close * 0.98
    volume = pd.Series(1_000_000.0, index=index)
    volume.iloc[-1] = 2_200_000.0
    return pd.DataFrame({
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    })


def regime() -> MarketRegime:
    return MarketRegime(
        regime="YUKSELIS",
        label="Yükseliş",
        color="green",
        sma_short=9_500,
        sma_long=8_800,
        index_price=10_000,
        performance_20d=3.0,
        trend_slope=0.2,
    )


def test_perfect_order_adds_explicit_trend_bonus():
    indicators = {
        "close": 120,
        "ema20": 110,
        "ema50": 100,
        "ema200": 90,
        "trend_slope": 0.3,
    }
    score, details = score_trend(indicators, wr_pct=100, wr_samples=5)

    assert details["perfect_order"] is True
    assert score >= 35
    assert details["wr_points"] > 0


def test_momentum_marks_overextended_ema_distance():
    indicators = {
        "rsi": 62,
        "macd": 2,
        "macd_signal": 1,
        "macd_hist": 1.2,
        "macd_hist_prev": 0.8,
        "adx": 35,
        "plus_di": 30,
        "minus_di": 15,
        "ema_distance_pct": 15,
    }
    _, details = score_momentum(indicators)

    assert details["adx_strong"] is True
    assert details["overextended"] is True


def test_squeeze_breakout_scores_setup_and_breakout():
    indicators = {
        "squeeze_on": True,
        "squeeze_breakout": True,
        "bb_width_pct": 4,
        "bb_width_p20": 6,
        "close": 102,
        "bb_upper": 100,
        "v_kat": 1.8,
    }
    score, details = score_squeeze_breakout(indicators)

    assert details["squeeze_on"] is True
    assert details["squeeze_breakout"] is True
    assert score >= 70


def test_calculate_score_returns_additive_morpheus_metrics():
    df = calculate_all_indicators(make_trending_df())
    indicators = get_latest_indicators(df)
    result = calculate_score(indicators, regime(), df)

    assert result.total > 100
    assert result.dzl_ok is True
    assert result.v_kat > 1
    assert result.adx > 0
    assert "squeeze_breakout" in result.details


def test_stop_and_targets_exist_for_hold_actions():
    df = calculate_all_indicators(make_trending_df())
    indicators = get_latest_indicators(df)
    indicators["beta"] = 1.0
    indicators["rsi"] = 80.0
    indicators["ema_distance_pct"] = 15.0
    score = calculate_score(indicators, regime(), df)
    signal = generate_signal("TEST", indicators, score, regime(), df=df)

    assert signal.signal == "BEKLE"
    assert signal.action == "KAR AL"
    assert signal.stop_loss > 0
    assert signal.target > 0
    assert signal.targets is not None
    assert signal.targets.short_target > 0
    assert signal.horizon_scores is not None
    assert signal.horizon_scores.short.horizon == "short"


def test_stop_and_targets_use_fallback_when_atr_missing():
    df = calculate_all_indicators(make_trending_df())
    indicators = get_latest_indicators(df)
    indicators["beta"] = 1.0
    indicators["atr"] = 0.0
    indicators["swing_low_20"] = 0.0
    indicators["swing_high_20"] = 0.0
    indicators["rsi"] = 65.0
    score = calculate_score(indicators, regime(), df)
    signal = generate_signal("TEST", indicators, score, regime(), df=df)

    assert signal.signal == "AL"
    assert signal.stop_loss > 0
    assert signal.target > 0
    assert signal.targets.short_target > 0
    assert signal.risk_pct > 0
