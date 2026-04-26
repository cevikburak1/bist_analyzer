# BIST Analyzer

BIST Analyzer, Borsa Istanbul hisseleri icin teknik analiz, temel degerleme, formasyon tarama ve akilli para birikim sinyallerini tek dashboard altinda toplayan Python + Next.js uygulamasidir.

Sistem yfinance ile OHLCV ve temel veri indirir, analizleri JSON snapshot olarak uretir ve `dashboard/` altindaki Next.js arayuzunde filtrelenebilir, siralanabilir ve sayfalanabilir tablolara donusturur.

## One Cikanlar

- Tum BIST sembol evreni: `data/symbols.txt` icindeki hisseler otomatik islenir.
- Teknik analiz: SMA, RSI, MACD, Bollinger, ATR, OBV, Fibonacci, Elliott, mum formasyonlari ve cok vadeli hedefler.
- ANKA v2.0: Yedi Vadi, adaptif kanatlar, kNN hacim, Fibonacci sentez teyidi ve gecmis basari kalibrasyonu.
- ANKA Motor: Katman motoru, lineer regresyon trend yogunlugu, kNN oruntu tahmini ve agirlikli sentez karari.
- Cup and Handle Quality: cup symmetry, handle depth, breakout quality, target projection ve AGPro tarzinda kalite paneli.
- Adil Deger v3.7.1: 10 degerleme metodu, sektor agirlikli agregasyon, confidence, iskonto/prim ve 8 donem finansal tablo.
- Sessiz Toplama Tarayici: RSI pozitif uyumsuzluk, OBV/CMF sessiz birikim, XU100 relatif guc ve uzun donem dip filtresi.
- TradingView snapshot dogrulama: `scanner.tradingview.com/turkey/scan` public endpoint'i best-effort son fiyat/hacim karsilastirmasi icin kullanilir.
- Dashboard: tum liste sayfalarinda alan bazli sorting ve pagination.

## Kurulum

Gereksinimler:

- Python 3.10+
- Node.js 18+

```bash
pip install -r requirements.txt
cd dashboard
npm install
cd ..
```

## Analiz Komutlari

Teknik analiz ve ANKA/Cup Handle ciktisi:

```bash
python main.py --quiet --no-html --no-charts
```

Sadece belirli semboller:

```bash
python main.py --symbols THYAO ASELS SASA --quiet --no-html --no-charts
```

Temel analiz ve Adil Deger:

```bash
python buffett_main.py --quiet
```

Sessiz Toplama tarayicisi:

```bash
python silent_accumulation_main.py
```

Belirli grup veya semboller:

```bash
python silent_accumulation_main.py --group 3
python silent_accumulation_main.py --symbols THYAO ASELS SASA
```

Dashboard:

```bash
cd dashboard
npm run dev
```

Arayuz varsayilan olarak `http://localhost:3000` adresinde acilir.

## Dashboard Sayfalari

| Sayfa | Rota | Aciklama |
| --- | --- | --- |
| Teknik Analiz | `/` | Tum hisseler, vade bazli teknik karar, hedefler, RSI, Fibonacci, mum ozeti ve Adil Deger kolonlari |
| Hisse Detay | `/hisse/[symbol]` | Teknik detay, fiyat grafikleri, hedefler, vade panelleri |
| ANKA v2 | `/anka-v2` | Yedi Vadi, kNN hacim, Fibonacci sentez, kalibrasyon listesi |
| ANKA v2 Detay | `/anka-v2/[symbol]` | TradingView tarzinda adaptif kanatlar, vadi osilatoru ve bilgi paneli |
| ANKA Motor | `/anka-engine` | K1-K5 katman, LR ve kNN motor sentez tablosu |
| ANKA Motor Detay | `/anka-engine/[symbol]` | LR + kNN + katman motor grafik paneli |
| Cup Handle | `/cup-handle-quality` | Cup and Handle kalite taramasi |
| Cup Handle Detay | `/cup-handle-quality/[symbol]` | Cup/handle kutulari, kalin kavisler, rim/target cizgileri ve kalite paneli |
| Adil Deger | `/fair-value` | 10 metotlu sektor agirlikli fair value tablosu |
| Adil Deger Detay | `/fair-value/[symbol]` | Method breakdown, confidence, iskonto/prim bandi ve finansal tablo |
| Sessiz Toplama | `/silent-accumulation` | 15 grup destekli cift sutun akilli para tarayicisi |
| Buffett | `/buffett` | Buffett tipi kalite ve temel analiz listesi |

## Uretilen Snapshot Dosyalari

