<div align="center">

# 📈 BIST Hisse Senedi Analiz ve Sinyal Sistemi

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Borsa İstanbul (BIST) paylarını gelişmiş teknik analiz yöntemleriyle değerlendiren, 0-100 arası skorlayan ve çok faktörlü **AL/SAT/BEKLE** sinyalleri üreten kapsamlı analiz sistemi ve modern web arayüzü.

[Özellikler](#-özellikler) • [Kurulum](#-kurulum) • [Kullanım](#-kullanım) • [Skorlama Sistemi](#-skorlama-sistemi) • [Dashboard](#-web-dashboard)

</div>

---

## 🌟 Özellikler

- **Geniş Sembol Evreni**: `data/symbols.txt` içindeki BIST pay listesini otomatik analiz eder.
- **Otomatik Veri Çekme**: `yfinance` entegrasyonu ile günlük OHLCV verilerini indirir ve önbellekler.
- **Gelişmiş Teknik Analiz**: SMA, RSI, MACD, Bollinger Bantları, OBV, Fibonacci Seviyeleri, Elliott Dalga Teorisi ve Mum Formasyonları.
- **5 Kategorili Skorlama Motoru**: Trend, Momentum, Hacim, Fiyat Pozisyonu ve Piyasa Uyumu (Beta) metriklerini harmanlayarak 0-100 arası skor üretir.
- **Akıllı Sinyal Sistemi**: Çok faktörlü kurallarla AL/SAT/BEKLE kararları verir.
- **Piyasa Rejimi Tespiti**: XU100 endeksine dayalı yükseliş/düşüş/yatay rejim analizi (Düşüş rejiminde riskli sinyaller filtrelenir).
- **Çoklu Rapor Formatları**:
  - 🖥️ **Terminal**: `Rich` kütüphanesi ile renkli ve okunabilir CLI çıktısı
  - 📊 **Görsel**: `Matplotlib` ile PNG formatında tablo ve grafikler
  - 🌐 **İnteraktif**: `Plotly` ile HTML raporlar
  - 💾 **Veri**: Entegrasyonlar için CSV ve JSON çıktıları
- **Modern Web Dashboard**: Analiz sonuçlarını görselleştiren, Next.js tabanlı şık kullanıcı arayüzü.

## 🚀 Kurulum

### Gereksinimler
- Python 3.10 veya üzeri
- Node.js 18+ (Dashboard için)

### Adımlar

1. **Projeyi Klonlayın**
   ```bash
   git clone https://github.com/kullaniciadi/bist_analyzer.git
   cd bist_analyzer
   ```

2. **Python Bağımlılıklarını Yükleyin**
   ```bash
   pip install -r requirements.txt
   ```

3. **Dashboard Bağımlılıklarını Yükleyin (Opsiyonel)**
   ```bash
   cd dashboard
   npm install
   cd ..
   ```

## 💻 Kullanım

Sistemi çalıştırmak için `main.py` dosyasını kullanabilirsiniz. Çeşitli parametrelerle analizi özelleştirebilirsiniz:

```bash
# Tüm BIST pay listesini analiz et
python main.py

# Sadece belirli hisseleri analiz et
python main.py --symbols THYAO ASELS KCHOL FROTO

# Analiz bittikten sonra React Dashboard'u otomatik başlat
python main.py --dashboard

# Sessiz mod (Terminal çıktısı vermez, sadece dosyaları oluşturur)
python main.py --quiet

# PNG grafik veya HTML rapor oluşturmayı devre dışı bırak
python main.py --no-charts
python main.py --no-html

# Önbelleği (cache) yoksay ve tüm verileri baştan indir
python main.py --force-download
```

## 🧠 Skorlama Sistemi

Her hisse senedi 5 ana kategoride değerlendirilir ve maksimum 100 puan üzerinden skorlanır:

| Kategori | Maks Puan | Kriterler |
|----------|-----------|-----------|
| **Trend Analizi** | 25 | Fiyat vs SMA50/200, Golden Cross durumu, Regresyon eğimi |
| **Momentum** | 25 | RSI ideal bölgesi, MACD kesişimleri ve gücü |
| **Hacim** | 20 | Hacim ortalaması kıyaslaması, OBV (On-Balance Volume) trendi |
| **Fiyat Pozisyonu** | 15 | 52-haftalık zirve/dip pozisyonu, Bollinger bantları konumu |
| **Piyasa Uyumu** | 15 | XU100 endeksine göre göreceli performans, Beta katsayısı |

## 🎯 Sinyal Kuralları

Sistem, hesaplanan skor ve teknik göstergelere dayanarak aşağıdaki kurallarla sinyal üretir:

- 🟢 **AL**: Skor >= 65, RSI 30-70 arası, Fiyat > 200 SMA, Hacim >= 1.2x ortalama
- 🔴 **SAT**: Skor <= 35 **VEYA** (RSI > 75 + Bollinger üst bant kırılımı) **VEYA** (MACD negatif + SMA50 altı)
- ⚪ **BEKLE**: Diğer tüm durumlar

> ⚠️ **Not:** Piyasa rejimi "Düşüş" (Bear Market) olarak tespit edilirse, AL sinyalleri için kriterler otomatik olarak zorlaştırılır veya filtrelenir.

## 🖥️ Web Dashboard

Proje, analiz sonuçlarını modern bir arayüzde inceleyebileceğiniz bir Next.js dashboard içerir.

Dashboard'u başlatmak için:
```bash
# Analiz ile birlikte başlatmak için:
python main.py --dashboard

# Veya manuel olarak başlatmak için:
cd dashboard
npm run dev
```
Tarayıcınızda `http://localhost:3000` adresine giderek arayüze erişebilirsiniz.

## 📁 Proje Yapısı

```text
bist_analyzer/
├── main.py                  # Ana orkestrasyon ve CLI giriş noktası
├── config.py                # Merkezi yapılandırma ayarları
├── data/
│   ├── downloader.py        # yfinance entegrasyonu ve önbellekleme
│   └── symbols.txt          # Analiz edilecek BIST pay listesi
├── analysis/
│   ├── indicators.py        # Teknik gösterge hesaplamaları
│   ├── scoring.py           # 5 kategorili skorlama motoru
│   ├── signals.py           # Sinyal üretim mantığı
│   ├── candle_patterns.py   # Mum formasyonları tespiti
│   └── market_regime.py     # XU100 tabanlı piyasa rejimi analizi
├── reports/                 # Terminal, PNG, HTML ve JSON/CSV raporlayıcıları
├── dashboard/               # Next.js tabanlı web arayüzü
├── output/                  # Üretilen rapor ve veri çıktıları
└── logs/                    # Sistem logları
```

## ⚙️ Yapılandırma

`config.py` dosyası üzerinden sistemin davranışını tamamen özelleştirebilirsiniz:
- Sinyal eşikleri (Örn: AL için min skor: 65)
- İndikatör periyotları (RSI: 14, SMA: 50/200)
- Hacim çarpanı (1.2x)
- Rate limiting ve önbellek süreleri

## ⚠️ Yasal Uyarı

Bu yazılım **kesinlikle yatırım tavsiyesi vermez**. Üretilen tüm sinyaller, skorlar ve analizler tamamen matematiksel formüllere ve geçmiş fiyat verilerine dayalı teknik göstergelerdir. 

Finansal piyasalarda işlem yapmak yüksek risk içerir. Yatırım kararlarınızı almadan önce kendi araştırmanızı yapmalı ve profesyonel bir finansal danışmandan destek almalısınız. Bu yazılımın kullanımından doğabilecek herhangi bir maddi kayıptan geliştiriciler sorumlu tutulamaz.

---
<div align="center">
<i>Bu proje <a href="https://cursor.sh">Cursor</a> ile geliştirilmiştir.</i>
</div>