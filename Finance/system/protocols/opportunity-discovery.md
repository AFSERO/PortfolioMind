# Opportunity Discovery

Status: DESIGN IN PROGRESS

Bu belge yalnızca tasarım kaydıdır; gerçek opportunity araştırması, aday listesi, implementation veya aktif schedule içermez.

## Purpose

Opportunity Discovery, araştırmaya değer fırsatları belirleyen research / finding protocolüdür.

Ana soru:

> Şu anda gerçekten araştırmaya değer yeni yatırım fırsatları var mı?

Quality over quantity esastır. Her run'da aday üretmek zorunlu değildir; **NO COMPELLING OPPORTUNITY** geçerli bir run sonucudur. Amaç favorable risk/reward, mispricing, quality, catalyst, portfolio usefulness ve asymmetric payoff üzerinden araştırmaya değer fırsat bulmaktır. “En çok yükselmesi beklenen hisseler” listesi veya investment recommendation üretmez.

## Typical Triggers

- Scheduled weekly / monthly discovery
- Manual user request
- Major market correction
- Sector dislocation
- Policy / regulatory change
- Crypto liquidation event
- Industry earnings inflection
- Spin-off / restructuring
- Full Portfolio Review sonucunda portfolio gap tespit edilmesi
- Meaningful new capital available

Weekly / monthly yalnız olası cadence seçenekleridir; kesin schedule belirlenmemiştir ve aktif schedule yoktur. Full Portfolio Review'da gap tespiti discovery önerisi oluşturabilir; mevcut karar uyarınca otomatik discovery başlatmaz. Kesin trigger koşulları açık bırakılır.

## Discovery Context

Discovery kör şekilde market taraması yapmamalıdır. Önce mümkün olduğunca şu compact context kullanılmalıdır:

- Current portfolio exposures
- Existing watchlist
- Previous candidates
- Previous rejects ve gerekçeleri
- Current research queue
- Portfolio concentration
- Available capital context
- Current market conditions
- Desired risk profile
- User investment objectives

Kullanılan context'in tarihi, kapsamı ve önemli boşlukları belirtilmelidir. Eski draft allocation hedefleri rigid rule değildir; güncel yönelim, draft ve historical / superseded kayıtlar birbirine karıştırılmaz. Sermayenin mevcut olması zorunlu aday veya deployment kararı gerektirmez.

## Existing Universe First

Yeni asset aramadan önce konsept olarak şu sıra izlenebilir:

1. Existing watchlist
2. Existing candidates
3. Previous WATCH / deferred names
4. Previous research results

Önceki adayların compact kayıtları, bekleme / ret gerekçeleri ve mevcut research queue birlikte kontrol edilir. Daha önce araştırılmış güçlü adaylar varken sürekli yeni ticker üretmek gerekmez. Yeniden ele alınan adayda neyin değiştiği belirtilir; aynı araştırma ihtiyacı yeni adaymış gibi çoğaltılmaz. Ret gerekçesi değişmemiş isimleri tekrar tekrar incelemekten kaçınılır; kesin duplicate / rejected candidate cooldown kuralları henüz tasarlanmaz.

Mevcut evren yeterli değilse trigger, portfolio ihtiyacı ve kullanıcı hedefleriyle sınırlı yeni arama düşünülebilir. Bütün market sınırsız taranmaz; candidate universe construction ve kesin tarama kapsamı açık tasarım konularıdır. Geçmiş workflow'daki örnek aday sayıları kota değildir.

## Discovery Layers and Portfolio Awareness

Fırsat tipleri konsept olarak ayrılabilir:

- High-quality compounders
- Valuation dislocations
- Cyclical opportunities
- Asymmetric growth
- Event-driven opportunities
- Early-stage / high-risk opportunities
- Crypto opportunities
- Local / Turkey opportunities

Bu liste kesin veya genişletilecek zorunlu taxonomy değildir; kategoriler örtüşebilir. Mevcut normal ve aggressive / asymmetric discovery yaklaşımından yararlanılabilir; aggressive yaklaşımda da kanıt ve risk görünürlüğü korunur. Hangi koşullarda aggressive discovery çalışacağı, scoring veya sayısal risk eşikleri burada belirlenmez.

