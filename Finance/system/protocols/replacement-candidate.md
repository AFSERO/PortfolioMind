# Replacement Candidate

Status: DESIGN IN PROGRESS

Bu belge yalnızca tasarım kaydıdır; gerçek alternatif araştırması, replacement listesi, implementation veya execution içermez.

## Purpose

Replacement Candidate, belirli sermayenin sonraki kullanımını portfolio role ve ilgili constraints çerçevesinde inceleyen research / finding protocolüdür.

Ana soru:

> Belirli bir pozisyondan çıkan veya çıkması düşünülen sermaye için portföy açısından en iyi sonraki kullanım nedir?

Cevap mutlaka başka bir hisse olmak zorunda değildir. Mevcut güçlü pozisyona ekleme adayı, yeni asset araştırması, farklı asset class, cash / defensive allocation, hiçbir şey yapmama veya yeni opportunity bekleme geçerli seçeneklerdir. “Bir şey sattık, yerine mutlaka başka bir şey alalım” mantığı kullanılmaz.

## Trigger and User Authority

Replacement Candidate, kullanıcı sermayenin yeniden kullanımını değerlendirmek istediğinde çalışır. Normal yol manual request'tir. Açık bir workflow trigger da ancak kullanıcının bu replacement araştırmasını açıkça onayladığı kapsamda kullanılabilir; SELL / REDUCE state'i tek başına izin veya trigger değildir.

Typical trigger context:

- Kullanıcının satış sonrası yeni sermaye kullanımı araması
- REDUCE sonrası serbest kalan sermayeyi değerlendirmek istemesi
- Full Portfolio Review'un pozisyon değişimi önerisinin kullanıcı tarafından araştırmaya alınması
- Kullanıcının belirli exposure'ı başka asset ile değiştirmek istemesi
- Portfolio role replacement ihtiyacı

[Full Portfolio Review](full-portfolio-review.md) önerisi kendi başına otomatik run başlatmaz. Kullanıcının redeployment araştırmasını istemesi, satışın veya yeni alımın onayı değildir. Automatic SELL → Replacement Candidate zinciri, automatic redeployment veya execution oluşturulmaz; final authority kullanıcıdadır.

## First Step: Understand the Removed Position

Yeni aday aramadan önce:

> Çıkan pozisyon portföyde hangi rolü oynuyordu?

Rol konsept olarak growth, defensive, income, crypto, inflation hedge, asymmetric upside, local exposure, global exposure, diversification veya tactical / event-driven olabilir. Bu örnekler kesin taxonomy değildir ve roller örtüşebilir.

Pozisyonun neden çıkarıldığı / azaltıldığı veya bunun neden düşünüldüğü anlaşılmalıdır. Önceki rolün korunması mı, değiştirilmesi mi, yoksa artık gerekli olmaması mı söz konusu olduğu değerlendirilir. Eski exposure otomatik olarak yeniden kurulmaz; örneğin concentration azaltma amacı aynı exposure'ı yeni isimle geri ekleyerek boşa çıkarılmamalıdır.

Gerçekleşmiş satış / azaltım ile düşünülen işlem ayrı tutulmalıdır. Released capital context; sermayenin kaynağını, gerçekleşmiş veya olası oluşunu, bilinen tutar / para birimi ve kullanılabilirlik bilgisini taşıyabilir. Düşünülen satış mevcut cash gibi sayılmaz; bilinmeyen tutar veya risk budget varsayımla doldurulmaz.

## Portfolio Context

Önce mümkün olduğunca compact context kullanılır:

- Current exposures
- Concentration
- Portfolio gaps
- Overlap
- Available cash
- Risk budget
- Existing watchlist
- Current recommendations
- Existing high-conviction positions
- User objectives

İlgili position / candidate state, önceki research references ve review tarihleri başlangıç noktasıdır. Context'in kapsamı, güncelliği ve önemli boşlukları belirtilir. Eski draft allocation target'ları rigid rule değildir; güncel karar, draft ve historical / superseded kayıtlar ayrılır. High conviction tek başına ekleme uygunluğu anlamına gelmez; valuation, concentration ve risk birlikte değerlendirilir.

## Search Order and Efficiency

