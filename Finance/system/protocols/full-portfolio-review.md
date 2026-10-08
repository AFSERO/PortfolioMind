# Full Portfolio Review

Status: DESIGN IN PROGRESS

Bu belge yalnızca tasarım kaydıdır; gerçek portfolio analizi, implementation, aktif schedule veya execution içermez.

## Purpose

Full Portfolio Review, portföyü bir bütün olarak değerlendiren portfolio-level strategic review protocolüdür.

Ana soru:

> Mevcut portföy bir bütün olarak hâlâ mantıklı mı, riskler dengeli mi ve sermaye doğru yerlerde mi?

Asset-level review değildir. Allocation, concentration, risk yapısı ve capital efficiency birlikte ele alınır; her şirketin research'i yeniden yapılmaz.

## Portfolio Monitoring vs Full Portfolio Review

| Boyut | Portfolio Monitoring | Full Portfolio Review |
|---|---|---|
| Ana soru | Son kontrolden beri material ne değişti? | Portföyün tamamı bugün yeniden değerlendirildiğinde sermaye dağılımı ve risk yapısı hâlâ mantıklı mı? |
| Kapsam | Değişiklik tespiti ve ilgili review'a yönlendirme | Portföyün bütününü stratejik olarak değerlendirme |
| Yaklaşım | Cheap Pre-Check ağırlıklı | Allocation, concentration, risk ve capital efficiency sentezi |
| Sıklık | Daha sık; mevcut tercih Weekly | Daha seyrek ve kapsamlı; kesin cadence açık |

İki protocol aynı işi yapmamalıdır. Full Portfolio Review, tek tek asset'lerde yeni gelişme olmasa da birikmiş exposure ve portföyün ortak risklerini değerlendirebilir. Bu, her asset için yeniden full research yapılmasını gerektirmez.

## Typical Triggers

- Scheduled monthly / periodic review
- Major market regime change
- Large portfolio drawdown
- Multiple assets simultaneously deteriorating
- Significant new capital inflow / outflow
- Major strategic allocation change
- Manual user request

Monthly / periodic yalnız olası trigger konseptidir; kesin schedule veya cadence belirlenmemiştir. Aktif schedule yoktur. Bir trigger, otomatik rebalance veya trade anlamına gelmez.

## Compact Inputs and Efficiency

Önce portfolio context ve compact asset state kullanılmalıdır. Portfolio context; portföy kapsamı, değer / ağırlık referansı, context tarihi, cash / liquidity durumu, ilgili sermaye giriş-çıkışları ve mevcut stratejik yönelimi taşıyabilir. Allocation referanslarının güncel karar mı, draft mı, yoksa historical / superseded kayıt mı olduğu korunmalıdır.

Her asset için konsept olarak:

- Instrument ve position size / portfolio weight
- Thesis status
- Valuation status
- Technical status
- Recommendation
- Latest review date
- Important open risks
- Upcoming events
- İlgili source/research references

Bütün research report'ları baştan okunmamalıdır. Ayrıntılı dosyalar yalnız problemli veya belirsiz pozisyonlarda, karar için gerekli evidence / context'i tamamlamak üzere açılmalıdır. Gereksiz Deep Research başlatılmaz.

Eksik veya stale asset state, sağlıklı pozisyon kanıtı sayılmamalıdır. Kullanılan context'in kapsamı ve güncelliği belirtilir; önemli boşluklar confidence ve follow-up'a yansıtılır. Yetersiz veriyle kesin correlation, overlap veya portfolio health sonucu üretilmez. Kesin freshness standardı açık bırakılır.

## Main Review Areas

### Allocation

- Global / local exposure
- Equity / crypto / gold / defensive exposure
- Active vs core exposure
- Cash level

Mevcut allocation target'ları rigid rule değildir; draft allocation'lar bağlayıcı değildir. Overweight / underweight gözlemleri, hangi güncel yönelim veya karşılaştırma referansına dayandığı açıklanarak sunulur. Bir draft'tan sapma tek başına düzeltme gerektiren sorun sayılmaz; yeni target allocation burada dayatılmaz.

### Concentration

- Single asset concentration
- Sector concentration
- Geography concentration
- Factor / theme concentration
- Correlated positions
- Hidden overlap

