"""
BIST Analyzer - Merkezi Ayarlar

Tüm eşik değerler, periyotlar ve yol tanımları burada tutulur.
CLI argümanları ile override edilebilir.
"""

import os
from pathlib import Path

# ── Proje Dizinleri ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"
WEB_OUTPUT_DIR = OUTPUT_DIR / "web"
WEB_STOCKS_DIR = WEB_OUTPUT_DIR / "stocks"

SYMBOLS_FILE = DATA_DIR / "symbols.txt"
LATEST_REPORT_PATH = WEB_OUTPUT_DIR / "latest_report.json"
ANALYSIS_STATUS_PATH = WEB_OUTPUT_DIR / "analysis_status.json"
ANALYSIS_LOCK_PATH = WEB_OUTPUT_DIR / "analysis.lock"

# ── Buffett (Temel Analiz) Hattı ─────────────────────────────────────────────
WEB_BUFFETT_DIR = WEB_OUTPUT_DIR / "buffett"
WEB_BUFFETT_STOCKS_DIR = WEB_BUFFETT_DIR / "stocks"
BUFFETT_REPORT_PATH = WEB_BUFFETT_DIR / "latest.json"
BUFFETT_STATUS_PATH = WEB_BUFFETT_DIR / "status.json"
BUFFETT_LOCK_PATH = WEB_BUFFETT_DIR / "buffett.lock"

# ── Veri Çekme ───────────────────────────────────────────────────────────────
DATA_PERIOD = "2y"              # yfinance period parametresi (aylık/yıllık sinyaller için 2 yıl)
INTRADAY_CACHE_DIR = CACHE_DIR / "intraday"
INTRADAY_PERIOD = "60d"         # yfinance intraday retention sınırlarına uygun AMD penceresi
INTRADAY_INTERVAL = "60m"       # AMD/CISD için varsayılan LTF bar aralığı
REQUEST_DELAY = 0.3             # yfinance çağrıları arasında bekleme (saniye)
MAX_WORKERS = 4                 # Paralel indirme thread sayısı

# ── İndikatör Periyotları ────────────────────────────────────────────────────
SMA_SHORT = 50
SMA_LONG = 200
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD = 2
OBV_SMA_PERIOD = 20

# ── Hacim Ayarları ───────────────────────────────────────────────────────────
VOLUME_AVG_PERIOD = 20          # Hacim ortalaması periyodu
VOLUME_SHORT_PERIOD = 5         # Kısa dönem hacim karşılaştırma
VOLUME_MULTIPLIER = 1.2         # AL sinyali için minimum hacim çarpanı

# ── Trend Analizi ────────────────────────────────────────────────────────────
TREND_REGRESSION_PERIOD = 20    # Lineer regresyon penceresi

# ── Skor Eşikleri ────────────────────────────────────────────────────────────
BUY_THRESHOLD = 65
SELL_THRESHOLD = 35

# ── Skor Ağırlıkları (toplam 100) ───────────────────────────────────────────
SCORE_WEIGHTS = {
    "trend": 25,
    "momentum": 25,
    "volume": 20,
    "price_position": 15,
    "market_regime": 15,
}

# ── Sinyal Kuralları ─────────────────────────────────────────────────────────
RSI_OVERBOUGHT = 75
RSI_OVERSOLD = 30
RSI_IDEAL_LOW = 40
RSI_IDEAL_HIGH = 70
RSI_BUY_LOW = 30
RSI_BUY_HIGH = 70

BETA_LOW = 0.5
BETA_HIGH = 1.5

# ── Piyasa Rejimi ────────────────────────────────────────────────────────────
MARKET_INDEX_SYMBOL = "XU100.IS"
MARKET_REGIME_PERIOD = 20       # Son N günlük performans penceresi

# ── Rapor Ayarları ───────────────────────────────────────────────────────────
MAX_BUY_SIGNALS_IN_CHART = 12   # PNG grafikte gösterilecek maks AL sinyali
REPORT_DATE_FORMAT = "%Y%m%d"
WEB_SERIES_LENGTH = 120
WEB_INTRADAY_SERIES_LENGTH = 180
INTRADAY_REFRESH_MINUTES = 15

# ── Loglama ──────────────────────────────────────────────────────────────────
LOG_FILE = LOG_DIR / "errors.log"
LOG_LEVEL = "INFO"

# Gerekli dizinleri oluştur
for d in [
    CACHE_DIR,
    INTRADAY_CACHE_DIR,
    OUTPUT_DIR,
    LOG_DIR,
    WEB_OUTPUT_DIR,
    WEB_STOCKS_DIR,
    WEB_BUFFETT_DIR,
    WEB_BUFFETT_STOCKS_DIR,
]:
    d.mkdir(parents=True, exist_ok=True)