Yeni ticker aramadan önce konsept olarak şu sıra kullanılır:

1. Existing portfolio positions
2. Existing watchlist
3. Existing candidates
4. Previous WATCH names
5. Opportunity Discovery universe
6. Yalnız gerekiyorsa new discovery

Cash / wait ve hiçbir şey yapmama seçenekleri karşılaştırma boyunca korunur; yeni asset bulunduktan sonra düşünülen son çare değildir. Existing universe first yaklaşımı gereksiz sürekli yeni asset üretimini önler.

Whole market deep scan yapılmaz. Compact kayıtlar ve cheap screening ile uygun olmayan seçenekler erken ayrılır; ayrıntılı eski research yalnız gerekli evidence veya değişen koşulu anlamak için açılır. Önceki adayların bekleme / ret gerekçeleri gözetilir; aynı çalışma gereksiz yere tekrarlanmaz. Candidate freshness / cooldown kuralları açık bırakılır.

## Candidate Evaluation and Restraint

Her replacement option konsept olarak şu açılardan karşılaştırılabilir:

- Portfolio role
- Thesis quality
- Valuation
- Expected risk/reward
- Diversification benefit
- Overlap
- Catalyst
- Liquidity
- Risk
- Confidence
- Required next step

Karşılaştırma, belirli sermaye ve ihtiyaç duyulan portfolio role üzerinden yapılmalıdır. Mevcut pozisyonlara ekleme, yeni asset veya asset class ve cash / defensive / wait seçeneklerinin avantaj ve sınırlamaları görünür tutulur. Discovery-level evidence doğrudan BUY recommendation değildir; rough valuation, tamamlanmış valuation gibi sunulmaz.

Yeni aday ancak materially better risk/reward, better portfolio fit, stronger thesis, better valuation veya needed diversification gibi meaningful advantage gösteriyorsa tercih edilmeye değer bir araştırma seçeneği olur. “Yeni olduğu için daha iyi” varsayımı yapılmaz. Turnover maliyeti ve uncertainty dikkate alınır; gereksiz turnover üretilmez. Minimum improvement threshold, comparison standard ve overlap penalty burada sayısallaştırılmaz.

Kanıt üstünlüğü göstermiyorsa aday zorlanmaz. Eksik veya stale evidence açıkça belirtilir; bu durum kesin üstünlük veya mevcut alternatiflerin kesin kötü olduğu iddiasına dönüşmez.

## Possible Outcomes

Aşağıdakiler konsept sonuç ifadeleridir; exact enum / schema değildir:

| Sonuç | Anlamı |
|---|---|
| EXISTING POSITION ADD CANDIDATE | Mevcut pozisyona ekleme daha ileri değerlendirmeye değer; ADD recommendation veya alım emri değildir. |
| NEW RESEARCH CANDIDATE | Yeni asset veya farklı asset class seçeneği screening / research için değerlendirilebilir. |
| WATCH | Seçenek izlenir; ilerlemek için gereken kanıt, fiyat veya catalyst açıklanır. |
| HOLD CASH / WAIT | Sermayeyi şimdilik kullanmama / yeni opportunity bekleme seçeneği daha uygun görünüyor. |
| NO COMPELLING REPLACEMENT | İncelenen seçeneklerde ve mevcut evidence ile yeterince güçlü replacement bulunmadı. |

Cash / defensive allocation konsept seçenek olarak ayrıca gerekçelendirilebilir; bunu ifade etmek için yeni enum eklemek gerekmez. Hiçbir replacement üretmemek geçerli sonuçtur. NO COMPELLING REPLACEMENT bütün markette alternatif olmadığı iddiası değildir; kapsam ve evidence sınırı belirtilir.

Bu verdict'ler execution command değildir. Mevcut **ADD / HOLD / REDUCE / SELL / REVIEW REQUIRED** investment recommendation setini değiştirmez veya onun yerine geçmez. Research progress, ownership, replacement verdict ve yatırım kararı ayrı tutulur. WATCH koşulunun sağlanması veya aday seçimi otomatik deployment başlatmaz.

## Relationship With Opportunity Discovery and Deep Research