Pozisyon sayısı tek başına çeşitlendirme göstergesi değildir. Ortak exposure'lar ve varsa dolaylı örtüşmeler mevcut evidence ölçüsünde değerlendirilir. Correlation / overlap analiz yöntemi ve concentration thresholds henüz belirlenmez.

### Portfolio Risk

- Drawdown risk
- Liquidity
- Volatility
- Thesis concentration
- Event concentration
- Currency exposure
- Portfolio fragility

Risk yalnız price volatility olarak tanımlanmamalıdır. Birden fazla pozisyonun aynı varsayıma, olaya veya likidite koşuluna bağımlılığı birlikte ele alınabilir. Risk aggregation yöntemi veya sayısal risk eşikleri bu aşamada tasarlanmaz.

### Capital Efficiency

Ana soru:

> Portföyde tuttuğumuz her pozisyon hâlâ sermaye kullanmaya değer mi?

Weak thesis + low upside, expensive asset, stale position, redundant exposure veya mevcut kanıtla desteklenen superior alternative gibi durumlar incelenebilir. Stale bilgi önce review ihtiyacı doğurur; tek başına SELL gerekçesi değildir. Daha iyi bir alternatifin varlığı kanıt olmadan varsayılmaz.

Bu değerlendirme otomatik replacement discovery başlatmaz. Mevcut sermayenin korunması, cash tutulması veya yeni capital deployment için inceleme ihtiyacı portfolio-level gözlem olarak kaydedilebilir.

## Review Flow and Materiality

1. Portfolio context, compact asset state ve bunların güncelliğini oku.
2. Allocation, concentration, risk ve capital efficiency'yi portföyün tamamı için birlikte değerlendir.
3. Material portfolio-level sorunları, redundant exposures ve meaningful capital allocation opportunities'yi ayır.
4. Olası değişikliğin faydasını turnover maliyeti, uncertainty ve mevcut thesis ile birlikte değerlendir.
5. Asset-level recommendations ile portfolio-level observations'ı ayrı kaydet; gerekli conditional follow-up'ları önceliklendir.
6. Compact Machine Record ve kısa Human Brief üret.

Full Portfolio Review, “her şeyi yeniden optimize et” protocolü değildir. Küçük değişiklikler için sürekli rebalancing önermemelidir. Material sorun veya anlamlı fırsat yoksa aksiyon gerekmeyebilir. Rebalance threshold açık tasarım sorusudur; automatic rebalancing veya execution yapılmaz.

## Portfolio-Level Findings and Recommendation Relationship

Konsept olarak şu sonuçlar üretilebilir:

- Portfolio health değerlendirmesi
- Concentration warnings
- Overweight / underweight observations
- Cash / liquidity observations
- Assets requiring review
- ADD için potansiyel olarak uygun asset'ler
- REDUCE / SELL için potansiyel olarak uygun asset'ler
- Redundant exposures
- Major portfolio-level risks
- Capital deployment opportunities
- Required follow-up protocols

Asset-level recommendation seti **ADD, HOLD, REDUCE, SELL, REVIEW REQUIRED** olarak korunur. Thesis, valuation ve technical status ayrı boyutlardır; portfolio context ile birlikte değerlendirilir. Bir asset'in thesis'i değişmeden concentration nedeniyle REDUCE değerlendirmesi yapılabilir; gerekçe portfolio-level olarak açıkça belirtilmelidir. Önceki asset recommendation ile yeni değerlendirme farklıysa neden açıklanır; eski sonuç sessizce yeniden yorumlanmaz.

Portfolio-level observations bu asset states'in yerine geçmez. Exact portfolio health / status seti henüz kesinleştirilmez. Recommendation veya portfolio action önerisi execution command değildir; final investment / capital allocation authority kullanıcıdadır. Mevcut tanımlar [System Overview](../architecture/system-overview.md#recommendation-states) ile uyumlu kalır.

## Conditional Follow-Up

| İhtiyaç | Önerilebilecek follow-up |
|---|---|
| Pozisyona özgü material sorun / belirsizlik | Single Asset Monitoring |
| Kritik thesis varsayımına ilişkin soru | Thesis Review |
| Stale valuation veya material değerleme etkisi | Valuation Update |
| İlgili technical deviation veya entry değerlendirmesi | Technical Review |
| Sermayenin başka varlığa aktarılmasının değerlendirilmesi | Replacement Candidate; kullanıcının redeployment kararı ve manual request'i sonrasında |
| Anlamlı yeni exposure / capital deployment araştırma ihtiyacı | Opportunity Discovery önerisi |

