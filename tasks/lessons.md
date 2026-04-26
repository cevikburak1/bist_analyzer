## Lessons

- React render içinde `Math.random()` gibi impure değerleri key olarak kullanma; lint bunu hata sayıyor ve rerender davranışını kararsızlaştırıyor. Deterministik `period-index` gibi key üret.
- Analiz doğrulaması öncesi `output/web/analysis.lock` ve `output/web/buffett/buffett.lock` stale kalmış mı kontrol et; önceki dev-server refresh denemeleri küçük sembol doğrulamasını engelleyebiliyor.