```text
output/web/latest_report.json                  # teknik analiz, ANKA v2, ANKA Motor, Cup Handle
output/web/stocks/{SYMBOL}.json                # teknik hisse detaylari
output/web/buffett/latest.json                 # temel analiz ve adil deger listesi
output/web/buffett/stocks/{SYMBOL}.json        # temel/adil deger detaylari
output/web/silent_accumulation/latest.json     # sessiz toplama tarayicisi
```

## Analiz Motorlari

### Teknik Analiz

Ana teknik motor 5 kategoriden skor uretir:

| Kategori | Maks Puan | Kriterler |
| --- | ---: | --- |
| Trend | 25 | SMA50/200, golden cross, regresyon egimi |
| Momentum | 25 | RSI, MACD, histogram |
| Hacim | 20 | Hacim ortalamasi, OBV trendi |
| Fiyat Pozisyonu | 15 | 52 hafta konumu, Bollinger orta bant |
| Piyasa Uyumu | 15 | XU100 rejimi, beta |

### ANKA v2.0

`analysis/anka_v2.py` sunlari hesaplar:

- Anka Vucudu: EMA tabanli orta egilim.
- Anka Nefesi: ATR/volatilite olcumu.
- Anka Kanatlari: adaptif dis kanal ve altin oran ic kanal.
- Yedi Vadi: momentum, trend gucu ve volatilite karisimindan 0-100 faz puani.
- kNN Hacim: mum govdesi, golgeler, kapanis konumu ve relatif hacim ile yakin oruntu analizi.
- Fibonacci Sentez Teyidi: destek/direnc seviyelerine gore bonus veya temkin uyarisi.
- Gecmis Basari Kalibrasyonu: son 50 barda 3-bar ufuk basari orani.

### ANKA Motor

ANKA Motor, ANKA v2 ciktisini ikinci karar katmanina tasir:

- Katman Motoru: Vadi, Momentum, Trend, Volatilite, Sinyal.
- LR Trend Yogunlugu: lineer regresyon egimi ve R2.
- kNN Oruntu Tahmini: N=8, ND=6, NY=3, spacing=25, ATR_N=14.
- Sentez: Katman Motoru %40, LR %30, kNN %30.

### Cup and Handle Quality

`analysis/cup_handle.py` pivot tabanli cup-and-handle yasam dongusunu tarar:

- Sol rim, cup base, sag rim, handle low.
- Cup symmetry.
- Handle depth.
- Breakout quality.
- Measured target projection.

### Adil Deger

`analysis/fair_value.py` 10 metodu ayni anda hesaplar:

1. Net Earnings P/E
2. ROE-Based
3. EV/EBIT
4. EV/EBITDA
5. EV/Revenue
6. Forward P/E
7. Forward P/S
8. P/FCF
9. Graham Number
10. DCF

Varsayilan agregasyon `Sector Weighted` modudur. Eksik finansal alani olan metotlar `null` kalir; confidence degeri metotlar arasi dagilimi gosterir.

### Sessiz Toplama Tarayici

`analysis/silent_accumulation.py` sunlari tarar:

- RSI pozitif divergence.
- Dar bantta fiyat + OBV/CMF birikimi.
- XU100'e gore relatif guc.
- Uzun donem dipten en fazla %15 uzaklik filtresi.
- 15 grup mantigi ve filtre modlari: Any, 2+, Flawless, Only RSI, Only Volume, Only RS, Only CMF.

## Dogrulama

Python dosyalari:

```bash
python -m py_compile analysis/anka_v2.py analysis/cup_handle.py analysis/fair_value.py analysis/silent_accumulation.py
```

Dashboard:

```bash
cd dashboard
npm run lint
npm run build
```

## Proje Yapisi

```text
bist_analyzer/
├── analysis/
│   ├── anka_v2.py
│   ├── cup_handle.py
│   ├── fair_value.py
│   ├── silent_accumulation.py
│   ├── scoring.py
│   └── signals.py
├── data/
│   ├── downloader.py
│   ├── tradingview.py
│   └── symbols.txt
├── reports/
│   ├── web_snapshot.py
│   ├── buffett_snapshot.py
│   └── silent_accumulation_snapshot.py
├── dashboard/
│   └── src/app/
│       ├── anka-v2/
│       ├── anka-engine/
│       ├── cup-handle-quality/
│       ├── fair-value/
│       └── silent-accumulation/
├── main.py
├── buffett_main.py
└── silent_accumulation_main.py
```

## Notlar

- TradingView scanner endpoint'i resmi ve stabil bir tarihsel veri API'si degildir. Sistem bu kaynagi sadece best-effort snapshot dogrulamasi olarak kullanir.
- Teknik analiz, temel analiz ve tarayicilar yatirim tavsiyesi degildir.
- Finansal piyasalarda islem yapmak yuksek risk icerir; kararlarinizi kendi arastirmaniz ve risk yonetiminizle vermelisiniz.
