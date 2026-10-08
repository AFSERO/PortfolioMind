# Deep Research

Status: DESIGN IN PROGRESS

Bu belge MVP için design / refinement kaydıdır. Production code, database / schema implementation, provider seçimi veya aktif research run içermez. Historical research çıktıları kendi dönem ve kapsamlarıyla korunur.

## Purpose

Deep Research, evidence üzerinden investment case oluşturan high-cost specialist protocol'dür.

Ana soru:

> Bu yatırım enstrümanını gerçekten anlayacak ve ileride thesis / valuation / monitoring süreçlerini besleyecek kadar güçlü bir investment case oluşturduk mu?

Amaç tek seferlik uzun rapor değil, sonraki review'ların tekrar kullanabileceği kanıt ve compact state üretmektir:

```text
Evidence
    ↓
Business Understanding
    ↓
Investment Thesis
    ↓
Key Risks
    ↓
Valuation Inputs
    ↓
Monitoring Variables
    ↓
Structured Persistent State
```

Structured Persistent State burada tasarım hedefidir; kesin schema veya storage implementation kararı değildir.

## Lifecycle and Entry Conditions

Mevcut research lifecycle korunur:

```text
Discovery → Preliminary Screening → Deep Research → Valuation
→ Portfolio Fit → Position Sizing → Technical Review → Entry
```

Yeni adaylarda Deep Research yalnız screening bar'ını geçen güçlü adaylara ayrılır. [Opportunity Discovery](opportunity-discovery.md) veya [Replacement Candidate](replacement-candidate.md) yönlendirmesi giriş bağlamını sağlar; bu protocol Discovery / Preliminary Screening'in yerine geçmez. Screening sonucu, gerekçesi ve açık sorular önce kullanılır. DEEP RESEARCH etiketi araştırmanın tamamlandığı anlamına gelmez.

Mevcut araştırmaya dönüşte ise önce unresolved questions, previous evidence, previous conclusions ve değişen koşul okunur. Earnings / Thesis / Single Asset review'dan gelen deeper research ihtiyacı önce hedefli bir devam olarak değerlendirilir; her seferinde discovery veya full research tekrarlanmaz.

Eski geniş research methodology'sindeki valuation, portfolio fit, sizing ve entry alanları lifecycle'ın bütününe aittir; bu dar specialist protocol hepsini aynı run'da tamamlamak zorunda değildir. Kullanıcının belirlediği pass / kapsam sınırı korunur. Sonraki aşamaya uygunluk, o aşamanın çalıştırıldığı veya yatırım kararı verildiği anlamına gelmez.

## Materiality-Based Research Scope

Asset'e göre conceptually şu alanlar incelenebilir:

- Business model, industry ve market structure
- Competitive position ve moat
- Unit economics ve growth drivers
- Financial quality ve cash generation
- Capital allocation, management ve governance
- Dilution
- Major risks ve regulatory exposure
- Catalysts ve key KPIs
- Thesis dependencies ve invalidation conditions

Her şirkette aynı checklist mekanik olarak doldurulmaz. Önce investment case'i değiştirecek sorular ve bunları cevaplayabilecek evidence belirlenir. İlgili historical trend ve karşılaştırmalar kullanılır; erişilemeyen veya karşılaştırılamayan seriler doldurulmuş gibi gösterilmez. Destekleyici olgular kadar karşı tez ve çelişkiler de ele alınır.

## Multi-Pass Research

Mevcut multi-pass yaklaşımı korunur; pass sayısı ve kapsamı asset type'a göre uyarlanabilir. Her pass önceki pass'in compact bulgularını kullanır; aynı kaynak toplama ve business anlatımı tekrarlanmaz.

| Pass | Ana sorular | Sonraki aşamaya aktarım |
|---|---|---|
| Pass 1 — Business / Industry / Moat | Nasıl para kazanıyor? Industry structure ve competitive advantage nedir? Long-term economics hangi koşullara bağlı? | Business understanding, preliminary thesis, growth drivers, karşı tez ve kritik açık sorular |
| Pass 2 — Financial Quality / Economic Reality | Reported numbers ekonomik gerçekliği yansıtıyor mu? Cash flow quality, SBC, dilution, working capital, normalization, capital intensity ve hidden liabilities / commitments ne gösteriyor? | Kaynaklı finansal context, reported-to-economic hesap köprüsü, riskler ve valuation inputs |
| Pass 3 — Valuation | Bu economics hangi varsayımlarla değerlenebilir? Sonuç hangi senaryolara hassas? | Ayrı valuation çalışması veya specialist handoff; varsa tamamlanan valuation'a referans |

