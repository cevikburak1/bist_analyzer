"""
Smart Money Silent Accumulation scanner.

The scanner is intentionally separate from the normal technical signal engine.
It looks for long-horizon Wyckoff-style bases before breakout: seller exhaustion,
quiet OBV/CMF accumulation, and relative strength against XU100.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_HORIZON = 60
MAX_BOTTOM_DISTANCE_PCT = 15.0
SIDEWAYS_LOOKBACK = 10
SIDEWAYS_MAX_RANGE_PCT = 4.0
RS_LOOKBACK = 10
CMF_PERIOD = 20


@dataclass
class SilentAccumulationResult:
    symbol: str
    price: float
    group: int
    score: int
    rsi_divergence: bool
    volume_accumulation: bool
    relative_strength: bool
    cmf_positive: bool
    before_breakout: bool
    bottom_distance_pct: float
    range_pct: float
    relative_strength_pct: float
    rsi: float
    obv_position: str
    cmf: float
    label: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": round(self.price, 4),
            "group": self.group,
            "score": self.score,
            "rsi_divergence": self.rsi_divergence,
            "volume_accumulation": self.volume_accumulation,
            "relative_strength": self.relative_strength,
            "cmf_positive": self.cmf_positive,
            "before_breakout": self.before_breakout,
            "bottom_distance_pct": round(self.bottom_distance_pct, 2),
            "range_pct": round(self.range_pct, 2),
            "relative_strength_pct": round(self.relative_strength_pct, 2),
            "rsi": round(self.rsi, 2),
            "obv_position": self.obv_position,
            "cmf": round(self.cmf, 4),
            "label": self.label,
            "reason": self.reason,
        }


def _safe(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    return float(value)


def calculate_cmf(df: pd.DataFrame, period: int = CMF_PERIOD) -> pd.Series:
    high_low = (df["high"] - df["low"]).replace(0, np.nan)
    money_flow_multiplier = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / high_low
    money_flow_volume = money_flow_multiplier.fillna(0) * df["volume"]
    volume_sum = df["volume"].rolling(
        period, min_periods=max(5, period // 2),
    ).sum().replace(0, np.nan)
    return money_flow_volume.rolling(
        period, min_periods=max(5, period // 2),
    ).sum() / volume_sum


def _rsi_positive_divergence(df: pd.DataFrame, horizon: int) -> bool:
    if "rsi" not in df.columns or len(df) < horizon + 5:
        return False
    recent = df.tail(horizon)
    half = max(10, horizon // 2)
    previous = recent.iloc[:half]
    current = recent.iloc[half:]
    # Fiyat ve RSI diplerini bağımsız minimumlar olarak eşlemek sahte
    # uyumsuzluk üretir. RSI'ı gerçek fiyat dibinin bulunduğu bardan al.
    previous_low_idx = previous["close"].astype(float).idxmin()
    current_low_idx = current["close"].astype(float).idxmin()
    previous_price_low = _safe(previous.at[previous_low_idx, "close"])
    current_price_low = _safe(current.at[current_low_idx, "close"])
    previous_rsi_low = _safe(previous.at[previous_low_idx, "rsi"])
    current_rsi_low = _safe(current.at[current_low_idx, "rsi"])
    return current_price_low <= previous_price_low * 1.02 and current_rsi_low > previous_rsi_low


def _relative_strength(df: pd.DataFrame, index_df: pd.DataFrame) -> tuple[bool, float]:
    if df.empty or index_df.empty:
        return False, 0.0

    stock = df[["close"]].rename(columns={"close": "stock"})
    market = index_df[["close"]].rename(columns={"close": "market"})
    aligned = stock.join(market, how="inner").dropna().sort_index()
    if len(aligned) < RS_LOOKBACK + 1:
        return False, 0.0

    recent = aligned.tail(RS_LOOKBACK + 1)
    stock_start = _safe(recent["stock"].iloc[0])
    market_start = _safe(recent["market"].iloc[0])
    if stock_start <= 0 or market_start <= 0:
        return False, 0.0
    stock_perf = (_safe(recent["stock"].iloc[-1]) / stock_start - 1) * 100
    index_perf = (_safe(recent["market"].iloc[-1]) / market_start - 1) * 100
    rel = stock_perf - index_perf
    return rel > 0, rel


def scan_symbol(
    symbol: str,
    df: pd.DataFrame,
    index_df: pd.DataFrame,
    *,
    group: int,
    horizon: int = DEFAULT_HORIZON,
) -> SilentAccumulationResult | None:
    if df is None or df.empty or len(df) < max(horizon, 80):
        return None

    work = df.sort_index().copy()
    if "obv" not in work.columns:
        direction = np.sign(work["close"].diff()).fillna(0)
        work["obv"] = (direction * work["volume"]).cumsum()
    if "cmf" not in work.columns:
        work["cmf"] = calculate_cmf(work)

    recent = work.tail(horizon)
    close = _safe(work["close"].iloc[-1])
    long_low = _safe(recent["low"].min(), close)
    bottom_distance_pct = ((close - long_low) / long_low * 100) if long_low > 0 else 0.0
    before_breakout = bottom_distance_pct <= MAX_BOTTOM_DISTANCE_PCT

    sideways = work.tail(SIDEWAYS_LOOKBACK)
    range_pct = ((_safe(sideways["high"].max()) - _safe(sideways["low"].min())) / close * 100) if close > 0 else 0.0
    obv_high = _safe(work["obv"].iloc[-1]) >= _safe(work["obv"].tail(SIDEWAYS_LOOKBACK).max())
    cmf = _safe(work["cmf"].iloc[-1])
    cmf_positive = cmf > 0.05
    volume_accumulation = range_pct <= SIDEWAYS_MAX_RANGE_PCT and obv_high and cmf_positive
    rsi_divergence = _rsi_positive_divergence(work, horizon)
    relative_strength, rs_pct = _relative_strength(work, index_df)
    raw_score = sum([rsi_divergence, volume_accumulation, relative_strength])
    score = raw_score if before_breakout else max(0, raw_score - 1)

    if score >= 3:
        label = "Flawless 3/3"
    elif score == 2:
        label = "Güçlü 2/3"
    elif score == 1:
        label = "İzle 1/3"
    else:
        label = "Zayıf"

    reason_bits = []
    if rsi_divergence:
        reason_bits.append("RSI pozitif uyumsuzluk")
    if volume_accumulation:
        reason_bits.append("OBV/CMF sessiz birikim")
    if relative_strength:
        reason_bits.append("XU100'e göre güçlü")
    if before_breakout:
        reason_bits.append("uzun dönem dipten <%15")
    reason = ", ".join(reason_bits) if reason_bits else "Kriterler zayıf"

    return SilentAccumulationResult(
        symbol=symbol,
        price=close,
        group=group,
        score=score,
        rsi_divergence=rsi_divergence,
        volume_accumulation=volume_accumulation,
        relative_strength=relative_strength,
        cmf_positive=cmf_positive,
        before_breakout=before_breakout,
        bottom_distance_pct=bottom_distance_pct,
        range_pct=range_pct,
        relative_strength_pct=rs_pct,
        rsi=_safe(work["rsi"].iloc[-1]),
        obv_position="10B HIGH" if obv_high else "NORMAL",
        cmf=cmf,
        label=label,
        reason=reason,
    )


def group_symbols(symbols: list[str], group_size: int = 39) -> dict[int, list[str]]:
    groups: dict[int, list[str]] = {}
    for index, symbol in enumerate(symbols):
        group_no = index // group_size + 1
        groups.setdefault(group_no, []).append(symbol)
    return groups
