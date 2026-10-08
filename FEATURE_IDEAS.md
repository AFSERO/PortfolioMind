# NetWorth İçin Yeni Özellik Fikirleri

> İlke: Önce [`FIXES_AND_TECH_DEBT.md`](FIXES_AND_TECH_DEBT.md) içindeki P0 veri bütünlüğü işleri tamamlanmalıdır. Aşağıdaki fikirler mevcut kişisel portföy/nakit izleme amacıyla sınırlıdır; sosyal ağ, kripto alım-satım borsası veya proje amacıyla ilgisiz trend özellikleri önerilmemiştir.

## Kullanıcıya doğrudan değer sağlayan özellikler

### 1. Broker/banka CSV içe aktarma ve mutabakat

1. **Özellik adı:** Akıllı CSV içe aktarma.
2. **Çözdüğü problem:** Çok sayıda eski BUY/SELL ve nakit hareketini elle girmek zaman alır ve hataya açıktır.
3. **Kısa açıklama:** Kullanıcı banka/broker export'unu yükler; kolonları eşler; sistem taslak işlemleri önizler, duplicate'leri bulur ve onaydan sonra atomik import eder.
4. **Kullanıcı akışı:** Dosya seç → sağlayıcı/kolon eşle → validation raporu → duplicate ve kur uyarılarını çöz → önizle → import et → mutabakat özeti gör.
5. **Teknik uygulama:** Parser adapter arayüzü, canonical import row modeli, content hash/idempotency key, dry-run endpoint ve background job.
6. **Backend değişiklikleri:** Upload/dry-run/commit endpoint'leri; CSV parser'ları; symbol/currency normalizasyonu; atomik batch service.
7. **Frontend değişiklikleri:** Wizard, kolon eşleme tablosu, hata satırı indirme, progress ve sonuç ekranı.
8. **DB değişiklikleri:** `imports`, `import_rows`, `source_external_id`/hash; transaction'a optional import reference.
9. **Güvenlik/gizlilik:** Dosya tipi/boyut sınırı, formula injection'a karşı export sanitization, kısa retention, şifreli object storage veya işlem bitince silme; finansal dosya loglanmamalı.
10. **Zorluk:** Zor.
11. **Kullanıcı değeri:** Yüksek.
12. **MVP:** Evet, stabilizasyondan sonraki ilk yüksek değerli genişleme; başlangıçta 1-2 yaygın CSV formatı + manuel kolon eşleme.

### 2. Hedefler ve katkı planlayıcısı

1. **Özellik adı:** Finansal hedef ve “ne kadar yatırmalıyım?” planı.
2. **Çözdüğü problem:** Kullanıcı mevcut net değeri görür fakat ev peşinatı, emeklilik veya acil fon hedefine giden yolu ölçemez.
3. **Kısa açıklama:** Hedef tutar/tarih/para birimi tanımlanır; sistem mevcut tahsis edilen bakiyeyi ve gerekli aylık katkıyı senaryo olarak gösterir.
4. **Kullanıcı akışı:** Hedef ekle → varlık/nakitleri hedefe bağla → varsayımsal getiri/enflasyon seç → aylık katkı sonucunu gör → ilerleme bildirimleri al.
5. **Teknik uygulama:** Deterministik future-value hesaplama servisi; senaryoların gerçek portföyden ayrılması; zaman serisi projeksiyonu.
6. **Backend değişiklikleri:** Goal CRUD, projection endpoint, para birimi/freshness metadata.
7. **Frontend değişiklikleri:** Goal cards, progress bar, senaryo slider'ları ve chart.
8. **DB değişiklikleri:** `goals`, `goal_allocations`, optional `goal_scenarios`.
9. **Güvenlik/gizlilik:** Hassas finansal hedefler kullanıcıya özel; paylaşım yok; sonuçlar yatırım tavsiyesi olmadığına dair açıklama.
10. **Zorluk:** Orta.
11. **Kullanıcı değeri:** Yüksek.
12. **MVP:** Evet; tek hedef para birimi ve basit sabit getiri varsayımıyla.

### 3. Gerçek performans analitiği ve benchmark karşılaştırması