Pass 3, lifecycle'daki ayrı Valuation aşaması olarak da yürütülebilir. Deep Research'un sorumluluğu valuation inputs'u hazırlamaktır; valuation'ın ayrıca tamamlanması otomatik varsayılmaz. Mevcut model varsa [Valuation Update](valuation-update.md) yalnız gerekli inputs'u günceller. İlk model yoksa initial valuation / rebuild ihtiyacı açıkça kaydedilir; bu belge model implementation'ı veya zorunlu yöntem seçmez.

Reported ölçüler, company-adjusted ölçüler, araştırmacı normalizasyonları ve forward assumptions ayrı tutulmalıdır. SBC / dilution / buyback, working capital, tax, leases veya commitments gibi düzeltmelerin mantığı açıklanır; aynı ekonomik maliyet iki kez sayılmaz. Economic normalization kararı AI judgment gerektirebilir; seçilen düzeltmenin aritmetiği ve kaynak izi ayrıca kontrol edilebilir olmalıdır.

## Collection, Calculation and Reasoning Separation

MVP'nin hedef akışı:

```text
Cheap deterministic collection
    ↓
Source extraction
    ↓
Financial calculations
    ↓
Normalized research context
    ↓
AI reasoning
```

Raw filings içinde tekrarlanan veri arama, basit hesap ve aynı veriyi yeniden toplama high-effort AI'nın varsayılan işi olmamalıdır. Collection / extraction / calculation katmanı mümkün olduğunca ayrı ve tekrar kullanılabilir context üretmelidir. Bu separation bir sorumluluk ayrımıdır; burada code, parser, adapter, vendor veya hesaplama altyapısı kurulmaz.

High-effort reasoning öncelikle contradiction analysis, business-quality judgment, thesis formation, risk reasoning, economic normalization ve final synthesis için ayrılır. Extraction hataları veya tanım değişiklikleri reasoning ile örtülmez; dönem, birim, para birimi, metric tanımı ve hesap paydası kaynakla kontrol edilir. Belirsiz düzeltmeler provisional / sensitivity olarak etiketlenir; audited gerçek gibi sunulmaz.

## Evidence Discipline

Konsept source tercih sırası:

1. Company filings / regulatory disclosures
2. Official investor relations
3. Regulators / exchanges
4. High-quality financial journalism
5. Reputable industry sources
6. Secondary sources
7. Social media — yalnız signal / lead

Source quality ayrımı korunur. Primary kaynak da kapsamı ve tarihi dışında kesin kanıt sayılmaz; management iddiası gerçekleşmiş sonuçla aynı değildir. Important claim'ler mümkün olduğunca kaynak, ilgili bölüm, dönem / publication tarihi ve confidence ile ilişkilendirilir. Veri kesiti, belge yayımlanma tarihi ve erişim tarihi birbirine karıştırılmaz.

Unverified high-impact claims final thesis'e doğrulanmış olgu olarak eklenmez; açık soru / risk lead'i olarak tutulur. Çelişen kaynaklar sessizce birleştirilmez. Kaynağın gerçekten incelenmiş olması, yalnız linkinin bulunması ve erişim kısıtı ayrı belirtilir. Hesap sonucu, tahmin ve analist yorumu kaynak olgusundan ayrılır; exact evidence representation ve confidence yöntemi henüz tasarlanmaz.

## Completion, Open Questions and Stop Rules

Bir pass sonunda neyin anlaşıldığı, neyin hâlâ belirsiz olduğu ve sonraki araştırmanın neden değerli olduğu kısaca kaydedilir. Sonucu değiştirebilecek en önemli açık sorular için gerekli evidence ve kamuya açık kaynaklarla cevaplanabilirlik belirtilir.

Investment case; destekleyici evidence, karşı tez, riskler, valuation inputs ve monitoring handoff ile anlaşılır hale geldiğinde mevcut kapsam kapatılabilir. Her açık soru kapanmak zorunda değildir; kritik boşluk varsa sonuç sınırlanır ve sonraki adım belirtilir. Ek araştırma sonucu değiştirmeyecekse veya gerekli kanıt kamuya açık değilse aynı arama uzatılmaz; yeniden açma koşulu kaydedilir. Exact cost / effort control ve pass completion standardı açık kalır.

Çalışmanın tamamlanması, güçlü investment case veya yatırım uygunluğu ile aynı şey değildir. Yetersiz kanıtla biten run da açık sınırlama ve follow-up ile kaydedilebilir.

## Research Outputs

Machine Record ve Human Brief ayrımı korunur; Detailed Research Report bunların kanıt ve ayrıntı katmanıdır.

