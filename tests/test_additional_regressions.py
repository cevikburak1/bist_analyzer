from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from analysis.amd_model import _key_opens, calculate_amd_model
from analysis.anka_v2 import (
    CALIBRATION_RETURN_HURDLE_PCT,
    _calculate_calibration,
)
from analysis.backtest import (
    BacktestConfig,
    SignalDecision,
    run_long_only_backtest,
    run_morpheus_backtest,
)
from analysis.cup_handle import MAX_BREAKOUT_AGE_BARS, _params, _score_candidate
from analysis.fibonacci import (
    calculate_fib_levels,
    current_fib_zone,
    nearest_support_resistance,
)
from analysis.silent_accumulation import scan_symbol
from analysis.timeframes import _resample
from data import downloader, tradingview
from reports import web_snapshot


ISTANBUL = ZoneInfo("Europe/Istanbul")


def _ohlcv(index: pd.Index, close: float | np.ndarray = 100.0) -> pd.DataFrame:
    values = np.full(len(index), close, dtype=float) if np.isscalar(close) else np.asarray(close, dtype=float)
    return pd.DataFrame(
        {
            "open": values,
            "high": values + 1,
            "low": values - 1,
            "close": values,
            "volume": 100.0,
        },
        index=index,
    )


def test_fibonacci_zone_respects_direction_and_missing_outer_resistance():
    up_retracements, up_extensions = calculate_fib_levels(100.0, 0.0, "UP")
    down_retracements, down_extensions = calculate_fib_levels(100.0, 0.0, "DOWN")

    assert current_fib_zone(90.0, up_retracements, 100.0, 0.0, "UP") == "%0.0-%23.6 bandı"
    assert current_fib_zone(10.0, down_retracements, 100.0, 0.0, "DOWN") == "%0.0-%23.6 bandı"
    assert "extension" in current_fib_zone(-1.0, down_retracements, 100.0, 0.0, "DOWN")
    support, resistance = nearest_support_resistance(
        500.0, up_retracements, up_extensions, 100.0, 0.0,
    )
    assert support > 0
    assert resistance == 0.0
    assert max(down_extensions.values()) <= 100.0


def _cup_frame(length: int = 21) -> tuple[pd.DataFrame, dict]:
    df = _ohlcv(pd.RangeIndex(length), 95.0)
    df["atr"] = 2.0
    df.loc[2, "high"] = 100.0
    df.loc[7, "low"] = 80.0
    df.loc[12, "high"] = 100.0
    df.loc[15, "low"] = 90.0
    df.loc[16:, ["open", "high", "low", "close"]] = [99.0, 102.0, 98.0, 99.0]
    df.loc[17:, ["open", "high", "low", "close"]] = [100.5, 102.0, 100.0, 101.0]
    candidate = {
        "left_rim": {"index": 2, "price": 100.0},
        "base": {"index": 7, "price": 80.0},
        "right_rim": {"index": 12, "price": 100.0},
        "handle_low": {"index": 15, "price": 90.0},
    }
    return df, candidate


def test_cup_breakout_quality_is_scored_on_trigger_bar_and_stale_trigger_expires():
    first, candidate = _cup_frame()
    second = first.copy()
    second.loc[20, ["open", "high", "low", "close", "volume"]] = [90.0, 110.0, 89.0, 105.0, 50_000.0]

    first_score = _score_candidate(first, candidate)
    second_score = _score_candidate(second, candidate)
    assert first_score is not None and second_score is not None
    assert first_score["points"]["breakout_index"] == 17
    assert second_score["points"]["breakout_index"] == 17
    assert second_score["breakout_quality"] == first_score["breakout_quality"]
    assert _params()["max_breakout_age_bars"] == MAX_BREAKOUT_AGE_BARS

    stale, stale_candidate = _cup_frame(22)
    assert _score_candidate(stale, stale_candidate) is None


def test_cup_uses_latest_real_recross_as_breakout():
    df, candidate = _cup_frame()
    df.loc[19, ["open", "high", "low", "close"]] = [100.0, 100.0, 98.0, 99.0]
    df.loc[20, ["open", "high", "low", "close"]] = [99.5, 102.0, 99.0, 101.0]
    scored = _score_candidate(df, candidate)
    assert scored is not None
    assert scored["points"]["breakout_index"] == 20