1. **Özellik adı:** TWR/XIRR, katkı etkisi ve benchmark.
2. **Çözdüğü problem:** Basit P/L, kullanıcının yatırma/çekme zamanlamasını gerçek yatırım performansından ayırmaz.
3. **Kısa açıklama:** Time-weighted return, money-weighted return (XIRR), realized/unrealized dağılımı ve seçilen endeks/altın/döviz benchmark'ı gösterilir.
4. **Kullanıcı akışı:** Analiz ekranı → dönem ve baz para seç → portföy/benchmark karşılaştır → getiriyi varlık tipi ve nakit akışı katkısına ayır.
5. **Teknik uygulama:** Günlük snapshot + cash-flow serisi, XIRR çözümü, benchmark price series cache'i.
6. **Backend değişiklikleri:** Performance service/endpoints; benchmark provider adapter; period validation.
7. **Frontend değişiklikleri:** Karşılaştırmalı line chart, waterfall/contribution tablosu, metodoloji tooltip'leri.
8. **DB değişiklikleri:** `benchmarks`, `benchmark_prices`; snapshot'a base-value/fx freshness metadata.
9. **Güvenlik/gizlilik:** Finansal sonuçların hassasiyeti; benchmark disclaimer; dış sağlayıcıya kullanıcı portföyü gönderilmemeli.
10. **Zorluk:** Zor.
11. **Kullanıcı değeri:** Yüksek.
12. **MVP:** Phase 1 çekirdeği için hayır; stabil snapshot ve ledger sonrası Phase 3/4.

## Kullanıcı deneyimi geliştirmeleri

### 4. Rehberli onboarding ve veri kalite merkezi

1. **Özellik adı:** İlk portföy sihirbazı + veri sağlık skoru.
2. **Çözdüğü problem:** Yeni kullanıcı asset, transaction, cash ve manual price ilişkisini anlamakta zorlanabilir; eksik kur/fiyat eskiyebilir.
3. **Kısa açıklama:** Onboarding adımları ilk nakdi, ilk varlığı ve fiyat kaynağını açıklar; sonrasında “eksik fiyat, bayat kur, mixed currency, negatif nakit” görev listesi sunar.
4. **Kullanıcı akışı:** Baz para seç → nakit ekle → ilk varlık/işlem → doğruluk özeti → dashboard; sonraki girişlerde yalnız açık veri sorunları görünür.
5. **Teknik uygulama:** Sunucu tarafından hesaplanan data-quality rules ve dismissible checklist.
6. **Backend değişiklikleri:** `/data-quality` endpoint'i; freshness/validation sonuçları; onboarding state.
7. **Frontend değişiklikleri:** Wizard, checklist, açıklayıcı empty states ve doğrudan düzeltme linkleri.
8. **DB değişiklikleri:** User onboarding state/dismissals; ana finans verisinde değişiklik gerekmez.
9. **Güvenlik/gizlilik:** Yalnız kullanıcı verisi; telemetry opt-in ve PII'siz olmalı.
10. **Zorluk:** Orta.
11. **Kullanıcı değeri:** Yüksek.
12. **MVP:** Evet; en azından ilk nakit + ilk varlık + stale price uyarıları.

### 5. Mobil hızlı işlem ve erişilebilir portföy görünümü

1. **Özellik adı:** Mobil quick-add ve erişilebilir responsive dashboard.
2. **Çözdüğü problem:** Masaüstü odaklı sabit paneller küçük ekranda işlem girişini ve okuma deneyimini zorlaştırır.
3. **Kısa açıklama:** Bottom navigation, quick-add sheet, tek kolon kartlar, mobile asset cards ve screen-reader uyumlu chart özetleri.
4. **Kullanıcı akışı:** Mobil ana ekran → `+` → BUY/SELL/nakit hareketi seç → kısa form → onay → güncel bakiye.
5. **Teknik uygulama:** Responsive composition, Drawer/Sheet, semantic table-card dönüşümü, chart için metin/tablo fallback'i.
6. **Backend değişiklikleri:** Yok; gerekirse küçük payload endpoint'leri mevcut contract'ı kullanır.
7. **Frontend değişiklikleri:** AppShell/nav, form drawer'ları, keyboard/focus, reduced-motion, aria summaries.
8. **DB değişiklikleri:** Yok.
9. **Güvenlik/gizlilik:** Mobilde hassas tutarları gizleme (“privacy mode”) ve clipboard/screenshot uyarısı opsiyonel olabilir.
10. **Zorluk:** Orta.
11. **Kullanıcı değeri:** Yüksek.
12. **MVP:** Evet; responsive düzeltme ve quick-add, yeni domain özelliğinden önce gelmeli.

## Otomasyon fikirleri

### 6. Otomatik günlük snapshot, fiyat yenileme ve tekrar eden katkılar