### Detailed Research Report

İnsan tarafından gerektiğinde açılabilecek uzun-form evidence / report, ilgili research folder içinde tutulabilir. Business understanding, karşı tez, financial quality, hesap izi, riskler, açık sorular ve source references içermelidir. Source register veya valuation eki ayrı olabilir; dosya sayısı / formatı bütün asset'lere zorunlu kılınmaz. Compact state ayrıntılı kanıta referans verir; sonraki run bütün raporu tekrar okumak zorunda kalmaz.

### Machine Record

Kesin schema: DESIGN PENDING. Konsept olarak şu bilgileri taşıyabilir:

- Protocol adı, instrument ve asset type
- Research date, research version ve tamamlanan pass / kapsam
- Business summary ve moat assessment
- Growth drivers
- Financial quality
- Key risks ve catalysts
- Investment thesis ve destek / karşı evidence referansları
- Thesis dependencies ve what must go right
- Invalidation conditions
- Key KPIs to monitor ve thesis triggers
- Known future events
- Open questions, gerekli evidence ve yeniden açma koşulları
- Confidence ve material evidence sınırlamaları
- Valuation inputs ve varsa ayrı valuation sonucu / model referansı
- Last major update, stale indicators ve material events since research
- Research-stage sonucu ve required next step
- Detailed report / source references

Alan tipleri, zorunlulukları, exact enum, JSON / database schema veya storage seçimi bu belgede belirlenmez.

### Human Brief

Kullanıcının mümkün olduğunca 30–60 saniyede okuyabileceği sade Türkçe, decision-focused özet olmalıdır. Business quality, moat, growth driver, ana risk, thesis, kritik açık soru ve next step öne çıkarılır. Aşağıdaki yalnız kurgusal tasarım örneğidir; gerçek ticker analizi değildir:

```text
ÖRNEK ENSTRÜMAN — DEEP RESEARCH

Business quality: Güçlü, ancak sermaye ihtiyacına duyarlı.
Moat: Dağıtım avantajı var; korunması müşteri devamlılığına bağlı.
Main growth driver: Mevcut müşterilerde kullanım artışı.
Main risk: Büyümenin nakde dönüşmemesi.
Thesis: Avantaj sürdükçe ölçeklenebilir; valuation disiplini gerekli.
Open question: Normalleşmiş ekonomik nakdin dayanıklılığı.
Sonuç: CONTINUE TO VALUATION
Next step: Açık belirsizliği senaryolarla taşıyarak valuation yap.
```

## Monitoring Handoff — Core Architecture Principle

Deep Research, gelecekteki monitoring için açık bir başlangıç noktası üretmelidir. Yalnız uzun rapora referans vermek yeterli değildir. Compact handoff şu bilgileri anlaşılır biçimde taşımalıdır:

- What must go right ve ilgili thesis dependencies
- Key KPIs; anlamı, mevcut kanıt dönemi ve uygun karşılaştırma bağlamı
- Thesis triggers ve neden review gerektirecekleri
- Thesis invalidation conditions
- Major risks
- Expected catalysts
- Known future events; gerçekleşmiş olay ile beklenen olay ayrımı

| Kullanan protocol | Handoff'ın kullanımı |
|---|---|
| Portfolio Monitoring | Cheap Pre-Check'te izlenecek material olay, risk ve thesis trigger'larını bilmek |
| Earnings Review | Yeni sonuçları önceden kaydedilmiş beklenti ve KPI'larla karşılaştırmak |
| Thesis Review | Varsayımların güçlenmesini, zayıflamasını veya geçersizleşmesini değerlendirmek |
| Single Asset Monitoring | Compact asset context üzerinden değişiklikleri birleştirmek ve ilgili review'a yönlendirmek |

Trigger gerçekleşmesi otomatik thesis invalidation veya trade değildir. Asset'e özgü ölçüm koşulları kanıtla destekleniyorsa kaydedilebilir; geçmiş run'lardaki sayısal eşikler genel kurala çevrilmez. Ölçülemeyen KPI / dependency açık soru olarak kalır. Research handoff, scheduler veya notification kurulması anlamına gelmez.

## Freshness and Reuse

Research sonsuza kadar current kabul edilmez. Research date, last major update, stale indicators ve research sonrasındaki material events izlenebilir. Mevcut methodology'deki FRESH / REVIEW_REQUIRED / STALE / INVALID freshness kavramları, thesis status ve investment recommendation'dan ayrı değerlendirilir; exact thresholds ve temsil açık kalır.

