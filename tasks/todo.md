- [x] Plan onaylandıktan sonra uygulanabilir checklist oluşturuldu.
- [x] ANKA v2.0 analiz motorunu ekle.
- [x] Python sinyal hattını ve web snapshot çıktısını ANKA v2.0 verisiyle genişlet.
- [x] Dashboard TypeScript tiplerini yeni payload için güncelle.
- [x] `/anka-v2` ve `/anka-v2/[symbol]` sayfalarını oluştur.
- [ ] Python analizi, dashboard lint ve mümkünse görsel doğrulamayı çalıştır.
- [x] TradingView public scanner istemcisini opsiyonel snapshot veri kaynağı olarak ekle.
- [x] TradingView snapshot değerlerini mevcut yfinance son değerleriyle toleranslı doğrula.
- [x] ANKA detay ekranını referans görsele daha yakın grafik, bant, Fibo çizgileri, sinyal işaretleri ve panel düzeniyle güncelle.
- [ ] Python analiz, JSON alan kontrolü, dashboard lint/build ve browser görsel kontrolünü çalıştır.
- [x] ANKA motoru için LR, kNN, K1-K5 katman, sentez ağırlıkları ve uyarı alanlarını veri modeline ekle.
- [x] Yeni ANKA Motor grafik bileşeni ve ayrı sayfaları oluştur, nav’a bağla.
- [ ] ANKA Motor için Python analiz, JSON alan kontrolü, lint/build ve tarayıcı doğrulamasını çalıştır.
- [x] Cup & Handle kalite motorunu Python analiz çıktısına ekle.
- [x] Cup & Handle liste ve detay sayfalarını, grafik overlay ve paneliyle oluştur.
- [ ] Cup & Handle için Python analiz, JSON kontrolü, lint/build ve mümkünse tarayıcı doğrulamasını çalıştır.
- [x] 10 yöntemli Adil Değer modelini temel analiz çıktısına ekle.
- [x] Fair Value liste ve detay sayfalarını panel, bant ve tablo görünümüyle oluştur.
- [x] Adil Değer için Python temel analiz/JSON kontrolü, dashboard lint/build ve uygun doğrulamaları çalıştır.
- [x] Sessiz Toplama için ayrı Python scanner, snapshot ve CLI çıktısını ekle.
- [x] Dashboard loader/API ve TypeScript tiplerini Silent Accumulation payload için ekle.
- [x] 15 grup + filtreli çift sütun dashboard sayfasını oluştur ve nav’a bağla.
- [x] Sessiz Toplama için Python scanner, JSON kontrolü, dashboard lint/build doğrulamalarını çalıştır.
- [x] Tüm BIST evreni için teknik, temel/adil değer ve sessiz toplama çıktıları yeniden üretildi.
- [x] Teknik Analiz sayfasına adil değer, iskonto/prim kolonları ve sorting eklendi.
- [x] ANKA v2, ANKA Motor, Cup Handle, Adil Değer ve Sessiz Toplama liste sayfalarına pagination ve alan bazlı sorting eklendi.

## AMD Model Engine
- [x] Plan onaylandıktan sonra uygulanabilir checklist oluşturuldu.
- [x] Intraday downloader, cache ve pipeline veri akışını ekle.
- [x] AMD/CISD/sweep/projection analiz motorunu oluştur ve sinyal payload’una bağla.
- [x] Web snapshot, TypeScript tipleri ve detay intraday serisini genişlet.
- [x] AMD liste ve hisse detay sayfalarını mevcut dashboard desenleriyle ekle.
- [x] Python küçük sembol analizi, JSON kontrolü, lint/build ve browser doğrulaması çalıştır.

## İnceleme
- AMD Model Engine için intraday yfinance/cache hattı, Python AMD motoru, web snapshot alanları ve `/amd-model` + `/amd-model/[symbol]` dashboard sayfaları eklendi. `python main.py --symbols THYAO ASELS --force-download --no-html --no-charts`, AMD JSON kontrolü, `npm run lint`, `npm run build` ve route HTTP kontrolleri geçti.

## Morpheus Scoring
- [x] EMA13/20/21/50/200, ADX, V_KAT ve Bollinger sıkışma göstergelerini ekle.
- [x] Ana teknik skoru additive Morpheus modeline geçir.
- [x] AL/SAT/BEKLE aksiyonlarını Morpheus skor, WR%, ADX, V_KAT ve aşırı EMA uzaklığına göre yeniden kalibre et.
- [x] Web snapshot, CSV/JSON, terminal, HTML ve PNG raporlarına Morpheus metriklerini ekle.
- [x] Dashboard ana tablo ve detay skor dağılımını Morpheus kolonlarıyla güncelle.
- [x] Python testleri, dashboard lint/type check ve sentetik sinyal doğrulamasını çalıştır.
- [x] Eski 0-100 vade skor çıktısını yeni snapshot için kapat; ana teknik yüzeylerde yalnızca Morpheus skoru kalsın.
- [x] BEKLE/KAR AL dahil tüm hisseler için stop/hedef seviyelerini üret.
- [x] ATR eksik veya yetersiz olduğunda stop/hedef için swing aralığı ya da fiyat yüzdesi fallback'i kullan.
- [x] `output/web/latest_report.json` yeniden üretildi ve 499/499 hissede stop/hedef dolu olduğu doğrulandı.

## İnceleme
- Morpheus Scoring için ana teknik puanlama artık 0-100 piyasa rejimi ağırlıklı model yerine 100 üstüne çıkabilen additive skor üretiyor. Eski vade skor paneli yeni snapshot'ta üretilmiyor; BEKLE/KAR AL dahil tüm hisselerde stop/hedef doluyor. ATR eksikse swing aralığı, o da yoksa fiyatın %3'ü ile fallback hedef/stop üretiliyor. `output/web/latest_report.json` yeniden üretildi ve eksik stop/hedef sayısı 0 olarak doğrulandı. `pytest`, `npm run lint`, `npx tsc --noEmit`, `compileall` ve sentetik sinyal doğrulamaları geçti; snapshot sonrası tekrar test/lint denemesi kullanıcı tarafından kesildi.