1. **Özellik adı:** Portföy otomasyon motoru.
2. **Çözdüğü problem:** Kullanıcı snapshot butonuna basmayı unutur; düzenli yatırım ve mevduatları tekrar tekrar girmek zorunda kalır.
3. **Kısa açıklama:** Timezone'a göre günlük fiyat/snapshot job'u ve kullanıcı onaylı recurring draft transaction/deposit üretimi.
4. **Kullanıcı akışı:** Otomasyon ekle → sıklık/tutar/para birimi seç → bir sonraki çalışma önizle → bildirimle onayla veya güvenli kurala göre otomatikleştir.
5. **Teknik uygulama:** Celery/RQ/Arq benzeri queue, idempotency key, distributed lock, retry/dead-letter ve job status.
6. **Backend değişiklikleri:** Scheduler/worker, automation CRUD, idempotent snapshot ve transaction command'ları.
7. **Frontend değişiklikleri:** Automation settings, upcoming runs, failure/retry ve pause controls.
8. **DB değişiklikleri:** `automations`, `automation_runs`; source/idempotency alanları.
9. **Güvenlik/gizlilik:** Otomatik finansal yazım açık kullanıcı onayı ve audit gerektirir; güvenlik açısından default “draft” olmalı.
10. **Zorluk:** Zor.
11. **Kullanıcı değeri:** Yüksek.
12. **MVP:** Günlük snapshot evet; otomatik transaction hayır, önce draft/hatırlatma.

### 7. Fiyat, tahsis ve veri tazeliği uyarıları

1. **Özellik adı:** Akıllı portföy alarmı.
2. **Çözdüğü problem:** Kullanıcı fiyat eşiği, aşırı yoğunlaşma veya bayat fiyatı düzenli kontrol etmek zorunda kalır.
3. **Kısa açıklama:** Fiyat/P&L/tahsis yüzdesi/stale-provider/negatif nakit kuralları; in-app ve tercihe bağlı e-posta bildirimi.
4. **Kullanıcı akışı:** Kural oluştur → asset/metric/eşik seç → sessiz saatleri belirle → tetiklenme ve geçmişi gör.
5. **Teknik uygulama:** Rule evaluator background job, debounce/cooldown, provider freshness ve notification adapter.
6. **Backend değişiklikleri:** Alert CRUD/evaluation, notification service, delivery status.
7. **Frontend değişiklikleri:** Kural builder, alert center, snooze/resolve.
8. **DB değişiklikleri:** `alert_rules`, `alert_events`, `notification_preferences`.
9. **Güvenlik/gizlilik:** E-posta içeriğinde tam portföy tutarı varsayılan olarak gösterilmemeli; unsubscribe/verification.
10. **Zorluk:** Orta/Zor.
11. **Kullanıcı değeri:** Yüksek.
12. **MVP:** Basit stale-price ve fiyat eşiği in-app uyarısı evet.

## Yapay zekâ kullanılabilecek alanlar

### 8. Kaynak gösteren AI portföy özeti ve anomali açıklaması

1. **Özellik adı:** Açıklanabilir finansal asistan.
2. **Çözdüğü problem:** Kullanıcı sayıların neden değiştiğini veya riskin nerede yoğunlaştığını anlamakta zorlanır.
3. **Kısa açıklama:** Deterministik hesaplanan metrikleri doğal dilde özetler; “bu ay ne değişti?” sorusunu ilgili transaction/snapshot kimliklerine dayandırır. Model hesap yapmaz, hesaplanmış veriyi açıklar.
4. **Kullanıcı akışı:** Dashboard “Özetle” → dönem seç → kaynak kartlarıyla anlatım → takip sorusu → ilgili asset/transaction'a git.
5. **Teknik uygulama:** RAG/context builder yalnız kullanıcının normalize edilmiş metriklerini verir; tool/function calling; cevap schema ve citation id'leri; hallucination guard.
6. **Backend değişiklikleri:** Insight context endpoint, AI orchestration, prompt/version/evaluation ve redaction.
7. **Frontend değişiklikleri:** Chat/insight paneli, source chips, feedback ve “yatırım tavsiyesi değildir” metni.
8. **DB değişiklikleri:** `ai_conversations`, `ai_messages`, optional feedback; ham finansal context yerine referanslar.
9. **Güvenlik/gizlilik:** Açık opt-in; veri minimizasyonu; provider retention ayarı; prompt injection'a karşı tool allowlist; kullanıcılar arası kesin izolasyon.
10. **Zorluk:** Zor.
11. **Kullanıcı değeri:** Orta/Yüksek.
12. **MVP:** Phase 3; önce read-only ve kaynaklı özet, işlem yapma yetkisi olmadan.

### 9. AI destekli import sınıflandırma ve açıklama normalizasyonu

