# BIST Analyzer

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=111111)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![BIST](https://img.shields.io/badge/Market-Borsa%20Istanbul-0F766E)

BIST Analyzer, Borsa Istanbul hisseleri icin teknik analiz, temel degerleme,
formasyon tarama, akilli para birikimi ve intraday AMD model okumasini tek
dashboard altinda birlestiren Python + Next.js analiz platformudur.

Sistem `yfinance` ile gunluk ve intraday OHLCV verisi indirir, analizleri JSON
snapshot olarak uretir ve `dashboard/` altindaki Next.js arayuzunde
filtrelenebilir, siralanabilir ve detayli grafiklerle incelenebilir hale getirir.

## Neler Var?

- Tum BIST evreni: `data/symbols.txt` icindeki semboller otomatik islenir.
- Teknik analiz: SMA, RSI, MACD, Bollinger, ATR, OBV, Fibonacci, Elliott, mum
  formasyonlari, cok vadeli hedefler ve aciklanabilir karar gerekceleri.
- AMD Model: intraday Power of 3 dongusu, accumulation box, manipulation sweep,
  CISD, distribution projection, HTF sweep, EQH/EQL ve key open seviyeleri.
- ANKA v2.0: Yedi Vadi, adaptif kanatlar, kNN hacim, Fibonacci sentez teyidi ve
  gecmis basari kalibrasyonu.
- ANKA Motor: K1-K5 katman motoru, lineer regresyon, kNN oruntu tahmini ve
  agirlikli sentez karari.
- Cup and Handle Quality: cup symmetry, handle depth, breakout quality ve
  measured target projection.
- Adil Deger v3.7.1: 10 degerleme metodu, sektor agirlikli agregasyon,
  confidence, iskonto/prim ve finansal tablo incelemesi.
- Sessiz Toplama Tarayici: RSI pozitif uyumsuzluk, OBV/CMF birikimi, XU100
  relatif guc ve uzun donem dip filtresi.
- TradingView snapshot dogrulama: public scanner endpoint'i best-effort son
  fiyat/hacim karsilastirmasi icin kullanilir.

## Sistem Mimarisi

```text
data/symbols.txt
      |
      v
data/downloader.py ---------------> gunluk OHLCV cache
      |                              intraday AMD cache
      v
analysis/
      |-- scoring.py
      |-- signals.py
      |-- amd_model.py
      |-- anka_v2.py
      |-- cup_handle.py
      |-- fair_value.py
      |-- silent_accumulation.py
      v
reports/web_snapshot.py ----------> output/web/*.json
      |
      v
dashboard/src/app ----------------> Next.js dashboard routes
```

Ana akista `main.py`, gunluk veriyle teknik sinyal uretir; ayni semboller icin
ayri intraday veri indirip AMD motorunu calistirir. Web dashboard sadece
uretilmis JSON snapshot'lari okur; analiz ve arayuz katmanlari bilincli olarak
birbirinden ayridir.

## Kurulum

Gereksinimler:

- Python 3.10+
- Node.js 18+
- Windows, macOS veya Linux terminali

```bash
pip install -r requirements.txt
cd dashboard
npm install
cd ..
```

Dashboard'u baslatmak icin:

```bash
cd dashboard
npm run dev
```

Varsayilan adres: `http://localhost:3000`

## Analiz Komutlari

Tum BIST evreni icin teknik analiz, ANKA, Cup Handle ve AMD snapshot'i:

```bash
python main.py --quiet --no-html --no-charts
```

Belirli sembollerle hizli dogrulama:

```bash
python main.py --symbols THYAO ASELS SASA --quiet --no-html --no-charts
```

Veri cache'ini yok sayarak yeniden indirme:

```bash
python main.py --force-download --no-html --no-charts
```

Temel analiz ve Adil Deger:

```bash
python buffett_main.py --quiet
```

Sessiz Toplama tarayicisi:

```bash
python silent_accumulation_main.py
python silent_accumulation_main.py --group 3
python silent_accumulation_main.py --symbols THYAO ASELS SASA
```

## Dashboard Haritasi

### Teknik ve Hisse Detay

- `LineChart` Teknik Analiz: `/`
  Tum hisseler icin skor, karar, hedef, RSI, Fibonacci, mum ozeti, adil deger
  kolonlari ve vade bazli kararlar.
- `LineChart` Hisse Detay: `/hisse/[symbol]`
  Teknik grafik, fiyat/indikator serileri, hedefler, vade panelleri ve
  aciklanabilir karar gerekceleri.

### AMD Model

- `Target` AMD Model: `/amd-model`
  Intraday AMD aday tablosu; model bias, faz, skor, sweep, CISD ve summary
  alanlariyla siralanabilir liste.
- `Target` AMD Model Detay: `/amd-model/[symbol]`
  Intraday mum grafigi, mavi accumulation kutusu, kirmizi manipulation bolgesi,
  yesil distribution alani, CISD cizgisi, 1.0/2.0/4.0 projection seviyeleri,
  EQH/EQL ve key open panelleri.

### ANKA ve Formasyon Motorlari

- `Flame` ANKA v2: `/anka-v2`
  Yedi Vadi, kNN hacim, Fibonacci sentez, kalibrasyon ve ana sinyal listesi.
- `BrainCircuit` ANKA Motor: `/anka-engine`
  K1-K5 katman, LR ve kNN motor sentez tablosu.
- `Trophy` Cup Handle: `/cup-handle-quality`
  Cup and Handle kalite taramasi ve target projection.

### Temel Analiz ve Akilli Para

- `Banknote` Adil Deger: `/fair-value`
  10 metotlu sektor agirlikli fair value tablosu.
- `Radar` Sessiz Toplama: `/silent-accumulation`
  15 grup destekli akilli para birikimi tarayicisi.
- `Landmark` Buffett: `/buffett`
  Buffett tipi kalite ve temel analiz listesi.

## AMD Model Detaylari

`analysis/amd_model.py`, CandelaCharts AMD / Power of 3 mantigini BIST intraday
verisine uyarlayan izole bir motor olarak calisir.

### 1. Accumulation

Motor, intraday context penceresinin erken bolumunde dar range ve fiyat
sikismasini tespit eder. Bu alan dashboard'da mavi kutu olarak gosterilir.

Uretilen alanlar:

- `accumulation.high`
- `accumulation.low`
- `accumulation.midpoint`
- `accumulation.start_time`
- `accumulation.end_time`

### 2. Manipulation

Accumulation high/low seviyesinin disina tasan ve tekrar range icine kapanan
hareket liquidity sweep olarak okunur. Sweep yonu model bias'ini belirler:

- `BULLISH`: Accumulation low sweep + rejection.
- `BEARISH`: Accumulation high sweep + rejection.
- `NEUTRAL`: Henuz anlamli sweep yok.

### 3. CISD

CISD, sweep sonrasi teslimat durumunun degistigini gosteren structural close
seviyesidir. Bullish modelde accumulation high ustu kapanis, bearish modelde
accumulation low alti kapanis onay olarak kullanilir.

Dashboard'da:

- CISD onay durumu.
- CISD seviyesi.
- CISD zamani.
- Onay sonrasi distribution bolgesi.

### 4. Distribution Projections

CISD onaylaninca accumulation range genisliginden fib-style hedefler uretilir:

- `1.0`
- `2.0`
- `4.0`

Bu seviyeler detay grafikte yatay projection cizgileri olarak gosterilir.

### 5. Liquidity ve Timing

Motor ayrica su alanlari uretir:

- `htf_sweep`: gunluk onceki high/low sweep ve rejection.
- `equal_highs`: intraday EQH likidite havuzlari.
- `equal_lows`: intraday EQL likidite havuzlari.
- `key_opens`: BIST acilis, gun ortasi ve kapanisa yakin open seviyeleri.
- `alerts`: CISD, displacement ve HTF sweep uyumu gibi ozet uyarilar.

## Analiz Motorlari

### Teknik Analiz

Ana teknik skor 5 kategori uzerinden hesaplanir:

- Trend: SMA50/200, golden cross ve regresyon egimi.
- Momentum: RSI, MACD ve histogram.
- Hacim: hacim ortalamasi ve OBV trendi.
- Fiyat Pozisyonu: 52 hafta konumu ve Bollinger orta bant.
- Piyasa Uyumu: XU100 rejimi ve beta.

### ANKA v2.0

`analysis/anka_v2.py` sunlari hesaplar:

- Anka Vucudu: EMA tabanli orta egilim.
- Anka Nefesi: ATR/volatilite olcumu.
- Anka Kanatlari: adaptif dis kanal ve altin oran ic kanal.
- Yedi Vadi: momentum, trend gucu ve volatilite karisimindan 0-100 faz puani.
- kNN Hacim: mum govdesi, golgeler, kapanis konumu ve relatif hacim ile yakin
  oruntu analizi.
- Fibonacci Sentez Teyidi: destek/direnc seviyelerine gore bonus veya temkin
  uyarisi.
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

Varsayilan agregasyon `Sector Weighted` modudur. Eksik finansal alani olan
metotlar `null` kalir; confidence degeri metotlar arasi dagilimi gosterir.

### Sessiz Toplama Tarayici

`analysis/silent_accumulation.py` sunlari tarar:

- RSI pozitif divergence.
- Dar bantta fiyat + OBV/CMF birikimi.
- XU100'e gore relatif guc.
- Uzun donem dipten en fazla %15 uzaklik filtresi.
- 15 grup mantigi ve filtre modlari: Any, 2+, Flawless, Only RSI, Only Volume,
  Only RS, Only CMF.

## Uretilen Snapshot Dosyalari

```text
output/web/latest_report.json                  # teknik analiz, AMD, ANKA, Cup Handle
output/web/stocks/{SYMBOL}.json                # hisse detaylari + intraday AMD serisi
output/web/buffett/latest.json                 # temel analiz ve adil deger listesi
output/web/buffett/stocks/{SYMBOL}.json        # temel/adil deger detaylari
output/web/silent_accumulation/latest.json     # sessiz toplama tarayicisi
```

AMD detay JSON'unda iki farkli seri bulunur:

- `series`: gunluk teknik grafik ve ANKA alanlari.
- `intraday_series`: AMD grafigi icin intraday OHLCV, ATR ve RSI alanlari.

## Proje Yapisi

```text
bist_analyzer/
|-- analysis/
|   |-- amd_model.py
|   |-- anka_v2.py
|   |-- cup_handle.py
|   |-- fair_value.py
|   |-- silent_accumulation.py
|   |-- scoring.py
|   `-- signals.py
|-- data/
|   |-- downloader.py
|   |-- tradingview.py
|   `-- symbols.txt
|-- reports/
|   |-- web_snapshot.py
|   |-- buffett_snapshot.py
|   `-- silent_accumulation_snapshot.py
|-- dashboard/
|   `-- src/
|       |-- app/
|       |   |-- amd-model/
|       |   |-- anka-v2/
|       |   |-- anka-engine/
|       |   |-- cup-handle-quality/
|       |   |-- fair-value/
|       |   `-- silent-accumulation/
|       |-- components/
|       `-- lib/
|-- main.py
|-- buffett_main.py
`-- silent_accumulation_main.py
```

## Dogrulama

Python modullerini derle:

```bash
python -m compileall analysis data reports main.py
```

Kucuk sembol setiyle veri ve AMD payload dogrula:

```bash
python main.py --symbols THYAO ASELS --force-download --no-html --no-charts
```

Tum evreni dashboard icin yeniden uret:

```bash
python main.py --no-html --no-charts
```

Dashboard kalite kontrolleri:

```bash
cd dashboard
npm run lint
npm run build
```

## Son Dogrulama Notu

AMD entegrasyonu sonrasinda tum BIST snapshot'i yeniden uretilmistir:

```text
total=499
amd=499
requested=501
successful=499
```

`requested` ve `successful` farki, veri kaynaginin ilgili semboller icin gecerli
OHLCV dondurmemesinden kaynaklanabilir; sistem bu sembolleri rapora dahil etmez.

## Onemli Notlar

- TradingView scanner endpoint'i resmi ve stabil bir tarihsel veri API'si
  degildir. Sistem bu kaynagi sadece best-effort snapshot dogrulamasi olarak
  kullanir.
- Yfinance intraday retention siniri nedeniyle AMD modeli varsayilan olarak son
  `60d` / `60m` veri penceresiyle calisir.
- Teknik analiz, temel analiz, AMD modeli ve tarayicilar yatirim tavsiyesi
  degildir.
- Finansal piyasalarda islem yapmak yuksek risk icerir; kararlarinizi kendi
  arastirmaniz ve risk yonetiminizle vermelisiniz.
