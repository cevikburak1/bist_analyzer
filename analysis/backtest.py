"""Point-in-time, next-bar execution backtest helpers.

This module deliberately keeps execution deterministic and long-only.  Signal
providers only receive data available through the current close; orders are
executed at the following bar's open with configurable commission and slippage.
It is a validation tool, not a promise of future performance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from math import sqrt
from typing import Callable, Optional

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 100_000.0
    allocation: float = 0.95
    commission_bps: float = 10.0
    slippage_bps: float = 10.0
    warmup_bars: int = 220

    def __post_init__(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if not 0 < self.allocation <= 1:
            raise ValueError("allocation must be in (0, 1]")
        if self.commission_bps < 0 or self.slippage_bps < 0:
            raise ValueError("cost assumptions cannot be negative")
        if self.warmup_bars < 1:
            raise ValueError("warmup_bars must be at least 1")


@dataclass(frozen=True)
class SignalDecision:
    signal: str
    stop_loss: float | None = None
    target: float | None = None
    reason: str = ""

    def __post_init__(self) -> None:
        if self.signal not in {"AL", "SAT", "BEKLE"}:
            raise ValueError("signal must be AL, SAT or BEKLE")


@dataclass
class BacktestTrade:
    entry_time: str
    exit_time: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_commission: float
    exit_commission: float
    pnl: float
    return_pct: float
    bars_held: int
    exit_reason: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class BacktestMetrics:
    initial_capital: float
    final_equity: float
    total_return_pct: float
    cagr_pct: float | None
    buy_hold_return_pct: float | None
    excess_vs_buy_hold_pct: float | None
    market_benchmark_return_pct: float | None
    excess_vs_market_pct: float | None
    max_drawdown_pct: float
    sharpe: float | None
    trade_count: int
    win_rate_pct: float | None
    profit_factor: float | None
    exposure_pct: float
    commission_bps: float
    slippage_bps: float

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class BacktestResult:
    metrics: BacktestMetrics
    trades: list[BacktestTrade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))

    def as_dict(self, *, include_equity_curve: bool = False) -> dict:
        payload = {
            "metrics": self.metrics.as_dict(),
            "trades": [trade.as_dict() for trade in self.trades],
            "methodology": {
                "execution": "next_bar_open",
                "positioning": "long_only_single_asset",
                "intrabar_conflict": "stop_first_conservative",
                "point_in_time": True,
                "out_of_sample_or_walk_forward": False,
                "fractional_quantity": True,
                "liquidity_and_limit_fill_model": False,
                "survivorship_bias_controlled": False,
            },
        }
        if include_equity_curve:
            payload["equity_curve"] = [
                {"date": pd.Timestamp(idx).isoformat(), "equity": round(float(value), 4)}
                for idx, value in self.equity_curve.items()
            ]
        return payload


SignalProvider = Callable[[pd.DataFrame], SignalDecision]


def _prepare_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    required = {"open", "high", "low", "close"}
    if df is None or df.empty or not required.issubset(df.columns):
        raise ValueError("backtest requires non-empty open/high/low/close data")

    work = df.sort_index().copy()
    work = work.loc[~work.index.duplicated(keep="last")]
    if df.attrs.get("contains_only_completed_bars") is False:
        raise ValueError("backtest input explicitly contains incomplete bars")
    if df.attrs.get("last_bar_closed") is False and len(work) > 1:
        work = work.iloc[:-1].copy()
    numeric = ["open", "high", "low", "close"]
    work[numeric] = work[numeric].apply(pd.to_numeric, errors="coerce")
    if work[numeric].isna().any().any():
        raise ValueError("OHLC data contains missing or non-numeric values")
    if (work[numeric] <= 0).any().any():
        raise ValueError("OHLC prices must be positive")
    if (
        (work["high"] < work[["open", "close", "low"]].max(axis=1))
        | (work["low"] > work[["open", "close", "high"]].min(axis=1))
    ).any():
        raise ValueError("OHLC high/low invariants are violated")
    return work


def _exit_fill(reference_price: float, slippage: float) -> float:
    return max(0.0001, reference_price * (1 - slippage))


def run_long_only_backtest(
    df: pd.DataFrame,
    signal_provider: SignalProvider,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run a single-asset point-in-time backtest.

    The provider is called after each completed bar and receives only the slice
    ending at that bar.  Its decision is never filled at the same close.
    """
    cfg = config or BacktestConfig()
    work = _prepare_ohlcv(df)
    if len(work) <= cfg.warmup_bars:
        raise ValueError("not enough bars after warmup for next-bar execution")

    commission = cfg.commission_bps / 10_000.0
    slippage = cfg.slippage_bps / 10_000.0
    cash = float(cfg.initial_capital)
    position: dict | None = None
    pending: tuple[str, SignalDecision, int] | None = None
    trades: list[BacktestTrade] = []
    equity_values: list[float] = []
    equity_index: list[pd.Timestamp] = []
    exposed_bars = 0

    def close_position(
        timestamp: pd.Timestamp,
        bar_index: int,
        fill_price: float,
        reason: str,
    ) -> None:
        nonlocal cash, position
        if position is None:
            return
        gross = position["quantity"] * fill_price
        exit_commission = gross * commission
        cash += gross - exit_commission
        entry_outlay = position["entry_outlay"]
        pnl = (gross - exit_commission) - entry_outlay
        trades.append(
            BacktestTrade(
                entry_time=position["entry_time"],
                exit_time=timestamp.isoformat(),
                entry_price=round(position["entry_price"], 6),
                exit_price=round(fill_price, 6),
                quantity=round(position["quantity"], 8),
                entry_commission=round(position["entry_commission"], 6),
                exit_commission=round(exit_commission, 6),
                pnl=round(pnl, 6),
                return_pct=round((pnl / entry_outlay) * 100, 4),
                bars_held=bar_index - position["entry_bar"],
                exit_reason=reason,
            )
        )
        position = None

    for bar_index, (raw_timestamp, row) in enumerate(work.iterrows()):
        timestamp = pd.Timestamp(raw_timestamp)

        # Previous close's decision is filled at this bar's open.
        if pending is not None:
            order, decision, decision_bar = pending
            if order == "EXIT" and position is not None:
                close_position(
                    timestamp,
                    bar_index,
                    _exit_fill(float(row["open"]), slippage),
                    "signal",
                )
            elif order == "ENTER" and position is None:
                entry_price = float(row["open"]) * (1 + slippage)
                planned_stop = (
                    float(decision.stop_loss)
                    if decision.stop_loss is not None
                    else None
                )
                planned_target = (
                    float(decision.target)
                    if decision.target is not None
                    else None
                )

                # A gap through the planned risk boundary invalidates the
                # setup.  Entering anyway and silently discarding the stop (or
                # a target already left behind) would give the simulation a
                # risk profile the signal never authorised.
                invalid_gap = (
                    planned_stop is not None
                    and planned_stop > 0
                    and entry_price <= planned_stop
                ) or (
                    planned_target is not None
                    and planned_target > 0
                    and entry_price >= planned_target
                )
                if not invalid_gap:
                    budget = cash * cfg.allocation
                    quantity = budget / (entry_price * (1 + commission))
                    gross = quantity * entry_price
                    entry_commission = gross * commission
                    cash -= gross + entry_commission
                    stop = (
                        planned_stop
                        if planned_stop is not None
                        and 0 < planned_stop < entry_price
                        else None
                    )
                    target = (
                        planned_target
                        if planned_target is not None and planned_target > entry_price
                        else None
                    )
                    position = {
                        "entry_time": timestamp.isoformat(),
                        "entry_bar": bar_index,
                        "entry_price": entry_price,
                        "quantity": quantity,
                        "entry_commission": entry_commission,
                        "entry_outlay": gross + entry_commission,
                        "stop": stop,
                        "target": target,
                        "decision_bar": decision_bar,
                    }
            pending = None

        # Gap fills use the open; if stop and target both occur intrabar, the
        # conservative stop-first assumption prevents optimistic bias.
        if position is not None:
            exposed_bars += 1
            stop = position["stop"]
            target = position["target"]
            if stop is not None and float(row["open"]) <= stop:
                close_position(
                    timestamp, bar_index, _exit_fill(float(row["open"]), slippage), "stop_gap",
                )
            elif target is not None and float(row["open"]) >= target:
                close_position(
                    timestamp, bar_index, _exit_fill(float(row["open"]), slippage), "target_gap",
                )
            elif stop is not None and float(row["low"]) <= stop:
                close_position(
                    timestamp, bar_index, _exit_fill(stop, slippage), "stop",
                )
            elif target is not None and float(row["high"]) >= target:
                close_position(
                    timestamp, bar_index, _exit_fill(target, slippage), "target",
                )

        mark_to_market = cash
        if position is not None:
            mark_to_market += position["quantity"] * float(row["close"])
        equity_values.append(mark_to_market)
        equity_index.append(timestamp)

        if bar_index >= cfg.warmup_bars - 1 and bar_index < len(work) - 1:
            history = work.iloc[: bar_index + 1].copy()
            decision = signal_provider(history)
            if not isinstance(decision, SignalDecision):
                raise TypeError("signal_provider must return SignalDecision")
            if position is None and decision.signal == "AL":
                pending = ("ENTER", decision, bar_index)
            elif position is not None and decision.signal == "SAT":
                pending = ("EXIT", decision, bar_index)

    if position is not None:
        last_time = pd.Timestamp(work.index[-1])
        close_position(
            last_time,
            len(work) - 1,
            _exit_fill(float(work["close"].iloc[-1]), slippage),
            "end_of_data",
        )
        equity_values[-1] = cash

    equity_curve = pd.Series(equity_values, index=pd.DatetimeIndex(equity_index), name="equity")
    # Calculate returns first, then trim the warmup.  This retains the first
    # active bar's return from warmup-1 -> warmup (including entry costs).
    returns = (
        equity_curve.pct_change()
        .iloc[cfg.warmup_bars:]
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    running_max = equity_curve.cummax()
    max_drawdown = float((equity_curve / running_max - 1).min() * 100)
    total_return = (cash / cfg.initial_capital - 1) * 100
    elapsed_days = max(
        1,
        (equity_curve.index[-1] - equity_curve.index[cfg.warmup_bars]).days,
    )
    cagr = ((cash / cfg.initial_capital) ** (365.25 / elapsed_days) - 1) * 100
    sharpe = None
    if len(returns) > 1 and float(returns.std(ddof=1)) > 0:
        sharpe = float(sqrt(252) * returns.mean() / returns.std(ddof=1))

    wins = [trade for trade in trades if trade.pnl > 0]
    losses = [trade for trade in trades if trade.pnl < 0]
    win_rate = (len(wins) / len(trades) * 100) if trades else None
    gross_profit = sum(trade.pnl for trade in wins)
    gross_loss = abs(sum(trade.pnl for trade in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    benchmark_start = float(work["open"].iloc[cfg.warmup_bars]) * (1 + slippage)
    benchmark_end = _exit_fill(float(work["close"].iloc[-1]), slippage)
    buy_hold_return = (
        ((benchmark_end * (1 - commission)) / (benchmark_start * (1 + commission))) - 1
    ) * 100
    excess_vs_buy_hold = total_return - buy_hold_return
    eligible_bars = max(1, len(work) - cfg.warmup_bars)

    metrics = BacktestMetrics(
        initial_capital=round(cfg.initial_capital, 2),
        final_equity=round(cash, 2),
        total_return_pct=round(total_return, 4),
        cagr_pct=round(cagr, 4),
        buy_hold_return_pct=round(buy_hold_return, 4),
        excess_vs_buy_hold_pct=round(excess_vs_buy_hold, 4),
        market_benchmark_return_pct=None,
        excess_vs_market_pct=None,
        max_drawdown_pct=round(max_drawdown, 4),
        sharpe=round(sharpe, 4) if sharpe is not None else None,
        trade_count=len(trades),
        win_rate_pct=round(win_rate, 2) if win_rate is not None else None,
        profit_factor=round(profit_factor, 4) if profit_factor is not None else None,
        exposure_pct=round(exposed_bars / eligible_bars * 100, 2),
        commission_bps=cfg.commission_bps,
        slippage_bps=cfg.slippage_bps,
    )
    return BacktestResult(metrics=metrics, trades=trades, equity_curve=equity_curve)


def run_morpheus_backtest(
    stock_df: pd.DataFrame,
    index_df: pd.DataFrame,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Backtest the repository's Morpheus decision path point-in-time."""
    from analysis.indicators import calculate_all_indicators, get_latest_indicators
    from analysis.market_regime import detect_market_regime
    from analysis.scoring import calculate_score
    from analysis.signals import generate_signal

    cfg = config or BacktestConfig()
    market = _prepare_ohlcv(index_df)

    def provider(history: pd.DataFrame) -> SignalDecision:
        timestamp = history.index[-1]
        market_history = market.loc[market.index <= timestamp]
        if len(market_history) < 200:
            return SignalDecision("BEKLE", reason="insufficient market history")
        enriched = calculate_all_indicators(history)
        indicators = get_latest_indicators(enriched)
        regime = detect_market_regime(market_history)
        score = calculate_score(indicators, regime, enriched)
        signal = generate_signal("BACKTEST", indicators, score, regime)
        # ``KAR AL`` is intentionally represented as a neutral base signal in
        # the live object so a fresh short is not opened.  For an existing
        # long-only backtest position it is nevertheless an exit instruction.
        execution_signal = "SAT" if signal.action == "KAR AL" else signal.signal
        return SignalDecision(
            signal=execution_signal,
            stop_loss=signal.stop_loss or None,
            target=signal.target or None,
            reason=signal.reason,
        )

    result = run_long_only_backtest(stock_df, provider, cfg)
    stock = _prepare_ohlcv(stock_df)

    # The generic benchmark is the same stock's buy-and-hold return.  Add the
    # actual XU100 comparison separately so the two baselines cannot be
    # confused in reports.
    start_time = pd.Timestamp(stock.index[cfg.warmup_bars])
    end_time = pd.Timestamp(stock.index[-1])
    market_compare = market.copy()
    compare_index = pd.DatetimeIndex(market_compare.index)
    if start_time.tzinfo is not None:
        if compare_index.tz is None:
            compare_index = compare_index.tz_localize(start_time.tzinfo)
        else:
            compare_index = compare_index.tz_convert(start_time.tzinfo)
    elif compare_index.tz is not None:
        compare_index = compare_index.tz_localize(None)
    market_compare.index = compare_index
    market_window = market_compare.loc[
        (market_compare.index >= start_time) & (market_compare.index <= end_time)
    ]
    if not market_window.empty:
        commission = cfg.commission_bps / 10_000.0
        slippage = cfg.slippage_bps / 10_000.0
        market_start = float(market_window["open"].iloc[0]) * (1 + slippage)
        market_end = _exit_fill(float(market_window["close"].iloc[-1]), slippage)
        market_return = (
            ((market_end * (1 - commission)) / (market_start * (1 + commission))) - 1
        ) * 100
        result.metrics.market_benchmark_return_pct = round(market_return, 4)
        result.metrics.excess_vs_market_pct = round(
            result.metrics.total_return_pct - market_return, 4,
        )
    return result
