# System Overview

Status: DESIGN / NOT IMPLEMENTED

CORE PROTOCOL DESIGN: MVP-READY

Design freeze: 15.09.2026. Core lifecycle'ın rolleri, araştırma / karar / hesaplama ayrımı ve handoff'ları MVP implementation'a başlamak için yeterince tanımlıdır. Bu durum bütün design questions'ın çözüldüğü, sayısal yatırım politikalarının onaylandığı veya sistemin implement edildiği anlamına gelmez. Bu görev implementation başlatmaz.

Amaç, kullanıcının kısa komutlarla çalıştırabileceği kişisel AI investment system vizyonunu kayıt altına almaktır. Örnek gelecekteki komutlar: `Portfolio Monitoring Protocol'u çalıştır`, `UBER Single Asset Monitoring yap`, `Opportunity Discovery Protocol'u çalıştır`, `Replacement Candidate araştır`, `Earnings Review yap`, `Full Portfolio Review yap`, `Deep Research yap` ve `Valuation Update yap`. Bunlar şu anda çalıştırılabilir komutlar değildir.

Yön gösterici gelecek akışı:

```text
External Data / APIs / MCP / Web / Primary Sources
                    ↓
              Data Collection
                    ↓
       Persistent State / Database
                    ↓
              Context Builder
                    ↓
           Compact JSON Context
                    ↓
             AI / Codex Agent
                    ↓
             Protocol Execution
                    ↓
         Research / Recommendation
                    ↓
             Persistent State
```

1. Portfolio Monitoring, gelecekte diğer protokolleri gerektiğinde çağırabilen bir orchestrator olabilir.
2. Sistem scheduled, event-driven ve manual trigger'larla çalışabilir.
3. Aynı pahalı araştırmanın tekrar tekrar yapılmaması için persistent state kullanılmalıdır.
4. AI mümkün olduğunca yalnızca değişen veya decision-relevant bilgiyi analiz etmelidir.
5. Expensive reasoning özellikle research synthesis, valuation ve decision support için saklanmalıdır.
6. Data collection ve deterministic calculations mümkün olduğunca AI reasoning'den ayrılmalıdır.
7. Final investment/action authority kullanıcıda kalmalıdır.

Core workflow ve aşağıdaki rol ayrımları MVP tasarım kararıdır. Altyapı, veri modelleri, kesin policy parametreleri ve detaylı otomasyon / routing kuralları henüz implementation kararı değildir; açık konular ayrıca tutulur.

## Core Lifecycle and Layer Roles

```text
DISCOVERY → PRELIMINARY SCREENING → DEEP RESEARCH → VALUATION
→ PORTFOLIO FIT → POSITION SIZING → TECHNICAL REVIEW
→ ENTRY / EXECUTION → MONITORING → EXIT / REBALANCE
```

| Katman | Sorumluluk |
|---|---|
| Opportunity Discovery | Portfolio-aware aday bulma; aday üretmeme sonucu geçerli |
| [Preliminary Screening](../protocols/preliminary-screening.md) | Cheap research gate: pahalı Deep Research'e değer mi? DEEP RESEARCH / WATCH / REJECT |
| Deep Research | High-cost evidence / reasoning ve monitoring'e aktarılabilir investment case |
| Valuation | Specialist valuation; initial model / gerektiğinde rebuild, mevcut modelde Valuation Update |
| [Portfolio Fit](../protocols/portfolio-fit.md) | Lightweight portfolio-context gate; iyi asset bu portföye uygun mu? |
| [Position Sizing](../policies/position-sizing.md) | Policy-driven / calculation-heavy component; explicit rules ile aralık ve constraints |
| Technical Review | Execution timing / technical context; entry zones ve teknik plan |
| Entry / Execution | Kullanıcının final işlem yetkisi altında uygulama; recommendation otomatik emir değildir |
| Monitoring | Compact state ile değişiklik takibi ve conditional specialist review |
| Exit / Rebalance | Material bulgular ve portfolio context ile kullanıcı değerlendirmesi; otomatik işlem zinciri değildir |

Lifecycle bütün adayların bütün aşamaları zorunlu geçeceği bir otomasyon değildir. WATCH / REJECT, eksik evidence, poor fit veya eksik sizing policy ilerlemeyi durdurabilir. Mevcut güncel sonuçlar yeniden kullanılabilir. SELL sonrası automatic Replacement Candidate veya redeployment oluşturulmaz.

