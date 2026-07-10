from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.fibonacci import FibonacciResult
from analysis.market_regime import MarketRegime
from analysis.scoring import ScoreBreakdown, _calculate_win_rate, score_trend
from analysis.signals import calculate_stop_and_target, generate_signal
from analysis.targets import calculate_targets


def regime() -> MarketRegime:
    return MarketRegime(
        regime="YUKSELIS",
        label="Yukselis",
        color="green",
        sma_short=9_500,
        sma_long=8_800,
        index_price=10_000,
        performance_20d=3.0,
        trend_slope=0.2,
    )


def ready_indicators() -> dict:
    return {
        "close": 100.0,
        "open": 99.0,
        "high": 102.0,
        "low": 98.0,
        "rsi": 55.0,
        "sma_short": 95.0,
        "sma_long": 90.0,
        "ema20": 98.0,
        "ema50": 95.0,
        "ema200": 90.0,
        "macd": 2.0,
        "macd_signal": 1.0,
        "adx": 30.0,
        "plus_di": 25.0,
        "minus_di": 15.0,
        "volume_avg": 1_000_000.0,
        "volume_short_avg": 1_500_000.0,
        "v_kat": 1.5,
        "atr": 2.0,
        "swing_low_20": 94.0,
        "swing_high_20": 104.0,
        "trend_slope": 0.2,
        "beta": 1.0,
    }


def win_rate_frame(future_price: float) -> pd.DataFrame:
    rows = 30
    close = np.full(rows, 100.0)
    close[8] = future_price
    frame = pd.DataFrame({
        "close": close,
        "perfect_order": False,
        "adx": 0.0,
        "v_kat": 0.0,
        "macd": 0.0,
        "macd_signal": 0.0,
    })
    frame.loc[5, ["perfect_order", "adx", "v_kat", "macd", "macd_signal"]] = [
        True, 30.0, 1.5, 2.0, 1.0,
    ]
    return frame


def test_win_rate_requires_move_above_cost_buffer_and_discloses_proxy():
    small_wr, small_samples, small_meta = _calculate_win_rate(win_rate_frame(100.1))
    clear_wr, clear_samples, clear_meta = _calculate_win_rate(win_rate_frame(101.0))

    assert (small_wr, small_samples) == (0.0, 1)
    assert (clear_wr, clear_samples) == (100.0, 1)
    assert small_meta["return_hurdle_pct"] == pytest.approx(0.5)
    assert small_meta["is_backtest"] is False
    assert clear_meta["status"] == "ok"


def test_win_rate_purges_overlapping_forward_windows():
    frame = win_rate_frame(100.0)
    for row in (6, 7, 8):
        frame.loc[row, ["perfect_order", "adx", "v_kat", "macd", "macd_signal"]] = [
            True, 30.0, 1.5, 2.0, 1.0,
        ]

    _, samples, metadata = _calculate_win_rate(frame, horizon=3)

    assert metadata["raw_entry_samples"] == 4
    assert metadata["purged_entry_samples"] == 2
    assert metadata["purge_bars"] == 3
    assert metadata["overlapping_samples"] is False
    assert samples == 2


def test_win_rate_points_are_discounted_until_sample_is_large_enough():
    indicators = ready_indicators()
    _, five_details = score_trend(indicators, wr_pct=100.0, wr_samples=5)
    _, twenty_details = score_trend(indicators, wr_pct=100.0, wr_samples=20)

    assert five_details["wr_points"] == pytest.approx(6.2, abs=0.1)
    assert twenty_details["wr_points"] == 25.0
    assert five_details["wr_sample_weight"] < twenty_details["wr_sample_weight"]


def test_single_win_rate_sample_cannot_create_strong_buy():
    indicators = ready_indicators()
    weak_evidence = ScoreBreakdown(
        total=250.0, wr_pct=100.0, wr_samples=1, adx=30.0, v_kat=1.5,
    )
    adequate_evidence = ScoreBreakdown(
        total=250.0, wr_pct=100.0, wr_samples=10, adx=30.0, v_kat=1.5,
    )

    weak_signal = generate_signal("TEST", indicators, weak_evidence, regime())
    adequate_signal = generate_signal("TEST", indicators, adequate_evidence, regime())

    assert weak_signal.signal == "AL"
    assert weak_signal.action == "AL"
    assert weak_signal.commentary is not None
    assert weak_signal.commentary.summary == "AL"
    assert adequate_signal.action == "GÜÇLÜ AL"
    assert adequate_signal.commentary is not None
    assert adequate_signal.commentary.summary == "GÜÇLÜ AL"


def test_incomplete_long_term_indicators_return_hold_instead_of_sell():
    indicators = ready_indicators()
    indicators["ema200"] = np.nan
    indicators["sma_long"] = np.nan

    signal = generate_signal("TEST", indicators, ScoreBreakdown(total=0.0), regime())

    assert signal.signal == "BEKLE"
    assert signal.action == "BEKLE"
    assert "veri yetersiz" in signal.reason.lower()
    assert signal.stop_loss == 0.0
    assert signal.target == 0.0


def test_too_few_price_bars_cannot_create_active_signal():
    index = pd.date_range("2026-01-01", periods=30, freq="B")
    close = pd.Series(np.linspace(95.0, 100.0, len(index)), index=index)
    frame = pd.DataFrame({
        "open": close * 0.99,
        "high": close * 1.01,
        "low": close * 0.98,
        "close": close,
        "volume": 1_000_000.0,
    })
    bullish_score = ScoreBreakdown(
        total=250.0, wr_pct=100.0, wr_samples=20, adx=30.0, v_kat=1.5,
    )

    signal = generate_signal(
        "TEST", ready_indicators(), bullish_score, regime(), df=frame,
    )

    assert signal.signal == "BEKLE"
    assert signal.action == "BEKLE"
    assert "30/200" in signal.reason


def test_neutral_hold_does_not_receive_forced_long_targets():
    signal = generate_signal(
        "TEST", ready_indicators(), ScoreBreakdown(total=120.0), regime(),
    )

    assert signal.signal == "BEKLE"
    assert signal.action == "BEKLE"
    assert signal.stop_loss == 0.0
    assert signal.target == 0.0
    assert signal.targets is not None
    assert signal.targets.short_target == 0.0
    assert signal.targets.medium_target == 0.0
    assert signal.targets.long_target == 0.0


def test_short_reward_uses_clamped_target():
    legacy = calculate_stop_and_target({"close": 1.0, "atr": 1.0}, "SAT")
    levels = calculate_targets(
        close=1.0,
        atr=1.0,
        stop_loss=3.0,
        fib=FibonacciResult(),
        signal="SAT",
    )

    assert legacy["target"] == 0.01
    assert legacy["reward_pct"] == 99.0
    assert legacy["rr_ratio"] == pytest.approx(0.49, abs=0.01)
    assert levels.short_target == 0.01
    assert levels.short_reward_pct == 99.0
    assert levels.medium_reward_pct == 99.0
    assert levels.long_reward_pct == 99.0


def test_non_finite_target_inputs_fail_closed():
    legacy = calculate_stop_and_target({"close": np.inf, "atr": 1.0}, "SAT")
    levels = calculate_targets(
        close=np.inf,
        atr=np.nan,
        stop_loss=np.inf,
        fib=FibonacciResult(nearest_support=np.inf),
        signal="SAT",
    )

    assert all(np.isfinite(value) for value in legacy.values() if isinstance(value, float))
    assert legacy["target"] == 0.0
    assert levels.short_target == 0.0
    assert levels.stop_loss == 0.0
