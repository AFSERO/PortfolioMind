# Part 5D — Live Evidence Acquisition

## Yapı ve kullanım

`live_providers.py` üç somut adapter içerir: `YahooFinanceMarketDataProvider`,
`GoogleNewsRSSProvider`, `SECDisclosureProvider`. İlk ikisi mevcut market/news
contract'larını kullanır; SEC için vendor-independent `DisclosureProvider` ve
`DisclosureItemRecord` eklendi. `StaticDisclosureProvider` ve mevcut static
provider'lar deterministik testlerde kalır. Yeni dependency veya migration yoktur.

Provider'lara transaction dışında kullanılabilen `InstrumentRecord` listesi verilir.
UUID çağrıları bu küçük, process-local identity listesinden çözülür; provider'lar
Session veya DB bağlantısı tutmaz. Doğrudan InstrumentRecord da kabul edilir.
Destek yalnız doğrulanmış US venue + equity kimlikleri içindir; desteklenmeyen venue,
instrument type veya ticker `DataUnavailableError` üretir. Bu bir security-master
veya instrument yaratma sistemi değildir.

```python
with session.begin():
    instrument = InstrumentRepository(session).get(instrument_id)

market = YahooFinanceMarketDataProvider([instrument])
news = GoogleNewsRSSProvider([instrument])
# II_SEC_USER_AGENT eksik/geçersizse constructor açık configuration error verir.
disclosures = SECDisclosureProvider([instrument])
workflow = ThesisReviewWorkflow(
    session, ai_provider, market, news, portfolio_provider,
    disclosure_provider=disclosures,
)
# Bu part içinde workflow.run çağrılmadı.
```

SEC bilinçli olarak kullanılmayacaksa `disclosure_provider=None` verilir:
context `unavailable / not_configured` gösterir. Constructor hatasını gizlice
başarılı boş sonuç olarak çevirmeyin. Python yalnız process environment okur;
`.env` otomatik yüklenmez. `.env.example` yalnız örnek contact bilgisi içerir.
Gerçek application adı ve contact email `II_SEC_USER_AGENT` ile tanımlanmalıdır;
örnek adres live çağrılarda kabul edilmez. Kullanıcının kişisel bilgisi kodda yoktur.

## Kaynaklar ve sınırlar

### Yahoo Finance

Structured `query1.finance.yahoo.com/v8/finance/chart/<symbol>` endpoint'inden
`regularMarketPrice`, `regularMarketTime` ve currency okunur. Kaynak sembolü,
EQUITY türü ve currency eşleşmesi kontrol edilir. Fiyat positive/finite olmalı;
kaynak zamanı UTC'ye çevrilir, erişim saati fiyat saati yerine yazılmaz.
Kaynak regular-session/latest fiyatıdır; gecikme belirsizdir, real-time garantisi
yoktur. After-hours fiyatı gibi sunulmaz. Endpoint public/anahtarsız fakat resmî
stabilite SLA'sı yoktur; 403/429 veya format değişikliği unavailable olabilir.
History bu MVP'de explicit `price_history_not_implemented` verir.

### Google News RSS

Structured RSS query şirket adı + ticker + after/before günlerini kullanır.
Feed araması gün hassasiyetinde olduğundan dış sorgu birer gün genişletilir;
exact `since <= published_at <= until` filtresi yerelde uygulanır. Sonuçlar
tarihe göre sıralanır, URL bazında tekrarlar ayıklanır, limit en fazla 10'dur.
Başlık, publisher, orijinal RSS URL'si ve UTC pubDate korunur. RSS HTML description
context'e alınmaz. Google yönlendirmesi/publisher makalesi otomatik açılmaz.

Her sonuç `RADAR_UNVERIFIED` taşır. Publisher Reuters olsa dahi RSS kaydı doğrulanmış
primary evidence olmaz. Arama şirketle ilgisiz sonuç üretebilir; instrument etiketi
sorgu kapsamını ifade eder, makalenin materiality veya entity doğrulaması değildir.
Feed bounded ve exhaustive değildir; başarılı boş sonuç bütün web'de haber yok demek
değildir. Bozuk item sessizce atılıp başarılı boş sonuç üretilmez; parsing hatası döner.

### SEC

Resmî `www.sec.gov/files/company_tickers.json` mapping'i instance başına 24 saat TTL
cache ile kullanılır. Sembol→10-digit CIK çözülür. `data.sec.gov/submissions/CIK....json`
üzerinden yalnız current filing metadata alınır; response CIK eşleşmesi doğrulanır.
Parallel JSON array uzunlukları, accession ve primaryDocument yolu kontrol edilir.
Form 4 için kullanılan `xslF345.../` gibi güvenli alt klasörler desteklenir.

Filtreleme UTC `acceptanceDateTime` üzerinden yapılır; `filingDate` ayrıca metadata'da
korunur. Eksik/naive acceptance zamanı için yapay intraday timestamp üretilmez;
provider error döner. Resmî filing URL, form, accession, source ve `PRIMARY` etiketi
context'e girer. Primary etiketi filing kaynağını belirtir; filing içeriği okunmuş
ve ekonomik yorumu doğrulanmış anlamına gelmez.

