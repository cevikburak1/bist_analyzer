"""
Fibonacci Analiz Modülü

ZigZag swing noktalarından Fibonacci retracement ve extension
seviyelerini hesaplar. Destek/direnç bölgeleri belirler.
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

RETRACEMENT_RATIOS = [0.236, 0.382, 0.5, 0.618, 0.786]
EXTENSION_RATIOS = [1.0, 1.272, 1.414, 1.618, 2.0, 2.618]


@dataclass
class FibonacciResult:
    swing_high: float = 0.0
    swing_low: float = 0.0
    trend_direction: str = "UP"  # "UP" veya "DOWN"
    retracement_levels: dict = field(default_factory=dict)
    extension_levels: dict = field(default_factory=dict)
    current_zone: str = ""
    nearest_support: float = 0.0
    nearest_resistance: float = 0.0


def find_swing_points(df: pd.DataFrame, depth: int = 10) -> tuple[float, float, str]:
    """
    Son anlamlı swing high ve swing low noktalarını bulur.
    depth: her iki tarafta kaç mum kontrol edileceği.

    Returns: (swing_high, swing_low, trend_direction)
    """
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    n = len(high)

    def fallback_direction(start: int = 0) -> str:
        """Pivot bulunamadığında yönü fiyatın gerçek hareketinden çıkar."""
        first = float(close[start])
        last = float(close[-1])
        return "UP" if last >= first else "DOWN"

    def fallback_pair(start: int = 0) -> tuple[float, float, str]:
        """Return chronological anchors instead of unrelated extrema."""
        direction = fallback_direction(start)
        segment_high = high[start:]
        segment_low = low[start:]
        if direction == "UP":
            high_pos = int(np.argmax(segment_high))
            swing_high = float(segment_high[high_pos])
            swing_low = float(np.min(segment_low[: high_pos + 1]))
        else:
            low_pos = int(np.argmin(segment_low))
            swing_low = float(segment_low[low_pos])
            swing_high = float(np.max(segment_high[: low_pos + 1]))
        if swing_high <= swing_low:
            swing_high = float(np.max(segment_high))
            swing_low = float(np.min(segment_low))
        return swing_high, swing_low, direction

    if n < depth * 3:
        return fallback_pair()

    swing_highs = []
    swing_lows = []

    for i in range(depth, n - depth):
        if high[i] == max(high[i - depth: i + depth + 1]):
            swing_highs.append((i, float(high[i])))
        if low[i] == min(low[i - depth: i + depth + 1]):
            swing_lows.append((i, float(low[i])))

    if not swing_highs or not swing_lows:
        period = min(120, n)
        return fallback_pair(n - period)

    last_sh_idx, last_sh_val = swing_highs[-1]
    last_sl_idx, last_sl_val = swing_lows[-1]

    # Trend yönü: son swing low'dan sonra swing high geldiyse UP, tersi DOWN
    if last_sh_idx > last_sl_idx:
        direction = "UP"
    else:
        direction = "DOWN"

    # Use one chronological pivot leg.  Independent max(high)/min(low) values
    # can belong to the opposite order and do not describe a tradable swing.
    lookback_start = max(0, n - 120)
    if direction == "UP":
        end_idx, sh = last_sh_idx, last_sh_val
        prior_lows = [(i, v) for i, v in swing_lows if lookback_start <= i < end_idx]
        if not prior_lows:
            return fallback_pair(lookback_start)
        _, sl = prior_lows[-1]
    else:
        end_idx, sl = last_sl_idx, last_sl_val
        prior_highs = [(i, v) for i, v in swing_highs if lookback_start <= i < end_idx]
        if not prior_highs:
            return fallback_pair(lookback_start)
        _, sh = prior_highs[-1]

    if sh <= sl:
        return fallback_pair(lookback_start)

    return sh, sl, direction


def calculate_fib_levels(
    swing_high: float,
    swing_low: float,
    direction: str = "UP",
) -> tuple[dict, dict]:
    """
    Fibonacci retracement ve extension seviyelerini hesaplar.

    UP trend: swing_low -> swing_high (retracement aşağı doğru)
    DOWN trend: swing_high -> swing_low (retracement yukarı doğru)

    Returns: (retracement_levels, extension_levels)
    """
    diff = swing_high - swing_low
    if diff <= 0:
        return {}, {}

    retracements = {}
    extensions = {}

    if direction == "UP":
        for ratio in RETRACEMENT_RATIOS:
            level = swing_high - diff * ratio
            retracements[ratio] = round(level, 2)
        for ratio in EXTENSION_RATIOS:
            level = swing_high + diff * (ratio - 1.0)
            extensions[ratio] = round(level, 2)
    else:
        for ratio in RETRACEMENT_RATIOS:
            level = swing_low + diff * ratio
            retracements[ratio] = round(level, 2)
        for ratio in EXTENSION_RATIOS:
            level = swing_low - diff * (ratio - 1.0)
            extensions[ratio] = round(max(0, level), 2)

    return retracements, extensions


def current_fib_zone(
    price: float,
    retracement_levels: dict,
    swing_high: float,
    swing_low: float,
    direction: str = "UP",
) -> str:
    """Fiyatın hangi Fibonacci bölgesinde olduğunu belirler."""
    if not retracement_levels:
        return "Veri yetersiz"

    endpoints = (
        [(1.0, swing_low), (0.0, swing_high)]
        if direction == "UP"
        else [(0.0, swing_low), (1.0, swing_high)]
    )
    all_levels = sorted(
        endpoints
        + [(r, v) for r, v in retracement_levels.items()],
        key=lambda x: x[1],
    )

    for i in range(len(all_levels) - 1):
        lower_ratio, lower_val = all_levels[i]
        upper_ratio, upper_val = all_levels[i + 1]
        if lower_val <= price <= upper_val:
            ratio_low, ratio_high = sorted((lower_ratio, upper_ratio))
            return f"%{ratio_low*100:.1f}-%{ratio_high*100:.1f} bandı"

    if price > swing_high:
        return (
            "Swing high üzerinde (extension bölgesi)"
            if direction == "UP"
            else "Swing high üzerinde (düşüş yapısı geçersiz)"
        )
    if price < swing_low:
        return (
            "Swing low altında"
            if direction == "UP"
            else "Swing low altında (extension bölgesi)"
        )

    return "Belirsiz"


def nearest_support_resistance(
    price: float,
    retracement_levels: dict,
    extension_levels: dict,
    swing_high: float,
    swing_low: float,
) -> tuple[float, float]:
    """Fiyata en yakın destek ve direnç seviyelerini döndürür."""
    all_levels = sorted(level for level in set(
        [swing_low, swing_high]
        + list(retracement_levels.values())
        + list(extension_levels.values())
    ) if np.isfinite(level) and level > 0)

    supports = [level for level in all_levels if level <= price]
    resistances = [level for level in all_levels if level > price]
    support = max(supports) if supports else 0.0
    resistance = min(resistances) if resistances else 0.0

    return round(support, 2), round(resistance, 2)


def calculate_fibonacci(df: pd.DataFrame, current_price: float) -> FibonacciResult:
    """
    Tek bir hisse için tam Fibonacci analizi.
    """
    try:
        sh, sl, direction = find_swing_points(df)
        retracements, extensions = calculate_fib_levels(sh, sl, direction)
        zone = current_fib_zone(current_price, retracements, sh, sl, direction)
        support, resistance = nearest_support_resistance(
            current_price, retracements, extensions, sh, sl
        )

        return FibonacciResult(
            swing_high=round(sh, 2),
            swing_low=round(sl, 2),
            trend_direction=direction,
            retracement_levels=retracements,
            extension_levels=extensions,
            current_zone=zone,
            nearest_support=support,
            nearest_resistance=resistance,
        )
    except Exception as e:
        logger.warning("Fibonacci hesaplama hatası: %s", str(e))
        return FibonacciResult()
