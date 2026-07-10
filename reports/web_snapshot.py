"""
Web dashboard snapshot and analysis status helpers.

The React dashboard consumes these JSON artifacts so it can render the latest
successful analysis while a background refresh is running.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from analysis.market_regime import MarketRegime
from analysis.signals import Signal
from config import (
    ANALYSIS_LOCK_PATH,
    ANALYSIS_STATUS_PATH,
    INTRADAY_INTERVAL,
    INTRADAY_REFRESH_MINUTES,
    LATEST_REPORT_PATH,
    WEB_INTRADAY_SERIES_LENGTH,
    WEB_SERIES_LENGTH,
    WEB_STOCKS_DIR,
)

logger = logging.getLogger(__name__)

MARKET_TIMEZONE = ZoneInfo("Europe/Istanbul")
MARKET_OPEN_TIME = dt_time(10, 0)
MARKET_CLOSE_TIME = dt_time(18, 10)
BAR_COMPLETION_GRACE = timedelta(minutes=5)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_istanbul(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=MARKET_TIMEZONE)
    return value.astimezone(MARKET_TIMEZONE)


def _interval_delta(interval: str = INTRADAY_INTERVAL) -> timedelta:
    value = interval.strip().lower()
    units = {"wk": "weeks", "m": "minutes", "h": "hours", "d": "days"}
    for suffix in ("wk", "m", "h", "d"):
        if value.endswith(suffix):
            amount = int(value[: -len(suffix)])
            if amount > 0:
                return timedelta(**{units[suffix]: amount})
    raise ValueError(f"Desteklenmeyen bar aralığı: {interval}")


def _market_is_open(now: datetime) -> bool:
    local_now = _as_istanbul(now)
    return (
        local_now.weekday() < 5
        and MARKET_OPEN_TIME <= local_now.time() < MARKET_CLOSE_TIME
    )


def _local_timestamp(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize(MARKET_TIMEZONE)
    return timestamp.tz_convert(MARKET_TIMEZONE)


def _bar_data_as_of(
    df: pd.DataFrame | None,
    *,
    intraday: bool,
) -> datetime | None:
    if df is None or df.empty:
        return None
    latest = _local_timestamp(df.index[-1]).to_pydatetime()
    session_close = datetime.combine(
        latest.date(), MARKET_CLOSE_TIME, tzinfo=MARKET_TIMEZONE
    )
    if not intraday:
        return session_close
    return min(latest + _interval_delta(), session_close)


def _source_freshness(
    df: pd.DataFrame | None,
    *,
    intraday: bool,
    now: datetime,
) -> dict[str, Any]:
    data_as_of = _bar_data_as_of(df, intraday=intraday)
    if data_as_of is None:
        return {
            "status": "missing",
            "data_as_of": None,
            "age_minutes": None,
            "last_bar_complete": None,
            "dropped_incomplete_bars": 0,
        }

    local_now = _as_istanbul(now)
    completion_time = data_as_of + BAR_COMPLETION_GRACE
    last_bar_complete = completion_time <= local_now
    age_minutes = round(
        max(0.0, (local_now - data_as_of).total_seconds() / 60.0), 1
    )
    if not last_bar_complete:
        status = "incomplete"
    else:
        max_age = (
            (_interval_delta().total_seconds() / 60)
            + INTRADAY_REFRESH_MINUTES
            + 10
            if intraday and _market_is_open(now)
            else 4 * 24 * 60
        )
        status = "fresh" if age_minutes <= max_age else "stale"

    attrs = getattr(df, "attrs", {}) if df is not None else {}
    return {
        "status": status,
        "data_as_of": data_as_of.astimezone(timezone.utc).isoformat(),
        "age_minutes": age_minutes,
        "last_bar_complete": last_bar_complete,
        "dropped_incomplete_bars": int(attrs.get("dropped_incomplete_bars", 0)),
    }


def _summarize_source_freshness(
    data: dict[str, pd.DataFrame],
    expected_symbols: set[str],
    *,
    intraday: bool,
    now: datetime,
) -> dict[str, Any]:
    details = {
        symbol: _source_freshness(df, intraday=intraday, now=now)
        for symbol, df in data.items()
        if not expected_symbols or symbol in expected_symbols
    }
    missing_symbols = sorted(expected_symbols - set(details))
    stale_symbols = sorted(
        symbol
        for symbol, item in details.items()
        if item["status"] in {"stale", "incomplete"}
    )
    as_of_values = [
        item["data_as_of"] for item in details.values() if item["data_as_of"]
    ]
    ages = [
        item["age_minutes"]
        for item in details.values()
        if item["age_minutes"] is not None
    ]

    if not details:
        status = "missing"
    elif stale_symbols or missing_symbols:
        status = "partial" if len(stale_symbols) + len(missing_symbols) < len(expected_symbols) else "stale"
    else:
        status = "fresh"

    return {
        "status": status,
        "latest_data_as_of": max(as_of_values) if as_of_values else None,
        "oldest_data_as_of": min(as_of_values) if as_of_values else None,
        "max_age_minutes": max(ages) if ages else None,
        "available_symbols": len(details),
        "expected_symbols": len(expected_symbols),
        "stale_symbols": stale_symbols,
        "missing_symbols": missing_symbols,
    }


def _build_freshness_payload(
    stock_data: dict[str, pd.DataFrame],
    stock_intraday: dict[str, pd.DataFrame],
    expected_symbols: set[str],
    *,
    now: datetime,
) -> dict[str, Any]:
    daily = _summarize_source_freshness(
        stock_data, expected_symbols, intraday=False, now=now
    )
    intraday = _summarize_source_freshness(
        stock_intraday, expected_symbols, intraday=True, now=now
    )
    statuses = {daily["status"], intraday["status"]}
    if statuses == {"fresh"}:
        status = "fresh"
    elif statuses == {"missing"}:
        status = "missing"
    else:
        status = "degraded"
    return {
        "status": status,
        "timezone": str(MARKET_TIMEZONE),
        "checked_at": now.astimezone(timezone.utc).isoformat(),
        "daily": daily,
        "intraday": intraday,
    }


def _stock_freshness_payload(
    daily_df: pd.DataFrame | None,
    intraday_df: pd.DataFrame | None,
    *,
    now: datetime,
) -> dict[str, Any]:
    daily = _source_freshness(daily_df, intraday=False, now=now)
    intraday = _source_freshness(intraday_df, intraday=True, now=now)
    statuses = {daily["status"], intraday["status"]}
    if statuses == {"fresh"}:
        status = "fresh"
    elif daily["status"] == "missing":
        status = "missing"
    else:
        status = "degraded"
    return {
        "status": status,
        "timezone": str(MARKET_TIMEZONE),
        "daily": daily,
        "intraday": intraday,
    }


def _latest_data_as_of(*values: str | None) -> str | None:
    timestamps = [pd.Timestamp(value) for value in values if value]
    if not timestamps:
        return None
    return max(timestamps).isoformat()


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
        "started_at": _utc_now().isoformat(),
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
        "updated_at": _utc_now().isoformat(),
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
    amd_model = sig.amd_model

    return {
        "symbol": sig.symbol,
        "price": round(sig.price, 4),
        "score": round(sig.score, 2),
        "signal_daily": sig.signal,
        "action": sig.action or sig.signal,
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
            "squeeze_breakout": sig.score_breakdown.squeeze_breakout,
            "wr_pct": sig.score_breakdown.wr_pct,
            "wr_samples": sig.score_breakdown.wr_samples,
            "adx": sig.score_breakdown.adx,
            "v_kat": sig.score_breakdown.v_kat,
            "dzl_ok": sig.score_breakdown.dzl_ok,
            "sqz_ok": sig.score_breakdown.sqz_ok,
            "ema_distance_pct": sig.score_breakdown.ema_distance_pct,
            "overextended": sig.score_breakdown.overextended,
            "details": sig.score_breakdown.details,
        },
        "horizon_guidance": horizon.as_dict() if horizon else None,
        "horizon_scores": (
            sig.horizon_scores.as_dict() if sig.horizon_scores else None
        ),
        "anka_v2": anka_v2.as_dict() if anka_v2 else None,
        "amd_model": amd_model.as_dict() if amd_model else None,
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
        "ema_fast",
        "ema_signal",
        "ema20",
        "ema50",
        "ema200",
        "bb_upper",
        "bb_lower",
        "bb_width_pct",
        "adx",
        "v_kat",
        "perfect_order",
        "squeeze_on",
        "squeeze_breakout",
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


def _build_intraday_series_payload(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []

    series = []
    columns = ["open", "high", "low", "close", "volume", "atr", "rsi"]
    recent = df.tail(WEB_INTRADAY_SERIES_LENGTH)

    for idx, row in recent.iterrows():
        item = {"date": pd.to_datetime(idx).isoformat()}
        for col in columns:
            item[col] = _safe_json_value(row[col]) if col in recent.columns else None
        series.append(item)

    return series


def save_web_snapshot(
    signals: list[Signal],
    stock_data: dict[str, pd.DataFrame],
    stock_intraday: dict[str, pd.DataFrame],
    regime: MarketRegime,
    *,
    requested_symbols: int,
) -> Path:
    now = _utc_now()
    generated_at = now.isoformat()
    expected_symbols = {sig.symbol for sig in signals}
    freshness = _build_freshness_payload(
        stock_data,
        stock_intraday,
        expected_symbols,
        now=now,
    )
    data_as_of = _latest_data_as_of(
        freshness["daily"]["latest_data_as_of"],
        freshness["intraday"]["latest_data_as_of"],
    )

    latest_report = {
        "generated_at": generated_at,
        "data_as_of": data_as_of,
        "freshness": freshness,
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
        daily_df = stock_data.get(sig.symbol)
        intraday_df = stock_intraday.get(sig.symbol)
        stock_freshness = _stock_freshness_payload(
            daily_df,
            intraday_df,
            now=now,
        )
        stock_data_as_of = _latest_data_as_of(
            stock_freshness["daily"]["data_as_of"],
            stock_freshness["intraday"]["data_as_of"],
        )
        stock_payload = {
            "generated_at": generated_at,
            "data_as_of": stock_data_as_of,
            "freshness": stock_freshness,
            "market_regime": latest_report["market_regime"],
            "meta": latest_report["meta"],
            "signal": _build_signal_payload(sig),
            "series": _build_series_payload(daily_df),
            "intraday_series": _build_intraday_series_payload(intraday_df),
        }
        _atomic_write_json(WEB_STOCKS_DIR / f"{sig.symbol}.json", _normalize_json(stock_payload))

    return LATEST_REPORT_PATH