Current submissions JSON son filing metadata grubunu tek response'ta getirir;
endpoint'in intrinsic tarih kapsamı request-side daraltılamaz. Yalnız review window
içindeki en fazla 10 kayıt döner. Eski archive dosyaları veya filing body indirilmez.
İstenen pencere current submissions'ın kapsadığı dönemi aşarsa açık unavailable
verilir; eksik history başarılı sıfır sonuç sayılmaz.

SEC API anahtar gerektirmez; resmî belgeler submissions formatını ve Fair Access
kurallarını açıklar:
[SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces),
[SEC Developer Resources](https://www.sec.gov/about/developer-resources).
Yayınlanan üst sınır 10 istek/saniye; uygulama tüm SEC adapter instance'ları için
process-local lock ile **2 istek/saniye** uygular. Çok process/host kullanımı için
ortak rate budget kurulmadı; bu MVP tek process kullanımını varsayar.

## HTTP ve workflow güvenliği

Standard-library HTTPS istemcisi: GET only, fixed host/path allowlist, TLS verification,
5 saniye connect ve 10 saniye read timeout, body okuması için süre sınırı, en fazla
4 MB response. Redirect'ler ve compressed response'lar reddedilir. Retry yoktur;
403/429 karşısında farklı kanal veya kimlikle tekrar denenmez. JSON nonfinite values,
XML DTD/entities ve alternate null-byte XML encoding reddedilir. AI URL'si, arbitrary
hostname, shell veya browser automation kullanılmaz. Dönen haber/filing URL'leri
yalnız referanstır; provider onları fetch etmez.

ThesisReviewWorkflow önce kısa DB transaction'ıyla baseline okur, sonra transaction
kapalıyken providers çağırır. `build_supplemental_context` aktif transaction'lı Session
ile çağrılırsa erken hata verir; caller transaction'ı gizlice commit edilmez.
Baseline önceliği Part 5C ile aynı kalır. News ve disclosures aynı exact since/until
değerlerini alır. Instrument/time/limit dönüşte yeniden filtrelenir; instrument_id
olmayan news, instrument-specific review'a sokulmaz.

Context'e `recent_disclosures`, `evidence_window`, `evidence_collection` eklendi.
Eski top-level timestamp alanları compatibility için korunur. Disclosure summary/body
ve arbitrary metadata alınmaz; yalnız küçük allowlist metadata taşınır. Başlıklar
300, news summary 600 karakterle sınırlıdır. Source quality rehberi AI'ya eklenir.

| Durum | Collection sonucu |
|---|---|
| Provider başarılı, sonuç yok | available, item_count=0 |
| Provider başarılı, sonuç var | available, item_count=N |
| Erişim/parsing/timeout hatası | unavailable, reason=provider_error |
| Desteklenmeyen/erişilemeyen veri | unavailable, reason=data_unavailable |
| Çağrı sırasında configuration hatası | unavailable, reason=configuration_error |
| SEC provider verilmemiş | unavailable, reason=not_configured |
| Limit 0 | skipped, item_count=0; network çağrısı yok |

Raw exception, credentials, local paths veya stack traces context'e yazılmaz.
Bir veya tüm provider'ların hatası AI review'u otomatik durdurmaz veya recommendation
atamaz. State application, baseline update ve approval otomasyonu eklenmedi.

## Validation — 2026-09-15

- İlk tam PostgreSQL turu: **263 passed**.
- Self-review düzeltmesi: SEC filing alt klasör desteği ve explicit application/contact
  kontrolü; ilave submission/RSS timeout testleri.
- Son tam PostgreSQL turu: **266 passed**; public internet bağımlılığı yok.
- Testler: parsing/currency/timestamp, malformed/unavailable/timeout, RSS query/window/
  UTC/limit/empty, SEC mapping/cache/expiry/UA/form/URL/array/coverage, SSRF/redirect/
  response bounds/throttle; workflow success-zero vs failure, aynı window, isolation,
  metadata-only AI context, transaction sınırı, state ve history güvenliği.
- Live smoke, provider başına tek deneme: Yahoo başarılı (71.43 USD,
  source timestamp 2026-09-15T20:00:03Z); RSS başarılı (limit 3, 3 radar item).
- SEC live smoke: gerçek `II_SEC_USER_AGENT` eksik/geçersiz olduğu için **SKIPPED**;
  hiç SEC live request gönderilmedi. Deterministik SEC testleri geçti; canlı erişim
  henüz doğrulanmadı. Third review'dan önce gerçek UA tanımlanmalıdır.
- UBER Thesis Review / CodexCLIProvider çağrılmadı; ana application DB değiştirilmedi.

## Bilinçli ertelenenler

History quotes, full filing body extraction/summary, publisher article verification,
IR-specific provider, earnings transcripts, archive backfill, distributed throttling,
Türkiye/KAP/crypto/paid APIs, yeni protocol/workflow'lar, scheduler/UI, NetWorth,
trading ve automatic state application bu part'ın dışında kaldı.
