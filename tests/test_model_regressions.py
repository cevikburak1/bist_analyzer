from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.amd_model import calculate_amd_model
from analysis.anka_v2 import _calculate_calibration
from analysis.backtest import BacktestConfig, SignalDecision, run_long_only_backtest
from analysis.commentary import _signal_strength
from analysis.fibonacci import find_swing_points
from analysis.timeframes import _resample
from config import STRONG_BUY_THRESHOLD
from data import tradingview


def _ohlc(index: pd.Index, close: np.ndarray | list[float]) -> pd.DataFrame:
    values = np.asarray(close, dtype=float)
    return pd.DataFrame(
        {
            "open": values,
            "high": values + 1,
            "low": values - 1,
            "close": values,
            "volume": 1_000.0,
        },
        index=index,
    )


def test_backtest_executes_decisions_at_next_open_with_costs():
    index = pd.date_range("2026-01-01", periods=7, freq="B")
    df = _ohlc(index, [100, 101, 102, 103, 104, 105, 106])

    def provider(history: pd.DataFrame) -> SignalDecision:
        if len(history) == 2:
            return SignalDecision("AL")
        if len(history) == 4:
            return SignalDecision("SAT")
        return SignalDecision("BEKLE")

    result = run_long_only_backtest(
        df,
        provider,
        BacktestConfig(
            initial_capital=10_000,
            allocation=1.0,
            commission_bps=10,
            slippage_bps=10,
            warmup_bars=2,
        ),
    )

    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_time == index[2].isoformat()
    assert trade.exit_time == index[4].isoformat()
    assert trade.entry_price > df.loc[index[2], "open"]
    assert trade.exit_price < df.loc[index[4], "open"]
    assert result.metrics.final_equity < 10_000 * (104 / 102)


def test_backtest_uses_conservative_stop_when_stop_and_target_both_hit():
    index = pd.date_range("2026-02-01", periods=3, freq="B")
    df = _ohlc(index, [100, 100, 100])
    df.loc[index[1], ["high", "low"]] = [106.0, 94.0]

    def provider(history: pd.DataFrame) -> SignalDecision:
        return SignalDecision("AL", stop_loss=95.0, target=105.0)

    result = run_long_only_backtest(
        df,
        provider,
        BacktestConfig(warmup_bars=1, commission_bps=0, slippage_bps=0),
    )
    assert result.trades[0].exit_reason == "stop"
    assert result.trades[0].exit_price == 95.0


def test_backtest_skips_entry_when_next_open_gaps_through_risk_levels():
    index = pd.date_range("2026-02-01", periods=4, freq="B")
    df = _ohlc(index, [100, 90, 91, 92])

    def provider(history: pd.DataFrame) -> SignalDecision:
        if len(history) == 1:
            return SignalDecision("AL", stop_loss=95.0, target=105.0)
        return SignalDecision("BEKLE")

    result = run_long_only_backtest(
        df,
        provider,
        BacktestConfig(warmup_bars=1, commission_bps=0, slippage_bps=0),
    )
    assert result.trades == []
    assert result.metrics.final_equity == result.metrics.initial_capital


def test_fibonacci_fallback_keeps_downtrend_direction():
    index = pd.date_range("2026-01-01", periods=12, freq="B")
    df = _ohlc(index, np.linspace(20, 10, len(index)))
    _, _, direction = find_swing_points(df, depth=5)
    assert direction == "DOWN"


def test_tradingview_missing_reference_cannot_be_verified(monkeypatch):
    monkeypatch.setattr(
        tradingview,
        "_request_scan",
        lambda *_: {"data": [{"s": "BIST:TEST", "d": ["TEST", None, 10, 9, None, 0]}]},
    )
    snapshot = tradingview.fetch_tradingview_snapshots(
        ["TEST"], latest_indicators={"TEST": {"close": 10.0, "volume": 1_000.0}},
    )["TEST"]
    assert snapshot.status == "unverified"


def test_commentary_uses_additive_morpheus_thresholds():
    assert _signal_strength(170, "AL") == "AL"
    assert _signal_strength(STRONG_BUY_THRESHOLD, "AL") == "GÜÇLÜ AL"


def test_resample_drops_partial_week_but_keeps_completed_friday():
    partial_index = pd.date_range("2026-01-05", periods=8, freq="B")  # Wed 14 Jan
    partial = _ohlc(partial_index, np.linspace(10, 11, len(partial_index)))
    weekly_partial = _resample(partial, "W-FRI")
    assert len(weekly_partial) == 1

    complete_index = pd.date_range("2026-01-05", periods=10, freq="B")
    complete = _ohlc(complete_index, np.linspace(10, 11, len(complete_index)))
    weekly_complete = _resample(complete, "W-FRI")
    assert len(weekly_complete) == 2


def test_anka_one_historical_signal_is_not_called_calibrated(monkeypatch):
    index = pd.date_range("2025-01-01", periods=120, freq="B")
    df = _ohlc(index, np.linspace(10, 20, len(index)))
    for column, value in {
        "anka_momentum_pct": 2.0,
        "anka_valley_score": 20.0,
        "anka_lower_wing": 5.0,
        "anka_upper_wing": 30.0,
        "anka_body": 12.0,
        "anka_inner_upper_wing": 11.0,
        "anka_inner_lower_wing": 9.0,
    }.items():
        df[column] = value

    chosen = index[-20]

    def one_signal(row: pd.Series, _prev: pd.Series) -> str:
        return "BULL" if row.name == chosen else "NONE"

    monkeypatch.setattr("analysis.anka_v2._historical_signal", one_signal)
    result = _calculate_calibration(df)
    assert result.total_signals == 1
    assert result.status == "INSUFFICIENT"


def test_amd_accumulation_is_confined_to_latest_session():
    days = pd.date_range("2026-01-05", periods=15, freq="B")
    timestamps = [
        day + pd.Timedelta(hours=hour)
        for day in days
        for hour in range(10, 16)
    ]
    index = pd.DatetimeIndex(timestamps)
    df = _ohlc(index, np.linspace(100, 102, len(index)))
    result = calculate_amd_model(df)
    assert result.accumulation is not None
    assert pd.Timestamp(result.accumulation.start_time).date() == days[-1].date()
    assert pd.Timestamp(result.accumulation.end_time).date() == days[-1].date()