| Protocol | Ana soru |
|---|---|
| Opportunity Discovery | Genel olarak yeni fırsatlar var mı? |
| Replacement Candidate | Belirli sermaye veya portfolio role için en iyi alternatif nedir? |

Replacement Candidate daha constraint-aware ve portfolio-specific çalışır. [Opportunity Discovery](opportunity-discovery.md)'nin mevcut evreninden yararlanabilir; yeni discovery yalnız gerekli olduğunda follow-up olarak ele alınır. Hangi durumda yeni Opportunity Discovery tetikleneceği açık tasarım sorusudur; her run'da otomatik başlatılmaz.

Strong replacement candidate şu akışa girebilir:

```text
Replacement Candidate
        ↓
Candidate identified
        ↓
Preliminary Screening
        ↓
Deep Research
```

Replacement Candidate full [Deep Research](deep-research.md) yapmaz; yalnız güçlü adaylarda deeper research önerir. Tamamlanmış screening / research güncelse kullanılabilir; sırf bu akış nedeniyle baştan tekrarlanmaz. Önerilen next step ile gerçekten tamamlanmış çalışma ayrılır. Research yönlendirmesi trade, sizing veya execution kararı değildir.

## Outputs

Dual-output principle geçerlidir.

### Machine Record

Kesin schema: DESIGN PENDING. Konsept olarak compact kayıt şu bilgileri taşıyabilir:

- Protocol adı ve review date / timestamp
- Trigger ve kullanıcı onaylı araştırma kapsamı
- Removed / reduced instrument; işlem gerçekleşmiş mi, düşünülüyor mu?
- Released capital context
- Previous portfolio role ve korunması / değiştirilmesi ihtiyacı
- Portfolio context reference ve portfolio gaps
- Candidate options
- Candidate role ve rationale
- Valuation context
- Portfolio fit, overlap ve diversification etkisi
- Risk / liquidity ve ilgili catalyst
- Confidence ve evidence sınırlamaları
- Verdict
- Next step / required follow-up
- Source / research / context references

Candidate options boş olabilir; cash / wait sonucu da kaydedilebilir. Alan tipleri, zorunlulukları, exact enum, database / JSON schema veya saklama yöntemi bu belgede belirlenmez.

### Human Brief

Kısa, sade Türkçe ve karar odaklı olmalıdır; mümkün olduğunca 30–60 saniyede okunabilmelidir. Çıkan / çıkması düşünülen pozisyon, önceki rol, en uygun görünen seçenek, gerekçe, varsa ikinci seçenek ve araştırma next step'i öne çıkarılır.

Aşağıdaki yalnızca kurgusal tasarım örneğidir; gerçek alternatif listesi veya trade recommendation değildir:

```text
REPLACEMENT REVIEW

Çıkan pozisyon: Örnek A
Portföydeki rolü: Global growth

En iyi seçenek: HOLD CASH / WAIT

Neden?
İncelenen watchlist'te valuation ve portfolio fit açısından yeterince güçlü alternatif yok.

İkinci seçenek: Örnek B — WATCH

Sonraki adım:
Daha iyi valuation veya yeni catalyst oluşursa yeniden screening yap.
Yeni yatırım kararı alınmadı.
```

## Integration-Ready and Architecture Relationship

Portfolio context kaynağı hard-code edilmez. `get_portfolio_context()` ve `get_position_context(instrument)` yalnız konsept abstraction adlarıdır; uygulanmış fonksiyon veya kesin API sözleşmesi değildir. Context bugün local state'ten, gelecekte NetWorth'ten sağlanabilir; bu aşamada entegrasyon, provider seçimi veya implementation yapılmaz.

Replacement Candidate, kullanıcı onaylı capital redeployment değerlendirmesi için çalışan research / finding protocolüdür. Portfolio-role-aware, constraint-aware ve existing universe first yaklaşımını kullanır. NO COMPELLING REPLACEMENT geçerli sonuçtur; automatic execution veya automatic redeployment yapmaz.

Role representation, released-capital representation, comparison standard, minimum improvement, overlap penalty, cash / wait tercihi, yeni discovery koşulları ve candidate freshness / cooldown [Open Design Questions](../architecture/open-design-questions.md) içinde açık bırakılmıştır.
