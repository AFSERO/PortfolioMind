# Earnings Review

Status: DESIGN IN PROGRESS

Bu belge yalnızca tasarım kaydıdır; gerçek şirket analizi, implementation veya aktif schedule içermez.

## Purpose

Earnings Review, yeni finansal sonuçların mevcut investment thesis, valuation ve recommendation üzerindeki etkisini inceleyen asset-level specialist protocol'dür.

Ana soru:

> Yeni açıklanan finansal sonuçlar, mevcut investment thesis, valuation ve recommendation üzerinde material bir değişiklik yaratıyor mu?

Şirketi sıfırdan deep research etmez. Mevcut compact state ve önceki beklentilerden başlayarak son review'dan beri yatırım kararı açısından ne değiştiğine odaklanır. Amaç earnings report'u özetlemek değildir.

## Typical Triggers

- Yeni quarterly / annual results
- Earnings release
- Earnings call
- Guidance update
- Material KPI update
- Portfolio Monitoring tarafından yeni earnings tespit edilmesi
- Single Asset Monitoring tarafından yönlendirme
- Manual user request

## Inputs and Efficiency

Önce şu compact context kullanılmalıdır:

- Compact asset state: instrument, mevcut thesis, valuation, recommendation ve ilgili portfolio / technical context
- Previous earnings / review state ve ilgili dönem
- Relevant thesis expectations: beklenen gelişmeler, temel varsayımlar ve invalidation koşulları
- Current earnings data ve source references

Karşılaştırma için gerektiğinde önceki dönem sonuçları, önceki management guidance ve mevcutsa karşılaştırılabilir consensus estimates kullanılabilir. Thesis beklentisi, management guidance ve consensus birbirinin yerine geçirilmemeli; hangi beklentiyle karşılaştırıldığı açık olmalıdır. Eksik beklenti verisi tahminle doldurulmamalıdır.

Her run'da bütün eski research klasörü, filings geçmişi veya company history baştan okunmamalıdır. Detaylı kaynaklar yalnız material ambiguity, conflicting evidence, thesis-critical evidence veya gerekli historical comparison için açılmalıdır. Compact state eksikse gerekli bağlam boşluğu belirtilir; otomatik full Deep Research başlatılmaz.

## Core Review

### Results vs Expectations

Şirketin business modeline ve mevcut thesis'e göre decision-relevant metric'ler seçilmelidir. Her şirket için aynı metric seti zorunlu değildir. Gerektiğinde şu alanlar karşılaştırılabilir:

- Revenue ve growth
- Margins ve operating income
- Cash flow / FCF
- EPS, ilgili olduğu ölçüde
- Important business KPIs
- Management guidance

Karşılaştırmada dönem ve metric tanımı uyumu gözetilir; karşılaştırılamayan veya eksik veriler açıkça belirtilir. Headline beat / miss tek başına materiality veya recommendation belirlemez.

### Previous Thesis Expectations

Yeni sonuçlar mevcut thesis beklentileriyle karşılaştırılmalıdır:

- Beklenen gelişmeler gerçekleşiyor mu?
- Thesis STRONGER, UNCHANGED veya WEAKER mı?
- Invalidation riski var mı; mevcut invalidation koşullarını destekleyen kanıt oluştu mu?

Olası invalidation ile kanıtla desteklenen INVALIDATED durumu ayrılmalıdır. Material thesis change gerektiğinde Thesis Review'a yönlendirilir.

### Guidance

Guidance değişimi raised, maintained, reduced veya withdrawn olarak, mevcut açıklamanın desteklediği ölçüde değerlendirilir. Değişimin kapsamı, dönemi ve thesis / valuation etkisi incelenir. Guidance verilmemesi otomatik olarak maintained veya withdrawn sayılmaz; belirsizlik belirtilir. Normalization yöntemi henüz tasarlanmamıştır.

### Management Commentary

Headline numbers yanında demand, competition, pricing, costs, capital allocation, regulatory issues ve önemli risklere ilişkin thesis-relevant açıklamalar incelenebilir. Management açıklaması ile gerçekleşmiş sonuç ayrılır; yalnız karar açısından anlamlı değişiklikler öne çıkarılır.

## Change-Focused Flow and Routing

1. Compact asset state, önceki review ve ilgili beklentileri oku.
2. Yeni sonuçları uygun beklenti ve önceki durumla karşılaştır.
3. Material değişiklikleri, thesis / valuation etkisini ve evidence boşluklarını belirle.
4. Gerekiyorsa ilgili specialist review'a yönlendir; ihtiyaç olmayan alt protocol'ları çalıştırma.
5. Earnings verdict ile recommendation'ı ayrı değerlendir; Machine Record ve kısa Human Brief üret.