Discovery portfolio-aware çalışmalıdır. Mevcut growth / tech concentration yüksekse aynı exposure için daha yüksek araştırma barı kullanılabilir; farklı exposure sağlayan fırsatların portfolio usefulness'ı daha yüksek olabilir. Diversification uğruna düşük kaliteli asset önerilmez. Portfolio fit, asset quality ve opportunity thesis ayrı gerekçelerle değerlendirilir; kesin portfolio-fit weighting açık bırakılır.

## Preliminary Evidence and Staged Funnel

İlk değerlendirme sorusu “Araştırmaya değer mi?” olmalıdır. Konsept olarak şu bilgiler kullanılır:

- Opportunity thesis
- Why now
- Rough valuation context
- Catalyst
- Key risk
- Portfolio fit
- Asymmetry
- Confidence
- Required next step

Rough valuation context ön değerlendirmedir; tamamlanmış valuation veya kesin getiri tahmini gibi sunulmaz. Catalyst ve asymmetry kanıtın desteklediği ölçüde açıklanır. Fiyat düşüşü, haber veya yüksek upside anlatısı tek başına güçlü aday kanıtı değildir. Önemli evidence boşlukları confidence ve next step'e yansıtılır.

Konsept akış:

```text
Portfolio context + existing candidate universe
        ↓
Opportunity Discovery
        ↓
Preliminary Candidate
        ↓
Preliminary Screening
        ↓
Strong candidate → Deep Research için yönlendirme
Other outcomes → WATCH veya REJECT / PASS
```

Ucuz ilk eleme ile zayıf adaylar erken ayrılır. Discovery, preliminary evidence ve araştırma yönlendirmesinde durur; full Deep Research yapmaz. Preliminary Screening henüz tamamlanmadıysa next step olarak açıkça belirtilir; tamamlanmış gibi gösterilmez. Expensive AI / Deep Research yalnız güçlü adaylarda, sonraki araştırma aşamasının kapsamı içinde kullanılmalıdır.

## Discovery Outcomes

Candidate-level research-stage sonuçları konsept olarak:

| Sonuç | Anlamı |
|---|---|
| DEEP RESEARCH | Ön değerlendirme daha ayrıntılı araştırmaya zaman ayırmayı destekliyor. Tamamlanmış Deep Research veya yatırım kararı değildir. |
| WATCH | Fırsat izlenmeye değer; ilerlemek için gereken gelişme, kanıt veya valuation koşulu belirtilir. |
| REJECT / PASS | Mevcut kanıt ve context ile daha fazla araştırma önceliği taşımıyor; kısa gerekçe kaydedilir. |

Mevcut workflow'daki **RESEARCH / WATCH / REJECT** ayrımıyla uyum korunur: DEEP RESEARCH burada RESEARCH yönündeki sonraki adımı belirtir; PASS, REJECT ile aynı aşamadaki eleme ifadesidir. Yeni geniş bir state taxonomy kurulmaz. Sonraki araştırma aşamasına ait BUY CANDIDATE / WATCHLIST / REJECT sonuçlarıyla discovery verdict karıştırılmaz.

Discovery verdict; ownership, research progress veya **ADD / HOLD / REDUCE / SELL / REVIEW REQUIRED** investment recommendation setinin yerine geçmez. WATCH koşulunun sağlanması otomatik alım değildir. DEEP RESEARCH etiketi sonraki protocol'ün çalıştırıldığı anlamına gelmez.

Run düzeyinde güçlü yeni araştırma fırsatı bulunmadığında **NO COMPELLING OPPORTUNITY** kullanılabilir; mevcut WATCH isimleri korunabilir. Bu sonuç yalnız incelenen kapsam ve mevcut evidence için geçerlidir, bütün markette fırsat olmadığı iddiası değildir. Veri yetersizliği varsa ayrıca açıklanır. Aday üretmek için kalite barı düşürülmez.

## Relationship With Other Protocols