Preliminary Screening full company research yapmaz; basic quality, growth, rough valuation, obvious risks, why now, portfolio relevance ve evidence availability ile ucuz filtering sağlar. Machine Record ve kısa Human Brief üretmesi öngörülür. Discovery'nin preliminary değerlendirmesi ayrı screening gate'inin tamamlandığı anlamına gelmez.

Portfolio Fit business quality'yi yeniden araştırmaz; exposure, overlap, concentration, geography, asset class, role, liquidity, available capital ve risk budget inceler. GOOD FIT / ACCEPTABLE / POOR FIT / REVIEW REQUIRED konsept sonuçlardır; scoring ve exact schema açık kalır. Full Portfolio Review bütün portföyü, bu gate ise belirli asset'in uygunluğunu değerlendirir.

Position Sizing sırf lifecycle'da bulunduğu için AI research protocolüne dönüştürülmez. Target position range, initial size, maximum size, staged-entry suggestion, rationale ve constraints hit üretmesi öngörülür. AI judgment destekleyicidir; açık kuralların veya limitlerin yerine keyfi yüzdeler koymaz. Policy eksikse sayısal çıktı zorlanmaz. Staged-entry sermaye miktarı sizing'e, teknik zone / timing Technical Review'a aittir.

BUY CANDIDATE, ADD, Portfolio Fit sonucu veya sizing planı trade command değildir. Position Sizing de execution yapmaz; final investment / action authority kullanıcıda kalır.

Core workflow açısından ciddi conceptual blocker saptanmamıştır. Screening thresholds, fit scoring, risk / sizing policy ve veri / schema / provider ayrıntıları açık tasarım işleridir; ilgili işlevin gerçek kullanımından önce ele alınırlar. MVP-READY bu açık konuları çözülmüş veya production-ready ilan etmez.

## Protocol Output Ayrımı

Bütün protocol run'ları mümkün olduğunca iki ayrı output üretmelidir: Machine Record ve Human Brief.

> Protocol outputs should separate machine-readable persistent state from user-facing decision summaries.

> AI should first read compact machine state from previous runs and only open detailed research reports when additional evidence or context is required.

**Machine Record:** AI/Codex'in sonraki run'larda önceki sonucu hızlı ve düşük context kullanımıyla anlayabilmesi için structured, compact, mümkün olduğunca JSON-compatible ve minimum narrative prose içeren kayıt. Timestamp, protocol adı ve asset/portfolio identity içermelidir. Protocol-relevant olduğunda thesis status, recommendation, valuation status, material changes, confidence, next action, open questions ve source/research references taşıyabilir. Uzun research raporunun yerine geçmesi gerekmez; ayrıntı için ilgili research report / source register'a referans verebilir. Kesin JSON schema henüz tasarlanmayacaktır.

**Human Brief:** kullanıcının sonucu 30–60 saniyede anlayabileceği kısa, sade Türkçe, minimum jargon içeren, karar odaklı özet. Gerektiğinde 3–8 maddelik olabilir. Normal kullanımda uzun teknik research raporlarını okumayı gerektirmemesi hedeflenir.

Amaçlar: context kullanımını azaltmak, tekrar research yapılmasını önlemek, Codex limit kullanımını azaltmak, historical state'i daha kolay karşılaştırmak ve kullanıcıya daha sade çıktı sunmak. Bu bir tasarım kararıdır; output alanları, schema, saklama yöntemi ve implementation henüz tasarlanmamıştır.

## News Monitoring

[News Monitoring](../protocols/news-monitoring.md) düşük maliyetli bir event-detection layer olabilir ve Portfolio Monitoring'den ayrı çalışmalıdır. Material events daha pahalı analysis protocols için review trigger oluşturabilir. Social claims doğrulanmadan investment decision'a dönüşmemelidir; materiality ile source confidence ayrı değerlendirilmelidir. Bu konsept henüz implement edilmemiştir ve aktif schedule içermez.

## Portfolio Monitoring — Cheap Pre-Check

