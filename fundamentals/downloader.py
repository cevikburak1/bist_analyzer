"""
yfinance fundamentals indirici + parquet cache.

Çekilen alanlar (Buffett skorlama için yeterli minimum set):

- info anlık özet: trailingPE, priceToBook, returnOnEquity, debtToEquity,
  profitMargins, grossMargins, dividendYield, sharesOutstanding, marketCap,
  freeCashflow, currentPrice, totalCash, totalDebt, sector, industry, longName.
- annual income statement: NetIncome, TotalRevenue, EBIT, InterestExpense
- annual balance sheet: TotalEquity, TotalDebt, TotalAssets, CurrentAssets,
  CurrentLiabilities, OrdinarySharesNumber
- annual cashflow: FreeCashFlow (yoksa OperatingCashFlow - CapitalExpenditure)
- dividends: yıllık toplam temettü serisi

Cache: data/cache_fundamentals/{SYMBOL}_{YYYYMMDD}.json
NaN değerler korunur (None olarak); skorlama tarafı "Yetersiz Veri" kararını verir.
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import yfinance as yf

from config import CACHE_DIR, REQUEST_DELAY, SYMBOLS_FILE
from fundamentals.sector_map import classify_sector, SectorClass

logger = logging.getLogger(__name__)


FUNDAMENTALS_CACHE_DIR = CACHE_DIR.parent / "cache_fundamentals"
FUNDAMENTALS_CACHE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FundamentalsBundle:
    """Tek bir hisse için Buffett skoruna girecek tüm temel veri paketi."""
    symbol: str
    fetched_at: str
    sector: dict[str, str]                          # SectorClass dict olarak
    info: dict[str, Any]                            # sayısal özet + piyasa metadatası
    income_annual: list[dict[str, Optional[float]]] # eski->yeni yıl sıralı
    balance_annual: list[dict[str, Optional[float]]]
    cashflow_annual: list[dict[str, Optional[float]]]
    dividends_annual: list[dict[str, Optional[float]]]
    fetch_errors: list[str] = field(default_factory=list)
    # Bu downloader yalnızca Yahoo'nun `.IS` sembollerini indirir. Alanı
    # bundle üzerinde saklamak, currency eksik olduğunda BIST hissesinin ABD
    # hissesi sanılmasını engeller. Eski cache'ler için varsayılan BIST'tir.
    market: str = "BIST"

    def has_minimum_data(self) -> bool:
        """Aynı mali yılda net kâr ve pozitif özsermaye varsa ``True``.

        Gelir tablosu ile bilançoyu liste sırasına göre eşlemek, kaynaklardan
        birinde yıl eksik olduğunda farklı yılları karşılaştırabiliyordu.
        """
        if not self.income_annual:
            return False
        if not self.balance_annual:
            return False

        income_by_year = {
            _period_year(row.get("period")): row
            for row in self.income_annual
            if _period_year(row.get("period")) is not None
        }
        balance_by_year = {
            _period_year(row.get("period")): row
            for row in self.balance_annual
            if _period_year(row.get("period")) is not None
        }
        common_years = sorted(set(income_by_year) & set(balance_by_year), reverse=True)
        for year in common_years:
            equity = _safe_float(balance_by_year[year].get("total_equity"))
            if (
                income_by_year[year].get("net_income") is not None
                and equity is not None
                and equity > 0
            ):
                return True

        # Dönem alanı bulunmayan eski/elle oluşturulmuş paketlerle uyumluluk.
        if not income_by_year and not balance_by_year:
            equity = _safe_float(self.balance_annual[-1].get("total_equity"))
            return (
                self.income_annual[-1].get("net_income") is not None
                and equity is not None
                and equity > 0
            )
        return False


# ── yfinance yardımcıları ────────────────────────────────────────────────────


def _safe_float(value: Any) -> Optional[float]:
    """NaN/None/numerik olmayan değerleri None döndürür."""
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


def _period_year(value: Any) -> Optional[int]:
    """Yıllık tablo dönemini mali yıl anahtarına dönüştür."""
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    try:
        return int(pd.to_datetime(value).year)
    except (TypeError, ValueError, OverflowError):
        return None


def _row_value(df: pd.DataFrame, candidates: tuple[str, ...]) -> Optional[pd.Series]:
    """yfinance tablolarında satır adı sürüm bazında değişiyor; bilinen adların
    ilkini döndür."""
    if df is None or df.empty:
        return None
    for name in candidates:
        if name in df.index:
            return df.loc[name]
    return None


def _annualize(df: pd.DataFrame, mapping: dict[str, tuple[str, ...]]) -> list[dict[str, Optional[float]]]:
    """yfinance tablosunu, eski->yeni sıralı yıllık dict listesine dönüştür.

    `mapping`: çıkış alanı -> (yfinance satır adı adayları)
    """
    if df is None or df.empty:
        return []

    rows: dict[str, pd.Series] = {}
    for out_key, candidates in mapping.items():
        series = _row_value(df, candidates)
        if series is not None:
            rows[out_key] = series

    if not rows:
        return []

    # Tarihleri metinsel sıraya değil gerçek dönem sırasına koy. yfinance
    # annual tablolarındaki her kolon tek bir mali yıldır; bu nedenle bunları
    # toplamak değil, ayrı yıllık gözlemler olarak korumak gerekir.
    def column_sort_key(col: Any) -> tuple[bool, int, str]:
        parsed = pd.to_datetime(col, errors="coerce")
        if pd.isna(parsed):
            return (False, 0, str(col))
        return (True, int(parsed.value), str(col))

    columns_sorted = sorted(df.columns, key=column_sort_key)
    annual: list[dict[str, Optional[float]]] = []
    for col in columns_sorted:
        period = pd.to_datetime(col).date().isoformat() if hasattr(col, "year") else str(col)
        item: dict[str, Optional[float]] = {"period": period}
        for out_key, series in rows.items():
            try:
                item[out_key] = _safe_float(series.get(col))
            except Exception:
                item[out_key] = None
        annual.append(item)
    return annual


_INCOME_MAPPING = {
    "net_income": ("Net Income", "NetIncome", "Net Income Common Stockholders"),
    "total_revenue": ("Total Revenue", "TotalRevenue", "Operating Revenue"),
    "ebit": ("EBIT", "Operating Income", "OperatingIncome"),
    "interest_expense": ("Interest Expense", "InterestExpense"),
    "gross_profit": ("Gross Profit", "GrossProfit"),
}

_BALANCE_MAPPING = {
    "total_equity": ("Total Equity Gross Minority Interest", "Stockholders Equity",
                     "Common Stock Equity", "TotalEquityGrossMinorityInterest"),
    "total_debt": ("Total Debt", "TotalDebt"),
    "total_assets": ("Total Assets", "TotalAssets"),
    "current_assets": ("Current Assets", "CurrentAssets"),
    "current_liabilities": ("Current Liabilities", "CurrentLiabilities"),
    "shares_outstanding": ("Ordinary Shares Number", "OrdinarySharesNumber",
                           "Share Issued", "Common Stock"),
    "cash": ("Cash And Cash Equivalents", "CashAndCashEquivalents",
             "Cash Cash Equivalents And Short Term Investments"),
}

_CASHFLOW_MAPPING = {
    "free_cash_flow": ("Free Cash Flow", "FreeCashFlow"),
    "operating_cash_flow": ("Operating Cash Flow", "Cash Flow From Continuing Operating Activities"),
    "capital_expenditure": ("Capital Expenditure", "CapitalExpenditure"),
}


def _patch_free_cash_flow(rows: list[dict[str, Optional[float]]]) -> None:
    """FCF satırı yoksa OCF - CapEx ile doldur (yfinance bazı sembollerde
    FCF satırını vermiyor)."""
    for row in rows:
        if row.get("free_cash_flow") is not None:
            continue
        ocf = row.get("operating_cash_flow")
        capex = row.get("capital_expenditure")
        if ocf is not None and capex is not None:
            row["free_cash_flow"] = ocf + capex  # capex zaten negatif gelir
        else:
            row["free_cash_flow"] = None


_INFO_KEYS = (
    "trailingPE", "forwardPE", "priceToBook", "returnOnEquity", "returnOnAssets",
    "debtToEquity", "profitMargins", "grossMargins", "operatingMargins",
    "dividendYield", "fiveYearAvgDividendYield",
    "sharesOutstanding", "marketCap", "freeCashflow",
    "currentPrice", "previousClose", "totalCash", "totalDebt",
    "totalRevenue", "netIncomeToCommon", "ebitda", "totalAssets",
    "currentRatio", "quickRatio",
)


def _extract_info(info: dict) -> dict[str, Any]:
    """yfinance info'dan sayısal/string anahtarları topla; sayılar safe_float."""
    out: dict[str, Any] = {}
    for k in _INFO_KEYS:
        out[k] = _safe_float(info.get(k))
    out["longName"] = info.get("longName") or info.get("shortName") or ""
    out["sector_raw"] = info.get("sector") or ""
    out["industry_raw"] = info.get("industry") or ""
    out["currency"] = info.get("currency") or ""
    out["exchange"] = info.get("exchange") or info.get("fullExchangeName") or ""
    out["quoteType"] = info.get("quoteType") or ""
    out["market"] = "BIST"
    return out