| Protocol | Ana soru ve rol |
|---|---|
| Opportunity Discovery | Genel olarak yeni ve anlamlı yatırım fırsatları var mı? Portfolio-aware aday bulma ve araştırma yönlendirmesi. |
| Replacement Candidate | Belirli bir pozisyondan çıkan sermaye için en iyi alternatif nedir? Daha constraint-aware ve portfolio-role-aware araştırma. |
| Deep Research | Screening sonrasında güçlü adayın detaylı incelenmesi; Discovery'nin içinde otomatik tamamlanmış sayılmaz. |

[Full Portfolio Review](full-portfolio-review.md), portfolio gap veya capital deployment ihtiyacını discovery için context olarak sağlayabilir. [Replacement Candidate](replacement-candidate.md) ayrı protocol olarak kalır; kullanıcının redeployment kararı ve manual request'i ilkesi korunur. Opportunity Discovery, belirli bir pozisyonu satma veya yerine aday alma kararı üretmez.

Strong candidates Preliminary Screening / [Deep Research](deep-research.md) sürecine yönlendirilebilir. Bu protocol yalnız candidate ve araştırma next step'i üretir; yatırım, sizing veya trade execution kararı vermez.

## Outputs

Dual-output principle geçerlidir.

### Machine Record

Kesin schema: DESIGN PENDING. Konsept olarak compact kayıt şu bilgileri taşıyabilir:

- Protocol adı ve discovery date / timestamp
- Discovery trigger ve incelenen kapsam
- Market context
- Portfolio context reference
- Candidate list ve mevcut aday / önceki araştırma referansları
- Candidate category
- Opportunity thesis ve why now
- Catalyst
- Major risks
- Rough valuation context
- Portfolio fit ve asymmetry
- Candidate discovery verdict ve run sonucu
- Confidence ve evidence sınırlamaları
- Required next step
- Source references

Candidate list boş olabilir. Alan tipleri, zorunlulukları, JSON / database schema veya saklama yöntemi bu belgede belirlenmez.

### Human Brief

Kısa, sade Türkçe ve araştırma kararı odaklı olmalıdır; mümkün olduğunca 30–60 saniyede okunabilmelidir. Aday varsa neden ilginç olduğu, ana risk, discovery verdict ve next step öne çıkarılır. Aday yoksa NO COMPELLING OPPORTUNITY kısa gerekçe ve kapsamla belirtilir.

Aşağıdaki yalnızca kurgusal tasarım örneğidir; gerçek fırsat listesi veya yatırım önerisi değildir:

```text
OPPORTUNITY DISCOVERY

Bu run'da 2 aday değerlendirildi.

1. Örnek A
Neden ilginç? Ön valuation daha makul; yeni katalizör var.
Ana risk: Marjlar baskı altında.
Sonuç: DEEP RESEARCH
Sonraki adım: Marj toparlanmasının dayanaklarını detaylı incele.

2. Örnek B
Neden ilginç? Güçlü iş modeli; valuation henüz pahalı.
Sonuç: WATCH
Sonraki adım: Valuation koşulları değişirse yeniden screening yap.

Yeni yatırım kararı alınmadı.
```

## Efficiency and Integration-Ready Principle

Existing universe first ve staged funnel, tekrar araştırmayı ve Codex / model kullanımını azaltmalıdır. Önce compact candidate state ve önceki verdict gerekçeleri okunur; ayrıntılı eski research yalnız gerekli evidence veya değişen koşulu anlamak için açılır. Zayıf adaylara pahalı research ayrılmaz ve run'ı doldurmak için sınırsız yeni arama yapılmaz.

Discovery data source veya screening vendor'ları protocol içine hard-code edilmez. Gelecekte farklı market data, fundamentals, news, screeners ve APIs kullanılabilecek şekilde kaynak bağımsızlığı korunur. Bu aşamada provider, implementation veya NetWorth entegrasyonu seçilmez.

Candidate universe, screening sources, cadence, scoring, portfolio-fit weighting, cooldown, market-regime awareness ve aggressive / asymmetric discovery koşulları [Open Design Questions](../architecture/open-design-questions.md) içinde açık bırakılmıştır.
