"""
3 Vadeli Hedef Fiyat Hesaplama

Kısa Vade (1-2 hafta): ATR + en yakın direnç + Fibonacci
Orta Vade (1 ay):       ATR*3 + Fib extension + swing high
Uzun Vade (3+ ay):      ATR*5 + Fib 1.618 + trend projection
"""

import logging
import math
from dataclasses import dataclass

from analysis.fibonacci import FibonacciResult

logger = logging.getLogger(__name__)


@dataclass
class TargetLevels:
    # Kısa vade (1-2 hafta)
    short_target: float = 0.0
    short_rr: float = 0.0
    short_reward_pct: float = 0.0
    # Orta vade (1 ay)
    medium_target: float = 0.0
    medium_rr: float = 0.0
    medium_reward_pct: float = 0.0
    # Uzun vade (3+ ay)
    long_target: float = 0.0
    long_rr: float = 0.0
    long_reward_pct: float = 0.0
    # Ortak stop
    stop_loss: float = 0.0
    risk_pct: float = 0.0


def _round_price(val: float) -> float:
    return round(val, 2) if math.isfinite(val) else 0.0


def _finite_float(value, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if math.isfinite(result) else default


def calculate_targets(
    close: float,
    atr: float,
    stop_loss: float,
    fib: FibonacciResult,
    signal: str,
) -> TargetLevels:
    """
    3 vadeli hedef hesaplar.

    AL sinyali → yukarı yönlü hedefler
    SAT sinyali → aşağı yönlü hedefler
    BEKLE → sıfır
    """
    close = _finite_float(close)
    atr = _finite_float(atr)
    stop_loss = _finite_float(stop_loss)
    fib = fib if isinstance(fib, FibonacciResult) else FibonacciResult()

    if close <= 0 or atr <= 0 or signal == "BEKLE":
        return TargetLevels(stop_loss=stop_loss)

    if signal == "AL":
        if not 0 < stop_loss < close:
            stop_loss = max(close * 0.01, close - atr * 2)
        risk = close - stop_loss
        return _buy_targets(close, atr, stop_loss, risk, fib)
    elif signal == "SAT":
        if stop_loss <= close:
            stop_loss = close + atr * 2
        risk = stop_loss - close
        return _sell_targets(close, atr, stop_loss, risk, fib)

    return TargetLevels(stop_loss=stop_loss)


def _buy_targets(
    close: float, atr: float, stop: float, risk: float, fib: FibonacciResult,
) -> TargetLevels:
    """AL sinyali için yukarı yönlü 3 hedef."""
    nearest_resistance = _finite_float(fib.nearest_resistance)
    fib_resistance = nearest_resistance if nearest_resistance > close else 0
    ext_levels = sorted(
        value for raw in fib.extension_levels.values()
        if (value := _finite_float(raw)) > 0
    ) if fib.extension_levels else []
    ext_above = [v for v in ext_levels if v > close]

    # ── Kısa Vade: min(1.5*ATR, en yakın direnç) ──
    atr_short = close + 1.5 * atr
    candidates = [atr_short]
    if fib_resistance > 0:
        candidates.append(fib_resistance)
    short_t = _round_price(min(candidates))
    if short_t <= close:
        short_t = _round_price(atr_short)

    # ── Orta Vade: min(3*ATR, Fib 1.272, swing high) ──
    atr_medium = close + 3.0 * atr
    candidates = [atr_medium]
    if ext_above:
        candidates.append(ext_above[0])
    swing_high = _finite_float(fib.swing_high)
    if swing_high > close:
        candidates.append(swing_high)
    medium_t = _round_price(min(candidates))
    if medium_t <= short_t:
        medium_t = _round_price(atr_medium)

    # ── Uzun Vade: max(5*ATR, Fib 1.618) ──
    atr_long = close + 5.0 * atr
    candidates = [atr_long]
    fib_1618 = _finite_float(fib.extension_levels.get(1.618, 0))
    if fib_1618 > close:
        candidates.append(fib_1618)
    long_t = _round_price(max(candidates))
    if long_t <= medium_t:
        long_t = _round_price(atr_long)

    risk_pct = round((risk / close) * 100, 2) if close > 0 else 0

    return TargetLevels(
        short_target=short_t,
        short_rr=round((short_t - close) / risk, 2) if risk > 0 else 0,
        short_reward_pct=round(((short_t - close) / close) * 100, 2),
        medium_target=medium_t,
        medium_rr=round((medium_t - close) / risk, 2) if risk > 0 else 0,
        medium_reward_pct=round(((medium_t - close) / close) * 100, 2),
        long_target=long_t,
        long_rr=round((long_t - close) / risk, 2) if risk > 0 else 0,
        long_reward_pct=round(((long_t - close) / close) * 100, 2),
        stop_loss=_round_price(stop),
        risk_pct=risk_pct,
    )


def _sell_targets(
    close: float, atr: float, stop: float, risk: float, fib: FibonacciResult,
) -> TargetLevels:
    """SAT sinyali için aşağı yönlü 3 hedef."""
    nearest_support = _finite_float(fib.nearest_support)
    fib_support = nearest_support if 0 < nearest_support < close else 0

    # ── Kısa Vade ──
    atr_short = close - 1.5 * atr
    short_t = _round_price(max(atr_short, fib_support)) if fib_support > 0 else _round_price(atr_short)
    short_t = max(0.01, short_t)

    # ── Orta Vade ──
    atr_medium = close - 3.0 * atr
    medium_t = _round_price(max(0.01, atr_medium))

    # ── Uzun Vade ──
    atr_long = close - 5.0 * atr
    long_t = _round_price(max(0.01, atr_long))

    risk_pct = round((risk / close) * 100, 2) if close > 0 else 0

    return TargetLevels(
        short_target=short_t,
        short_rr=round((close - short_t) / risk, 2) if risk > 0 else 0,
        short_reward_pct=round(((close - short_t) / close) * 100, 2),
        medium_target=medium_t,
        medium_rr=round((close - medium_t) / risk, 2) if risk > 0 else 0,
        medium_reward_pct=round(((close - medium_t) / close) * 100, 2),
        long_target=long_t,
        long_rr=round((close - long_t) / risk, 2) if risk > 0 else 0,
        long_reward_pct=round(((close - long_t) / close) * 100, 2),
        stop_loss=_round_price(stop),
        risk_pct=risk_pct,
    )