def _extract_dividends(ticker: yf.Ticker) -> list[dict[str, Optional[float]]]:
    """Yıllık temettü toplamları (eski->yeni sıralı)."""
    try:
        div = ticker.dividends
    except Exception:
        return []

    if div is None or len(div) == 0:
        return []

    try:
        annual = div.groupby(div.index.year).sum()
    except Exception:
        return []

    rows: list[dict[str, Optional[float]]] = []
    for year, amount in sorted(annual.items()):
        rows.append({"period": str(year), "dividend": _safe_float(amount)})
    return rows


# ── Cache ────────────────────────────────────────────────────────────────────


def _cache_path(symbol: str, today: str) -> Path:
    return FUNDAMENTALS_CACHE_DIR / f"{symbol}_{today}.json"


def _clean_old_cache(symbol: str, today: str) -> None:
    for old in FUNDAMENTALS_CACHE_DIR.glob(f"{symbol}_*.json"):
        if today not in old.name:
            old.unlink(missing_ok=True)


def _read_cache(symbol: str, today: str) -> Optional[FundamentalsBundle]:
    path = _cache_path(symbol, today)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return FundamentalsBundle(**data)
    except Exception:
        logger.warning("Fundamentals cache okunamadı: %s", symbol)
        return None


def _write_cache(bundle: FundamentalsBundle, today: str) -> None:
    path = _cache_path(bundle.symbol, today)
    path.write_text(
        json.dumps(asdict(bundle), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _clean_old_cache(bundle.symbol, today)


# ── Public API ───────────────────────────────────────────────────────────────


def download_fundamentals(symbol: str, force: bool = False) -> Optional[FundamentalsBundle]:
    """Tek bir BIST hissesi için fundamentals çekip cache'ler."""
    sym = symbol.upper().replace(".IS", "")
    yahoo_symbol = f"{sym}.IS"
    today = date.today().strftime("%Y%m%d")

    if not force:
        cached = _read_cache(sym, today)
        if cached is not None:
            logger.debug("Fundamentals cache: %s", sym)
            return cached

    errors: list[str] = []

    info: dict = {}
    income_df: Optional[pd.DataFrame] = None
    balance_df: Optional[pd.DataFrame] = None
    cashflow_df: Optional[pd.DataFrame] = None
    dividends_rows: list[dict[str, Optional[float]]] = []

    try:
        ticker = yf.Ticker(yahoo_symbol)
        try:
            info = ticker.info or {}
        except Exception as e:
            errors.append(f"info: {e}")

        try:
            income_df = ticker.income_stmt
        except Exception as e:
            errors.append(f"income_stmt: {e}")

        try:
            balance_df = ticker.balance_sheet
        except Exception as e:
            errors.append(f"balance_sheet: {e}")

        try:
            cashflow_df = ticker.cashflow
        except Exception as e:
            errors.append(f"cashflow: {e}")

        try:
            dividends_rows = _extract_dividends(ticker)
        except Exception as e:
            errors.append(f"dividends: {e}")

    except Exception as e:
        logger.error("Fundamentals indirme hatası [%s]: %s", yahoo_symbol, e)
        return None

    income_rows = _annualize(income_df, _INCOME_MAPPING) if income_df is not None else []
    balance_rows = _annualize(balance_df, _BALANCE_MAPPING) if balance_df is not None else []
    cashflow_rows = _annualize(cashflow_df, _CASHFLOW_MAPPING) if cashflow_df is not None else []
    _patch_free_cash_flow(cashflow_rows)

    sector: SectorClass = classify_sector(sym, info)

    bundle = FundamentalsBundle(
        symbol=sym,
        fetched_at=date.today().isoformat(),
        sector={"kind": sector.kind, "label": sector.label, "source": sector.source},
        info=_extract_info(info),
        income_annual=income_rows,
        balance_annual=balance_rows,
        cashflow_annual=cashflow_rows,
        dividends_annual=dividends_rows,
        fetch_errors=errors,
        market="BIST",
    )

    _write_cache(bundle, today)
    logger.info("Fundamentals indirildi: %s (income=%d, bs=%d, cf=%d)",
                sym, len(income_rows), len(balance_rows), len(cashflow_rows))
    return bundle


def load_symbols(filepath: Optional[Path] = None) -> list[str]:
    """symbols.txt'tan sembol listesini oku (mevcut data.downloader.load_symbols
    ile aynı format)."""
    filepath = filepath or SYMBOLS_FILE
    out: list[str] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line.upper())
    return out


def download_all_fundamentals(
    symbols: Optional[list[str]] = None,
    force: bool = False,
) -> dict[str, FundamentalsBundle]:
    """Tüm semboller için fundamentals indir. Cache'i kullanır, rate limit uygular."""
    if symbols is None:
        symbols = load_symbols()

    out: dict[str, FundamentalsBundle] = {}
    failed: list[str] = []

    for i, sym in enumerate(symbols, 1):
        logger.info("[Buffett %d/%d] %s", i, len(symbols), sym)
        bundle = download_fundamentals(sym, force=force)
        if bundle is not None:
            out[sym] = bundle
        else:
            failed.append(sym)
        if i < len(symbols):
            time.sleep(REQUEST_DELAY)

    logger.info("Fundamentals tamamlandı: %d başarılı, %d başarısız", len(out), len(failed))
    if failed:
        logger.warning("Fundamentals başarısız: %s", ", ".join(failed))
    return out