[Portfolio Monitoring](../protocols/portfolio-monitoring.md) için tercih edilen normal cadence Weekly'dir; manual user request veya başka bir protocol'ün önemli olay tetiklemesiyle event-driven review da yapılabilir. Henüz hiçbir schedule aktif değildir.

Weekly review bütün pozisyonları baştan deep research etmemelidir. Önce portfolio ve son monitoring state okunarak düşük maliyetli Cheap Pre-Check ile decision-relevant değişiklikler aranmalıdır. Material değişiklik olmayan pozisyonlar atlanır; değişiklik tespit edilenler için ilgili analysis protocol önerilir. Kesin routing kuralları henüz tasarlanmamıştır.

> Expensive analysis should only be triggered for assets where the cheap monitoring layer detects a potentially decision-relevant change.

Amaç repeated research ve Codex/model usage azaltmak, monitoring'i ölçeklenebilir kılmak ve user-facing noise azaltmaktır. Unusual price movement tek başına yatırım aksiyonu sinyali değildir; nedeninin thesis / valuation açısından önemi araştırılabilir. Sebep bulunamazsa veya material değilse daha ileri research zorunlu değildir.

## Full Portfolio Review

[Full Portfolio Review](../protocols/full-portfolio-review.md), portföyün tamamında sermaye dağılımı ve risk yapısının hâlâ mantıklı olup olmadığını değerlendiren portfolio-level strategic review protocolüdür. Portfolio Monitoring'in “son kontrolden beri material ne değişti?” sorusundan farklı olarak allocation, concentration, portfolio risk ve capital efficiency'yi birlikte inceler. Daha seyrek ve kapsamlıdır; monthly / periodic review olası bir trigger'dır, kesin schedule belirlenmemiştir.

Compact asset state ve portfolio context kullanır; yalnız problemli / belirsiz pozisyonlarda detaylı research'e iner. Allocation target'ları rigid rule değildir ve draft allocation'lar bağlayıcı değildir. Amaç material portfolio-level issues ve meaningful capital allocation opportunities bulmaktır; küçük değişiklikler için sürekli rebalancing önerilmez. Turnover maliyeti, uncertainty ve mevcut thesis dikkate alınır.

Asset-level specialist protocol'lara conditional follow-up üretir; Replacement Candidate ve Opportunity Discovery için gerektiğinde araştırma önerisi sunabilir. Replacement Candidate, kullanıcının redeployment kararı ve ayrı manual request'i sonrasında ele alınır; SELL recommendation otomatik replacement discovery başlatmaz. Automatic rebalancing veya execution yapılmaz; final authority kullanıcıdadır. Asset recommendation seti korunur, portfolio-level observations ayrı tutulur ve exact portfolio health status seti açık bırakılır. Machine Record ve kısa Human Brief öngörülür. Portfolio context kaynağa bağımlı değildir; NetWorth entegrasyonu bu aşamada yapılmaz.

## Opportunity Discovery

[Opportunity Discovery](../protocols/opportunity-discovery.md), portfolio-aware çalışan research / finding protocolüdür. Existing candidate universe first yaklaşımıyla watchlist, mevcut adaylar, WATCH / deferred isimler ve önceki research sonuçlarından başlar; sınırlı ve staged screening ile araştırmaya değer fırsatları ayırır. Quality over quantity esastır; her run'da zorla aday üretmez ve NO COMPELLING OPPORTUNITY geçerli sonuçtur.

Strong candidates Preliminary Screening / Deep Research sürecine yönlendirilebilir. DEEP RESEARCH / WATCH / REJECT-PASS research-stage sonuçları investment recommendation veya tamamlanmış araştırma değildir. Discovery full Deep Research, investment recommendation veya trade execution üretmez. Full Portfolio Review'dan portfolio gap context'i alabilir; otomatik discovery tetikleme koşulları açık kalır. Belirli bir pozisyondan çıkan sermayeye odaklanan, manual istenen Replacement Candidate ayrı protocol'dür.

Compact Machine Record ve kısa Human Brief öngörülür. Draft allocation hedefleri bağlayıcı değildir; diversification için kalite barı düşürülmez. Data sources / vendors hard-code edilmez; kesin schedule, scoring, taxonomy genişletmesi veya schema bu aşamada tasarlanmaz.

## Replacement Candidate