1. **Özellik adı:** İşlem satırı eşleme yardımcısı.
2. **Çözdüğü problem:** Farklı broker açıklamalarını symbol, BUY/SELL ve fee alanlarına elle eşlemek zordur.
3. **Kısa açıklama:** Belirsiz CSV satırları için model öneri üretir; kullanıcı her öneriyi onaylar. Kesin sayısal değerler parser'dan gelir, model değiştiremez.
4. **Kullanıcı akışı:** Import → belirsiz satırlar → AI önerisi + confidence → kabul/düzelt → mapping template'i kaydet.
5. **Teknik uygulama:** Structured output, allowlisted enum/symbol search tool, confidence threshold, insan onayı.
6. **Backend değişiklikleri:** Import pipeline'a optional classifier; prompt/evaluation fixtures.
7. **Frontend değişiklikleri:** Side-by-side source/öneri, bulk accept yalnız yüksek confidence için.
8. **DB değişiklikleri:** Mapping templates, suggestion audit ve user corrections.
9. **Güvenlik/gizlilik:** Satır açıklamaları PII içerebilir; redaction ve provider'a minimum alan gönderimi gerekir.
10. **Zorluk:** Orta/Zor.
11. **Kullanıcı değeri:** Orta.
12. **MVP:** Hayır; deterministic import tamamlandıktan sonra.

## Yönetim paneli ve raporlama özellikleri

### 10. Provider sağlık ve veri kalite yönetim paneli

1. **Özellik adı:** Operasyon konsolu.
2. **Çözdüğü problem:** Hangi fiyat sağlayıcısının başarısız, kotasının dolu veya verisinin bayat olduğu görünmüyor.
3. **Kısa açıklama:** Provider başarı oranı/latency/cache hit, stale asset sayısı, failed job ve kullanıcı etkisini PII'siz gösterir.
4. **Kullanıcı akışı:** Admin giriş → health overview → provider detayı → son hatalar → safe retry/cache invalidate.
5. **Teknik uygulama:** Metrics/event aggregation, RBAC admin scope, read-only varsayılan ve auditable actions.
6. **Backend değişiklikleri:** Admin auth/role, metrics endpoints, provider event instrumentation.
7. **Frontend değişiklikleri:** Ayrı admin route/layout, charts, filters, retry confirmation.
8. **DB değişiklikleri:** `provider_events` veya metrics backend; `admin_audit_log`; user role.
9. **Güvenlik/gizlilik:** Admin least privilege, MFA, PII minimizasyonu, tüm write action audit'i.
10. **Zorluk:** Zor.
11. **Kullanıcı değeri:** Son kullanıcıya dolaylı ama yüksek operasyonel değer.
12. **MVP:** Tek kullanıcılı/private MVP'de hayır; production öncesi basic health dashboard evet.

## Güvenlik özellikleri

### 11. MFA, cihaz oturumları ve güvenlik günlüğü

1. **Özellik adı:** Hesap güvenlik merkezi.
2. **Çözdüğü problem:** Parola/refresh token ele geçirilirse kullanıcı aktif oturumları göremez veya tek tek iptal edemez.
3. **Kısa açıklama:** TOTP MFA, recovery code, aktif cihaz/session listesi, son login ve kritik değişiklik bildirimleri.
4. **Kullanıcı akışı:** Settings → MFA kur → QR doğrula → recovery code kaydet → cihazları görüntüle/iptal et.
5. **Teknik uygulama:** Refresh session altyapısı, encrypted TOTP secret, one-time recovery code hash'i, step-up auth.
6. **Backend değişiklikleri:** MFA enrollment/verify/recovery/session revoke endpoint'leri; riskli action guard.
7. **Frontend değişiklikleri:** Security settings, QR/OTP formu, session list ve confirmation dialogs.
8. **DB değişiklikleri:** `auth_sessions`, `mfa_methods`, `recovery_codes`, `security_events`.
9. **Güvenlik/gizlilik:** Secret encryption/KMS, rate limiting, backup-code tek kullanım, account recovery süreci.
10. **Zorluk:** Zor.
11. **Kullanıcı değeri:** Yüksek.
12. **MVP:** Public production için session revocation evet; MFA kısa sonraki aşama.

## Performans ve ölçeklenebilirlik geliştirmeleri

### 12. Background fiyat pipeline'ı ve paylaşılan cache