Yeni earnings, fiyat hareketi veya bir varsayım değişikliği önce ilgili specialist review'la ele alınabilir. Yalnız valuation'ın eskimesi bütün business research'ün geçersizleştiği anlamına gelmez. Full research her monitoring run'da tekrarlanmaz.

Tam rebuild; company materially changed, old evidence stale, major contradiction veya explicit user request gibi durumlarda düşünülebilir. Hangi bölümlerin yeniden kurulacağı ve neden hedefli update'in yetmediği belirtilir. Geçerli eski evidence yeniden kullanılır; tarihsel conclusions sessizce rewrite edilmez. Exact full-rebuild threshold henüz tasarlanmamıştır.

## Asset-Type Flexibility

Protocol yalnız US equities için değildir; equities, funds, crypto ve gelecekte başka investable instruments için uyarlanabilir. Her asset'e aynı template zorlanmaz. Funds için mandate, holdings / look-through, manager, fees, benchmark, liquidity ve capacity; crypto için ekonomik kullanım, değer aktarımı, arz / dilution, governance ve teknik riskler material olabilir. Bunlar kesin asset-specific template veya zorunlu taxonomy değildir. Uygun olmayan company metric veya DCF zorla kullanılmaz.

## Research Outcome and Recommendation Relationship

Research-stage sonuçları konsept olarak **CONTINUE TO VALUATION, WATCH, REJECT / PASS, MORE EVIDENCE REQUIRED** olabilir. Bunlar yatırım recommendation'ı veya kesin enum değildir. Önceki workflow'daki research / watchlist sonuçları tarihsel aşamalarıyla korunur; otomatik yeniden sınıflandırılmaz.

Deep Research doğrudan automatic BUY üretmez. Nihai yatırım değerlendirmesi Research + Valuation + Portfolio Fit + Position Sizing + ilgili Technical Review sonrasında oluşmalıdır. Mevcut ADD / HOLD / REDUCE / SELL / REVIEW REQUIRED recommendation seti değişmez; araştırma ilerlemesi, thesis status, ownership ve yatırım kararı ayrı tutulur. Final investment / action authority kullanıcıdadır.

## Lessons from Existing Local Runs

Bu refinement için mevcut workflow ve historical run'lar yalnız yöntem / çıktı yapısı açısından incelendi; yatırım sonuçları yeniden doğrulanmadı veya değiştirilmedi:

- Araştırma metodolojisi ve işletim kuralları: screening, primary evidence, asset-type ayrımı ve research / decision lifecycle başlangıç noktasıdır; bu görevdeki MVP kapsamı eski geniş şablonun bütün aşamalarını aynı run'a taşımaz.
- [UBER Pass 1](../../research/UBER/2026-09-13-pass-1/README.md): pass kapsamı, business değerlendirmesi, confidence ve yatırım sonucu ayrı; sonraki pass için açık sorular kayıtlıdır.
- [UBER Pass 2](../../research/UBER/2026-09-14-pass-2/research-report.md) ve [source register](../../research/UBER/2026-09-14-pass-2/source-register.md): önceki business çalışmasını tekrarlamadan financial quality; reported / normalized economic metrics ve hesap izi ayrımı.
- [UBER Pass 3](../../research/UBER/2026-09-14-pass-3/research-report.md) ve [valuation model](../../research/UBER/2026-09-14-pass-3/valuation-model.md): önceki pass'lerden valuation'a aktarım, dönem / payda / model sınırları, thesis dependencies ve monitoring koşulları.
- [THF workflow retrospective](../../research/THF/2026-09-12/workflow-retrospective.md): kısa memo + evidence ekleri, fund-specific tanım / tarih sınırları, public answerability ve yeniden açma koşulları. Tek run bütün sistemin doğrulandığı anlamına gelmez.

Bu örneklerdeki şirket / fon sonuçları, hesap konvansiyonları ve eşikler başka asset'lere genel politika olarak aktarılmaz. Historical çıktılarda Machine Record bulunması varsayılmaz; compact state bu MVP'nin ileriye dönük hedefidir, bu görev eski kayıtları migrate etmez.

## Integration-Ready Relationship

Deep Research, NetWorth'e, market-data vendor'a veya research-source vendor'a bağımlı olmamalıdır. External data access gelecekte provider / adapters üzerinden sağlanabilir; bu belge adapter sözleşmesi veya implementation seçmez ve NetWorth entegrasyonu yapmaz.

Pass structure, evidence representation, confidence, asset-specific templates, freshness, open-question tracking, normalized financial calculation layer, full rebuild threshold, cost / effort control ve Machine Record schema [Open Design Questions](../architecture/open-design-questions.md) içinde açık kalır.