[Replacement Candidate](../protocols/replacement-candidate.md), belirli bir pozisyondan çıkan veya çıkması düşünülen sermayenin sonraki kullanımını araştıran research / finding protocolüdür. Kullanıcı onaylı capital redeployment değerlendirmesi için manual request veya kullanıcının bu araştırmayı açıkça onayladığı workflow trigger ile çalışır; SELL / REDUCE veya Full Portfolio Review önerisi tek başına otomatik run başlatmaz. Araştırma onayı satış / alım veya redeployment execution onayı değildir.

Önce çıkarılan / azaltılan pozisyonun portfolio role'ünü ve mevcut constraints'i anlar. Portfolio-role-aware ve constraint-aware çalışır; existing portfolio positions, watchlist, candidates, WATCH isimleri ve Opportunity Discovery universe'den başlar. Yeni discovery yalnız gerekiyorsa ele alınır. Mevcut pozisyona ekleme adayı, yeni asset / asset class araştırması, cash / defensive veya bekleme seçenekleri karşılaştırılabilir. NO COMPELLING REPLACEMENT geçerli sonuçtur; gereksiz turnover veya zorunlu yeni aday üretmez.

Opportunity Discovery'nin genel fırsat aramasından farklıdır; güçlü adayları Preliminary Screening / Deep Research'e yönlendirebilir, kendisi full Deep Research yapmaz. Compact Machine Record ve kısa Human Brief öngörülür. Konsept replacement verdict'leri investment recommendation veya exact enum değildir. Automatic execution ve automatic redeployment yapılmaz; context kaynağı hard-code edilmez ve NetWorth entegrasyonu bu aşamada yapılmaz. Karşılaştırma standardı, eşikler ve veri temsilleri açık tasarım konularıdır.

## Deep Research

[Deep Research](../protocols/deep-research.md), yeni adaylarda Preliminary Screening sonrası güçlü investment case oluşturmaya ayrılan high-cost specialist protocol'dür. Discovery → Preliminary Screening → Deep Research → Valuation → Portfolio Fit → Position Sizing → Technical Review → Entry lifecycle'ı korunur. Multi-pass business / industry / moat ve financial quality / economic reality çalışmaları valuation inputs üretir; Valuation pass'i ayrı specialist aşama olarak yürütülebilir. Asset type'a göre kapsam uyarlanır.

Amaç yalnız uzun rapor değildir: evidence ve Detailed Research Report yanında compact Machine Record ile kısa Human Brief üretilmesi öngörülür. **Monitoring handoff temel mimari ilkedir:** what must go right, thesis dependencies, key KPIs, thesis triggers, invalidation conditions, major risks, catalysts ve known future events açıkça kaydedilir. Portfolio Monitoring, Earnings Review, Thesis Review ve Single Asset Monitoring bu başlangıç noktasını kullanır; full research her monitoring run'da tekrarlanmaz.

Deterministic collection, source extraction ve financial calculations mümkün olduğunca AI reasoning'den ayrılır. High-effort reasoning contradiction analysis, business judgment, economic normalization ve synthesis için ayrılır. Mevcut research state ve evidence önce yeniden kullanılır; freshness ve material değişiklikler hedefli review veya gerekçeli rebuild ihtiyacını belirler. Research-stage sonuçları automatic BUY veya execution değildir. Exact schema, pass / effort standardı, calculation layer ve freshness / rebuild eşikleri açık kalır; provider implementation ve NetWorth entegrasyonu bu aşamada yapılmaz.

## Single Asset Monitoring

[Single Asset Monitoring](../protocols/single-asset-monitoring.md) asset-level synthesis/router protocolüdür. Portfolio Monitoring'in material change bulduğu varlıklarda kullanılabilir. Önce compact machine state'i kullanır ve son incelemeden beri değişen bilgilere odaklanır; gerektiğinde specialist sub-protocol'lara yönlendirip sonuçları asset-level recommendation altında birleştirir. Detaylı eski research yalnızca ek kanıt veya bağlam gerektiğinde açılır. Varsayılan olarak full deep research çalıştırmaz; Deep Research yalnızca evidence ciddi biçimde yetersizse veya şirket materially değişmişse kullanılmalıdır.

## Earnings Review