def test_amd_key_opens_support_half_hour_anchored_hourly_bars():
    index = pd.date_range("2026-07-10 09:30", periods=8, freq="60min", tz=ISTANBUL)
    result = _key_opens(_ohlcv(index))
    assert [pd.Timestamp(item["time"]).strftime("%H:%M") for item in result] == [
        "09:30", "12:30", "15:30",
    ]


def test_amd_accumulation_boundary_is_stable_after_wall_clock_cutoff():
    prior_days = pd.date_range("2026-07-01", periods=7, freq="B")
    history_index = pd.DatetimeIndex(
        [day + pd.Timedelta(hours=hour, minutes=30) for day in prior_days[:-1] for hour in range(9, 16)]
    )
    current_day = prior_days[-1]
    prefix_a = pd.DatetimeIndex(
        [current_day + pd.Timedelta(hours=hour, minutes=30) for hour in range(9, 15)]
    )
    prefix_b = pd.DatetimeIndex(
        [current_day + pd.Timedelta(hours=hour, minutes=30) for hour in range(9, 17)]
    )
    result_a = calculate_amd_model(_ohlcv(history_index.append(prefix_a)))
    result_b = calculate_amd_model(_ohlcv(history_index.append(prefix_b)))
    assert result_a.accumulation is not None and result_b.accumulation is not None
    assert pd.Timestamp(result_a.accumulation.end_time).strftime("%H:%M") == "12:30"
    assert result_a.accumulation.end_time == result_b.accumulation.end_time


def test_anka_calibration_uses_cost_hurdle_and_discloses_trailing_method(monkeypatch):
    index = pd.date_range("2025-01-01", periods=130, freq="B")
    close = 100 * (1.001 ** np.arange(len(index)))
    df = _ohlcv(index, close)
    monkeypatch.setattr("analysis.anka_v2._historical_signal", lambda *_: "BULL")
    result = _calculate_calibration(df)
    assert result.total_success_rate == 0.0
    assert result.status != "CALIBRATED"
    assert result.return_hurdle_pct == CALIBRATION_RETURN_HURDLE_PCT
    assert result.method.endswith("not_oos")


def test_daily_cache_rejects_week_old_session_and_retries_delayed_close():
    old = _ohlcv(pd.DatetimeIndex(["2026-07-03"]))
    during = datetime(2026, 7, 10, 12, 0, tzinfo=ISTANBUL)
    assert downloader._daily_cache_session_coverage(old, now=during) is False

    delayed = _ohlcv(pd.DatetimeIndex(["2026-07-09"]))
    delayed.attrs["downloaded_at"] = "2026-07-10T15:15:00+00:00"
    assert downloader._daily_cache_session_coverage(
        delayed, now=datetime(2026, 7, 10, 18, 20, tzinfo=ISTANBUL),
    ) is True
    assert downloader._daily_cache_session_coverage(
        delayed, now=datetime(2026, 7, 10, 18, 30, tzinfo=ISTANBUL),
    ) is False


def test_snapshot_marks_yesterday_stale_after_close_and_counts_missing_universe():
    now = datetime(2026, 7, 10, 18, 16, tzinfo=ISTANBUL)
    yesterday = _ohlcv(pd.DatetimeIndex(["2026-07-09"]))
    source = web_snapshot._source_freshness(yesterday, intraday=False, now=now)
    assert source["status"] == "stale"

    payload = web_snapshot._build_freshness_payload(
        {"ONLY": yesterday},
        {"ONLY": yesterday},
        {"ONLY"},
        now=now,
        expected_count=500,
    )
    assert payload["status"] == "degraded"
    assert payload["daily"]["missing_symbol_count"] == 499