Bu protocol'ların hepsi otomatik çalıştırılmaz. Follow-up önerisi, gerçekten tetiklenen protocol ve tamamlanan sonuç ayrı tutulur. Opportunity Discovery'nin hangi koşullarda tetikleneceği açık tasarım sorusudur; bu review otomatik discovery başlatmaz.

Replacement Candidate için manual karar ayrımı korunur. Kurgusal akış:

```text
Örnek Pozisyon: SELL recommendation
        ↓
Kullanıcı sermayenin yeniden dağıtılıp dağıtılmayacağına karar verir
        ↓
Replacement Candidate ayrıca manual olarak istenir
```

SELL recommendation, gerçekleşmiş satış veya otomatik serbest sermaye anlamına gelmez; replacement araştırmasını kendiliğinden başlatmaz.

## Outputs

Dual-output principle geçerlidir.

### Machine Record

Kesin schema: DESIGN PENDING. Konsept olarak compact kayıt şu bilgileri taşıyabilir:

- Protocol adı ve review date / timestamp
- Portfolio identity, value / context reference ve context tarihi
- Portfolio health değerlendirmesi
- Allocation observations
- Concentration risks ve redundant exposures
- Liquidity / cash observations
- Asset recommendations ve gerekçeleri
- Assets requiring review
- Major portfolio risks
- Capital efficiency / deployment observations
- Follow-up actions ve ilgili protocol'lar
- Confidence, evidence sınırlamaları ve open questions
- Source / research / context references

Alan tipleri, zorunlulukları, exact portfolio status seti, database / JSON schema veya saklama yöntemi bu belgede belirlenmez.

### Human Brief

Kısa, sade Türkçe ve decision-focused olmalıdır; mümkün olduğunca 30–60 saniyede okunabilmelidir. Genel durum, en önemli portfolio risk, gerekli asset / portfolio aksiyonları ve acil review ihtiyacı öne çıkarılır. Material evidence boşluğu varsa belirtilir.

Aşağıdaki yalnızca kurgusal tasarım örneğidir; gerçek portföy analizi veya investment recommendation değildir:

```text
FULL PORTFOLIO REVIEW

Genel durum:
Portföyün yapısı makul; ancak aynı growth temasında yoğunlaşma var.

Ana risk:
Örnek A ve Örnek B aynı talep varsayımına bağımlı.

Asset önerileri:
- Örnek A: HOLD
- Örnek B: HOLD

Portfolio önerisi:
Aynı temaya ek sermaye yönlendirme.
Yeni sermaye için farklı exposure ihtiyacını değerlendir.

Acil review gereken pozisyon:
Yok.
```

## Integration-Ready Principle

Portfolio verisinin kaynağı protocol içinde hard-code edilmemelidir. Portfolio context ve position context kaynaktan bağımsız olarak düşünülür. `get_portfolio_context()` ve `get_position_context(instrument)` yalnız konsept abstraction adlarıdır; uygulanmış fonksiyon veya kesin API sözleşmesi değildir.

Context bugün local state'ten sağlanabilir; gelecekte NetWorth sağlayabilir. Bu tasarım kaydı provider seçmez, code / schema oluşturmaz ve NetWorth entegrasyonu yapmaz.

## Architecture Relationship

Full Portfolio Review, [Portfolio Monitoring](portfolio-monitoring.md)'den daha seyrek ve kapsamlı portfolio-level strategic review protocolüdür. Compact asset state kullanır; [Single Asset Monitoring](single-asset-monitoring.md), [Thesis Review](thesis-review.md), [Valuation Update](valuation-update.md) ve [Technical Review](technical-review.md) için conditional follow-up üretir. Asset-level specialist review'ların yerine geçmez; automatic rebalancing veya execution yapmaz.

Portfolio health representation, concentration thresholds, risk aggregation, correlation / overlap, context freshness, cash / liquidity framework, rebalance threshold ve Opportunity Discovery ilişkisi [Open Design Questions](../architecture/open-design-questions.md) içinde açık bırakılmıştır.