[Earnings Review](../protocols/earnings-review.md) yeni finansal sonuçların mevcut thesis, valuation ve recommendation üzerindeki material etkisini inceleyen asset-level specialist protocol'dür. Portfolio Monitoring tarafından tetiklenebilir veya Single Asset Monitoring tarafından çağrılabilir. Önce compact asset state, previous earnings / review state, ilgili thesis beklentileri ve current earnings data kullanılır; amaç earnings raporunu özetlemek değil son review'dan beri karar açısından ne değiştiğini belirlemektir.

Gerektiğinde Thesis Review, Valuation Update veya Technical Review'a yönlendirir; her earnings sonrası bütün alt protocol'ları otomatik çalıştırmaz ve kendisi full Deep Research değildir. Evidence ciddi biçimde yetersizse veya şirket structurally değişmişse deeper research değerlendirilebilir. Machine Record ve 30–60 saniyelik Human Brief üretmesi öngörülür; kesin schema henüz tasarlanmamıştır.

Earnings verdict konsepti POSITIVE / NEUTRAL / NEGATIVE / MIXED olarak recommendation'dan ayrı tutulur. Positive earnings ve stronger thesis, expensive valuation nedeniyle HOLD ile birlikte bulunabilir. Earnings surprise tek başına yatırım aksiyonu üretmez; mevcut recommendation seti ve final user authority korunur.

## Thesis Review

[Thesis Review](../protocols/thesis-review.md), bir varlığı alma veya elde tutma nedeninin hâlâ geçerli olup olmadığını inceleyen asset-level specialist protocol'dür. Mevcut compact thesis state ile yeni material evidence'ı karşılaştırır; yalnız değişen kritik varsayımlara odaklanır. Single Asset Monitoring tarafından çağrılabilir, Earnings Review tarafından tetiklenebilir veya Portfolio Monitoring / News Monitoring escalation sonucu çalışabilir. Şirketi sıfırdan araştırmaz ve Deep Research'in yerine geçmez.

Thesis status seti STRONGER / UNCHANGED / WEAKER / INVALIDATED olarak korunur ve fiyat hareketinden ayrı değerlendirilir. INVALIDATED, temel yatırım gerekçesinin bozulduğunu destekleyen güçlü evidence gerektirir; tek bir kötü quarter veya fiyat düşüşü kendi başına yeterli değildir. Thesis status ile recommendation ayrı boyutlardır. INVALIDATED, SELL consideration yaratabilir ancak otomatik execution command değildir; final authority kullanıcıdadır.

Gerektiğinde Valuation Update, Technical Review, deeper research consideration veya portfolio-level review context oluşturur; bütün alt protocol'ları otomatik çalıştırmaz. Compact Machine Record ve 30–60 saniyelik Human Brief öngörülür. Kesin schema, invalidation threshold ve evidence değerlendirme yöntemleri açık tasarım konularıdır.

## Valuation Update

[Valuation Update](../protocols/valuation-update.md), yeni finansal veriler, thesis varsayımları veya önemli fiyat hareketleri sonrası mevcut valuation'ın geçerliliğini inceleyen asset-level specialist protocol'dür. Önce previous valuation state / model assumptions kullanılır; yalnız gerekli inputs güncellenir. Business value değişimi ile market price değişimi ayrı değerlendirilir: intrinsic value değişmeden de fiyat hareketi valuation status'u değiştirebilir.

Valuation status seti ATTRACTIVE / FAIR / EXPENSIVE olarak korunur ve recommendation'dan ayrı tutulur. Güvenilir valuation üretilemiyorsa recommendation tarafında REVIEW REQUIRED kullanılabilir. Methodology açıkça kaydedilir; tek yöntem veya sabit margin-of-safety eşiği bütün şirketlere zorunlu kılınmaz. Range ve scenario kullanımı tercih edilebilir; gereksiz precision üretilmemelidir.

Earnings Review ve Thesis Review tarafından tetiklenebilir, Single Asset Monitoring tarafından çağrılabilir veya Portfolio Monitoring escalation sonucu çalışabilir. Gerektiğinde Thesis Review context, Technical Review, portfolio / future sizing context veya deeper research consideration oluşturur; bütün protocol'ları otomatik çalıştırmaz ve Deep Research'in yerine geçmez. Eski model çok stale veya geçersizse full rebuild ihtiyacı değerlendirilebilir. Compact Machine Record ve 30–60 saniyelik Human Brief öngörülür; kesin schema, yöntem seçimi, freshness, eşikler ve rebuild koşulları açık tasarım konularıdır.

