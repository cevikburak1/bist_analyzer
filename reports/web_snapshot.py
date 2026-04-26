"""
Web dashboard snapshot and analysis status helpers.

The React dashboard consumes these JSON artifacts so it can render the latest
successful analysis while a background refresh is running.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from analysis.market_regime import MarketRegime
from analysis.signals import Signal
from config import (
    ANALYSIS_LOCK_PATH,
    ANALYSIS_STATUS_PATH,
    INTRADAY_REFRESH_MINUTES,
    LATEST_REPORT_PATH,
    WEB_SERIES_LENGTH,
    WEB_STOCKS_DIR,
)

logger = logging.getLogger(__name__)


def _safe_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if pd.isna(value):
            return None
        return round(value, 4)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def _normalize_json(data: Any) -> Any:
    if isinstance(data, dict):
        return {str(key): _normalize_json(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_normalize_json(item) for item in data]
    return _safe_json_value(data)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp_path, path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("JSON okunamadı: %s", path)
        return {}


def acquire_analysis_lock(run_id: str, requested_symbols: int) -> bool:
    if ANALYSIS_LOCK_PATH.exists():
        return False

    lock_data = {
        "run_id": run_id,
        "pid": os.getpid(),
        "requested_symbols": requested_symbols,
        "started_at": datetime.now().isoformat(),
    }
    _atomic_write_json(ANALYSIS_LOCK_PATH, lock_data)
    return True


def clear_analysis_lock() -> None:
    ANALYSIS_LOCK_PATH.unlink(missing_ok=True)


def is_analysis_running() -> bool:
    return ANALYSIS_LOCK_PATH.exists()


def write_analysis_status(
    *,
    state: str,
    run_id: str,
    requested_symbols: int,
    successful_symbols: int = 0,
    error: str = "",
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    existing = _read_json(ANALYSIS_STATUS_PATH)
    last_success_at = existing.get("last_success_at")

    if state == "idle" and finished_at:
        last_success_at = finished_at

    payload = {
        "state": state,
        "run_id": run_id,
        "pid": os.getpid(),
        "requested_symbols": requested_symbols,
        "successful_symbols": successful_symbols,
        "refresh_interval_minutes": INTRADAY_REFRESH_MINUTES,
        "started_at": started_at,
        "finished_at": finished_at,
        "last_success_at": last_success_at,
        "error": error,
        "updated_at": datetime.now().isoformat(),
    }
    _atomic_write_json(ANALYSIS_STATUS_PATH, payload)


def _build_market_regime_payload(regime: MarketRegime) -> dict[str, Any]:
    return {
        "regime": regime.regime,
        "label": regime.label,
        "index_price": round(regime.index_price, 4),
        "sma_short": round(regime.sma_short, 4),
        "sma_long": round(regime.sma_long, 4),
        "performance_20d": regime.performance_20d,
    }


def _build_signal_payload(sig: Signal) -> dict[str, Any]:
    tf = sig.timeframes
    tgt = sig.targets
    fib = sig.fibonacci
    ew = sig.elliott_wave
    comm = sig.commentary
    horizon = sig.horizon_guidance
    anka_v2 = sig.anka_v2

    return {
        "symbol": sig.symbol,
        "price": round(sig.price, 4),
        "score": round(sig.score, 2),
        "signal_daily": sig.signal,
        "summary": sig.summary,
        "timeframes": {
            "daily": tf.daily if tf else sig.signal,
            "weekly": tf.weekly if tf else "",
            "monthly": tf.monthly if tf else "",
            "yearly": tf.yearly if tf else "",
        },
        "trend": sig.trend,
        "rsi": sig.rsi,
        "volume_status": sig.volume_status,
        "entry": round(sig.entry, 4),
        "stop_loss": round(sig.stop_loss, 4),
        "target": round(sig.target, 4),
        "risk_pct": round(sig.risk_pct, 2),
        "reward_pct": round(sig.reward_pct, 2),
        "rr_ratio": round(sig.rr_ratio, 2),
        "targets": {
            "short_target": tgt.short_target if tgt else 0,
            "short_rr": tgt.short_rr if tgt else 0,
            "short_reward_pct": tgt.short_reward_pct if tgt else 0,
            "medium_target": tgt.medium_target if tgt else 0,
            "medium_rr": tgt.medium_rr if tgt else 0,
            "medium_reward_pct": tgt.medium_reward_pct if tgt else 0,
            "long_target": tgt.long_target if tgt else 0,
            "long_rr": tgt.long_rr if tgt else 0,
            "long_reward_pct": tgt.long_reward_pct if tgt else 0,
            "stop_loss": tgt.stop_loss if tgt else round(sig.stop_loss, 4),
            "risk_pct": tgt.risk_pct if tgt else round(sig.risk_pct, 2),
        },
        "fibonacci": {
            "support": fib.nearest_support if fib else 0,
            "resistance": fib.nearest_resistance if fib else 0,
            "zone": fib.current_zone if fib else "",
            "swing_low": fib.swing_low if fib else 0,
            "swing_high": fib.swing_high if fib else 0,
            "retracement_levels": fib.retracement_levels if fib else {},
            "extension_levels": fib.extension_levels if fib else {},
        },
        "candle_patterns": [
            {
                "name": pattern.name,
                "direction": pattern.direction,
                "strength": pattern.strength,
                "description": pattern.english,
            }
            for pattern in sig.candle_patterns
        ],
        "candle_summary": ", ".join(pattern.name for pattern in sig.candle_patterns[:5]),
        "candle_bias": sig.candle_bias,
        "elliott_wave": {
            "current_wave": ew.current_wave if ew else "",
            "phase": ew.phase if ew else "",
            "confidence": ew.confidence if ew else "",
            "next_expected": ew.next_expected if ew else "",
        },
        "commentary": {
            "summary": comm.summary if comm else "",
            "paragraph": comm.paragraph if comm else "",
            "key_points": comm.key_points if comm else [],
            "risks": comm.risks if comm else [],
        },
        "reason": sig.reason,
        "reason_factors": list(sig.reason_factors),
        "score_breakdown": {
            "trend": sig.score_breakdown.trend,
            "momentum": sig.score_breakdown.momentum,
            "volume": sig.score_breakdown.volume,
            "price_position": sig.score_breakdown.price_position,
            "market_regime": sig.score_breakdown.market_regime,
        },
        "horizon_guidance": horizon.as_dict() if horizon else None,
        "horizon_scores": (
            sig.horizon_scores.as_dict() if sig.horizon_scores else None
        ),
        "anka_v2": anka_v2.as_dict() if anka_v2 else None,
        "tradingview_snapshot": sig.tradingview_snapshot,
        "cup_handle_quality": (
            sig.cup_handle_quality.as_dict() if sig.cup_handle_quality else None
        ),
    }


def _build_series_payload(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []

    series = []
    columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "sma_short",
        "sma_long",
        "bb_upper",
        "bb_lower",
        "rsi",
        "anka_body",
        "anka_upper_wing",
        "anka_lower_wing",
        "anka_inner_upper_wing",
        "anka_inner_lower_wing",
        "anka_valley_score",
        "anka_is_ash_phase",
    ]
    recent = df.tail(WEB_SERIES_LENGTH)

    for idx, row in recent.iterrows():
        item = {"date": pd.to_datetime(idx).date().isoformat()}
        for col in columns:
            item[col] = _safe_json_value(row[col]) if col in recent.columns else None
        series.append(item)

    return series


def save_web_snapshot(
    signals: list[Signal],
    stock_data: dict[str, pd.DataFrame],
    regime: MarketRegime,
    *,
    requested_symbols: int,
) -> Path:
    generated_at = datetime.now().isoformat()

    latest_report = {
        "generated_at": generated_at,
        "market_regime": _build_market_regime_payload(regime),
        "summary": {
            "total": len(signals),
            "buy": sum(1 for s in signals if s.signal == "AL"),
            "sell": sum(1 for s in signals if s.signal == "SAT"),
            "hold": sum(1 for s in signals if s.signal == "BEKLE"),
        },
        "meta": {
            "requested_symbols": requested_symbols,
            "successful_symbols": len(signals),
            "refresh_interval_minutes": INTRADAY_REFRESH_MINUTES,
        },
        "signals": [_build_signal_payload(sig) for sig in signals],
    }
    _atomic_write_json(LATEST_REPORT_PATH, _normalize_json(latest_report))

    for sig in signals:
        stock_payload = {
            "generated_at": generated_at,
            "market_regime": latest_report["market_regime"],
            "meta": latest_report["meta"],
            "signal": _build_signal_payload(sig),
            "series": _build_series_payload(stock_data.get(sig.symbol)),
        }
        _atomic_write_json(WEB_STOCKS_DIR / f"{sig.symbol}.json", _normalize_json(stock_payload))

    return LATEST_REPORT_PATH