def test_tradingview_verification_requires_same_completed_session_and_volume(monkeypatch):
    now = datetime(2026, 7, 10, 18, 20, tzinfo=ISTANBUL)
    monkeypatch.setattr(
        tradingview,
        "_request_scan",
        lambda *_: {"data": [{"s": "BIST:TEST", "d": ["TEST", 10, 11, 9, 1_000, 0]}]},
    )
    reference = {"TEST": {"close": 10.0, "volume": 1_000.0, "data_as_of": "2026-07-10T00:00:00+03:00"}}
    verified = tradingview.fetch_tradingview_snapshots(
        ["TEST"], latest_indicators=reference, now=now,
    )["TEST"]
    assert verified.status == "verified"
    assert verified.comparison_reason == "same_completed_session"
    assert verified.fetched_at == now.isoformat()

    reference["TEST"]["volume"] = None
    unverified = tradingview.fetch_tradingview_snapshots(
        ["TEST"], latest_indicators=reference, now=now,
    )["TEST"]
    assert unverified.status == "unverified"


def test_backtest_rejects_explicit_incomplete_input_and_keeps_first_active_return():
    index = pd.date_range("2026-01-01", periods=5, freq="B")
    df = _ohlcv(index, np.array([100.0, 101.0, 103.0, 102.0, 104.0]))
    incomplete = df.copy()
    incomplete.attrs["contains_only_completed_bars"] = False
    with pytest.raises(ValueError, match="incomplete"):
        run_long_only_backtest(
            incomplete, lambda _: SignalDecision("BEKLE"), BacktestConfig(warmup_bars=1),
        )

    def provider(history: pd.DataFrame) -> SignalDecision:
        return SignalDecision("AL") if len(history) == 1 else SignalDecision("BEKLE")

    result = run_long_only_backtest(
        df,
        provider,
        BacktestConfig(warmup_bars=1, commission_bps=10, slippage_bps=0),
    )
    expected = result.equity_curve.pct_change().iloc[1:].dropna()
    expected_sharpe = np.sqrt(252) * expected.mean() / expected.std(ddof=1)
    assert result.metrics.sharpe == pytest.approx(expected_sharpe, abs=1e-4)


def test_morpheus_backtest_exits_on_take_profit_action_and_uses_xu100_benchmark(monkeypatch):
    index = pd.date_range("2025-01-01", periods=205, freq="B")
    stock = _ohlcv(index, np.linspace(100.0, 120.0, len(index)))
    market = _ohlcv(index, np.linspace(100.0, 80.0, len(index)))

    monkeypatch.setattr("analysis.indicators.calculate_all_indicators", lambda history: history)
    monkeypatch.setattr(
        "analysis.indicators.get_latest_indicators",
        lambda history: {"bars": len(history)},
    )
    monkeypatch.setattr("analysis.market_regime.detect_market_regime", lambda _: object())
    monkeypatch.setattr("analysis.scoring.calculate_score", lambda *_: object())

    def fake_signal(_symbol, indicators, *_args, **_kwargs):
        bars = indicators["bars"]
        if bars == 200:
            return SimpleNamespace(signal="AL", action="AL", stop_loss=0.0, target=0.0, reason="entry")
        if bars == 201:
            return SimpleNamespace(signal="BEKLE", action="KAR AL", stop_loss=0.0, target=0.0, reason="exit")
        return SimpleNamespace(signal="BEKLE", action="BEKLE", stop_loss=0.0, target=0.0, reason="hold")

    monkeypatch.setattr("analysis.signals.generate_signal", fake_signal)
    result = run_morpheus_backtest(
        stock,
        market,
        BacktestConfig(warmup_bars=200, commission_bps=0, slippage_bps=0),
    )

    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "signal"
    assert result.metrics.buy_hold_return_pct > 0
    assert result.metrics.market_benchmark_return_pct is not None
    assert result.metrics.market_benchmark_return_pct < 0
    assert result.metrics.excess_vs_market_pct is not None


def test_silent_accumulation_rejects_too_short_horizon():
    frame = _ohlcv(pd.date_range("2025-01-01", periods=100, freq="B"))
    with pytest.raises(ValueError, match="en az 20"):
        scan_symbol("TEST", frame, frame, group=1, horizon=10)


def test_month_end_resample_uses_version_agnostic_offset():
    frame = _ohlcv(pd.date_range("2025-01-01", periods=70, freq="B"))
    result = _resample(frame, pd.offsets.MonthEnd(), completed_only=False)
    assert len(result) >= 3
