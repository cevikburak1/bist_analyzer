# BIST Hisse Senedi Analiz ve Sinyal Sistemi

Borsa Istanbul (BIST) paylarını teknik analiz ile değerlendiren,
0-100 arası skorlayan ve AL/SAT/BEKLE sinyali üreten Python tabanlı analiz sistemi.

## Özellikler

- **Geniş Sembol Evreni**: `data/symbols.txt` içindeki repo-committed BIST pay listesini analiz eder
- **Otomatik Veri Çekme**: yfinance ile seçili BIST paylarının günlük OHLCV verilerini indirir
- **5 Kategorili Skorlama**: Trend, Momentum, Hacim, Fiyat Pozisyonu, Piyasa Uyumu
- **Akıllı Sinyal Sistemi**: Çok faktörlü AL/SAT/BEKLE kararları
- **Piyasa Rejimi Tespiti**: XU100 bazlı yükseliş/düşüş/yatay rejim analizi
- **Çoklu Rapor Formatları**: Terminal (Rich), PNG (Matplotlib), HTML (Plotly), CSV, JSON

## Kurulum

```bash
cd bist_analyzer
pip install -r requirements.txt
```

## Kullanım

```bash
# Repo içindeki tam BIST pay listesini analiz et
python main.py

# Belirli hisseleri analiz et
python main.py --symbols THYAO ASELS KCHOL FROTO

# Sessiz mod (terminal çıktısı yok, sadece dosyalar)
python main.py --quiet

# PNG grafik oluşturma
python main.py --no-charts

# HTML rapor oluşturma
python main.py --no-html

# Cache'i yoksay, tüm verileri yeniden indir
python main.py --force-download

# Analizden sonra React dashboard'u başlat
python main.py --dashboard
```

Varsayılan sembol evreni `data/symbols.txt` dosyasından yüklenir. Dosya, repo içinde tutulan geniş BIST pay listesidir; isterseniz bu listeyi doğrudan düzenleyebilir veya çalıştırma anında `--symbols` ile daraltabilirsiniz.

## Skorlama Sistemi

| Kategori | Maks Puan | Kriterler |
|----------|-----------|-----------|
| Trend Analizi | 25 | Fiyat vs SMA50/200, Golden Cross, Regresyon eğimi |
| Momentum | 25 | RSI ideal bölge, MACD durumu |
| Hacim | 20 | Hacim ortalaması, OBV trendi |
| Fiyat Pozisyonu | 15 | 52-hafta pozisyonu, Bollinger bantları |
| Piyasa Uyumu | 15 | XU100 performansı, Beta |

## Sinyal Kuralları

**AL**: Skor >= 65, RSI 30-70, fiyat > 200 SMA, hacim >= 1.2x ortalama

**SAT**: Skor <= 35 VEYA (RSI > 75 + BB üst kırılımı) VEYA (MACD negatif + SMA50 altı)

**BEKLE**: Diğer tüm durumlar

> Düşüş rejiminde AL sinyalleri otomatik olarak filtrelenir.

## Çıktılar

| Dosya | Konum | Açıklama |
|-------|-------|----------|
| Terminal raporu | stdout | Rich ile renkli tablo |
| Tablo PNG | `output/bist_table_YYYYMMDD.png` | Formatlı tablo görseli |
| Grafik PNG | `output/bist_charts_YYYYMMDD.png` | AL sinyalli hisse grafikleri |
| İnteraktif HTML | `output/bist_interactive_YYYYMMDD.html` | Plotly interaktif rapor |
| CSV | `output/signals_YYYYMMDD.csv` | Tüm sinyal verileri |
| JSON | `output/signals_YYYYMMDD.json` | API uyumlu format |

## Proje Yapısı

```
bist_analyzer/
├── main.py                  # Ana çalıştırma ve CLI
├── config.py                # Merkezi ayarlar
├── data/
│   ├── downloader.py        # yfinance veri indirme + cache
│   ├── symbols.txt          # Repo-committed BIST pay listesi
│   └── cache/               # Parquet cache dosyaları
├── analysis/
│   ├── indicators.py        # Teknik göstergeler (SMA, RSI, MACD, BB, OBV)
│   ├── scoring.py           # 5 kategorili skorlama motoru
│   ├── signals.py           # AL/SAT/BEKLE sinyal mantığı
│   └── market_regime.py     # Piyasa rejimi tespiti
├── reports/
│   ├── terminal_report.py   # Rich terminal raporu
│   ├── chart_report.py      # Matplotlib PNG grafikleri
│   └── html_report.py       # Plotly interaktif HTML
├── output/                  # Rapor çıktıları
├── logs/                    # Hata logları
└── requirements.txt
```

## Yapılandırma

`config.py` dosyasından tüm parametreler ayarlanabilir:
- Skor eşikleri (AL: 65, SAT: 35)
- İndikatör periyotları (RSI: 14, SMA: 50/200)
- Hacim çarpanı (1.2x)
- Rate limiting süresi

## Uyarı

Bu sistem yatırım tavsiyesi vermez. Tüm analizler tamamen teknik veriye dayanır.
Yatırım kararlarınızı kendi araştırmanıza dayandırın.