| Bulgular | Olası yönlendirme |
|---|---|
| Material thesis change veya invalidation riski | Thesis Review |
| Valuation'ı materially değiştiren sonuçlar / varsayımlar | Valuation Update |
| Material price / chart change veya mevcut technical plan'dan sapma | Technical Review |
| Evidence ciddi biçimde yetersiz veya şirket structurally değişmiş | Deeper research consideration |

Her earnings sonrası bütün sub-protocol'lar otomatik çalıştırılmamalıdır. Eksik kanıt önce hedefli follow-up ile ele alınabilir; Deep Research varsayılan adım değildir. Gerekli follow-up ile gerçekten tetiklenen / tamamlanan review'lar karıştırılmamalı; bekleyen incelemeler sonuçlanmış gibi sunulmamalıdır. Kesin materiality thresholds ve routing kuralları açık tasarım konularıdır.

Material değişiklik yoksa bu kısa şekilde kaydedilir; ek inceleme zorunlu değildir. Material olmayan ayrıntılar Human Brief'e doldurulmaz.

## Earnings Verdict and Recommendation

Earnings'e özel kısa verdict konsepti: **POSITIVE, NEUTRAL, NEGATIVE, MIXED**. Bu alan sonuçların ilgili beklentiler karşısındaki genel değerlendirmesidir; recommendation değildir. Kanıt verdict vermeye yetmiyorsa belirsizlik ve gerekli follow-up belirtilir; eksik kanıt NEUTRAL anlamına gelmez. Eksik değerlerin kesin temsili schema tasarımına bırakılır.

Mevcut recommendation seti korunur: **ADD, HOLD, REDUCE, SELL, REVIEW REQUIRED**. Earnings surprise tek başına doğrudan BUY / SELL veya başka bir investment action üretmemelidir.

Recommendation; thesis, valuation, portfolio context ve ilgili olduğunda technical context birlikte değerlendirilerek oluşturulmalıdır. Mevcut valuation veya context güncel değerlendirme için yetersizse bu sınırlama belirtilir; önemli inceleme ihtiyacı veya yetersiz evidence için REVIEW REQUIRED kullanılabilir. Earnings verdict, thesis status ve valuation status ayrı boyutlardır; tanımlar [System Overview](../architecture/system-overview.md#recommendation-states) ile uyumlu kalmalıdır.

Recommendation execution command değildir; final investment / action authority kullanıcıda kalır.

## Outputs

Dual-output principle geçerlidir.

### Machine Record

Kesin schema: DESIGN PENDING. Konsept olarak compact kayıt şu bilgileri taşıyabilir:

- Protocol adı ve instrument
- Earnings period ve review date / timestamp
- Earnings verdict
- Major changes ve karşılaştırılan beklentiler
- Guidance change
- Key KPI changes
- Thesis status
- Valuation status
- Recommendation ve kısa gerekçesi
- Confidence ve material evidence sınırlamaları
- Required follow-up / open questions
- Triggered sub-protocols ve bekleyen sonuçlar
- Source references ve gerektiğinde ilgili eski research referansları

Alan tipleri, zorunlulukları, JSON / database schema ve saklama yöntemi bu belgede belirlenmez.

### Human Brief

30–60 saniyede okunabilir, sade Türkçe ve değişiklik odaklı olmalıdır. Verdict, thesis, recommendation, en önemli değişiklik ve gerekli aksiyon / follow-up yeterlidir. Kararı etkileyen evidence boşluğu varsa kısaca belirtilir.

Aşağıdaki yalnızca kurgusal tasarım örneğidir; gerçek ticker analizi veya investment recommendation değildir:

```text
ÖRNEK ŞİRKET — EARNINGS REVIEW

Sonuç: POSITIVE
Thesis: STRONGER
Valuation: EXPENSIVE
Recommendation: HOLD

Ne değişti?
Büyüme thesis beklentisini karşıladı; FCF beklentinin üzerinde geldi.
Mevcut valuation değerlendirmesi hâlâ pahalı.

Aksiyon:
Pozisyonu koru; artırımı değerlendirmeden önce Valuation Update gerekli.
```

## Architecture Relationship

Earnings Review, [Portfolio Monitoring](portfolio-monitoring.md) tarafından tetiklenebilir veya [Single Asset Monitoring](single-asset-monitoring.md) tarafından çağrılabilir. Single Asset Monitoring'in çağırdığı durumda bulgular onun asset-level synthesis'ine girdi sağlar. Earnings Review gerektiğinde Thesis Review, Valuation Update veya Technical Review'a yönlendirir; kendisi full Deep Research değildir.

Veri kaynakları, consensus, KPI mapping, guidance normalization, transcript handling, freshness, confidence ve materiality konuları [Open Design Questions](../architecture/open-design-questions.md) içinde açık bırakılmıştır.
