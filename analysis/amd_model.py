"""
Intraday AMD (Accumulation, Manipulation, Distribution) model engine.

The detector converts lower-timeframe OHLCV bars into a dashboard-friendly
Power of 3 read: accumulation range, liquidity sweep, CISD confirmation and
fib-style distribution projections.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

MIN_INTRADAY_BARS = 36
CONTEXT_BARS = 90
ACCUMULATION_FRACTION = 0.34
EQUAL_LIQUIDITY_TOLERANCE_PCT = 0.18
DISPLACEMENT_MULTIPLIER = 1.35
PROJECTION_MULTIPLES = (1.0, 2.0, 4.0)


@dataclass
class AmdRange:
    start_index: int
    end_index: int
    start_time: str
    end_time: str
    high: float
    low: float
    midpoint: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_index": self.start_index,
            "end_index": self.end_index,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "high": self.high,
            "low": self.low,
            "midpoint": self.midpoint,
        }


@dataclass
class AmdSweep:
    direction: str
    index: int
    time: str
    price: float
    liquidity_pool: str
    rejection_pct: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "index": self.index,
            "time": self.time,
            "price": self.price,
            "liquidity_pool": self.liquidity_pool,
            "rejection_pct": self.rejection_pct,
        }


@dataclass
class AmdCisd:
    direction: str
    index: int | None
    time: str | None
    level: float
    confirmed: bool
    range_high: float
    range_low: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "index": self.index,
            "time": self.time,
            "level": self.level,
            "confirmed": self.confirmed,
            "range_high": self.range_high,
            "range_low": self.range_low,
        }


@dataclass
class AmdModelResult:
    status: str
    model_bias: str
    phase: str
    score: float
    timeframe: str
    interval: str
    summary: str
    accumulation: AmdRange | None
    manipulation: AmdRange | None
    distribution: AmdRange | None
    sweep: AmdSweep | None
    cisd: AmdCisd | None
    projections: dict[str, float]
    htf_sweep: dict[str, Any] | None
    equal_highs: list[dict[str, Any]]
    equal_lows: list[dict[str, Any]]
    key_opens: list[dict[str, Any]]
    alerts: list[str]
    params: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "model_bias": self.model_bias,
            "phase": self.phase,
            "score": self.score,
            "timeframe": self.timeframe,
            "interval": self.interval,
            "summary": self.summary,
            "accumulation": self.accumulation.as_dict() if self.accumulation else None,
            "manipulation": self.manipulation.as_dict() if self.manipulation else None,
            "distribution": self.distribution.as_dict() if self.distribution else None,
            "sweep": self.sweep.as_dict() if self.sweep else None,
            "cisd": self.cisd.as_dict() if self.cisd else None,
            "projections": self.projections,
            "htf_sweep": self.htf_sweep,
            "equal_highs": self.equal_highs,
            "equal_lows": self.equal_lows,
            "key_opens": self.key_opens,
            "alerts": self.alerts,
            "params": self.params,
        }


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    return float(value)


def _time(index: pd.Index, pos: int) -> str:
    return pd.to_datetime(index[pos]).isoformat()


def _range(df: pd.DataFrame, start: int, end: int) -> AmdRange:
    part = df.iloc[start:end + 1]
    high = _safe_float(part["high"].max())
    low = _safe_float(part["low"].min())
    return AmdRange(
        start_index=int(start),
        end_index=int(end),
        start_time=_time(df.index, start),
        end_time=_time(df.index, end),
        high=round(high, 4),
        low=round(low, 4),
        midpoint=round((high + low) * 0.5, 4),
    )


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    return pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def _empty(message: str, interval: str) -> AmdModelResult:
    return AmdModelResult(
        status="NO_DATA",
        model_bias="NEUTRAL",
        phase="NONE",
        score=0.0,
        timeframe="Intraday",
        interval=interval,
        summary=message,
        accumulation=None,
        manipulation=None,
        distribution=None,
        sweep=None,
        cisd=None,
        projections={},
        htf_sweep=None,
        equal_highs=[],
        equal_lows=[],
        key_opens=[],
        alerts=[],
        params=_params(interval),
    )


def _params(interval: str) -> dict[str, Any]:
    return {
        "min_intraday_bars": MIN_INTRADAY_BARS,
        "context_bars": CONTEXT_BARS,
        "accumulation_fraction": ACCUMULATION_FRACTION,
        "equal_liquidity_tolerance_pct": EQUAL_LIQUIDITY_TOLERANCE_PCT,
        "displacement_multiplier": DISPLACEMENT_MULTIPLIER,
        "projection_multiples": list(PROJECTION_MULTIPLES),
        "interval": interval,
        "session_aware": True,
        "timezone": "Europe/Istanbul",
    }


def _detect_sweep(df: pd.DataFrame, accumulation: AmdRange, search_start: int) -> AmdSweep | None:
    candidates: list[AmdSweep] = []
    for pos in range(search_start, len(df)):
        row = df.iloc[pos]
        low = _safe_float(row["low"])
        high = _safe_float(row["high"])
        close = _safe_float(row["close"])
        bar_range = max(high - low, 0.0001)

        if low < accumulation.low and close > accumulation.low:
            rejection = (close - low) / bar_range * 100
            candidates.append(
                AmdSweep(
                    direction="BULLISH",
                    index=pos,
                    time=_time(df.index, pos),
                    price=round(low, 4),
                    liquidity_pool="Accumulation Low",
                    rejection_pct=round(rejection, 1),
                )
            )
        if high > accumulation.high and close < accumulation.high:
            rejection = (high - close) / bar_range * 100
            candidates.append(
                AmdSweep(
                    direction="BEARISH",
                    index=pos,
                    time=_time(df.index, pos),
                    price=round(high, 4),
                    liquidity_pool="Accumulation High",
                    rejection_pct=round(rejection, 1),
                )
            )

    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.index, item.rejection_pct))


def _detect_cisd(df: pd.DataFrame, accumulation: AmdRange, sweep: AmdSweep) -> AmdCisd:
    level = accumulation.high if sweep.direction == "BULLISH" else accumulation.low
    confirmed_index: int | None = None
    for pos in range(sweep.index + 1, len(df)):
        close = _safe_float(df["close"].iloc[pos])
        if sweep.direction == "BULLISH" and close > level:
            confirmed_index = pos
            break
        if sweep.direction == "BEARISH" and close < level:
            confirmed_index = pos
            break

    sweep_to_now = df.iloc[sweep.index:]
    return AmdCisd(
        direction=sweep.direction,
        index=confirmed_index,
        time=_time(df.index, confirmed_index) if confirmed_index is not None else None,
        level=round(level, 4),
        confirmed=confirmed_index is not None,
        range_high=round(_safe_float(sweep_to_now["high"].max()), 4),
        range_low=round(_safe_float(sweep_to_now["low"].min()), 4),
    )


def _projection_levels(accumulation: AmdRange, cisd: AmdCisd) -> dict[str, float]:
    range_size = max(accumulation.high - accumulation.low, 0.0001)
    direction = 1 if cisd.direction == "BULLISH" else -1
    return {
        f"{multiple:.1f}": round(cisd.level + direction * range_size * multiple, 4)
        for multiple in PROJECTION_MULTIPLES
    }


def _daily_sweep(df: pd.DataFrame) -> dict[str, Any] | None:
    daily = df.resample("1D").agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()
    if len(daily) < 2:
        return None
    prev = daily.iloc[-2]
    current = daily.iloc[-1]
    if current["low"] < prev["low"] and current["close"] > prev["low"]:
        return {
            "direction": "BULLISH",
            "time": pd.to_datetime(daily.index[-1]).date().isoformat(),
            "level": round(_safe_float(prev["low"]), 4),
            "swept_price": round(_safe_float(current["low"]), 4),
        }
    if current["high"] > prev["high"] and current["close"] < prev["high"]:
        return {
            "direction": "BEARISH",
            "time": pd.to_datetime(daily.index[-1]).date().isoformat(),
            "level": round(_safe_float(prev["high"]), 4),
            "swept_price": round(_safe_float(current["high"]), 4),
        }
    return None


def _equal_liquidity(df: pd.DataFrame, kind: str) -> list[dict[str, Any]]:
    column = "high" if kind == "high" else "low"
    values = df[column].to_numpy(dtype=float)
    pivots: list[tuple[int, float]] = []
    for pos in range(2, len(values) - 2):
        window = values[pos - 2:pos + 3]
        if kind == "high" and values[pos] >= np.max(window):
            pivots.append((pos, float(values[pos])))
        if kind == "low" and values[pos] <= np.min(window):
            pivots.append((pos, float(values[pos])))

    levels: list[dict[str, Any]] = []
    tolerance = EQUAL_LIQUIDITY_TOLERANCE_PCT * 0.01
    for left_idx, left_price in pivots[-24:]:
        for right_idx, right_price in pivots[-24:]:
            if right_idx <= left_idx:
                continue
            average = (left_price + right_price) * 0.5
            if average <= 0:
                continue
            if abs(left_price - right_price) / average <= tolerance:
                levels.append(
                    {
                        "start_index": left_idx,
                        "end_index": right_idx,
                        "start_time": _time(df.index, left_idx),
                        "end_time": _time(df.index, right_idx),
                        "price": round(average, 4),
                    }
                )
                break
    return levels[-5:]


def _key_opens(df: pd.DataFrame) -> list[dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    wanted = {"10:00": "BIST Açılış", "13:00": "Gün Ortası", "16:00": "Kapanışa Yakın"}
    for pos, timestamp in enumerate(pd.to_datetime(df.index)):
        key = timestamp.strftime("%H:%M")
        if key not in wanted:
            continue
        session_key = (timestamp.date().isoformat(), key)
        result[session_key] = {
            "label": wanted[key],
            "time": timestamp.isoformat(),
            "price": round(_safe_float(df["open"].iloc[pos]), 4),
        }
    return list(result.values())[-6:]


def _istanbul_index(index: pd.Index) -> pd.DatetimeIndex:
    """AMD saat kurallarını her çalışma ortamında BIST yerel saatine sabitle."""
    localized = pd.DatetimeIndex(pd.to_datetime(index))
    if localized.tz is None:
        return localized.tz_localize("Europe/Istanbul")
    return localized.tz_convert("Europe/Istanbul")


def _displacement(df: pd.DataFrame, pos: int | None) -> bool:
    if pos is None or pos < 5:
        return False
    ranges = _true_range(df)
    current = _safe_float(ranges.iloc[pos])
    baseline = _safe_float(ranges.iloc[max(0, pos - 20):pos].mean(), current)
    return baseline > 0 and current >= baseline * DISPLACEMENT_MULTIPLIER


def calculate_amd_model(intraday_df: pd.DataFrame | None, interval: str = "60m") -> AmdModelResult:
    if intraday_df is None or intraday_df.empty:
        return _empty("AMD modeli için intraday veri bulunamadı.", interval)

    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(intraday_df.columns):
        return _empty("AMD modeli için OHLCV kolonları eksik.", interval)

    df = (
        intraday_df.dropna(subset=["open", "high", "low", "close"])
        .sort_index()
        .tail(CONTEXT_BARS)
        .copy()
    )
    df.index = _istanbul_index(df.index)
    if len(df) < MIN_INTRADAY_BARS:
        return _empty("AMD modeli için yeterli intraday bar yok.", interval)

    # Accumulation/manipulation aynı işlem seansına ait olmalıdır. Eski kod
    # 90 barlık pencerenin ilk %34'ünü (birkaç farklı günü) tek range yapıyordu.
    session_dates = np.asarray(df.index.date)
    latest_session = session_dates[-1]
    session_positions = np.flatnonzero(session_dates == latest_session)
    if len(session_positions) < 3:
        return _empty("Güncel BIST seansında AMD için yeterli bar yok.", interval)
    session_start = int(session_positions[0])
    session_size = len(session_positions)
    accumulation_bars = min(
        max(2, int(np.ceil(session_size * ACCUMULATION_FRACTION))),
        session_size - 1,
    )
    accumulation_end = session_start + accumulation_bars - 1
    accumulation = _range(df, session_start, accumulation_end)
    sweep = _detect_sweep(df, accumulation, accumulation_end + 1)
    htf_sweep = _daily_sweep(df)
    equal_highs = _equal_liquidity(df, "high")
    equal_lows = _equal_liquidity(df, "low")
    key_opens = _key_opens(df)

    if sweep is None:
        compression = (accumulation.high - accumulation.low) / max(_safe_float(df["close"].iloc[-1]), 0.0001) * 100
        score = max(10.0, min(45.0, 45.0 - compression * 2))
        return AmdModelResult(
            status="DEVELOPING",
            model_bias="NEUTRAL",
            phase="ACCUMULATION",
            score=round(score, 1),
            timeframe="Intraday",
            interval=interval,
            summary="Fiyat accumulation aralığında; henüz net liquidity sweep oluşmadı.",
            accumulation=accumulation,
            manipulation=None,
            distribution=None,
            sweep=None,
            cisd=None,
            projections={},
            htf_sweep=htf_sweep,
            equal_highs=equal_highs,
            equal_lows=equal_lows,
            key_opens=key_opens,
            alerts=[],
            params=_params(interval),
        )

    cisd = _detect_cisd(df, accumulation, sweep)
    manipulation_end = cisd.index if cisd.index is not None else len(df) - 1
    manipulation = _range(df, accumulation_end + 1, manipulation_end)
    distribution = _range(df, cisd.index, len(df) - 1) if cisd.index is not None else None
    projections = _projection_levels(accumulation, cisd) if cisd.confirmed else {}
    has_displacement = _displacement(df, cisd.index)

    score = 48.0 + sweep.rejection_pct * 0.18
    alerts = [f"{sweep.liquidity_pool} sweep"]
    phase = "MANIPULATION"
    status = "DEVELOPING"
    if cisd.confirmed:
        score += 24.0
        phase = "DISTRIBUTION"
        status = "CONFIRMED"
        alerts.append("CISD confirmed")
    if has_displacement:
        score += 12.0
        alerts.append("Displacement candle")
    if htf_sweep and htf_sweep["direction"] == sweep.direction:
        score += 8.0
        alerts.append("HTF sweep aligned")
    score = round(max(0.0, min(score, 100.0)), 1)

    bias_label = "Bullish" if sweep.direction == "BULLISH" else "Bearish"
    summary = (
        f"{bias_label} AMD modeli: liquidity sweep sonrası "
        f"{'CISD doğrulandı' if cisd.confirmed else 'CISD bekleniyor'}."
    )

    return AmdModelResult(
        status=status,
        model_bias=sweep.direction,
        phase=phase,
        score=score,
        timeframe="Intraday",
        interval=interval,
        summary=summary,
        accumulation=accumulation,
        manipulation=manipulation,
        distribution=distribution,
        sweep=sweep,
        cisd=cisd,
        projections=projections,
        htf_sweep=htf_sweep,
        equal_highs=equal_highs,
        equal_lows=equal_lows,
        key_opens=key_opens,
        alerts=alerts,
        params=_params(interval),
    )