1. **Özellik adı:** Asenkron piyasa verisi katmanı.
2. **Çözdüğü problem:** Dashboard request'i provider latency'sine bağlanıyor; multi-worker cache paylaşılmıyor.
3. **Kısa açıklama:** Fiyatları job queue günceller, Redis coalescing/cache kullanılır, UI son bilinen fiyat ve freshness'i anında okur.
4. **Kullanıcı akışı:** Dashboard hemen açılır → fiyatların “as of” zamanı görünür → refresh job durumu canlı/polling güncellenir.
5. **Teknik uygulama:** Queue worker, Redis lock/cache, provider adapter retry/circuit breaker, event/polling.
6. **Backend değişiklikleri:** Refresh command/job status endpoint, shared HTTP client, cache abstraction.
7. **Frontend değişiklikleri:** Non-blocking refresh status, stale badge, partial failure detayları.
8. **DB değişiklikleri:** `price_refresh_jobs` veya job backend; price source/fetched_at alanları.
9. **Güvenlik/gizlilik:** Job ownership; admin ve user job scope ayrımı; provider key'leri worker secret'ında.
10. **Zorluk:** Zor.
11. **Kullanıcı değeri:** Orta/Yüksek.
12. **MVP:** Tek instance MVP'de hayır; kullanıcı/portföy sayısı büyümeden önce.

## Gelir modeli ve ürünleştirme fikirleri

### 13. Katmanlı abonelik: ücretsiz takip + premium analitik/otomasyon

1. **Özellik adı:** Free / Plus / Pro paketleri.
2. **Çözdüğü problem:** Ürünün sürdürülebilir maliyet modeli yok; provider/AI/notification özelliklerinin değişken maliyeti var.
3. **Kısa açıklama:** Ücretsiz temel manuel takip; Plus otomatik import/uyarı/benchmark; Pro AI özetleri ve gelişmiş raporlar. Temel veri export'u paywall arkasına konmamalı.
4. **Kullanıcı akışı:** Limit/fayda ekranı → plan seç → checkout → entitlement anında aktif → fatura/iptal yönetimi.
5. **Teknik uygulama:** Billing provider, webhook idempotency, entitlement service ve usage metering.
6. **Backend değişiklikleri:** Subscription/webhook/entitlement endpoints, feature guards, usage counters.
7. **Frontend değişiklikleri:** Pricing, checkout redirect, billing settings ve açıklayıcı upgrade prompts.
8. **DB değişiklikleri:** `subscriptions`, `entitlements`, `usage_events`, webhook dedupe.
9. **Güvenlik/gizlilik:** Kart verisi uygulamaya girmemeli; signed webhook; plan iptalinde veri sahipliği/export korunmalı.
10. **Zorluk:** Zor.
11. **Kullanıcı değeri:** Dolaylı; ürün sürdürülebilirliği yüksek.
12. **MVP:** Hayır; retention ve çekirdek doğruluk kanıtlandıktan sonra.

## Developer experience geliştirmeleri

### 14. Contract-first SDK, seed senaryoları ve observability sandbox'ı

1. **Özellik adı:** Geliştirici güvenlik ağı.
2. **Çözdüğü problem:** Backend/frontend tip drift'i, boş local dashboard ve provider bağımlılığı geliştirmeyi yavaşlatır.
3. **Kısa açıklama:** OpenAPI'den TS client, deterministik demo seed'leri, fake provider modu ve tek komutla PostgreSQL test ortamı.
4. **Kullanıcı akışı:** Geliştirici `make/dev` benzeri komut çalıştırır → migration + seed → frontend demo data → contract/test/trace hazır.
5. **Teknik uygulama:** OpenAPI codegen, fixtures/factories, provider protocol ve fake adapter, Compose profiles.
6. **Backend değişiklikleri:** Kesin response models, seed CLI, provider dependency injection.
7. **Frontend değişiklikleri:** Generated client tüketimi; manual duplicate types kaldırma.
8. **DB değişiklikleri:** Production schema değişikliği yok; seed yalnız development DB.
9. **Güvenlik/gizlilik:** Fake data açıkça işaretli; gerçek secret/production DB ile seed komutu fail-fast reddedilmeli.
10. **Zorluk:** Orta.
11. **Kullanıcı değeri:** Son kullanıcıya dolaylı, geliştirme hızına yüksek.
12. **MVP:** Evet; P2 teknik borç aşamasında küçük kapsamla.

## En değerli beş fikir

1. Broker/banka CSV içe aktarma ve mutabakat.
2. Finansal hedefler ve katkı planlayıcısı.
3. Otomatik günlük snapshot + güvenli otomasyon motoru.
4. Fiyat/tahsis/veri tazeliği uyarıları.
5. Kaynak gösteren, read-only AI portföy özeti.

Önerilen ürün sırası: onboarding/veri kalitesi → import → otomatik snapshot/uyarı → hedefler/performance → AI. Bu sıra, AI ve gelişmiş analitiği güvenilir bir ledger ve kaliteli veri üzerine kurar.
