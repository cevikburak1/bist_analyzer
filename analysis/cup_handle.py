"""
Cup and Handle Quality pattern engine.

The detector maps a complete cup-and-handle lifecycle: left rim, cup base,
right rim recovery, handle pullback, breakout quality, and measured projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

PIVOT_SPAN = 3
MIN_CUP_BARS = 8
MAX_CUP_BARS = 280
MIN_HANDLE_BARS = 2
MAX_RIM_VARIANCE_PCT = 78.0
MIN_CUP_DEPTH_ATR = 0.25
HANDLE_MIN_PCT = 1.5
HANDLE_MAX_PCT = 98.0
VOLUME_BASELINE = 50
MIN_SETUP_SCORE = 28.0
MIN_BREAKOUT_QUALITY = 16.0
MIN_PATTERN_SCORE = 36.0
TARGET_PROJECTION_BARS = 64
MAX_BREAKOUT_AGE_BARS = 3


@dataclass
class CupHandleQuality:
    status: str
    is_detected: bool
    is_confirmed: bool
    cup_symmetry: float | None
    handle_depth_pct: float | None
    breakout_quality: float | None
    score: float | None
    rim_price: float | None
    target_price: float | None
    cup_depth: float | None
    message: str
    points: dict[str, Any]
    params: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "is_detected": self.is_detected,
            "is_confirmed": self.is_confirmed,
            "cup_symmetry": self.cup_symmetry,
            "handle_depth_pct": self.handle_depth_pct,
            "breakout_quality": self.breakout_quality,
            "score": self.score,
            "rim_price": self.rim_price,
            "target_price": self.target_price,
            "cup_depth": self.cup_depth,
            "message": self.message,
            "points": self.points,
            "params": self.params,
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


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _params() -> dict[str, Any]:
    return {
        "pivot_span": PIVOT_SPAN,
        "min_cup_bars": MIN_CUP_BARS,
        "max_cup_bars": MAX_CUP_BARS,
        "min_handle_bars": MIN_HANDLE_BARS,
        "max_rim_variance_pct": MAX_RIM_VARIANCE_PCT,
        "min_cup_depth_atr": MIN_CUP_DEPTH_ATR,
        "handle_min_pct": HANDLE_MIN_PCT,
        "handle_max_pct": HANDLE_MAX_PCT,
        "volume_baseline": VOLUME_BASELINE,
        "min_setup_score": MIN_SETUP_SCORE,
        "min_breakout_quality": MIN_BREAKOUT_QUALITY,
        "min_pattern_score": MIN_PATTERN_SCORE,
        "target_projection_bars": TARGET_PROJECTION_BARS,
        "max_breakout_age_bars": MAX_BREAKOUT_AGE_BARS,
    }


def _empty(message: str = "Nitelikli cup-and-handle yapısı bulunamadı.") -> CupHandleQuality:
    return CupHandleQuality(
        status="NONE",
        is_detected=False,
        is_confirmed=False,
        cup_symmetry=None,
        handle_depth_pct=None,
        breakout_quality=None,
        score=None,
        rim_price=None,
        target_price=None,
        cup_depth=None,
        message=message,
        points={},
        params=_params(),
    )


def _find_pivots(df: pd.DataFrame, span: int = PIVOT_SPAN) -> list[dict[str, Any]]:
    pivots: list[dict[str, Any]] = []
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    for idx in range(span, len(df) - span):
        high_window = highs[idx - span:idx + span + 1]
        low_window = lows[idx - span:idx + span + 1]
        if highs[idx] >= np.max(high_window):
            _store_pivot(pivots, "H", idx, highs[idx])
        if lows[idx] <= np.min(low_window):
            _store_pivot(pivots, "L", idx, lows[idx])
    return pivots[-60:]


def _store_pivot(pivots: list[dict[str, Any]], kind: str, index: int, price: float) -> None:
    if pivots and pivots[-1]["kind"] == kind:
        should_replace = price >= pivots[-1]["price"] if kind == "H" else price <= pivots[-1]["price"]
        if should_replace:
            pivots[-1] = {"kind": kind, "index": index, "price": float(price)}
        return
    pivots.append({"kind": kind, "index": index, "price": float(price)})


def _atr(df: pd.DataFrame) -> pd.Series:
    if "atr" in df.columns:
        return df["atr"].astype(float)
    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()


def _candidate_from_sequence(df: pd.DataFrame, pivots: list[dict[str, Any]], start: int, use_developing: bool) -> dict[str, Any] | None:
    left = pivots[start]
    base = pivots[start + 1]
    right = pivots[start + 2]
    if left["kind"] != "H" or base["kind"] != "L" or right["kind"] != "H":
        return None
    if use_developing:
        right_index = int(right["index"])
        handle_slice = df.iloc[right_index:]
        if len(handle_slice) < MIN_HANDLE_BARS:
            return None
        handle_offset = int(handle_slice["low"].astype(float).argmin())
        handle = {
            "kind": "L",
            "index": right_index + handle_offset,
            "price": float(handle_slice["low"].iloc[handle_offset]),
        }
    else:
        if start + 3 >= len(pivots) or pivots[start + 3]["kind"] != "L":
            return None
        handle = pivots[start + 3]

    return {
        "left_rim": left,
        "base": base,
        "right_rim": right,
        "handle_low": handle,
    }


def _score_candidate(df: pd.DataFrame, candidate: dict[str, Any]) -> dict[str, Any] | None:
    left = candidate["left_rim"]
    base = candidate["base"]
    right = candidate["right_rim"]
    handle = candidate["handle_low"]

    left_idx = int(left["index"])
    base_idx = int(base["index"])
    right_idx = int(right["index"])
    handle_idx = int(handle["index"])
    if not (left_idx < base_idx < right_idx < handle_idx):
        return None

    rim_average = (left["price"] + right["price"]) * 0.5
    rim_price = max(left["price"], right["price"])
    cup_depth = rim_average - base["price"]
    cup_bars = right_idx - left_idx
    handle_bars = handle_idx - right_idx
    if cup_depth <= 0 or cup_bars < MIN_CUP_BARS or cup_bars > MAX_CUP_BARS or handle_bars < MIN_HANDLE_BARS:
        return None

    atr_value = _safe(_atr(df).iloc[-1], 0.0)
    rim_variance = abs(left["price"] - right["price"]) / cup_depth
    handle_depth = (rim_price - handle["price"]) / cup_depth
    if (
        cup_depth < atr_value * MIN_CUP_DEPTH_ATR
        or rim_variance > MAX_RIM_VARIANCE_PCT * 0.01
        or handle_depth < HANDLE_MIN_PCT * 0.01
        or handle_depth > HANDLE_MAX_PCT * 0.01
        or handle["price"] <= base["price"] + cup_depth * 0.01
    ):
        return None

    left_bars = base_idx - left_idx
    right_bars = right_idx - base_idx
    rim_score = 100 * (1 - _clamp(rim_variance / (MAX_RIM_VARIANCE_PCT * 0.01), 0, 1))
    time_score = 100 * _clamp(min(left_bars, right_bars) / max(left_bars, right_bars), 0, 1)
    cup_symmetry = rim_score * 0.5 + time_score * 0.5
    handle_center = (HANDLE_MIN_PCT + HANDLE_MAX_PCT) * 0.005
    handle_width = max((HANDLE_MAX_PCT - HANDLE_MIN_PCT) * 0.005, 0.01)
    handle_depth_score = 100 * (1 - _clamp(abs(handle_depth - handle_center) / handle_width, 0, 1))
    handle_time_score = 100 * (1 - _clamp(handle_bars / max(cup_bars * 1.65, 1), 0, 1))
    handle_quality = handle_depth_score * 0.66 + handle_time_score * 0.34

    post_handle = df["close"].astype(float).iloc[handle_idx + 1:]
    above_rim = post_handle > rim_price
    # A trigger is a crossing, not every bar that remains above the rim.  Use
    # the latest crossing so a genuine fresh re-breakout is not hidden by an
    # old historical crossing.
    breakout_crosses = above_rim & ~above_rim.shift(1, fill_value=False)
    breakout_hits = np.flatnonzero(breakout_crosses.to_numpy())
    breakout_idx = (
        handle_idx + 1 + int(breakout_hits[-1]) if len(breakout_hits) else None
    )
    breakout_is_recent = (
        breakout_idx is not None
        and (len(df) - 1 - breakout_idx) <= MAX_BREAKOUT_AGE_BARS
    )
    max_developing_age = max(20, cup_bars // 2)
    if breakout_idx is None and (len(df) - 1 - handle_idx) > max_developing_age:
        return None
    if breakout_idx is not None and not breakout_is_recent:
        # Kırılım haftalar önce gerçekleştiyse formasyon artık güncel bir tetik değildir.
        return None

    current_close = _safe(df["close"].iloc[-1])
    breakout_quality = 0.0
    if breakout_idx is not None:
        breakout_bar = df.iloc[breakout_idx]
        close = _safe(breakout_bar.get("close"))
        open_ = _safe(breakout_bar.get("open"))
        high = _safe(breakout_bar.get("high"))
        low = _safe(breakout_bar.get("low"))
        volume = _safe(breakout_bar.get("volume"))
        volume_average = _safe(
            df["volume"].shift(1).rolling(
                VOLUME_BASELINE, min_periods=10,
            ).mean().iloc[breakout_idx],
            volume,
        )
        breakout_atr = _safe(_atr(df).iloc[breakout_idx], atr_value)
        bar_range = max(high - low, 0.0001)
        breakout_distance_score = 100 * _clamp(
            (close - rim_price) / max(breakout_atr, 0.0001), 0, 1,
        )
        volume_score = (
            100 * _clamp(((volume / volume_average) - 0.8) / 0.9, 0, 1)
            if volume_average > 0 else 50
        )
        # Bearish bir kırılım mumu yalnızca gövdesi büyük diye boğa
        # kalitesi almamalı.
        body_score = 100 * _clamp((close - open_) / bar_range * 1.25, 0, 1)
        close_score = 100 * _clamp((close - low) / bar_range, 0, 1)
        breakout_quality = (
            breakout_distance_score * 0.35
            + volume_score * 0.25
            + body_score * 0.20
            + close_score * 0.20
        )
    setup_score = cup_symmetry * 0.55 + handle_quality * 0.45
    pattern_score = cup_symmetry * 0.33 + handle_quality * 0.27 + breakout_quality * 0.40
    is_confirmed = (
        breakout_is_recent
        and current_close > rim_price
        and breakout_quality >= MIN_BREAKOUT_QUALITY
        and pattern_score >= MIN_PATTERN_SCORE
    )
    is_detected = setup_score >= MIN_SETUP_SCORE
    if not is_detected:
        return None

    status = "CONFIRMED" if is_confirmed else "DEVELOPING"
    target_price = rim_price + cup_depth
    return {
        "status": status,
        "is_detected": True,
        "is_confirmed": is_confirmed,
        "cup_symmetry": round(cup_symmetry, 1),
        "handle_depth_pct": round(handle_depth * 100, 1),
        "breakout_quality": round(breakout_quality, 1),
        "score": round(pattern_score if is_confirmed else setup_score, 1),
        "rim_price": round(rim_price, 4),
        "target_price": round(target_price, 4),
        "cup_depth": round(cup_depth, 4),
        "message": (
            "Yüksek kaliteli cup-and-handle kırılımı onaylandı."
            if is_confirmed
            else "Gelişen cup-and-handle yapısı kalite eşiğini geçti."
        ),
        "points": {
            "left_rim": {"index": left_idx, "price": round(left["price"], 4)},
            "cup_base": {"index": base_idx, "price": round(base["price"], 4)},
            "right_rim": {"index": right_idx, "price": round(right["price"], 4)},
            "handle_low": {"index": handle_idx, "price": round(handle["price"], 4)},
            "breakout_index": breakout_idx,
            "target_end_index": (
                breakout_idx + TARGET_PROJECTION_BARS
                if breakout_idx is not None else len(df) - 1 + TARGET_PROJECTION_BARS
            ),
        },
    }


def calculate_cup_handle_quality(df: pd.DataFrame) -> CupHandleQuality:
    if df is None or len(df) < MIN_CUP_BARS + MIN_HANDLE_BARS + PIVOT_SPAN * 2:
        return _empty("Cup-and-handle için yeterli bar yok.")

    work = df.reset_index(drop=True).copy()
    pivots = _find_pivots(work)
    if len(pivots) < 3:
        return _empty()

    best: dict[str, Any] | None = None
    for start in range(max(0, len(pivots) - 30), len(pivots) - 2):
        for developing in (False, True):
            candidate = _candidate_from_sequence(work, pivots, start, developing)
            if candidate is None:
                continue
            scored = _score_candidate(work, candidate)
            if scored is None:
                continue
            trigger_idx = scored["points"].get("breakout_index")
            if trigger_idx is None:
                trigger_idx = scored["points"]["handle_low"]["index"]
            best_trigger_idx = -1
            if best is not None:
                best_trigger_idx = best["points"].get("breakout_index")
                if best_trigger_idx is None:
                    best_trigger_idx = best["points"]["handle_low"]["index"]
            rank = (bool(scored["is_confirmed"]), int(trigger_idx), float(scored["score"] or 0))
            best_rank = (
                (bool(best["is_confirmed"]), int(best_trigger_idx), float(best["score"] or 0))
                if best is not None else None
            )
            if best_rank is None or rank > best_rank:
                best = scored

    if best is None:
        return _empty()

    return CupHandleQuality(
        status=best["status"],
        is_detected=best["is_detected"],
        is_confirmed=best["is_confirmed"],
        cup_symmetry=best["cup_symmetry"],
        handle_depth_pct=best["handle_depth_pct"],
        breakout_quality=best["breakout_quality"],
        score=best["score"],
        rim_price=best["rim_price"],
        target_price=best["target_price"],
        cup_depth=best["cup_depth"],
        message=best["message"],
        points=best["points"],
        params=_params(),
    )
