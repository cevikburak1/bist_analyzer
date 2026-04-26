"""
ANKA v2.0 analysis engine.

This module keeps the new ANKA calculations isolated from the legacy
AL/SAT/BEKLE rules so the first v2 release can be validated without changing the
existing signal contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from analysis.fibonacci import FibonacciResult


PHI = 0.618
ANKA_BODY_PERIOD = 34
ANKA_LOOKBACK = 100
KNN_K = 7
KNN_HISTORY = 80
KNN_PATTERN_N = 8
KNN_PATTERN_WINDOW = 6
KNN_PATTERN_HORIZON = 3
KNN_PATTERN_SPACING = 25
CALIBRATION_LOOKBACK = 50
CALIBRATION_HORIZON = 3


@dataclass
class AnkaValley:
    score: float
    name: str
    color: str
    metaphor: str
    market_comment: str
    potential_move: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "name": self.name,
            "color": self.color,
            "metaphor": self.metaphor,
            "market_comment": self.market_comment,
            "potential_move": self.potential_move,
        }


@dataclass
class AnkaKnnVolume:
    relative_volume: float
    neighbor_count: int
    bullish_ratio: float
    bearish_ratio: float
    confidence: float
    label: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "relative_volume": self.relative_volume,
            "neighbor_count": self.neighbor_count,
            "bullish_ratio": self.bullish_ratio,
            "bearish_ratio": self.bearish_ratio,
            "confidence": self.confidence,
            "label": self.label,
        }


@dataclass
class AnkaFibonacciConfirmation:
    bonus: float
    label: str
    level_name: str
    level_price: float
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "bonus": self.bonus,
            "label": self.label,
            "level_name": self.level_name,
            "level_price": self.level_price,
            "message": self.message,
        }


@dataclass
class AnkaCalibration:
    status: str
    label: str
    total_success_rate: float | None
    bull_success_rate: float | None
    bear_success_rate: float | None
    total_signals: int
    bull_signals: int
    bear_signals: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "label": self.label,
            "total_success_rate": self.total_success_rate,
            "bull_success_rate": self.bull_success_rate,
            "bear_success_rate": self.bear_success_rate,
            "total_signals": self.total_signals,
            "bull_signals": self.bull_signals,
            "bear_signals": self.bear_signals,
        }


@dataclass
class AnkaV2Result:
    synthesis_score: float
    synthesis_decision: str
    primary_signal: str
    phase: str
    trend: str
    momentum_label: str
    fire_power: float
    body: float
    breath: float
    upper_wing: float
    lower_wing: float
    inner_upper_wing: float
    inner_lower_wing: float
    is_ash_phase: bool
    valley: AnkaValley
    knn_volume: AnkaKnnVolume
    fibonacci_confirmation: AnkaFibonacciConfirmation
    calibration: AnkaCalibration
    lr_engine: dict[str, Any]
    knn_pattern: dict[str, Any]
    layer_engine: dict[str, Any]
    synthesis_weights: dict[str, float]
    alerts: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "synthesis_score": self.synthesis_score,
            "synthesis_decision": self.synthesis_decision,
            "primary_signal": self.primary_signal,
            "phase": self.phase,
            "trend": self.trend,
            "momentum_label": self.momentum_label,
            "fire_power": self.fire_power,
            "body": self.body,
            "breath": self.breath,
            "upper_wing": self.upper_wing,
            "lower_wing": self.lower_wing,
            "inner_upper_wing": self.inner_upper_wing,
            "inner_lower_wing": self.inner_lower_wing,
            "is_ash_phase": self.is_ash_phase,
            "valley": self.valley.as_dict(),
            "knn_volume": self.knn_volume.as_dict(),
            "fibonacci_confirmation": self.fibonacci_confirmation.as_dict(),
            "calibration": self.calibration.as_dict(),
            "lr_engine": self.lr_engine,
            "knn_pattern": self.knn_pattern,
            "layer_engine": self.layer_engine,
            "synthesis_weights": self.synthesis_weights,
            "alerts": self.alerts,
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


def _round_or_none(value: float | None) -> float | None:
    if value is None or np.isnan(value):
        return None
    return round(float(value), 1)


def _normalize_series(series: pd.Series, lookback: int = ANKA_LOOKBACK) -> pd.Series:
    rolling_min = series.rolling(lookback, min_periods=20).min()
    rolling_max = series.rolling(lookback, min_periods=20).max()
    normalized = (series - rolling_min) / (rolling_max - rolling_min).replace(0, np.nan)
    return normalized.mul(100).fillna(50).clip(0, 100)


def _true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    ranges = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def add_anka_columns(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)

    body = close.ewm(span=ANKA_BODY_PERIOD, adjust=False).mean()
    atr = df["atr"] if "atr" in df.columns else _true_range(df).ewm(alpha=1 / 14, adjust=False).mean()
    breath = atr.fillna(_true_range(df).rolling(14, min_periods=3).mean()).fillna(0)

    momentum_pct = close.pct_change(10).mul(100).replace([np.inf, -np.inf], np.nan).fillna(0)
    body_distance_pct = ((close - body) / body.replace(0, np.nan)).mul(100).fillna(0)
    volatility_pct = (breath / close.replace(0, np.nan)).mul(100).fillna(0)

    momentum_norm = _normalize_series(momentum_pct)
    trend_norm = _normalize_series(body_distance_pct)
    volatility_norm = _normalize_series(volatility_pct)
    valley_score = (momentum_norm * 0.45 + trend_norm * 0.35 + volatility_norm * 0.20).clip(0, 100)

    trend_strength = body_distance_pct.abs().rolling(5, min_periods=1).mean().clip(0, 8)
    channel_multiplier = 1.2 + trend_strength / 4
    upper = body + breath * channel_multiplier
    lower = body - breath * channel_multiplier
    inner_upper = body + (upper - body) * PHI
    inner_lower = body - (body - lower) * PHI

    df["anka_body"] = body
    df["anka_breath"] = breath
    df["anka_upper_wing"] = upper
    df["anka_lower_wing"] = lower
    df["anka_inner_upper_wing"] = inner_upper
    df["anka_inner_lower_wing"] = inner_lower
    df["anka_momentum_pct"] = momentum_pct
    df["anka_volatility_norm"] = volatility_norm
    df["anka_valley_score"] = valley_score
    df["anka_is_ash_phase"] = (
        close.between(inner_lower, inner_upper) & (volatility_norm < 35)
    )

    return df


def _valley_from_score(score: float) -> AnkaValley:
    definitions = [
        (15, "Aşk", "red", "Dip ve aşırı korku", "Aşırı satım, yüksek fırsat", "Güçlü yükseliş doğuşu"),
        (30, "Ayrılık", "red-orange", "Düşüş ve kontrol kaybı", "Güçlü düşüş trendi", "Trend devamı veya ani tepki"),
        (45, "İrade", "orange", "Zayıflık ve kontrollü düşüş", "Sağlıklı düşüş trendi", "Düşüş trendi devamı"),
        (55, "Şüphe", "yellow", "Nötr ve kararsızlık", "Yön arayışı, yatay hareket", "Kül Fazı veya kırılım"),
        (70, "Ben", "cyan", "Güven ve kontrollü yükseliş", "Sağlıklı yükseliş trendi", "Trend devamı"),
        (85, "Şaşkınlık", "green", "Güçlü trend ve hız", "Momentum yüksek", "Trend devamı veya ani düzeltme"),
        (101, "Yok Oluş", "pink", "Zirve ve aşırı coşku", "Aşırı alım, yüksek risk", "Düzeltme veya düşüş doğuşu"),
    ]
    for upper_bound, name, color, metaphor, comment, move in definitions:
        if score < upper_bound:
            return AnkaValley(round(score, 1), name, color, metaphor, comment, move)
    return AnkaValley(round(score, 1), "Belirsiz", "slate", "Veri yetersiz", "Yorum yok", "Bekle")


def _calculate_knn_volume(df: pd.DataFrame) -> AnkaKnnVolume:
    work = df.tail(KNN_HISTORY + CALIBRATION_HORIZON + 5).copy()
    price_range = (work["high"] - work["low"]).replace(0, np.nan)
    rel_volume = work["volume"] / work["volume"].rolling(20, min_periods=5).mean()

    features = pd.DataFrame(index=work.index)
    features["body"] = ((work["close"] - work["open"]).abs() / price_range).fillna(0)
    features["upper_shadow"] = ((work["high"] - work[["open", "close"]].max(axis=1)) / price_range).fillna(0)
    features["lower_shadow"] = ((work[["open", "close"]].min(axis=1) - work["low"]) / price_range).fillna(0)
    features["close_position"] = ((work["close"] - work["low"]) / price_range).fillna(0.5)
    features["relative_volume"] = rel_volume.replace([np.inf, -np.inf], np.nan).fillna(1.0)
    features = features.replace([np.inf, -np.inf], np.nan).dropna()

    latest_relative_volume = round(_safe_float(rel_volume.iloc[-1], 1.0), 2)
    if len(features) < KNN_K + CALIBRATION_HORIZON + 1:
        return AnkaKnnVolume(latest_relative_volume, 0, 0.5, 0.5, 0.0, "Veri yetersiz")

    latest = features.iloc[-1]
    candidates = features.iloc[: -CALIBRATION_HORIZON]
    future_return = work["close"].shift(-CALIBRATION_HORIZON) / work["close"] - 1
    candidate_returns = future_return.reindex(candidates.index).dropna()
    candidates = candidates.reindex(candidate_returns.index)

    if len(candidates) < KNN_K:
        return AnkaKnnVolume(latest_relative_volume, 0, 0.5, 0.5, 0.0, "Veri yetersiz")

    std = candidates.std().replace(0, 1)
    distances = (((candidates - latest) / std) ** 2).sum(axis=1).pow(0.5)
    nearest = distances.nsmallest(KNN_K).index
    outcomes = candidate_returns.reindex(nearest)
    bullish_ratio = float((outcomes > 0.01).mean())
    bearish_ratio = float((outcomes < -0.01).mean())
    confidence = max(bullish_ratio, bearish_ratio)

    if latest_relative_volume >= 1.2 and bullish_ratio > bearish_ratio:
        label = "Hacimli boğa örüntüsü"
    elif latest_relative_volume >= 1.2 and bearish_ratio > bullish_ratio:
        label = "Hacimli ayı örüntüsü"
    elif latest_relative_volume >= 1.2:
        label = "Hacim yüksek, yön kararsız"
    else:
        label = "Hacim teyidi zayıf"

    return AnkaKnnVolume(
        relative_volume=latest_relative_volume,
        neighbor_count=len(nearest),
        bullish_ratio=round(bullish_ratio * 100, 1),
        bearish_ratio=round(bearish_ratio * 100, 1),
        confidence=round(confidence * 100, 1),
        label=label,
    )


def _nearest_fib_level(price: float, fib: FibonacciResult) -> tuple[str, float, float] | None:
    levels: list[tuple[str, float]] = []
    for ratio, level in fib.retracement_levels.items():
        levels.append((f"F{float(ratio) * 100:.1f}%", _safe_float(level)))
    if fib.swing_low > 0:
        levels.append(("F0.0%", fib.swing_low))
    if fib.swing_high > 0:
        levels.append(("F100.0%", fib.swing_high))
    if not levels:
        return None

    level_name, level_price = min(levels, key=lambda item: abs(price - item[1]))
    tolerance = max(price * 0.015, abs(fib.swing_high - fib.swing_low) * 0.025)
    if abs(price - level_price) > tolerance:
        return None
    return level_name, level_price, tolerance


def _fibonacci_confirmation(price: float, signal: str, fib: FibonacciResult) -> AnkaFibonacciConfirmation:
    nearest = _nearest_fib_level(price, fib)
    if nearest is None:
        return AnkaFibonacciConfirmation(0.0, "Nötr", "", 0.0, "Fiyat kritik Fibonacci bölgesinde değil.")

    level_name, level_price, _ = nearest
    support_levels = {"F23.6%", "F38.2%", "F50.0%"}
    resistance_levels = {"F61.8%", "F78.6%", "F100.0%"}
    is_support = level_name in support_levels
    is_resistance = level_name in resistance_levels

    if signal == "AL" and is_support:
        bonus = 8.0
        label = "Boğa teyidi"
        message = f"Alım sinyali {level_name} destek bölgesinde güçleniyor."
    elif signal == "SAT" and is_resistance:
        bonus = -8.0
        label = "Ayı teyidi"
        message = f"Satış sinyali {level_name} direnç bölgesinde güçleniyor."
    elif signal == "SAT" and is_support:
        bonus = 4.0
        label = "Çapraz uyarı"
        message = f"Fiyat {level_name} desteğinde; ayı sinyali temkinli okunmalı."
    elif signal == "AL" and is_resistance:
        bonus = -4.0
        label = "Çapraz uyarı"
        message = f"Fiyat {level_name} direncinde; boğa sinyali temkinli okunmalı."
    else:
        bonus = 0.0
        label = "Yakın seviye"
        message = f"Fiyat {level_name} seviyesine yakın, net yön teyidi yok."

    return AnkaFibonacciConfirmation(
        bonus=bonus,
        label=label,
        level_name=level_name,
        level_price=round(level_price, 4),
        message=message,
    )


def _calibration_status(rate: float | None) -> tuple[str, str]:
    if rate is None:
        return "INSUFFICIENT", "Veri yetersiz"
    if rate >= 65:
        return "CALIBRATED", "Kalibre"
    if rate >= 50:
        return "MODERATE", "Orta"
    if rate >= 35:
        return "WEAK", "Zayıf"
    return "INVERSE", "Ters"


def _historical_signal(row: pd.Series, prev: pd.Series) -> str:
    close = _safe_float(row.get("close"))
    prev_close = _safe_float(prev.get("close"))
    momentum = _safe_float(row.get("anka_momentum_pct"))
    valley = _safe_float(row.get("anka_valley_score"), 50)

    bullish_rebirth = (
        prev_close < _safe_float(prev.get("anka_lower_wing"))
        and close > _safe_float(row.get("anka_lower_wing"))
        and valley < 30
        and momentum > 0
    )
    bearish_rebirth = (
        prev_close > _safe_float(prev.get("anka_upper_wing"))
        and close < _safe_float(row.get("anka_upper_wing"))
        and valley > 70
        and momentum < 0
    )
    bull_fire = (
        close > _safe_float(row.get("anka_body"))
        and close > _safe_float(row.get("anka_inner_upper_wing"))
        and momentum > 1.0
    )
    bear_fire = (
        close < _safe_float(row.get("anka_body"))
        and close < _safe_float(row.get("anka_inner_lower_wing"))
        and momentum < -1.0
    )

    if bullish_rebirth or bull_fire:
        return "BULL"
    if bearish_rebirth or bear_fire:
        return "BEAR"
    return "NONE"


def _calculate_calibration(df: pd.DataFrame) -> AnkaCalibration:
    if len(df) < CALIBRATION_LOOKBACK + CALIBRATION_HORIZON + 2:
        status, label = _calibration_status(None)
        return AnkaCalibration(status, label, None, None, None, 0, 0, 0)

    recent = df.iloc[-(CALIBRATION_LOOKBACK + CALIBRATION_HORIZON + 1):]
    bull_hits = bull_total = bear_hits = bear_total = 0

    for idx in range(1, len(recent) - CALIBRATION_HORIZON):
        row = recent.iloc[idx]
        prev = recent.iloc[idx - 1]
        direction = _historical_signal(row, prev)
        if direction == "NONE":
            continue

        current_close = _safe_float(row.get("close"))
        future_close = _safe_float(recent.iloc[idx + CALIBRATION_HORIZON].get("close"))
        if current_close <= 0 or future_close <= 0:
            continue

        if direction == "BULL":
            bull_total += 1
            if future_close > current_close:
                bull_hits += 1
        elif direction == "BEAR":
            bear_total += 1
            if future_close < current_close:
                bear_hits += 1

    total = bull_total + bear_total
    total_hits = bull_hits + bear_hits
    total_rate = (total_hits / total * 100) if total else None
    bull_rate = (bull_hits / bull_total * 100) if bull_total else None
    bear_rate = (bear_hits / bear_total * 100) if bear_total else None
    status, label = _calibration_status(total_rate)

    return AnkaCalibration(
        status=status,
        label=label,
        total_success_rate=_round_or_none(total_rate),
        bull_success_rate=_round_or_none(bull_rate),
        bear_success_rate=_round_or_none(bear_rate),
        total_signals=total,
        bull_signals=bull_total,
        bear_signals=bear_total,
    )


def _momentum_label(momentum_pct: float) -> str:
    if momentum_pct >= 4:
        return "Çok güçlü pozitif"
    if momentum_pct >= 1.5:
        return "Güçlü pozitif"
    if momentum_pct <= -4:
        return "Çok güçlü negatif"
    if momentum_pct <= -1.5:
        return "Güçlü negatif"
    return "Nötr"


def _trend_label(close: float, body: float, body_slope: float) -> str:
    if close > body and body_slope > 0:
        return "Yükseliş"
    if close < body and body_slope < 0:
        return "Düşüş"
    return "Kararsız"


def _primary_signal(latest: pd.Series, prev: pd.Series, valley: AnkaValley) -> tuple[str, str]:
    direction = _historical_signal(latest, prev)
    if direction == "BULL" and valley.score < 30:
        return "Yükseliş Doğuşu", "AL"
    if direction == "BEAR" and valley.score > 70:
        return "Düşüş Doğuşu", "SAT"
    if direction == "BULL":
        return "Boğa Ateşi", "AL"
    if direction == "BEAR":
        return "Ayı Ateşi", "SAT"
    if bool(latest.get("anka_is_ash_phase", False)):
        return "Kül Fazı", "BEKLE"
    return "Bekle", "BEKLE"


def _decision_from_score(score: float) -> str:
    if score >= 70:
        return "GÜÇLÜ ALIŞ"
    if score >= 58:
        return "ALIŞ"
    if score <= 30:
        return "GÜÇLÜ SATIŞ"
    if score <= 42:
        return "SATIŞ"
    return "BEKLE"


def _recommendation_from_score(score: float) -> str:
    if score >= 75:
        return "⬆ GÜÇLÜ ALIŞ"
    if score >= 60:
        return "↗ ALIŞ"
    if score <= 25:
        return "⬇ GÜÇLÜ SATIŞ"
    if score <= 40:
        return "↘ SATIŞ"
    if 45 <= score <= 55:
        return "⏸ BEKLE"
    return "🔍 İZLE"


def _calculate_lr_engine(df: pd.DataFrame) -> dict[str, Any]:
    close = df["close"].astype(float).tail(50)
    if len(close) < 12:
        return {
            "score": 50.0,
            "direction": "NÖTR",
            "slope_pct": 0.0,
            "r2": 0.0,
            "intensity": "Veri yetersiz",
        }

    y = close.to_numpy()
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    predicted = slope * x + intercept
    residual = float(np.sum((y - predicted) ** 2))
    total = float(np.sum((y - np.mean(y)) ** 2)) or 1.0
    r2 = max(0.0, min(1.0, 1 - residual / total))
    slope_pct = (slope / (float(np.mean(y)) or 1.0)) * 100
    raw = 50 + np.clip(slope_pct * 22, -32, 32) + (r2 - 0.35) * 18 * np.sign(slope_pct)
    score = float(np.clip(raw, 0, 100))

    if score >= 70:
        direction = "GÜÇLÜ YÜKSELİŞ"
    elif score >= 56:
        direction = "YÜKSELİŞ"
    elif score <= 30:
        direction = "GÜÇLÜ DÜŞÜŞ"
    elif score <= 44:
        direction = "DÜŞÜŞ"
    else:
        direction = "NÖTR"

    return {
        "score": round(score, 1),
        "direction": direction,
        "slope_pct": round(float(slope_pct), 4),
        "r2": round(r2, 3),
        "intensity": f"{direction} · R² {r2:.2f}",
    }


def _pattern_features(window: pd.DataFrame) -> np.ndarray:
    ranges = (window["high"] - window["low"]).replace(0, np.nan)
    atr = window["anka_breath"].replace(0, np.nan)
    body = ((window["close"] - window["open"]) / atr).replace([np.inf, -np.inf], np.nan).fillna(0)
    candle_range = (ranges / atr).replace([np.inf, -np.inf], np.nan).fillna(0)
    lower_shadow = ((window[["open", "close"]].min(axis=1) - window["low"]) / atr).replace([np.inf, -np.inf], np.nan).fillna(0)
    upper_shadow = ((window["high"] - window[["open", "close"]].max(axis=1)) / atr).replace([np.inf, -np.inf], np.nan).fillna(0)
    relative_volume = (window["volume"] / window["volume"].rolling(20, min_periods=3).mean()).replace([np.inf, -np.inf], np.nan).fillna(1)
    return np.array([
        body.mean(),
        candle_range.mean(),
        lower_shadow.mean(),
        upper_shadow.mean(),
        relative_volume.mean(),
    ], dtype=float)


def _calculate_knn_pattern(df: pd.DataFrame) -> dict[str, Any]:
    params = {
        "n": KNN_PATTERN_N,
        "nd": KNN_PATTERN_WINDOW,
        "ny": KNN_PATTERN_HORIZON,
        "spacing": KNN_PATTERN_SPACING,
        "atr_n": 14,
        "features": ["body_atr", "range_atr", "lower_shadow_atr", "upper_shadow_atr", "relative_volume"],
    }
    min_len = KNN_PATTERN_WINDOW + KNN_PATTERN_HORIZON + KNN_PATTERN_SPACING
    if len(df) < min_len:
        return {
            "score": 50.0,
            "prediction": "NÖTR",
            "confidence": 0.0,
            "neighbors": 0,
            "params": params,
        }

    current = _pattern_features(df.tail(KNN_PATTERN_WINDOW))
    candidates: list[tuple[float, float]] = []
    last_start = len(df) - KNN_PATTERN_WINDOW - KNN_PATTERN_HORIZON
    for end_idx in range(KNN_PATTERN_WINDOW, last_start, KNN_PATTERN_SPACING):
        window = df.iloc[end_idx - KNN_PATTERN_WINDOW:end_idx]
        future_idx = end_idx + KNN_PATTERN_HORIZON - 1
        if future_idx >= len(df):
            continue
        features = _pattern_features(window)
        distance = float(np.linalg.norm(current - features))
        start_close = _safe_float(df.iloc[end_idx - 1].get("close"))
        future_close = _safe_float(df.iloc[future_idx].get("close"))
        if start_close <= 0 or future_close <= 0:
            continue
        future_return = (future_close / start_close) - 1
        candidates.append((distance, future_return))

    nearest = sorted(candidates, key=lambda item: item[0])[:KNN_PATTERN_N]
    if not nearest:
        return {
            "score": 50.0,
            "prediction": "NÖTR",
            "confidence": 0.0,
            "neighbors": 0,
            "params": params,
        }

    weights = np.array([1 / (distance + 1e-6) for distance, _ in nearest])
    returns = np.array([future_return for _, future_return in nearest])
    weighted_return = float(np.average(returns, weights=weights))
    score = float(np.clip(50 + weighted_return * 900, 0, 100))
    confidence = float(np.clip(abs(score - 50) * 2, 0, 100))
    prediction = "YÜKSELİŞ ÖRÜNTÜSÜ" if score > 56 else "DÜŞÜŞ ÖRÜNTÜSÜ" if score < 44 else "NÖTR"

    return {
        "score": round(score, 1),
        "prediction": prediction,
        "confidence": round(confidence, 1),
        "neighbors": len(nearest),
        "weighted_return_pct": round(weighted_return * 100, 2),
        "params": params,
    }


def _layer_state(label: str, score: float) -> dict[str, Any]:
    if score > 56:
        direction = "UP"
        symbol = f"{label}↑"
    elif score < 44:
        direction = "DOWN"
        symbol = f"{label}↓"
    else:
        direction = "NEUTRAL"
        symbol = f"{label}→"
    return {"score": round(float(score), 1), "direction": direction, "symbol": symbol}


def _calculate_layer_engine(
    latest: pd.Series,
    valley: AnkaValley,
    primary_signal: str,
    lr_engine: dict[str, Any],
    knn_pattern: dict[str, Any],
) -> dict[str, Any]:
    momentum_pct = _safe_float(latest.get("anka_momentum_pct"))
    volatility_norm = _safe_float(latest.get("anka_volatility_norm"), 50)
    close = _safe_float(latest.get("close"))
    body = _safe_float(latest.get("anka_body"))

    valley_layer = _layer_state("V", 100 - valley.score if valley.score > 85 else valley.score)
    momentum_layer = _layer_state("M", float(np.clip(50 + momentum_pct * 7, 0, 100)))
    trend_layer = _layer_state("T", lr_engine["score"])
    volatility_layer = _layer_state("σ", float(np.clip(100 - abs(volatility_norm - 45), 0, 100)))
    signal_layer_score = 68 if "Boğa" in primary_signal or "Yükseliş" in primary_signal else 32 if "Ayı" in primary_signal or "Düşüş" in primary_signal else 50
    if close > body:
        signal_layer_score += 5
    elif close < body:
        signal_layer_score -= 5
    signal_layer = _layer_state("S", float(np.clip(signal_layer_score, 0, 100)))

    layers = {
        "valley": valley_layer,
        "momentum": momentum_layer,
        "trend": trend_layer,
        "volatility": volatility_layer,
        "signal": signal_layer,
    }
    score = (
        valley_layer["score"] * 0.20
        + momentum_layer["score"] * 0.20
        + trend_layer["score"] * 0.25
        + volatility_layer["score"] * 0.15
        + signal_layer["score"] * 0.20
    )
    confidence = int(np.clip(round(abs(score - 50) / 10) + 1, 1, 5))
    chain = " ".join(layer["symbol"] for layer in layers.values())
    if primary_signal == "Kül Fazı":
        scenario = "Kül Fazı: İç kanatlar arasında sıkışma, kırılım beklenmeli."
    elif valley.name in {"Aşk", "Ayrılık"} and score > 55:
        scenario = "Dip Yeniden Doğuş: Alt bölgelerden toparlanma arayışı."
    elif valley.name in {"Yok Oluş", "Şaşkınlık"} and score < 45:
        scenario = "Zirve Uyarısı: Üst bölgede zayıflama ve düzeltme riski."
    elif score > 60:
        scenario = "Trend Devamı: Katmanlar yükseliş tarafında hizalanıyor."
    elif score < 40:
        scenario = "Zayıflama: Katmanlar düşüş tarafında hizalanıyor."
    else:
        scenario = "Kararsız Bölge: Net yön için ek teyit beklenmeli."

    return {
        "score": round(float(score), 1),
        "confidence_stars": confidence,
        "chain": chain,
        "scenario": scenario,
        "recommendation": _recommendation_from_score(score),
        "layers": layers,
    }


def _build_alerts(
    primary_signal: str,
    synthesis_decision: str,
    lr_engine: dict[str, Any],
    knn_pattern: dict[str, Any],
    is_ash_phase: bool,
) -> list[str]:
    alerts: list[str] = []
    if primary_signal in {"Yükseliş Doğuşu", "Düşüş Doğuşu", "Boğa Ateşi", "Ayı Ateşi"}:
        alerts.append(f"Anka: {primary_signal}")
    if is_ash_phase:
        alerts.append("Anka: Kül Fazı")
    if lr_engine["score"] >= 70:
        alerts.append("LR: Güçlü Yükseliş")
    if lr_engine["score"] <= 30:
        alerts.append("LR: Güçlü Düşüş")
    if knn_pattern["score"] >= 60:
        alerts.append("kNN: Yükseliş Örüntüsü")
    if knn_pattern["score"] <= 40:
        alerts.append("kNN: Düşüş Örüntüsü")
    if "GÜÇLÜ ALIŞ" in synthesis_decision:
        alerts.append("Sentez: Güçlü Alış")
    if "GÜÇLÜ SATIŞ" in synthesis_decision:
        alerts.append("Sentez: Güçlü Satış")
    return alerts


def calculate_anka_v2(
    df: pd.DataFrame,
    *,
    base_score: float,
    base_signal: str,
    fibonacci: FibonacciResult,
) -> AnkaV2Result:
    if df.empty:
        raise ValueError("ANKA v2 requires non-empty stock data")

    add_anka_columns(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest

    close = _safe_float(latest.get("close"))
    body = _safe_float(latest.get("anka_body"))
    breath = _safe_float(latest.get("anka_breath"))
    valley = _valley_from_score(_safe_float(latest.get("anka_valley_score"), 50))
    knn_volume = _calculate_knn_volume(df)

    primary_signal, implied_signal = _primary_signal(latest, prev, valley)
    signal_for_fib = base_signal if base_signal != "BEKLE" else implied_signal
    fib_confirmation = _fibonacci_confirmation(close, signal_for_fib, fibonacci)
    calibration = _calculate_calibration(df)
    lr_engine = _calculate_lr_engine(df)
    knn_pattern = _calculate_knn_pattern(df)

    momentum_pct = _safe_float(latest.get("anka_momentum_pct"))
    volatility_norm = _safe_float(latest.get("anka_volatility_norm"), 50)
    fire_power = min(100.0, abs(momentum_pct) * 8 + volatility_norm * 0.55 + knn_volume.relative_volume * 8)
    body_slope = body - _safe_float(prev.get("anka_body"))
    trend = _trend_label(close, body, body_slope)
    phase = "Kül Fazı" if bool(latest.get("anka_is_ash_phase", False)) else ("Fiyat vücut üstünde" if close >= body else "Fiyat vücut altında")
    layer_engine = _calculate_layer_engine(latest, valley, primary_signal, lr_engine, knn_pattern)
    synthesis_weights = {
        "layer_engine": 0.40,
        "lr_engine": 0.30,
        "knn_pattern": 0.30,
        "fibonacci_bonus_points": fib_confirmation.bonus,
    }
    ash_penalty = -4 if bool(latest.get("anka_is_ash_phase", False)) else 0
    synthesis_score = float(np.clip(
        layer_engine["score"] * synthesis_weights["layer_engine"]
        + lr_engine["score"] * synthesis_weights["lr_engine"]
        + knn_pattern["score"] * synthesis_weights["knn_pattern"]
        + fib_confirmation.bonus
        + ash_penalty,
        0,
        100,
    ))
    synthesis_decision = _recommendation_from_score(synthesis_score)
    alerts = _build_alerts(
        primary_signal,
        synthesis_decision,
        lr_engine,
        knn_pattern,
        bool(latest.get("anka_is_ash_phase", False)),
    )

    return AnkaV2Result(
        synthesis_score=round(synthesis_score, 1),
        synthesis_decision=synthesis_decision,
        primary_signal=primary_signal,
        phase=phase,
        trend=trend,
        momentum_label=_momentum_label(momentum_pct),
        fire_power=round(fire_power, 1),
        body=round(body, 4),
        breath=round(breath, 4),
        upper_wing=round(_safe_float(latest.get("anka_upper_wing")), 4),
        lower_wing=round(_safe_float(latest.get("anka_lower_wing")), 4),
        inner_upper_wing=round(_safe_float(latest.get("anka_inner_upper_wing")), 4),
        inner_lower_wing=round(_safe_float(latest.get("anka_inner_lower_wing")), 4),
        is_ash_phase=bool(latest.get("anka_is_ash_phase", False)),
        valley=valley,
        knn_volume=knn_volume,
        fibonacci_confirmation=fib_confirmation,
        calibration=calibration,
        lr_engine=lr_engine,
        knn_pattern=knn_pattern,
        layer_engine=layer_engine,
        synthesis_weights=synthesis_weights,
        alerts=alerts,
    )
