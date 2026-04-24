"""
Buffett snapshot yazıcı.

Üretilen JSON dosyaları:
- output/web/buffett/latest.json           (liste sayfası için)
- output/web/buffett/stocks/{SYMBOL}.json  (detay sayfası için)
- output/web/buffett/status.json           (analiz durumu)
- output/web/buffett/buffett.lock          (eşzamanlılık kilidi)

Mevcut [reports/web_snapshot.py] deseninden esinlenir; yapısal olarak ayrı
tutulmuştur ki teknik hattaki değişiklikler etkilemesin.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from analysis.buffett_score import BuffettScoreBreakdown
from analysis.buffett_signal import BuffettSignal
from analysis.intrinsic_value import IntrinsicValueResult
from config import (
    BUFFETT_LOCK_PATH,
    BUFFETT_REPORT_PATH,
    BUFFETT_STATUS_PATH,
    WEB_BUFFETT_STOCKS_DIR,
)
from fundamentals.downloader import FundamentalsBundle

logger = logging.getLogger(__name__)


# ── JSON normalizasyonu ──────────────────────────────────────────────────────


def _safe_json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    return value


def _normalize(data: Any) -> Any:
    if isinstance(data, dict):
        return {str(k): _normalize(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_normalize(v) for v in data]
    return _safe_json_value(data)


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning("Buffett JSON okunamadı: %s", path)
        return {}


# ── Lock & Status ────────────────────────────────────────────────────────────


def acquire_buffett_lock(run_id: str, requested_symbols: int) -> bool:
    if BUFFETT_LOCK_PATH.exists():
        return False
    _atomic_write_json(
        BUFFETT_LOCK_PATH,
        {
            "run_id": run_id,
            "pid": os.getpid(),
            "requested_symbols": requested_symbols,
            "started_at": datetime.now().isoformat(),
        },
    )
    return True


def clear_buffett_lock() -> None:
    BUFFETT_LOCK_PATH.unlink(missing_ok=True)


def is_buffett_running() -> bool:
    return BUFFETT_LOCK_PATH.exists()


def write_buffett_status(
    *,
    state: str,
    run_id: str,
    requested_symbols: int,
    successful_symbols: int = 0,
    error: str = "",
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
) -> None:
    existing = _read_json(BUFFETT_STATUS_PATH)
    last_success_at = existing.get("last_success_at")
    if state == "idle" and finished_at:
        last_success_at = finished_at

    payload = {
        "state": state,
        "run_id": run_id,
        "pid": os.getpid(),
        "requested_symbols": requested_symbols,
        "successful_symbols": successful_symbols,
        "started_at": started_at,
        "finished_at": finished_at,
        "last_success_at": last_success_at,
        "error": error,
        "updated_at": datetime.now().isoformat(),
    }
    _atomic_write_json(BUFFETT_STATUS_PATH, payload)


# ── Per-stock snapshot inşası ────────────────────────────────────────────────


@dataclass
class BuffettStockResult:
    bundle: FundamentalsBundle
    score: BuffettScoreBreakdown
    intrinsic: IntrinsicValueResult
    signal: BuffettSignal


def _key_metrics_summary(bundle: FundamentalsBundle, score: BuffettScoreBreakdown) -> dict:
    """Liste sayfasında gösterilecek özet metrikler."""
    info = bundle.info
    moat = score.moat.details
    val = score.valuation.details
    fin = score.financial.details
    return {
        "pe": val.get("pe"),
        "pb": val.get("pb"),
        "p_fcf": val.get("p_fcf"),
        "roe_avg_5y": moat.get("roe_avg_5y"),
        "net_margin_avg_5y": moat.get("net_margin_avg_5y"),
        "net_income_cagr": moat.get("net_income_cagr"),
        "debt_to_equity": fin.get("debt_to_equity"),
        "dividend_yield": info.get("dividendYield"),
    }


def _history_series(bundle: FundamentalsBundle) -> dict:
    """Detay sayfasındaki grafikler için 5y geçmiş seriler."""
    income = bundle.income_annual[-5:]
    balance = bundle.balance_annual[-5:]
    cashflow = bundle.cashflow_annual[-5:]

    roe_series: list[dict] = []
    for inc, bal in zip(income, balance):
        ni = inc.get("net_income")
        eq = bal.get("total_equity")
        roe = (ni / eq) if (ni is not None and eq) else None
        roe_series.append({"period": inc.get("period"), "roe": roe})

    revenue_series = [
        {"period": r.get("period"), "value": r.get("total_revenue")} for r in income
    ]
    net_income_series = [
        {"period": r.get("period"), "value": r.get("net_income")} for r in income
    ]
    fcf_series = [
        {"period": r.get("period"), "value": r.get("free_cash_flow")} for r in cashflow
    ]
    de_series: list[dict] = []
    for bal in balance:
        eq = bal.get("total_equity")
        debt = bal.get("total_debt")
        de = (debt / eq) if (debt is not None and eq) else None
        de_series.append({"period": bal.get("period"), "value": de})

    return {
        "roe": roe_series,
        "revenue": revenue_series,
        "net_income": net_income_series,
        "free_cash_flow": fcf_series,
        "debt_to_equity": de_series,
        "dividends": list(bundle.dividends_annual[-5:]),
    }


def _build_summary_payload(result: BuffettStockResult) -> dict:
    """Liste sayfasında gösterilecek satır."""
    bundle = result.bundle
    info = bundle.info
    return {
        "symbol": bundle.symbol,
        "name": info.get("longName") or bundle.symbol,
        "sector": bundle.sector,
        "label_key": result.signal.label_key,
        "label": result.signal.label,
        "color": result.signal.color,
        "score": round(result.score.total_score, 2),
        "data_quality_pct": round(result.score.data_quality_pct, 1),
        "current_price": _safe_json_value(info.get("currentPrice") or info.get("previousClose")),
        "intrinsic_value": _safe_json_value(result.intrinsic.intrinsic_value_per_share),
        "margin_of_safety": _safe_json_value(result.signal.margin_of_safety),
        "holding_recommendation": result.signal.holding_recommendation,
        "warnings_count": len(result.signal.warnings),
        "key_metrics": _key_metrics_summary(bundle, result.score),
    }


def _build_detail_payload(result: BuffettStockResult, generated_at: str) -> dict:
    """Detay sayfasının ihtiyacı olan tam payload."""
    return {
        "generated_at": generated_at,
        "symbol": result.bundle.symbol,
        "name": result.bundle.info.get("longName") or result.bundle.symbol,
        "sector": result.bundle.sector,
        "info": result.bundle.info,
        "signal": result.signal.as_dict(),
        "score": result.score.as_dict(),
        "intrinsic": result.intrinsic.as_dict(),
        "history": _history_series(result.bundle),
        "fetch_errors": list(result.bundle.fetch_errors),
        "fetched_at": result.bundle.fetched_at,
    }


# ── Public ───────────────────────────────────────────────────────────────────


def save_buffett_snapshot(results: list[BuffettStockResult]) -> Path:
    """Liste + detay JSON'larını yazar; latest.json yolunu döndürür."""
    generated_at = datetime.now().isoformat()

    summaries = [_build_summary_payload(r) for r in results]

    label_counts: dict[str, int] = {}
    for r in results:
        label_counts[r.signal.label_key] = label_counts.get(r.signal.label_key, 0) + 1

    latest = {
        "generated_at": generated_at,
        "summary": {
            "total": len(results),
            "by_label": label_counts,
        },
        "items": summaries,
    }

    _atomic_write_json(BUFFETT_REPORT_PATH, _normalize(latest))

    for r in results:
        detail = _build_detail_payload(r, generated_at)
        _atomic_write_json(
            WEB_BUFFETT_STOCKS_DIR / f"{r.bundle.symbol}.json",
            _normalize(detail),
        )

    logger.info("Buffett snapshot yazıldı: %s (%d hisse)", BUFFETT_REPORT_PATH, len(results))
    return BUFFETT_REPORT_PATH