## Technical Review

[Technical Review](../protocols/technical-review.md) ayrı bir decision-support layer'dır; fundamental thesis'in yerine geçmez. Pre-investment execution planning ve ongoing monitoring'de kullanılabilir. Historical technical plan saklanmalı ve monitoring sırasında güncel fiyat davranışı onunla karşılaştırılmalıdır. Material technical deviation daha kapsamlı review için trigger olabilir. Technical status ile portfolio recommendation ayrı tutulur; teknik seviyeler otomatik trade command değildir.

## Recommendation States

Portfolio Monitoring, Single Asset Review, Earnings Review, Thesis Review veya Valuation Review sonucunda kullanılabilecek ana recommendation seti şimdilik **ADD, HOLD, REDUCE, SELL, REVIEW REQUIRED** olarak kabul edilmiştir. Set mümkün olduğunca sade tutulacaktır.

| Recommendation | Anlamı |
|---|---|
| ADD | Mevcut pozisyonun artırılması değerlendirilebilir. Otomatik alım emri değildir; final action için gerektiğinde valuation, portfolio fit, position sizing, technical review ve available capital ayrıca değerlendirilmelidir. |
| HOLD | Mevcut pozisyonun korunması uygundur. Human Brief içinde “HOLD — do not add”, “HOLD — valuation expensive” veya “HOLD — thesis unchanged” gibi açıklamalar kullanılabilir; bunlar ayrı recommendation state değildir. |
| REDUCE | Pozisyondan tamamen çıkılmadan ağırlığın azaltılması değerlendirilebilir. Aşırı valuation, artan portfolio concentration, zayıflayan thesis veya kötüleşen risk/reward gibi kesin neden protocol output içinde açıklanmalıdır. |
| SELL | Mevcut pozisyonun tamamen kapatılması değerlendirilebilir. Thesis invalidated, unacceptable risk, structural deterioration, materially superior alternative veya portfolio-level reason gibi nedenlere dayanabilir. Otomatik execution anlamına gelmez. |
| REVIEW REQUIRED | Evidence doğrudan ADD/HOLD/REDUCE/SELL sonucu vermek için yetersizdir veya önemli yeni gelişme daha kapsamlı inceleme gerektirir. HIGH + UNVERIFIED news, material technical deviation, unexpected earnings result, possible thesis break, conflicting data veya major price move sonrası stale valuation örnek nedenlerdir. İlgili alt protocol önerilebilir. |

### Separate Decision Dimensions

Recommendation, underlying analysis'ten ayrı tutulmalıdır. Mümkün olduğunca aşağıdaki boyutlar ayrı kaydedilir:

- Thesis Status (konsept): STRONGER, UNCHANGED, WEAKER, INVALIDATED.
- Valuation Status (konsept): ATTRACTIVE, FAIR, EXPENSIVE. Kesin valuation thresholds daha sonra tasarlanacaktır.
- Technical Status (mevcut Technical Review konsepti): ON TRACK, NEUTRAL, DEVIATED, REVIEW REQUIRED. Kesin state definitions daha sonra tasarlanacaktır.

Strong thesis ≠ automatic ADD; valuation pahalı olabilir. Technical breakdown ≠ automatic SELL; fundamental thesis hâlâ geçerli olabilir. Recommendation, thesis + valuation + technical + portfolio context birlikte değerlendirilerek üretilmelidir. Recommendation bir execution command değildir; final investment/trade authority kullanıcıda kalır.

Aşağıdakiler yalnızca boyut ayrımını gösteren tasarım örnekleridir; gerçek ticker analizi veya investment recommendation değildir:

```text
Asset: UBER
Thesis: UNCHANGED
Valuation: FAIR
Technical: ON TRACK
Recommendation: HOLD
Confidence: HIGH
```

```text
Asset: XYZ
Thesis: WEAKER
Valuation: EXPENSIVE
Technical: DEVIATED
Recommendation: REVIEW REQUIRED
Confidence: MEDIUM
```
