## Lessons

- React render içinde `Math.random()` gibi impure değerleri key olarak kullanma; lint bunu hata sayıyor ve rerender davranışını kararsızlaştırıyor. Deterministik `period-index` gibi key üret.
- Analiz doğrulaması öncesi `output/web/analysis.lock` ve `output/web/buffett/buffett.lock` stale kalmış mı kontrol et; önceki dev-server refresh denemeleri küçük sembol doğrulamasını engelleyebiliyor.
- Teknik aksiyon etiketi `GÜÇLÜ AL`/`KAR AL` gibi genişleyebilir; stop/hedef ve zaman dilimi hesaplarını bozmamak için ana `signal` alanını `AL`/`SAT`/`BEKLE` tutup tablo etiketi için ayrı `action` alanı kullan.
- Kullanıcı "tüm skorlamalar Morpheus" dediğinde eski 0-100 yardımcı skorları da yeni snapshot'tan kaldır; aksi halde ana tablo Morpheus olsa bile detay ekranında eski kategori puanları kafa karıştırır.
- Stop/hedef seviyeleri sadece AL/SAT için değil, BEKLE/KAR AL satırları için de gösterge amaçlı üretilmeli; hedef yönü sinyal yoksa EMA200/trend eğimi/DMI ile seç.
- ATR eksik olduğunda stop/hedefi boş bırakma; swing aralığı veya fiyat yüzdesi fallback'i kullanarak her fiyatlı hisse için pozitif seviye üret.
